"""Human-readable Taiga ticket descriptions from existing execution records."""
import json
import re
from urllib.parse import urlparse, urljoin, parse_qs, urlencode

STAGES = {'inputs': '자료·웹 탐색', 'strategy': '기획 전략', 'assets': '이미지 계획',
          'write': '블록 집필', 'feedback': '자체 검토', 'official': '로지텍 검토',
          'official_interpret': '공식 피드백 해석', 'image_generation': '이미지 제작',
          'publish_checks': '발행 전 검사', 'finished': '실행 종료', 'blocked': '조치 필요'}
OUTCOMES = {'REVISION_REQUIRED': '수정 필요', 'NEEDS_EVIDENCE': '근거 보완 필요',
            'COMPLETED_REVIEW_PENDING': '관리자 확인 대기', 'COMPLETED_READY': '작성 처리 완료',
            'RUNNING': '실행 중', 'CHECKING': '점검 중', 'FAILED': '실행 실패'}


def text(value):
    if value is None:
        return '미기록'
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def cell(value):
    return text(value).replace('|', '\\|').replace('\n', '<br>')


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(cell(v) for v in row) + ' |' for row in rows])


def number(value):
    return f'{value:,}' if isinstance(value, (int, float)) else '미기록'


def article_with_images(markdown, bindings, console_url):
    def replace(match):
        identifier = match.group(1)
        binding = next((b for b in bindings if identifier in {
            (b.get('need') or {}).get('id'), (b.get('need') or {}).get('asset_id'),
            (b.get('candidate') or {}).get('asset_id')} or
            (b.get('need') or {}).get('anchor') == match.group(0)), None)
        candidate = (binding or {}).get('candidate') or {}
        base = urlparse(console_url)
        cid = candidate.get('content_id') or parse_qs(base.query).get('content', [''])[0]
        action = ''
        if binding and cid and base.scheme in {'http', 'https'} and base.netloc:
            action_url = urljoin(console_url, '/asset-revision.html') + '?' + urlencode({'content': cid, 'need': (binding.get('need') or {}).get('id') or identifier})
            action = '\n\n[이미지 생성·재제작 요청](' + action_url + ')\n\n'
        if candidate.get('review_status') == 'rejected' or (binding or {}).get('status') == 'rejected':
            return '\n\n> 이미지 사용 불가 · ' + identifier + '\n\n' + action
        url = None
        for value in [candidate.get(k) for k in ('public_url', 'drive_url', 'url')]:
            if not isinstance(value, str):
                continue
            if value.startswith('/api/content-system/assets/'):
                base = urlparse(console_url)
                if base.scheme in {'http', 'https'} and base.netloc:
                    url = urljoin(console_url, value)
                    break
            parsed = urlparse(value)
            if parsed.scheme == 'https' and parsed.netloc and not parsed.username and not parsed.password:
                url = value
                break
        if not url:
            return '\n\n> 이미지 확보 대기 · ' + identifier + '\n\n' + action
        caption = candidate.get('caption') or (binding.get('need') or {}).get('purpose') or identifier
        alt = text(candidate.get('alt') or caption).replace('[', '').replace(']', '').replace('\n', ' ')
        # Explicitly a preview; no approval status or source draft is mutated.
        state = '승인됨' if binding.get('status') == 'approved' else '미리보기 · 승인 상태 확인 필요'
        url = url.replace(' ', '%20').replace('(', '%28').replace(')', '%29')
        return '\n\n![' + alt + '](' + url + ')\n\n*' + text(caption) + ' — ' + state + '*\n\n' + action
    return re.sub(r'\{\{asset:([^}]+)\}\}', replace, markdown)


