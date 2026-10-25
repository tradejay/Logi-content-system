import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from services.pipeline_status import (
    calculate_effective_status,
    get_aggregated_status_counts,
    read_pipeline_lock,
    check_process_liveness
)
from services.pipeline_context import digest


class TestPipelineStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'content-system/working/CNT-TEST-001').mkdir(parents=True, exist_ok=True)
        (self.root / 'content-system/02_writer_ai/drafts').mkdir(parents=True, exist_ok=True)
        (self.root / 'content-system/registry').mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_published_status_preserved(self):
        cid = 'CNT-TEST-001'
        reg_row = {'content_id': cid, 'status': 'PUBLISHED'}
        res = calculate_effective_status(self.root, cid, registry_row=reg_row)
        self.assertEqual(res['effective_status'], 'PUBLISHED')
        self.assertTrue(res['publish_ready'])

    def test_archived_cancelled_status_preserved(self):
        cid = 'CNT-TEST-001'
        reg_row = {'content_id': cid, 'status': 'CANCELLED'}
        res = calculate_effective_status(self.root, cid, registry_row=reg_row)
        self.assertEqual(res['effective_status'], 'CANCELLED')
        self.assertFalse(res['publish_ready'])

    def test_active_lock_running(self):
        cid = 'CNT-TEST-001'
        lock_path = self.root / f'content-system/working/{cid}/pipeline.lock'
        import psutil
        cur_proc = psutil.Process()
        lock_data = {
            'content_id': cid,
            'run_id': 'run-1',
            'pid': os.getpid(),
            'process_create_time': cur_proc.create_time(),
            'status': 'RUNNING',
            'stage': 'feedback'
        }
        lock_path.write_text(json.dumps(lock_data), encoding='utf-8')

        res = calculate_effective_status(self.root, cid)
        self.assertEqual(res['effective_status'], 'RUNNING')
        self.assertFalse(res['publish_ready'])
        self.assertTrue(res['is_locked'])

    def test_dead_lock_interrupted(self):
        cid = 'CNT-TEST-001'
        lock_path = self.root / f'content-system/working/{cid}/pipeline.lock'
        lock_data = {
            'content_id': cid,
            'run_id': 'run-dead',
            'pid': 99999999,  # 존재하지 않는 PID
            'status': 'RUNNING',
            'stage': 'write'
        }
        lock_path.write_text(json.dumps(lock_data), encoding='utf-8')

        res = calculate_effective_status(self.root, cid)
        self.assertEqual(res['effective_status'], 'INTERRUPTED')
        self.assertTrue(res['is_interrupted'])
        self.assertFalse(res['publish_ready'])

    def test_running_outcome_without_lock_interrupted(self):
        cid = 'CNT-TEST-001'
        latest = {
            'run_id': 'run-2',
            'outcome': 'RUNNING',
            'stage': 'write'
        }
        res = calculate_effective_status(self.root, cid, latest_run=latest)
        self.assertEqual(res['effective_status'], 'INTERRUPTED')
        self.assertTrue(res['is_interrupted'])

    def test_revision_required_not_ready(self):
        cid = 'CNT-TEST-001'
        latest = {
            'run_id': 'run-rev',
            'outcome': 'REVISION_REQUIRED',
            'publish_ready': False,
            'admin_checks': [{'kind': 'qa', 'detail': '근거 부족'}]
        }
        res = calculate_effective_status(self.root, cid, latest_run=latest)
        self.assertEqual(res['effective_status'], 'REVISION_REQUIRED')
        self.assertFalse(res['publish_ready'])

    def test_completed_review_pending_not_ready(self):
        cid = 'CNT-TEST-001'
        latest = {
            'run_id': 'run-rev-pen',
            'outcome': 'COMPLETED_REVIEW_PENDING',
            'publish_ready': False,
            'admin_checks': [{'kind': 'asset', 'need_id': 'banner'}]
        }
        res = calculate_effective_status(self.root, cid, latest_run=latest)
        self.assertEqual(res['effective_status'], 'COMPLETED_REVIEW_PENDING')
        self.assertFalse(res['publish_ready'])

    def test_completed_ready_with_draft_change_downgraded(self):
        cid = 'CNT-TEST-001'
        draft_file = self.root / f'content-system/02_writer_ai/drafts/{cid}.draft.md'
        draft_file.write_text('새로 수정된 원고', encoding='utf-8')
        old_hash = digest('과거 승인 원고')
        latest = {
            'run_id': 'run-ready',
            'outcome': 'COMPLETED_READY',
            'publish_ready': True,
            'draft_sha256': old_hash,
            'admin_checks': []
        }
        res = calculate_effective_status(self.root, cid, latest_run=latest)
        self.assertEqual(res['effective_status'], 'REVISION_REQUIRED')
        self.assertTrue(res['draft_changed'])
        self.assertFalse(res['publish_ready'])

    def test_completed_ready_valid(self):
        cid = 'CNT-TEST-001'
        text = '완벽히 일치하는 원고'
        draft_file = self.root / f'content-system/02_writer_ai/drafts/{cid}.draft.md'
        draft_file.write_text(text, encoding='utf-8')
        latest = {
            'run_id': 'run-ready-valid',
            'outcome': 'COMPLETED_READY',
            'publish_ready': True,
            'draft_sha256': digest(text),
            'admin_checks': []
        }
        res = calculate_effective_status(self.root, cid, latest_run=latest)
        self.assertEqual(res['effective_status'], 'READY_TO_PUBLISH')
        self.assertTrue(res['publish_ready'])
        self.assertTrue(res['qa_passed'])

    def test_aggregated_status_counts(self):
        # CSV 레지스트리 작성
        reg_file = self.root / 'content-system/registry/CONTENT_REGISTRY.csv'
        reg_content = (
            "content_id,status,title\n"
            "CNT-TEST-001,REVISION_REQUIRED,글1\n"
            "CNT-TEST-002,PUBLISHED,글2\n"
            "CNT-TEST-003,PLANNING,글3\n"
        )
        reg_file.write_text(reg_content, encoding='utf-8-sig')

        # CNT-TEST-001: REVISION_REQUIRED latest
        latest_path1 = self.root / 'content-system/working/CNT-TEST-001/pipeline-latest.json'
        latest_path1.write_text(json.dumps({'run_id': 'r1', 'outcome': 'REVISION_REQUIRED'}), encoding='utf-8')

        counts = get_aggregated_status_counts(self.root)
        self.assertEqual(counts['REVISION_REQUIRED'], 1)
        self.assertEqual(counts['PUBLISHED'], 1)
        self.assertEqual(counts['PLANNING'], 1)
        self.assertEqual(counts['READY_TO_PUBLISH'], 0)


    def test_approved_ready_with_admin_checks_and_approval_is_ready_to_publish(self):
        cid = 'CNT-TEST-001'
        text = '승인 완료된 원고'
        draft_file = self.root / f'content-system/02_writer_ai/drafts/{cid}.draft.md'
        draft_file.write_text(text, encoding='utf-8')
        latest = {
            'run_id': 'run-approved',
            'outcome': 'COMPLETED_READY',
            'publish_ready': True,
            'draft_sha256': digest(text),
            'admin_checks': [{'kind': 'asset', 'need_id': 'banner'}],  # admin_checks가 남아있음
            'approval': {
                'reviewer': 'ADMIN',
                'draft_sha256': digest(text),
                'at': '2026-10-01T00:00:00Z',
                'resolutions': ['승인 처리 완료']
            }
        }
        res = calculate_effective_status(self.root, cid, latest_run=latest)
        self.assertEqual(res['effective_status'], 'READY_TO_PUBLISH')
        self.assertTrue(res['publish_ready'])

    def test_access_denied_returns_unknown(self):
        import psutil
        with patch('psutil.pid_exists', return_value=True):
            with patch('psutil.Process', side_effect=psutil.AccessDenied()):
                res = check_process_liveness({'pid': 1234, 'process_create_time': 100.0})
                self.assertEqual(res, 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()
