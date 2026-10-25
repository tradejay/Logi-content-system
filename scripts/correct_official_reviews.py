"""Bounded official-feedback correction, independent review, and official recheck."""
import hashlib
import argparse
import re
import subprocess
import sys
import time
from copy import deepcopy
from pathlib import Path
from services.ide_worker_bridge import ROOT, load, save
from services.asset_revision import snapshot
from scripts.run_ide_article_batch import dispatch, receive, assemble, claim_map
from services.ide_worker_artifacts import review_packet


def merge_edits(original, result, facts):
    edits = result.get('blocks', [])
    if [b.get('id') for b in edits] != [b['id'] for b in original]:
        raise ValueError('Correction changed block IDs/order or omitted blocks')
    merged = []
    for old, edit in zip(original, edits):
        if not isinstance(edit.get('markdown'), str) or not edit['markdown'].strip():
            raise ValueError('Empty corrected block')
        if re.findall(r'\{\{asset:[^}]+\}\}', old['markdown']) != re.findall(r'\{\{asset:[^}]+\}\}', edit['markdown']):
            raise ValueError('Correction changed image slots')
        if old.get('role') in {'title', 'opening.inquiry_banner', 'closing.inquiry_banner'} and edit['markdown'] != old['markdown']:
            raise ValueError('Correction changed protected common block')
        merged.append({**deepcopy(old), 'markdown': edit['markdown'], 'claims': edit.get('claims', old.get('claims', []))})
    mapped = claim_map(merged, facts)
    if not mapped:
        raise ValueError('Correction removed all product claims')
    return merged, mapped


