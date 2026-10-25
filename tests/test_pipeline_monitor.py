import json
from pathlib import Path
import tempfile
import unittest

from services.pipeline_monitor import read_monitor


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.work = self.root / 'content-system/working/CNT-test'
        self.run = self.work / 'runs/run-1'
        self.run.mkdir(parents=True)
        self.put(self.work / 'pipeline-latest.json', {'run_id': 'run-1', 'outcome': 'FAILED',
                  'created_at': '2026-10-08T07:00:00+00:00', 'updated_at': '2026-10-08T07:01:00+00:00'})

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding='utf-8')

    def test_failed_run_does_not_show_prior_article(self):
        self.put(self.run / 'brief.json', {'brief': {'topic': 'Topic', 'search': {'primary_keyword': 'Keyword'}}})
        old = self.work / 'runs/old/revisions'
        old.mkdir(parents=True)
        (old / 'r1.draft.md').write_text('Prior article', encoding='utf-8')
        data = read_monitor(self.root, 'CNT-test')
        self.assertEqual(data['markdown'], '')
        self.assertEqual(data['elapsed_seconds'], 60)
        self.assertFalse(data['publish_ready'])
        self.assertEqual(data['keyword'], 'Keyword')

    def test_numeric_revision_and_usage_accounting(self):
        revisions = self.run / 'revisions'
        revisions.mkdir()
        (revisions / 'r2.draft.md').write_text('second', encoding='utf-8')
        (revisions / 'r10.draft.md').write_text('tenth', encoding='utf-8')
        self.put(self.run / 'context-metrics/r1.write.json', {'stage': 'write', 'input_tokens': 52000,
                 'within_token_budget': False, 'input_token_budget': 50000})
        self.put(self.run / 'context-metrics/r1.feedback.json', {'stage': 'feedback', 'input_tokens': 100,
                 'usage_metadata': {'promptTokenCount': 100, 'candidatesTokenCount': 20, 'totalTokenCount': 120}})
        self.put(self.run / 'web-research.json', {'cache_hit': True, 'usage_metadata': {'promptTokenCount': 400, 'totalTokenCount': 500}})
        data = read_monitor(self.root, 'CNT-test')
        self.assertEqual(data['markdown'], 'tenth')
        self.assertEqual(data['totals']['input_tokens'], 52100)
        self.assertEqual(data['totals']['provider_total_tokens'], 120)
        self.assertEqual(data['totals']['provider_input_tokens'], 100)
        self.assertEqual(data['totals']['unmeasured_input_calls'], 0)

    def test_paths_are_scoped(self):
        with self.assertRaises(ValueError):
            read_monitor(self.root, '../secret')
        with self.assertRaises(ValueError):
            read_monitor(self.root, 'CNT-test', '../../secret')
        with self.assertRaises(FileNotFoundError):
            read_monitor(self.root, 'CNT-test', 'absent')

    def test_text_usage_in_failed_logs_does_not_break_console(self):
        self.put(self.run / 'context-metrics/strategy.json', {'stage': 'strategy',
                 'usage_metadata': 'provider error: usage unavailable'})
        self.put(self.run / 'context-metrics/write.json', {'stage': 'write',
                 'usage_metadata': '{"promptTokenCount":100,"totalTokenCount":120}'})
        self.put(self.run / 'web-research.json', {'usage_metadata': 'unavailable'})
        data = read_monitor(self.root, 'CNT-test')
        self.assertEqual(data['outcome'], 'FAILED')
        self.assertEqual(len(data['calls']), 3)
        self.assertEqual(data['totals']['provider_total_tokens'], 120)
        self.assertIsNone(next(c for c in data['calls'] if c['call'] == 'strategy')['output_tokens'])


if __name__ == '__main__':
    unittest.main()
