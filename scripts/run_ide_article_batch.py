"""Bounded IDE-only rerun controller; bookkeeping and assembly stay on the host."""
import argparse
import hashlib
import json
import os
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from services.ide_worker_bridge import ROOT, load, save, local
from services.worker_dispatch import enqueue, status
from services.article_publish_checks import inspect_article


def receive(record):
    worker = ROOT / 'worker-workspaces' / record['worker_folder']
    # No conversation reads or repeated messages while a worker is working.
    if not (worker / 'outbox' / record['task_id'] / 'report.json').exists():
        task = load(worker / 'inbox' / record['task_id'] / 'task.json')
        if not local(worker, task['ai_output']).exists():
            return None
    state = status(record['task_id'])
    if state['status'] != 'collected':
        if state['status'] in {'error', 'delivery_unknown'}:
            raise RuntimeError(state.get('error', state['status']))
        return None
    return load(local(worker, state['result_file']))


def dispatch(directory, role, message, payload, guides=''):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    packet = directory / 'packets' / (stamp + '.json')
    save(packet, payload)
    inputs = [packet]
    if guides:
        guide = directory / 'packets' / (stamp + '.md')
        guide.write_text(guides, encoding='utf-8')
        inputs.append(guide)
    record = enqueue(role, message, inputs, kind='article-rerun', operational=True)
    save(directory / 'dispatch' / (record['task_id'] + '.json'), record)
    sent = status(record['task_id'])
    if sent['status'] in {'error', 'delivery_unknown'}:
        raise RuntimeError(sent.get('error', sent['status']))
    return record


def assemble(blocks):
    if not blocks or any(not isinstance(b.get('markdown'), str) or not b['markdown'].strip() for b in blocks):
        raise ValueError('Empty or missing article blocks')
    return '\n\n'.join(b['markdown'].strip() for b in blocks) + '\n'


def claim_map(blocks, facts):
    known = {f['id'] for f in facts}
    claims = []
    for block in blocks:
        for claim in block.get('claims', []):
            if not claim.get('fact_ids') or set(claim['fact_ids']) - known:
                raise ValueError('Claim has missing or unknown Fact references')
            pattern = r'\s+'.join(re.escape(t) for t in claim['text'].split())
            match = re.search(pattern, block['markdown']) if pattern else None
            if not match:
                raise ValueError('Claim text not preserved in its block')
            claims.append({'id': f'CLM-{len(claims)+1:03}', 'block_id': block['id'], 'text': match.group(0), 'fact_ids': claim['fact_ids']})
    return claims


def prepare_plan(plan):
    """Select configured common elements and exclude non-specific web citations."""
    plan = dict(plan)
    excluded, references = [], []
    for ref in plan.get('references', []):
        parsed = urlparse(ref.get('url', ''))
        allowed = parsed.scheme == 'https' and parsed.hostname in {'avixa.org', 'www.avixa.org', 'psni.org', 'www.psni.org'}
        (references if allowed and parsed.path.strip('/') else excluded).append(ref)
    plan['references'] = references
    if excluded:
        plan['unresolved_items'] = list(plan.get('unresolved_items', [])) + [{'kind': 'unverified_planning_reference', 'detail': '구체적인 원문 URL이 없는 참고 내용은 본문 근거로 사용하지 않음'}]
    common = load(ROOT / 'content-system/00_system/templates/articles/common.json')
    def block(elements, role):
        return {'role': role, 'purpose': ' / '.join(e['content_task'] for e in elements), 'fact_ids': []}
    opening = common['opening_sequence']
    closing = common['closing_sequence']
    plan['ordered_blocks'] = [
        block([e for e in opening if e['element'] == 'title'], 'title'),
        block([e for e in opening if e['element'] not in {'title', 'opening.inquiry_banner'}], 'opening'),
        block([e for e in opening if e['element'] == 'opening.inquiry_banner'], 'opening.inquiry_banner'),
        *[b for b in plan['ordered_blocks'] if b.get('role') != 'cta'],
        block([e for e in closing if e['element'] != 'closing.inquiry_banner'], 'closing'),
        block([e for e in closing if e['element'] == 'closing.inquiry_banner'], 'closing.inquiry_banner'),
    ]
    return plan


