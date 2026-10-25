import json
from pathlib import Path
import tempfile
from unittest.mock import patch
from unittest.mock import Mock

import pytest

from services.review_app.auto_reviewer import scan_and_enqueue_completed_tasks
from scripts import review_diff
from services.review_app.connector import ReviewAppConnector


def test_scan_baselines_old_tasks_then_enqueues_new_completion():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        folder = root / 'worker-control/dispatch/tasks'
        folder.mkdir(parents=True)
        (folder / 'TASK-OLD.json').write_text(json.dumps({'task_id': 'TASK-OLD', 'worker': 'system'}))
        assert scan_and_enqueue_completed_tasks(root) == []
        (folder / 'TASK-NEW.json').write_text(json.dumps({'task_id': 'TASK-NEW', 'worker': 'system'}))
        with patch('services.worker_dispatch.status', return_value={'status': 'collected'}), patch(
            'services.review_app.auto_reviewer.enqueue_auto_review', return_value=({}, True)
        ) as enqueue:
            assert scan_and_enqueue_completed_tasks(root) == ['TASK-NEW']
            enqueue.assert_called_once_with('TASK-NEW', root=root)


def test_diff_only_fetches_patches_for_eligible_paths():
    calls = []

    def git(args):
        calls.append(args)
        if '--name-only' in args:
            return 'services/review_app/server.py\nconfig/local.secrets.json'
        return '+safe line'

    with patch.object(review_diff, 'run_git', side_effect=git):
        diff, files, skipped = review_diff.get_diff()
    assert files == ['services/review_app/server.py']
    assert skipped
    assert calls[-1] == ['diff', 'HEAD', '--', 'services/review_app/server.py']
    assert diff == '+safe line'


def test_failed_publication_recovers_without_worker_redispatch():
    with tempfile.TemporaryDirectory() as temp:
        connector = object.__new__(ReviewAppConnector)
        connector.root = Path(temp)
        connector._post = Mock(side_effect=RuntimeError('temporary server error'))
        with pytest.raises(RuntimeError):
            connector.publish_review('T-1', 'Title', '', '', [])
        assert len(list((connector.root / 'data/review-webapp/publish-outbox').glob('*.json'))) == 1
        connector._post = Mock(return_value={'status': 'published'})
        assert connector.recover_pending_publication() is True
        connector._post.assert_called_once()
        assert not list((connector.root / 'data/review-webapp/publish-outbox').glob('*.json'))
