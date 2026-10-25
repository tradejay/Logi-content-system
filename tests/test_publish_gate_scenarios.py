"""Isolated command-level checks for one representative article; no model calls."""
import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.content_pipeline import ContentPipeline, atomic
from services.pipeline_context import digest


SCRIPT = Path(__file__).resolve().parents[1] / 'content-system/scripts/change_status.py'
spec = importlib.util.spec_from_file_location('publish_gate_change_status', SCRIPT)
change_status = importlib.util.module_from_spec(spec)
spec.loader.exec_module(change_status)


class PublishGateScenarios(unittest.TestCase):
    def setUp(self):
        workspace_tmp = Path(__file__).resolve().parents[1] / '.test-tmp'
        workspace_tmp.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=workspace_tmp)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cid = 'CNT-GATE-TEST'
        self.pipeline = ContentPipeline(self.root)
        self.draft = self.pipeline.draft_path(self.cid)
        self.draft.parent.mkdir(parents=True)
        self.draft.write_text('검증용 원고: 기능은 공식 근거 확인 후 기술합니다.', encoding='utf-8')
        sha = digest(self.draft.read_text(encoding='utf-8'))
        self.latest = {
            'run_id': 'run-fixture-1', 'outcome': 'COMPLETED_READY', 'publish_ready': True,
            'draft_sha256': sha, 'qa': {'passed': True},
            'official_review': {'status': 'REVIEWED', 'draft_sha256': sha,
                                'claims': [{'id': 'claim-1', 'verdict': 'confirmed'}]},
            'admin_checks': ['근거 확인'],
            'approval': {'reviewer': 'test-reviewer', 'draft_sha256': sha, 'resolutions': ['확인 완료']},
        }
        self.latest_path = self.pipeline.work(self.cid) / 'pipeline-latest.json'
        system = self.root / 'content-system'
        self.registry = system / 'registry/CONTENT_REGISTRY.csv'
        self.registry.parent.mkdir(parents=True)
        with self.registry.open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['content_id', 'status', 'last_reviewed'])
            writer.writeheader()
            writer.writerow({'content_id': self.cid, 'status': 'READY_FOR_QA'})
        self.patchers = [
            patch.object(change_status, 'REGISTRY_FILE', str(self.registry)),
            patch.object(change_status, 'BRIEFS_DIR', str(system / '01_keyword_ai/briefs')),
            patch.object(change_status, 'QUEUE_DIR', str(system / 'queue')),
            patch.object(change_status, 'LOCKS_DIR', str(system / 'locks')),
            patch.object(change_status, 'LOGS_DIR', str(system / 'logs')),
            patch.object(change_status, 'EVENTS_LOG', str(system / 'logs/events.jsonl')),
            patch('services.content_pipeline.ContentPipeline', return_value=self.pipeline),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        (system / 'queue').mkdir(parents=True)

    def attempt(self, expected_allowed, expected_reason=None):
        atomic(self.latest_path, self.latest)
        if expected_allowed:
            self.assertEqual(change_status.execute_status_transaction(self.cid, 'READY_TO_PUBLISH'),
                             ('READY_FOR_QA', 'READY_TO_PUBLISH'))
        else:
            with self.assertRaisesRegex(ValueError, expected_reason):
                change_status.execute_status_transaction(self.cid, 'READY_TO_PUBLISH')
        with self.registry.open(newline='', encoding='utf-8') as f:
            row = next(csv.DictReader(f))
        self.assertEqual(row['status'], 'READY_TO_PUBLISH' if expected_allowed else 'READY_FOR_QA')
        decisions = [json.loads(line) for line in
                     (self.pipeline.work(self.cid) / 'publish-gate.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(decisions[-1]['allowed'], expected_allowed)
        self.assertTrue(decisions[-1]['reason'])

    def test_valid_review_and_approval_allows_command(self):
        self.attempt(True)

    def test_review_server_failure_blocks_command(self):
        self.latest.update(outcome='FAILED', publish_ready=False, error='review transport unavailable')
        self.latest['official_review'] = {'status': 'ERROR', 'claims': []}
        self.attempt(False, 'not approved')

    def test_empty_or_malformed_review_blocks_command(self):
        for review in ({'status': 'REVIEWED', 'claims': []}, {'status': 'REVIEWED', 'claims': 'bad'}):
            self.latest['official_review'] = review
            self.attempt(False, 'Official review')

    def test_unresolved_review_item_blocks_command(self):
        self.latest['approval']['resolutions'] = []
        self.attempt(False, 'Admin review items')

    def test_draft_changed_after_review_blocks_command(self):
        self.draft.write_text('검수 후 변경된 원고', encoding='utf-8')
        self.attempt(False, 'rerun review')


if __name__ == '__main__':
    unittest.main()