def snapshot(directory, state):
    """Publish actual new-run state, never stale drafts or invented approval."""
    active = next((a['content_id'] for a in state.get('articles', []) if a['stage'] not in {'done', 'blocked'}), None)
    for article in state.get('articles', []):
        cid = article['content_id']
        work = ROOT / 'content-system/working' / cid
        run = work / 'runs' / state['batch_id']
        run.mkdir(parents=True, exist_ok=True)
        previous = work / 'pipeline-latest.json'
        if previous.exists() and not (run / 'previous-result.json').exists():
            save(run / 'previous-result.json', load(previous))
        context = load(directory / (cid + '.context.json'))
        save(run / 'brief.json', {'brief': context['brief']})
        save(run / 'strategy.json', article['plan'])
        save(run / 'fact-bundle.json', {'facts': context['facts']})
        old = load(run / 'run-result.json') if (run / 'run-result.json').exists() else {}
        stage = {'write': 'write', 'edit': 'naver_edit', 'rewrite': 'write', 'review': 'feedback', 'official': 'official', 'official_interpret': 'official_interpret', 'assets': 'image_generation'}.get(article['stage'], old.get('stage', 'feedback'))
        result = {**old, 'content_id': cid, 'run_id': state['batch_id'], 'run_directory': str(run),
                  'execution_type': 'ide', 'created_at': old.get('created_at', datetime.now(timezone.utc).isoformat()),
                  'updated_at': datetime.now(timezone.utc).isoformat(), 'stage': stage,
                  'outcome': 'REVISION_REQUIRED' if article['stage'] == 'blocked' else 'COMPLETED_REVIEW_PENDING' if article['stage'] == 'done' else 'RUNNING',
                  'stage_detail': article.get('reason', article['stage']), 'publish_ready': False,
                  'admin_checks': [{'kind': 'rerun', 'detail': article['reason']}] if article.get('reason') else [],
                  'natural_logs': old.get('natural_logs', [])}
        if article['stage'] == 'write':
            result['stage_detail'] = f"블록별 집필 {len(article['blocks'])}/{len(article['plan']['ordered_blocks'])} 완료"
        if cid != active and article['stage'] not in {'done', 'blocked'}:
            result.update(outcome='PREPARED', stage='inputs', stage_detail='재기획 완료 · 순차 집필 대기')
        if not result['natural_logs'] or result['natural_logs'][-1]['message'] != result['stage_detail']:
            result['natural_logs'].append({'at': result['updated_at'], 'stage': stage, 'title': 'IDE 재실행', 'message': result['stage_detail'], 'status': 'INFO'})
        if article.get('draft_ready'):
            markdown = assemble(article['blocks'])
            revision = run / 'revisions/r1.draft.md'
            revision.parent.mkdir(parents=True, exist_ok=True)
            revision.write_text(markdown, encoding='utf-8')
            result.update(draft_file=str(revision), draft_sha256=hashlib.sha256(revision.read_bytes()).hexdigest())
            save(run / 'revisions/r1.claim-map.json', {'claims': claim_map(article['blocks'], context['facts'])})
            save(run / 'revisions/r1.writer-metadata.json', {'blocks': article['blocks']})
        output = directory / 'articles' / cid
        if (output / 'review.json').exists():
            result['qa'] = load(output / 'review.json')
        if (output / 'official-interpretation.json').exists():
            interpretation = load(output / 'official-interpretation.json')
            expected = {c['id'] for c in claim_map(article['blocks'], context['facts'])}
            verdicts = interpretation.get('claims', [])
            response = output / 'official-response.txt'
            valid = bool(expected) and {c.get('claim_id', c.get('id')) for c in verdicts} == expected and len(verdicts) == len(expected) and response.exists() and bool(response.read_text(encoding='utf-8').strip())
            result['official_review'] = {'status': 'REVIEWED' if valid else 'INCOMPLETE', 'decision': interpretation,
                                         'claims': verdicts, 'draft_sha256': result.get('draft_sha256')}
        if article.get('draft_ready'):
            slots = list(dict.fromkeys(re.findall(r'\{\{asset:([^}]+)\}\}', assemble(article['blocks']))))
            candidates = load(output / 'asset-candidates.json').get('candidates', []) if (output / 'asset-candidates.json').exists() else []
            needs = {n.get('asset_need_id', n.get('id')): n for n in article['plan'].get('asset_needs', [])}
            bindings = []
            for slot in slots:
                candidate = next((c for c in candidates if c.get('need_id') == slot), None)
                bindings.append({'need': {'id': slot, 'purpose': needs.get(slot, {}).get('purpose', slot)}, 'candidate': candidate, 'status': 'pending_review' if candidate else 'missing'})
            save(run / 'asset-bindings.json', {'bindings': bindings})
        save(run / 'run-result.json', result)
        save(previous, result)


