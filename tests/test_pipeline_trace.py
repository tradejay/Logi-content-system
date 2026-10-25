import unittest
import test_content_pipeline as fixtures
from services.pipeline_trace import read_trace, redact


class TraceTests(unittest.TestCase):
    setUp = fixtures.PipelineTests.setUp
    tearDown = fixtures.PipelineTests.tearDown
    run_pipeline = fixtures.PipelineTests.run_pipeline

    def test_actual_payloads_and_responses_are_separate(self):
        result = self.run_pipeline()
        trace = read_trace('CNT-test', self.root)
        self.assertEqual(trace['run_id'], result['run_id'])
        rows = [e for e in trace['entries'] if e['stage'] == '원고 작성 r1']
        self.assertEqual({e['kind'] for e in rows}, {'facts', 'instruction', 'response'})
        sent = next(e for e in rows if e['kind'] == 'facts')
        self.assertEqual(sent['content']['facts'][0]['id'], 'F1')
        receipt = next(e for e in trace['entries'] if e['source'].replace('\\', '/') == 'rule-audit/r1.write.json')
        self.assertEqual(receipt['content']['receipt_status'], 'verified')
        self.assertIn('별도 검토', receipt['natural_summary']['summary'])
        self.assertTrue(read_trace('CNT-test', self.root, trace['signature'])['unchanged'])

    def test_empty_run_and_credentials(self):
        self.assertEqual(read_trace('CNT-test', self.root)['entries'], [])
        self.assertEqual(redact({'api_key': 'private'})['api_key'], '[인증정보 숨김]')
        with self.assertRaises(ValueError): read_trace('../escape', self.root)
