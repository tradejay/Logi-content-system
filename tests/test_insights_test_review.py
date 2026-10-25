import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from services.blog_performance.insights.test_review import queue_test_review


def test_failed_run_queues_exact_snapshot_once():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name in ('code.py', 'services/blog_performance/insights/test_runner.py', 'services/blog_performance/insights/test_review.py'):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('original = True', encoding='utf-8')
        control = root / 'worker-control'
        control.mkdir()
        (control / 'CODE-REVIEW-GUIDE.md').write_text('guide', encoding='utf-8')
        (control / 'INSIGHTS-REVIEW-CONTEXT.json').write_text(json.dumps({'source_files': ['code.py']}), encoding='utf-8')
        evidence = root / 'verification-test'
        evidence.mkdir()
        (evidence / 'results.json').write_text(json.dumps({'summary': {'failed': 1}, 'tests': [{'nodeid': 'test_failure', 'outcome': 'failed'}]}), encoding='utf-8')
        pkg = {'title': 'review', 'target_scope': 'system', 'diff': 'unrelated diff', 'changed_files': [], 'test_stats': {}}
        with patch('services.review_app.auto_reviewer.package_completed_task', return_value=pkg):
            first = queue_test_review(evidence, 1, root)
            second = queue_test_review(evidence, 1, root)
        assert first['created'] and not second['created']
        assert first['job_id'] == second['job_id']
        (root / 'code.py').write_text('changed = True', encoding='utf-8')
        assert (evidence / 'source/code.py').read_text() == 'original = True'
        summary = json.loads((evidence / 'review-summary.json').read_text())
        assert summary['returncode'] == 1
        assert summary['failures'][0]['test_id'] == 'test_failure'


def test_missing_test_record_is_not_queued():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        with patch('services.review_app.auto_reviewer.enqueue_auto_review') as enqueue:
            try:
                queue_test_review(root, 2, root)
            except FileNotFoundError:
                pass
            else:
                raise AssertionError('Missing evidence must be rejected')
            enqueue.assert_not_called()