def tick(directory, state):
    if state['stage'] == 'planning':
        result = receive(state['planner_task'])
        if result is None:
            return
        plans = result.get('articles', [])
        if len(plans) != 5 or {p.get('content_id') for p in plans} != set(state['content_ids']):
            raise ValueError('Planner must return exactly the five assigned articles')
        for plan in plans:
            if not plan.get('ordered_blocks') or not plan.get('title'):
                raise ValueError('Incomplete article plan')
        plans = [prepare_plan(p) for p in plans]
        result = {'articles': plans}
        save(directory / 'plans.json', result)
        state.update(stage='articles', articles=[{'content_id': p['content_id'], 'plan': p, 'stage': 'write', 'blocks': [], 'round': 0} for p in plans])
    if state['stage'] != 'articles':
        return
    # One assignment at a time per batch; an IDE session never receives racing jobs.
    article = next((a for a in state['articles'] if a['stage'] not in {'done', 'blocked'}), None)
    if article is None:
        state['stage'] = 'finished'
        return
    cid = article['content_id']
    context = load(directory / (cid + '.context.json'))
    plan = article['plan']
    output = directory / 'articles' / cid
    output.mkdir(parents=True, exist_ok=True)
    pending = article.get('pending')
    result = receive(pending) if pending else None
    if pending and result is None:
        return
    if article['stage'] == 'write':
        specs = plan['ordered_blocks']
        if result is not None:
            if not isinstance(result.get('markdown'), str) or not result['markdown'].strip():
                raise ValueError('Writer returned an empty block')
            if 'claims' not in result and not specs[len(article['blocks'])].get('fact_ids'):
                result['claims'] = []
            if not isinstance(result.get('claims'), list):
                raise ValueError('Writer must return claim content and Fact references')
            article['blocks'].append({'id': f'BLK-{len(article["blocks"])+1:03}', 'role': specs[len(article['blocks'])].get('role'), 'markdown': result['markdown'], 'claims': result['claims']})
            claim_map(article['blocks'], context['facts'])
            article.pop('pending')
        index = len(article['blocks'])
        if index < len(specs):
            spec = specs[index]
            required = set(spec.get('fact_ids', []))
            facts = [f for f in context['facts'] if f['id'] in required]
            if required - {f['id'] for f in facts}:
                article.update(stage='blocked', reason='Planning refers to unavailable Fact IDs')
                return
            payload = {'content_id': cid, 'title': plan['title'], 'keyword': plan.get('primary_keyword'), 'reader_question': plan.get('reader_question'),
                       'central_decision': plan.get('central_decision'), 'block': spec, 'facts': facts,
                       'outline': [{'role': s.get('role'), 'purpose': s.get('purpose')} for s in specs],
                       'previous_block': article['blocks'][-1]['markdown'] if article['blocks'] else '',
                       'product_choices': plan.get('product_choices', []), 'product_links': context['product_links'],
                       'references': plan.get('references', []), 'asset_needs': plan.get('asset_needs', []),
                       'input_notice': '기획의 목적·추천 사유는 작업 방향이며 사실 근거가 아닙니다. 제품 주장은 facts로만 확정하고 미확인 AVIXA/PSNI 내용은 사용하지 않습니다.'}
            guides = '\n\n'.join(context['guides'].get(name, '') for name in ['03-opening-body-closing.md', '04-images.md'])
            guides += '\n\n' + '\n\n'.join(r['body'] for r in context['cautions'])
            guides += '\n\n' + '\n\n'.join((ROOT / path).read_text(encoding='utf-8-sig') for path in ['content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md', 'content-system/02_writer_ai/authoring/rules/reader-and-style.md'])
            article['pending'] = dispatch(directory, 'writer', '지정된 구성 블록 하나만 새로 집필하세요. 다른 블록은 작성하지 않습니다. 원시인 모드. 제공 Fact·출처 범위를 넘는 제품 수치·기능·지원·실증을 만들지 않습니다. 문장은 자연스럽게, 문단과 실제 줄바꿈은 의미 단위로 배치합니다. 제목 블록은 # 제목, 본문 소제목은 ## 사용. 출력은 {"markdown":"이 블록의 완성 문장","claims":[{"text":"제품 주장의 본문 정확한 인용","fact_ids":["실제 Fact ID"]}]}만. 제품 주장이 없으면 claims는 빈 배열. 이미지가 필요하면 지정 need_id의 {{asset:NEED-ID}} 슬롯 사용. 해시·로그·변경표·검증 코드는 작성하지 않습니다.', payload, guides)
            return
        article['stage'] = 'edit'
        result = None
    if article['stage'] in {'edit', 'rewrite'}:
        if result is not None:
            blocks = result.get('blocks', [])
            if [b.get('id') for b in blocks] != [b['id'] for b in article['blocks']]:
                raise ValueError('Editing omitted or reordered blocks')
            assemble(blocks)
            blocks = [{**old, 'markdown': new['markdown']} for old, new in zip(article['blocks'], blocks)]
            claim_map(blocks, context['facts'])
            article['blocks'] = blocks
            article['draft_ready'] = True
            article.pop('pending')
            article['stage'] = 'review'
            result = None
        else:
            rewriting = article['stage'] == 'rewrite'
            payload = {'blocks': [{'id': b['id'], 'markdown': b['markdown'], 'protected_claims': b.get('claims', [])} for b in article['blocks']]}
            if rewriting:
                payload.update(feedback=article.get('issues', []), facts=context['facts'], sources=context['sources'])
            guide = context['guides'].get('03-opening-body-closing.md', '') + '\n\n' + (ROOT / 'content-system/05_publish/naver-editorial-layout.md').read_text(encoding='utf-8-sig')
            article['pending'] = dispatch(directory, 'writer', ('독립 검토의 문제를 수정하세요. 지적이 타당한 곳만 수정하세요. protected_claims의 오류로 보존할 수 없다면 원고를 추측 수정하지 말고 unresolved_items에 남기세요. ' if rewriting else '') + '네이버 블로그용 문단·어투 편집입니다. 모든 블록을 편집하되 정보·수치·조건·링크·이미지 슬롯은 보존합니다. protected_claims는 공백과 개행만 조절할 수 있습니다. 의미 단위 실제 줄바꿈과 문단 사이 빈 줄을 사용하고 수식어-명사·숫자-단위를 끊지 마세요. 문맥상 이미 아는 대상을 장황하게 다시 지칭하지 마세요. 출력은 {"blocks":[{"id":"입력 id","markdown":"편집문"}]}만. 기록·전후 비교·로그는 작성하지 않습니다.', payload, guide)
            return
    if article['stage'] == 'review':
        markdown = assemble(article['blocks'])
        (output / 'draft.md').write_text(markdown, encoding='utf-8')
        save(output / 'blocks.json', {'blocks': article['blocks']})
        save(output / 'publish-checks.json', inspect_article(markdown, context['brief'], []))
        if result is None:
            article['pending'] = dispatch(directory, 'review', '새로 쓴 글 전문을 독립 검토하세요. 검색 의도·문제 회수·제품 적용 조건·Claim 누락과 Fact/실제 출처 일치·빠진 주의사항·중복 지칭·자연스러운 문단/줄바꿈·브랜드/이미지 규칙을 확인하세요. 기존 기획자의 설명을 옹호하지 마세요. 실제 문제만 passed와 issues(location,reason,requested_change)로 반환. 원고·기록·검증 코드 작성 금지.', {'blocks': article['blocks'], 'claims': claim_map(article['blocks'], context['facts']), 'brief': context['brief'], 'facts': context['facts'], 'sources': context['sources'], 'cautions': context['cautions']}, context['guides'].get('05-feedback-and-review.md', ''))
            return
        save(output / 'review.json', result)
        article.pop('pending')
        if result.get('passed') is not True:
            article['round'] += 1
            article.update(stage='rewrite' if article['round'] <= 2 else 'blocked', issues=result.get('issues', []))
            if article['stage'] == 'blocked':
                article['reason'] = 'Independent review still requires revision after two rewrites'
            return
        article['stage'] = 'official'
    if article['stage'] == 'official':
        import requests
        request_payload = {'markdown': assemble(article['blocks']), 'claims': claim_map(article['blocks'], context['facts']), 'facts': context['facts'], 'sources': context['sources']}
        request_file = output / 'official-request.json'
        save(request_file, request_payload)
        audit = {'status': 'checking_server', 'endpoint': 'http://127.0.0.1:5050/ask', 'started_at': datetime.now(timezone.utc).isoformat(),
                 'request_sha256': hashlib.sha256(request_file.read_bytes()).hexdigest(), 'claim_count': len(request_payload['claims'])}
        save(output / 'official-call.json', audit)
        try:
            health = requests.get('http://127.0.0.1:5050/health', timeout=5)
            if health.status_code != 200 or health.json().get('status') != 'ready':
                raise RuntimeError('Logitech review service is not ready')
            from services.pipeline_provider import ModelProvider
            provider = ModelProvider(ROOT)
            audit['status'] = 'sending'
            save(output / 'official-call.json', audit)
            official = provider.official('원고의 제품 주장과 Fact·출처 위치를 대조해 오류와 조건 누락을 검토해 주세요.', request_payload)
            (output / 'official-response.txt').write_bytes(official.encode('utf-8'))
            audit.update(status='response_received', completed_at=datetime.now(timezone.utc).isoformat(), response_sha256=hashlib.sha256(official.encode('utf-8')).hexdigest())
            save(output / 'official-call.json', audit)
            article.update(stage='official_interpret')
            result = None
        except Exception as error:
            from services.logitech_review_status import inspect_failure
            failure = inspect_failure(error)
            audit.update(status='failed', completed_at=datetime.now(timezone.utc).isoformat(), error_type=type(error).__name__, diagnostic=failure)
            save(output / 'official-call.json', audit)
            save(output / 'official-failure.json', failure)
            article.update(stage='assets', official_pending=True, official_failure=failure, reason=failure['action_required'])
            result = None
    if article['stage'] == 'official_interpret':
        if result is None:
            article['pending'] = dispatch(directory, 'review', '로지텍 AI 응답을 원고·Claim·공식 근거와 대조하여 진행 가능 여부를 의미로 판단하세요. 단어 포함 여부로 판정하지 마세요. 실제 사양 오류·조건 누락·근거 충돌은 수정 요청합니다. 단순 면책·일반적 확인 권고는 이유 없이 중단 사유로 삼지 않습니다. 신뢰할 근거가 부족하면 보류합니다. 출력은 passed,issues,claims입니다. claims 배열에 전달된 모든 Claim의 claim_id,verdict(confirmed/rejected/insufficient_evidence),reason을 반환하세요. 응답이 확인하지 않은 주장을 일괄 confirmed로 만들지 마세요.', {'markdown': assemble(article['blocks']), 'claims': claim_map(article['blocks'], context['facts']), 'facts': context['facts'], 'sources': context['sources'], 'official_response': (output / 'official-response.txt').read_text(encoding='utf-8')}, context['guides'].get('05-feedback-and-review.md', ''))
            return
        save(output / 'official-interpretation.json', result)
        article.pop('pending')
        expected = {c['id'] for c in claim_map(article['blocks'], context['facts'])}
        verdicts = result.get('claims', [])
        if not expected or {c.get('claim_id', c.get('id')) for c in verdicts} != expected or len(verdicts) != len(expected):
            article.update(stage='blocked', official_pending=True, reason='공식 검토 Claim별 판정 누락: 검토 완료로 처리하지 않습니다.')
            return
        if result.get('passed') is not True:
            article['round'] += 1
            article.update(stage='rewrite' if article['round'] <= 2 else 'blocked', issues=result.get('issues', []))
            if article['stage'] == 'blocked':
                article['reason'] = 'Official review still requires revision after two rewrites'
            return
        article['stage'] = 'assets'
        result = None
    if article['stage'] == 'assets':
        if result is None:
            article['pending'] = dispatch(directory, 'assets', '새 원고의 이미지 슬롯과 목적에 맞는 자산 후보를 확보하세요. 승인된 공식 자산 우선, 없는 상황 이미지·도식은 IDE 내장 이미지 생성 도구를 직접 호출해 실제 PNG 파일을 자기 work/TASK-ID/asset_fulfillment/images/content_id/need_id.png에 제작하세요. 생성 가능한 자리를 시도 없이 미해결로 넘기지 마세요. 제품 실물·포트·설정 화면은 추측 생성하지 않고 공식 자료가 없으면 구체적 사유를 남깁니다. 배너는 지정 공통 자산을 사용합니다. 원고·승인·Fact·발행은 변경하지 마세요. 결과는 {"candidates":[{"need_id":"지정 ID","path":"실제 생성한 자기 루트 상대경로 또는 빈 문자열","url":"검증된 실제 URL 또는 빈 문자열","caption":"설명"}],"unresolved_items":[]}만. 제작 도구 실패·사용 불가·공식 자료 필수인 경우에만 unresolved_items에 need_id와 reason을 반환하세요. 로그·기록·검증 코드는 작성하지 않습니다.', {'content_id': cid, 'blocks': article['blocks'], 'asset_needs': plan.get('asset_needs', []), 'existing_assets': context['assets']}, context['guides'].get('04-images.md', ''))
            return
        if not isinstance(result.get('candidates'), list) or not isinstance(result.get('unresolved_items'), list):
            raise ValueError('Invalid asset candidate response')
        for candidate in result['candidates']:
            if candidate.get('path'):
                source = local(ROOT / 'worker-workspaces' / '05_assets', candidate['path'])
                if not source.is_file() or source.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg'}:
                    raise ValueError('Asset worker returned an unavailable image file')
                destination = output / 'assets' / source.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                candidate['local_path'] = str(destination)
        # Candidate submission is never an asset approval or final approval.
        save(output / 'asset-candidates.json', result)
        article.pop('pending')
        missing = result.get('unresolved_items', [])
        official_reason = article.get('official_failure', {}).get('action_required', '공식 검토 재확인 필요') if article.get('official_pending') else ''
        asset_reason = f'이미지 제작·확보 미완료 {len(missing)}건' if missing else '이미지 후보 검토·최종 원고 승인 대기'
        article.update(stage='blocked' if article.get('official_pending') or missing else 'done', reason=' '.join(x for x in [official_reason, asset_reason] if x), unresolved_assets=missing)
    # Results are new candidates. No automatic approval, publication, or stale draft overwrite.


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', required=True)
    parser.add_argument('--planner-task', required=True)
    parser.add_argument('--watch', action='store_true')
    args = parser.parse_args()
    directory = local(ROOT, args.directory)
    state_path = directory / 'execution.json'
    if not state_path.exists():
        initial = load(directory / 'state.json')
        initial.update(stage='planning', planner_task=load(ROOT / 'worker-control/dispatch/tasks' / (args.planner_task + '.json')))
        save(state_path, initial)
    lock = directory / 'controller.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    deadline = time.monotonic() + 86400
    try:
        while True:
            state = load(state_path)
            try:
                tick(directory, state)
                snapshot(directory, state)
                state['updated_at'] = datetime.now(timezone.utc).isoformat()
                signature = [[a['content_id'], a['stage']] for a in state.get('articles', [])]
                if signature and signature != state.get('taiga_signature'):
                    try:
                        from services.taiga_tracking import synchronize
                        synchronize()
                        state['taiga_signature'] = signature
                    except Exception as error:
                        state['taiga_sync_error'] = type(error).__name__
            except Exception as error:
                active = next((a for a in state.get('articles', []) if a['stage'] not in {'done', 'blocked'}), None)
                if active:
                    active.update(stage='blocked', reason=type(error).__name__ + ': ' + str(error)[:220])
                else:
                    state.update(stage='error', error=type(error).__name__ + ': ' + str(error)[:220])
            save(state_path, state)
            if not args.watch or state['stage'] in {'finished', 'error'} or time.monotonic() > deadline:
                print(json.dumps({'batch_id': state['batch_id'], 'stage': state['stage'], 'error': state.get('error')}, ensure_ascii=False))
                break
            time.sleep(10)
    finally:
        lock.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