def wait_result(task):
    deadline = time.monotonic() + 1800
    while time.monotonic() < deadline:
        result = receive(task)
        if result is not None:
            return result
        time.sleep(5)
    raise TimeoutError('Worker output not received; existing task retained')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--content')
    parser.add_argument('--retry', action='store_true')
    parser.add_argument('--instruction', default='')
    args = parser.parse_args()
    directory = ROOT / 'worker-control/article-reruns/RERUN-20261016T050248'
    progress = directory / 'official-corrections.json'
    state = load(progress) if progress.exists() else {'status': 'running', 'articles': {}}
    lock = directory / 'official-corrections.lock'
    with lock.open('x'):
        pass
    try:
        for cid in load(directory / 'execution.json')['content_ids']:
            if args.content and cid != args.content:
                continue
            item = state['articles'].setdefault(cid, {'round': 0})
            if item.get('status') in {'confirmed', 'needs_attention'} and not args.retry:
                continue
            try:
                view = snapshot(cid)
                run = ROOT / 'content-system/working' / cid / 'runs' / view['run_id']
                context = load(directory / (cid + '.context.json'))
                facts = load(run / 'fact-bundle.json')['facts']
                latest_path = ROOT / 'content-system/working' / cid / 'pipeline-latest.json'
                previous_rounds = list((run / 'official-corrections').glob('round-*'))
                start = max([item['round']] + [int(p.name.split('-')[-1]) for p in previous_rounds]) if args.retry else item['round']
                for attempt in range(start + 1, start + 3):
                    latest = load(latest_path)
                    before_hash = latest['draft_sha256']
                    metadata = Path(latest.get('writer_metadata_file', run / 'revisions/r1.writer-metadata.json'))
                    original = load(metadata)['blocks']
                    feedback = load(run / 'official-interpretation.json')
                    if all(v.get('verdict') == 'confirmed' for v in feedback.get('claims', [])) and feedback.get('claims') and feedback.get('passed'):
                        item.update(status='confirmed')
                        break
                    folder = run / 'official-corrections' / f'round-{attempt}'
                    folder.mkdir(parents=True, exist_ok=True)
                    if not (folder / 'writer-task.json').exists():
                        task = dispatch(directory, 'writer',
                            '공식 검토 지적만 수정하세요. 지적은 제안이며 Fact·공식 출처와 대조하고 근거 없는 추가 단정은 하지 마세요. 미확인 주장은 삭제·완화할 수 있습니다. 새 Fact 확정은 금지합니다. 네이버 어투·의미 단위 줄바꿈과 이미지 슬롯, 블록 순서, 제목·배너는 유지하세요. 출력 blocks 배열에 모든 블록의 id,markdown,claims(text,fact_ids)를 반환하세요. claims는 수정된 제품 주장의 정확한 인용과 제공된 실제 Fact ID만 사용합니다. 로그·변경표·해시·검증 코드는 작성하지 마세요.',
                            {'content_id': cid, 'blocks': original, 'feedback': feedback['issues'], 'additional_instruction': args.instruction, 'facts': facts,
                             'sources': context['sources'], 'official_response': (run / 'official-response.txt').read_text(encoding='utf-8')},
                            context.get('guides', {}).get('05-feedback-and-review.md', '') + '\n' + (ROOT / 'content-system/05_publish/naver-editorial-layout.md').read_text(encoding='utf-8-sig'))
                        save(folder / 'writer-task.json', task)
                    item.update(status='rewriting', active_round=attempt)
                    save(progress, state)
                    result = wait_result(load(folder / 'writer-task.json'))
                    blocks, claims = merge_edits(original, result, facts)
                    if not (folder / 'review-task.json').exists():
                        task = dispatch(directory, 'review',
                            '수정본 전문을 독립 검토하세요. 전달된 지적 해결 여부, 제품 주장과 Fact·출처의 일치, 새 오류·조건 누락, 문단·줄바꿈과 이미지 위치 적합도를 판단하세요. 이전 리뷰나 집필자 판단을 그대로 수용하지 마세요. 출력 passed,issues만. 기록·비교표·재작성은 하지 마세요.',
                            {**review_packet(original, blocks), 'claims': claims, 'facts': facts, 'sources': context['sources'],
                             'feedback': feedback['issues'], 'asset_bindings': load(run / 'asset-bindings.json')},
                            context.get('guides', {}).get('05-feedback-and-review.md', ''))
                        save(folder / 'review-task.json', task)
                    item.update(status='independent_review')
                    save(progress, state)
                    review = wait_result(load(folder / 'review-task.json'))
                    save(folder / 'review.json', review)
                    save(folder / 'candidate-blocks.json', {'blocks': blocks})
                    if review.get('passed') is not True:
                        item.update(status='needs_attention', reason='수정본 독립 검토 미통과', issues=review.get('issues', []))
                        break
                    current = snapshot(cid)
                    if current['draft_sha256'] != before_hash or current['run_id'] != view['run_id']:
                        raise ValueError('Current draft changed while worker was editing')
                    # Only text/claim pointers change. Bindings and old revisions remain intact.
                    revision = run / 'revisions' / f'official-r{attempt + 1}'
                    draft = revision.with_suffix('.draft.md')
                    draft.write_bytes(assemble(blocks).encode('utf-8'))
                    claim_path = revision.with_suffix('.claim-map.json')
                    metadata_path = revision.with_suffix('.writer-metadata.json')
                    save(claim_path, {'claims': claims})
                    save(metadata_path, {'blocks': blocks})
                    save(folder / 'previous-result.json', latest)
                    for name in ['official-request.json', 'official-call.json', 'official-response.txt', 'official-interpretation.json']:
                        source = run / name
                        if source.exists():
                            (folder / ('previous-' + name)).write_bytes(source.read_bytes())
                    latest = load(latest_path)
                    latest.update(draft_file=str(draft), draft_sha256=hashlib.sha256(draft.read_bytes()).hexdigest(),
                                  claim_map_file=str(claim_path), writer_metadata_file=str(metadata_path), qa=review,
                                  official_review={'status': 'PENDING', 'claims': []}, publish_ready=False,
                                  stage='official', stage_detail='지적 수정·독립 검토 완료 · 로지텍 재검증 중')
                    latest.pop('approval', None)
                    latest.pop('approved_at', None)
                    save(latest_path, latest)
                    save(run / 'run-result.json', latest)
                    item.update(status='official_recheck', round=attempt)
                    save(progress, state)
                    subprocess.run([sys.executable, '-m', 'scripts.resume_official_reviews', '--content', cid], cwd=ROOT, check=True)
                    updated = load(latest_path).get('official_review', {})
                    if updated.get('status') != 'REVIEWED':
                        item.update(status='needs_attention', reason='로지텍 재검증 응답 또는 Claim 판정 미완료')
                        break
                    if updated.get('claims') and all(c.get('verdict') == 'confirmed' for c in updated['claims']) and updated.get('decision', {}).get('passed') is True:
                        item.update(status='confirmed')
                        break
                if item.get('status') not in {'confirmed', 'needs_attention'}:
                    item.update(status='needs_attention', reason='수정·공식 재검증 2회 상한 도달')
            except Exception as error:
                item.update(status='needs_attention', reason=str(error))
            save(progress, state)
            subprocess.run([sys.executable, '-m', 'scripts.sync_taiga', '--sync'], cwd=ROOT, check=False)
        state['status'] = 'finished'
        save(progress, state)
    finally:
        lock.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
