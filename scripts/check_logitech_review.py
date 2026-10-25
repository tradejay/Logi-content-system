"""Verify one real local official-review call; never grants review approval."""
import argparse
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from services.ide_worker_bridge import ROOT, load, save, local
from services.pipeline_provider import ModelProvider
from services.logitech_review_status import inspect_failure


def record_received(cid, view, run):
    audit = load(run / 'official-call.json')
    response = run / 'official-response.txt'
    file_hash = hashlib.sha256(response.read_bytes()).hexdigest()
    if audit.get('response_sha256') != file_hash and audit.get('response_sha256') == hashlib.sha256(response.read_text(encoding='utf-8').encode()).hexdigest():
        backup = run / 'official-call.before-filehash-normalization.json'
        if not backup.exists():
            save(backup, audit)
        audit.update(response_text_sha256=audit['response_sha256'], response_sha256=file_hash)
        save(run / 'official-call.json', audit)
    if audit.get('status') != 'response_received' or audit.get('draft_sha256') != view['draft_sha256'] or hashlib.sha256(response.read_bytes()).hexdigest() != audit.get('response_sha256'):
        raise ValueError('Official response is not verified for the current draft')
    path = ROOT / 'content-system/working' / cid / 'pipeline-latest.json'
    latest = load(path)
    if latest['run_id'] != view['run_id'] or latest['draft_sha256'] != view['draft_sha256']:
        raise ValueError('Current run changed')
    latest.update(official_review={'status': 'RESPONSE_RECEIVED', 'claims': [], 'draft_sha256': view['draft_sha256'],
                                  'response_file': str(response), 'response_sha256': audit['response_sha256']},
                  publish_ready=False, stage='official_interpret', stage_detail='로지텍 응답 수신 완료 · Claim별 판정 대기')
    latest.pop('official_failure', None)
    events = latest.setdefault('natural_logs', [])
    if not any(e.get('response_sha256') == audit['response_sha256'] for e in events):
        events.append({'at': audit.get('completed_at'), 'stage': 'official', 'status': 'INFO', 'title': '로지텍 응답 수신',
                       'message': f"로지텍 검토 응답 수신 완료 · Claim {audit.get('claim_count')}개 · 별도 판정 대기", 'response_sha256': audit['response_sha256']})
    save(path, latest)
    save(run / 'run-result.json', latest)
    batch_path = ROOT / 'worker-control/article-reruns' / view['run_id'] / 'execution.json'
    if batch_path.exists() and not (batch_path.parent / 'controller.lock').exists():
        batch = load(batch_path)
        for article in batch.get('articles', []):
            if article['content_id'] == cid:
                article.pop('official_failure', None)
                article.update(official_pending=True, reason='로지텍 응답 수신 · Claim별 판정 대기')
        save(batch_path, batch)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--content', required=True)
    parser.add_argument('--record-only', action='store_true')
    args = parser.parse_args()
    from services.asset_revision import snapshot
    view = snapshot(args.content)
    latest = load(ROOT / 'content-system/working' / args.content / 'pipeline-latest.json')
    run = local(ROOT / 'content-system/working' / args.content / 'runs', view['run_id'])
    if args.record_only:
        record_received(args.content, view, run)
        print('verified response recorded; not approved')
        return
    claims = load(Path(latest.get('claim_map_file', run / 'revisions/r1.claim-map.json')))['claims']
    ids = {fid for claim in claims for fid in claim['fact_ids']}
    facts = [f for f in load(run / 'fact-bundle.json')['facts'] if f['id'] in ids]
    request = {'content_id': args.content, 'run_id': view['run_id'], 'draft_sha256': view['draft_sha256'],
               'markdown': local(ROOT, str(Path(latest['draft_file']).relative_to(ROOT))).read_text(encoding='utf-8'),
               'claims': claims, 'facts': facts,
               'source_locations': [f.get('source') for f in facts]}
    save(run / 'official-request.json', request)
    audit = {'status': 'sending', 'started_at': datetime.now(timezone.utc).isoformat(), 'claim_count': len(claims),
             'request_sha256': hashlib.sha256((run / 'official-request.json').read_bytes()).hexdigest(), 'draft_sha256': view['draft_sha256']}
    save(run / 'official-call.json', audit)
    try:
        response = ModelProvider(ROOT).official('공식 기술 검토 요청입니다. 원고 전문과 각 Claim, 연결 Fact 및 출처 위치를 대조해 주세요. 제품 사양 오류·지원 조건 누락을 Claim ID별로 지적하고, 확인할 수 없는 내용은 확인 불가로 명시해 주세요.', request)
        (run / 'official-response.txt').write_bytes(response.encode('utf-8'))
        audit.update(status='response_received', response_chars=len(response), response_sha256=hashlib.sha256(response.encode()).hexdigest())
        print('response_received', len(response), 'chars; interpretation still required', flush=True)
    except Exception as error:
        audit.update(status='failed', error_type=type(error).__name__, diagnostic=inspect_failure(error))
        print('failed:', audit['diagnostic']['action_required'], flush=True)
    audit['completed_at'] = datetime.now(timezone.utc).isoformat()
    save(run / 'official-call.json', audit)
    if audit['status'] == 'response_received':
        record_received(args.content, view, run)


if __name__ == '__main__':
    main()