def render_ticket(task):
    ref, summary, details = task.get('refs', {}), task.get('summary', {}), task.get('details', {})
    parts = ['<!-- content-ops:' + task['key'] + ' -->',
             '## 작업 현황', table(['항목', '현재 상태'], [
                 ['작업 종류', task['category']], ['진행 상태', task['state']],
                 ['실행 판정', OUTCOMES.get(summary.get('outcome'), summary.get('outcome') or summary.get('status') or task['state'])],
                 ['콘텐츠', ref.get('content_id') or '해당 없음'], ['실행 ID', ref.get('run_id') or '해당 없음']])]
    if task.get('console_url'):
        parts.append('[원고·이미지·전체 실행 로그 열기](' + task['console_url'] + ')')
        if task['category']=='글':
            approval_url=task['console_url'].split('/article-console.html',1)[0]+'/article-approval.html?content='+ref['content_id']
            parts.append('## [이미지 승인 · 글 확정 · 다음 단계](' + approval_url + ')\n사진 검토 결과, 공개 주소 연결, 최종 승인을 버튼으로 진행합니다.')
    if task.get('editor_url'):
        parts.append('### 원고 수정\n[원고 편집 카드 열기](' + task['editor_url'] + ')\n\n'
                     '이 카드의 설명은 자동 현황입니다. 원고 편집 카드에서 본문을 수정하고 저장하세요. '
                     '약 60초 뒤 원본 새 버전으로 저장되고 기존 승인이 해제되며 변경 검토 상태로 전환됩니다. '
                     'AI 재검토는 상세 콘솔에서 실행합니다.')
    if task.get('workflow_note'):
        parts.append('### 요청 처리 결과\n' + task['workflow_note'])
    if task.get('tracking_note'):
        parts.append('### 기록 구분\n' + task['tracking_note'])
    if task.get('current_stage'):
        stage = task['current_stage']
        parts.append('**현재 단계: ' + str(stage['number']) + '단계 · ' + stage['name'] + '** — ' + stage['reason'])
        parts.append('작업 주체: ' + stage.get('actors', '확인 필요') + '\n\n관리자 개입: ' + stage.get('intervention', '확인 필요'))
    parts.append('작업 완료는 글 발행·이미지 승인·Fact 확정을 대신하지 않습니다.')
    if task['category'] == '글':
        calls = details.get('calls') or []
        totals = details.get('totals') or {}
        elapsed = details.get('elapsed_seconds')
        measured = lambda key: number(totals.get(key)) if any(isinstance(c.get(key), (int, float)) for c in calls) else '미기록'
        parts.extend(['## 실행 성능', table(['항목', '기록'], [
            ['소요 시간', f'{elapsed:.1f}초' if isinstance(elapsed, (int, float)) else '미기록'],
            ['입력 토큰 측정 합계', measured('input_tokens')],
            ['생성 응답 총 토큰', measured('provider_total_tokens')],
            ['원고 분량', str(details.get('draft_chars', 0)) + '자'],
            ['주 키워드', details.get('keyword') or '미기록'],
            ['가이드 릴리스', details.get('release_id') or '미기록']]),
            '토큰은 기록된 호출만 합산합니다. 입력 측정에는 생성이 차단된 호출도 포함될 수 있습니다.'])
        groups = details.get('stage_groups') or []
        if groups:
            parts.append('## 실행 순서\n' + ' → '.join(STAGES.get(g['stage'], g['stage']) for g in groups))
        events = details.get('events') or []
        if events:
            parts.append(table(['단계', '상태', '내용'], [
                [STAGES.get(e.get('stage'), e.get('stage')), e.get('status'),
                 e.get('message') or e.get('detail') or e.get('title')] for e in events]))
        checks = details.get('checks') or {}
        qa = checks.get('qa') or {}
        if isinstance(qa, dict):
            passed = qa.get('passed')
            feedback = qa.get('feedback') or {}
            parts.append('## 검토 결과\n자체 검토: ' + ('통과' if passed is True else '보완 필요' if passed is False else '미기록'))
            if isinstance(feedback, dict):
                issues = feedback.get('issues') or []
                if issues:
                    parts.append(table(['Claim', '분류', '수정·검토 사유'], [[i.get('claim_id'), i.get('category'), i.get('detail')] for i in issues]))
                for field, label in [('missing_claims', '누락된 주장'), ('contract_errors', '출력 계약 오류')]:
                    if feedback.get(field):
                        parts.append('### ' + label + '\n' + '\n'.join('- ' + text(i) for i in feedback[field]))
            if qa.get('contract_errors') and not (isinstance(feedback, dict) and feedback.get('contract_errors')):
                parts.append('### 출력 계약 오류\n' + '\n'.join('- ' + text(i) for i in qa['contract_errors']))
        official = checks.get('official')
        if official:
            parts.append('### 로지텍 검토 기록\n```json\n' + json.dumps(official, ensure_ascii=False, indent=2) + '\n```')
        if details.get('admin_checks'):
            parts.append('### 남은 확인 항목\n' + '\n'.join('- ' + text(i) for i in details['admin_checks']))
        if summary.get('error'):
            parts.append('### 실행 오류\n' + text(summary['error']))
        parts.append('## 작성된 글\n> 실행 원고입니다. 검토·수정 또는 이미지 승인이 남아 있을 수 있습니다.\n\n' +
                     (article_with_images(details['markdown'], details.get('asset_bindings') or [], task.get('console_url', ''))
                      if details.get('markdown') else '작성 결과 없음 — 이 실행에 대응하는 검증된 원고가 없습니다.'))
        if details.get('notes'):
            parts.append('## 기록 참고\n' + '\n'.join('- ' + text(n) for n in details['notes']))
    else:
        parts.append('## 작업 내용\n```json\n' + json.dumps(summary, ensure_ascii=False, indent=2) + '\n```')
    if task['category'] == '이미지':
        parts.append('## 이미지 검토 입력\n'
                     '아래 JSON을 편집해 저장하면 검토 요청으로 처리합니다. decision은 '
                     '`pending` / `approve` / `revise` / `reject`입니다. review_note에 검토 의견을 적으세요. '
                     '승인은 공개 HTTPS 이미지 주소와 현재 원고·자산 검증이 필요합니다. 완료 이동만으로 승인되지 않습니다.\n\n'
                     '```json\n' + (task.get('review_input_raw') or json.dumps(task.get('review_input') or {
                         'decision': 'pending', 'asset_id': (summary.get('output') or {}).get('asset_id') or '',
                         'draft_sha256': ref.get('draft_sha256'), 'review_note': '', 'public_url': ''}, ensure_ascii=False, indent=2)) + '\n```')
    parts.append('## 추적 정보\n원본: `' + (task.get('source_path') or '별도 등록 작업') + '`\n\n```json\n' +
                 json.dumps(ref, ensure_ascii=False, indent=2) + '\n```')
    return '\n\n'.join(parts).strip()
