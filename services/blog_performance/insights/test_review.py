"""Package one completed test run for the independent review queue, without AI logging."""
import hashlib
import json
from pathlib import Path


def queue_test_review(evidence_dir: Path, returncode: int, root: Path):
    from services.review_app.auto_reviewer import enqueue_auto_review

    root = root.resolve()
    evidence_dir = evidence_dir.resolve()
    evidence_dir.relative_to(root)
    receipt_path = evidence_dir / 'review-registration.json'
    if receipt_path.exists():
        previous = json.loads(receipt_path.read_text(encoding='utf-8'))
        if previous.get('job_id'):
            return dict(previous, created=False)
    result = json.loads((evidence_dir / 'results.json').read_text(encoding='utf-8'))
    manifest = json.loads((root / 'worker-control/INSIGHTS-REVIEW-CONTEXT.json').read_text(encoding='utf-8'))
    sources = list(dict.fromkeys(manifest['source_files'] + [
        'services/blog_performance/insights/test_runner.py',
        'services/blog_performance/insights/test_review.py',
    ]))
    snapshots, source_map = [], []
    for name in sources:
        path = (root / name).resolve()
        path.relative_to(root)
        data = path.read_bytes()
        target = evidence_dir / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        snapshots.append(target.relative_to(root).as_posix())
        source_map.append({'source': name, 'sha256': hashlib.sha256(data).hexdigest()})
    coverage_file = evidence_dir / 'coverage.json'
    coverage = json.loads(coverage_file.read_text(encoding='utf-8')).get('totals', {}) if coverage_file.exists() else {}
    summary = {
        'returncode': returncode, 'summary': result.get('summary', {}),
        'duration': result.get('duration'),
        'failures': [{'test_id': t.get('nodeid'), 'outcome': t.get('outcome')} for t in result.get('tests', []) if t.get('outcome') != 'passed'],
        'coverage': coverage, 'source_map': source_map,
        'report': (evidence_dir / 'index.html').relative_to(root).as_posix(),
        'scope_note': 'This test run only. Coverage is not AI semantic accuracy. Source snapshots are the review baseline.',
    }
    summary_path = evidence_dir / 'review-summary.json'
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    context = {
        'scope': '보고서 제작 파이프라인 테스트 결과와 고정된 소스 스냅샷 독립 리뷰. 실패 원인·검증 한계·설계 학습을 작성하며 구현이나 운영 실행은 하지 않는다.',
        'source_files': snapshots,
        'evidence_files': [summary_path.relative_to(root).as_posix(), 'worker-control/CODE-REVIEW-GUIDE.md'],
    }
    context_path = evidence_dir / 'review-context.json'
    context_path.write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding='utf-8')
    job, created = enqueue_auto_review(
        'INSIGHTS-' + evidence_dir.name.upper(),
        title='보고서 파이프라인 자동 테스트 리뷰 · ' + evidence_dir.name,
        root=root, context_file=context_path.relative_to(root).as_posix(),
    )
    receipt = {'job_id': job['job_id'], 'status': job['status'], 'created': created}
    (evidence_dir / 'review-registration.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    return receipt
