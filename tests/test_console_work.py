import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch, Mock
from services.ide_worker_bridge import save
from services.console_work import artifacts, start


class ConsoleWorkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        registry = self.root / 'content-system/registry/CONTENT_REGISTRY.csv'
        registry.parent.mkdir(parents=True)
        registry.write_text('content_id,title\nCNT-TEST,테스트\n', encoding='utf-8')
        self.work = self.root / 'content-system/working/CNT-TEST'
        self.run = self.work / 'runs/RERUN-20261016T050248'
        save(self.work / 'pipeline-latest.json', {'run_id': self.run.name, 'draft_file': str(self.run / 'draft.md'), 'draft_sha256': 'abc'})
        self.run.mkdir(parents=True)
        (self.run / 'draft.md').write_text('원고', encoding='utf-8')
        self.data = {'request_id': str(uuid.uuid4()), 'action': 'review', 'run_id': self.run.name, 'draft_sha256': 'abc'}

    def test_artifacts_are_content_scoped_and_keep_revision_history(self):
        save(self.run / 'official-corrections/round-1/review.json', {'passed': False})
        save(self.root / 'config/secret.json', {'token': 'private'})
        rows = artifacts('CNT-TEST', root=self.root)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({r['id'] for r in rows}), 2)
        self.assertTrue(all('config' not in r['path'] for r in rows))
        with self.assertRaises(ValueError):
            artifacts('CNT-OTHER', root=self.root)
        with self.assertRaises(ValueError):
            artifacts('CNT-TEST', '../config', root=self.root)

    @patch('services.console_work.subprocess.Popen')
    def test_action_is_fixed_ide_command_and_idempotent(self, popen):
        popen.return_value = Mock(pid=1234)
        first = start('CNT-TEST', self.data, self.root)
        second = start('CNT-TEST', self.data, self.root)
        self.assertEqual(first['id'], second['id'])
        popen.assert_called_once()
        self.assertEqual(popen.call_args.args[0][3:5], ['scripts.run_console_action', '--job'])
        self.assertEqual(first['execution_type'], 'ide')

    @patch('services.console_work.subprocess.Popen')
    def test_stale_duplicate_and_active_pipeline_are_rejected(self, popen):
        with self.assertRaises(ValueError):
            start('CNT-TEST', {**self.data, 'draft_sha256': 'old'}, self.root)
        batch = self.root / 'worker-control/article-reruns' / self.run.name
        batch.mkdir(parents=True)
        (batch / 'official-corrections.lock').write_text('')
        with self.assertRaises(ValueError):
            start('CNT-TEST', self.data, self.root)
        popen.assert_not_called()


if __name__ == '__main__':
    unittest.main()
