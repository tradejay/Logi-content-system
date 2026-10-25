"""Resume official calls and IDE interpretation without touching drafts or assets."""
import hashlib
import argparse
import subprocess
import sys
import time
from datetime import datetime, timezone
from services.ide_worker_bridge import ROOT, load, save
from services.asset_revision import snapshot
from scripts.check_logitech_review import record_received
from scripts.run_ide_article_batch import dispatch, receive


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--content')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    directory = ROOT / 'worker-control/article-reruns/RERUN-20261016T050248'
    progress = directory / 'official-resume.json'
    state = load(progress) if progress.exists() else {'articles': {}, 'status': 'running'}
    lock = directory / 'official-resume.lock'
    with lock.open('x'):
        pass
    try:
        for cid in load(directory / 'execution.json')['content_ids']:
            if args.content and cid != args.content:
                continue
            item = state['articles'].setdefault(cid, {})
            view = snapshot(cid)
            if item.get('status') == 'interpreted' and item.get('draft_sha256') == view['draft_sha256'] and not args.force:
                continue
            if item.get('draft_sha256') != view['draft_sha256']:
                item.clear()
                item['draft_sha256'] = view['draft_sha256']
            run = ROOT / 'content-system/working' / cid / 'runs' / view['run_id']
            if args.force:
                archive = run / 'official-rechecks' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
                for name in ['official-call.json', 'official-request.json', 'official-response.txt', 'official-interpretation.json']:
                    old = run / name
                    if old.exists():
                        archive.mkdir(parents=True, exist_ok=True)
                        (archive / name).write_bytes(old.read_bytes())
                item.clear()
                item['draft_sha256'] = view['draft_sha256']
            audit_path = run / 'official-call.json'
            audit = load(audit_path) if audit_path.exists() else {}
            reusable = (not args.force and audit.get('status') == 'response_received' and
                        audit.get('draft_sha256') == view['draft_sha256'] and
                        (run / 'official-response.txt').exists())
            item.update(status='calling' if not reusable else 'response_received')
            save(progress, state)
            if not reusable:
                subprocess.run([sys.executable, '-m', 'scripts.check_logitech_review', '--content', cid], cwd=ROOT, check=True)
                audit = load(audit_path)
                if audit.get('status') != 'response_received':
                    item.update(status='failed', diagnostic=audit.get('diagnostic'))
                    save(progress, state)
                    # A transport failure must not fan out into four more blind calls.
                    break
            record_received(cid, view, run)
            request = load(run / 'official-request.json')
            context = load(directory / (cid + '.context.json'))
            if not item.get('task'):
                item['task'] = dispatch(directory, 'review',
                    '로지텍 응답을 원고·Claim·근거와 대조해 판단하세요. 단순 면책은 중단 사유가 아닙니다. 실제 오류·조건 누락·근거 부족만 지적하세요. 출력 passed, issues, claims. claims에는 모든 Claim의 claim_id, verdict(confirmed/rejected/insufficient_evidence), reason을 넣으세요. 확인되지 않은 주장을 confirmed로 만들지 마세요. 기록·전후 비교·원고 재작성은 하지 마세요.',
                    {**request, 'official_response': (run / 'official-response.txt').read_text(encoding='utf-8')},
                    context.get('guides', {}).get('05-feedback-and-review.md', ''))
            item.update(status='reviewing')
            save(progress, state)
            deadline = time.monotonic() + 1800
            result = None
            while result is None and time.monotonic() < deadline:
                result = receive(item['task'])
                if result is None:
                    time.sleep(5)
            if result is None:
                item.update(status='waiting_review')
                save(progress, state)
                break
            current = snapshot(cid)
            if current['run_id'] != view['run_id'] or current['draft_sha256'] != view['draft_sha256']:
                raise ValueError('Draft changed during official interpretation')
            expected = {c['id'] for c in request['claims']}
            verdicts = result.get('claims', [])
            complete = bool(expected) and len(verdicts) == len(expected) and {v.get('claim_id') for v in verdicts} == expected and all(v.get('verdict') in {'confirmed', 'rejected', 'insufficient_evidence'} for v in verdicts)
            confirmed = complete and all(v['verdict'] == 'confirmed' for v in verdicts) and result.get('passed') is True
            save(run / 'official-interpretation.json', result)
            latest_path = ROOT / 'content-system/working' / cid / 'pipeline-latest.json'
            latest = load(latest_path)
            latest.update(official_review={'status': 'REVIEWED' if complete else 'INCOMPLETE', 'claims': verdicts,
                          'draft_sha256': view['draft_sha256'], 'decision': result,
                          'response_file': str(run / 'official-response.txt'), 'response_sha256': audit['response_sha256']},
                          publish_ready=False, stage='feedback' if not confirmed else 'image_review',
                          stage_detail='공식 검토 통과 · 이미지 승인 별도' if confirmed else '공식 검토 후 수정·근거 보완 필요')
            latest['outcome'] = 'COMPLETED_REVIEW_PENDING' if confirmed else 'REVISION_REQUIRED'
            save(latest_path, latest)
            save(run / 'run-result.json', latest)
            item.update(status='interpreted', complete=complete, confirmed=confirmed, issue_count=len(result.get('issues', [])), completed_at=datetime.now(timezone.utc).isoformat())
            save(progress, state)
            subprocess.run([sys.executable, '-m', 'scripts.sync_taiga', '--sync'], cwd=ROOT, check=False)
        state['status'] = 'finished' if all(a.get('status') == 'interpreted' for a in state['articles'].values()) and len(state['articles']) == 5 else 'paused'
        save(progress, state)
    finally:
        lock.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
