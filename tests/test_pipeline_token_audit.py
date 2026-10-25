import json
import tempfile
import unittest
from pathlib import Path
from services.pipeline_token_audit import estimate_input, calibration_from_runs, audit_saved_run, text_chars
from scripts.verify_pipeline_tokens import synthetic_snapshot


class TokenAuditTests(unittest.TestCase):
    def test_real_measurement_and_estimate_are_distinct(self):
        row = estimate_input('write', 'instruction', {'facts': []}, budget=50, measured=70)
        self.assertEqual(row['status'], 'MEASURED_OVER_BUDGET')
        self.assertEqual(row['actual_input_tokens'], 70)
        self.assertEqual(row['quality_compliance'], 'not_evaluated')

    def test_fixed_variable_and_duplicate_findings(self):
        ctx = {'guides': {'G': '규칙' * 1000}, 'draft': {'markdown': '본문', 'blocks': [{'markdown': '본문'}]}}
        row = estimate_input('feedback', 'review', ctx)
        self.assertEqual(row['fixed_chars'] + row['variable_chars'], row['total_chars'])
        self.assertEqual(len(row['findings']), 2)
        self.assertLess(row['estimated_range'][0], row['estimated_input_tokens'])
        self.assertGreater(row['estimated_range'][1], row['estimated_input_tokens'])

    def test_calibration_uses_measured_serialized_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'prompts').mkdir(); (root / 'context-metrics').mkdir()
            prompt = {'instruction': 'review', 'context': {'facts': [], 'text': '회의실'}}
            (root / 'prompts/a.json').write_text(json.dumps({'prompt': prompt}), encoding='utf-8')
            metrics = {'stage': 'feedback', 'token_count_status': 'measured', 'input_tokens': 123, 'input_token_budget': 100}
            (root / 'context-metrics/a.json').write_text(json.dumps(metrics), encoding='utf-8')
            calibration = calibration_from_runs([root])
            row = estimate_input('feedback', **prompt, calibration=calibration)
            self.assertEqual(row['estimated_input_tokens'], 123)
            self.assertEqual(audit_saved_run(root)['actual_input_tokens_total'], 123)
            self.assertEqual(calibration['feedback'][0]['chars'], text_chars(**prompt))

    def test_fixture_has_no_artifact_envelopes_or_retry_instruction(self):
        profile = dict(article_chars=5000, blocks=2, claims=2, facts=2, reference_items=2,
                       reference_chars=200, source_chars=500, strategy_chars=100, brief_chars=100)
        seed = {'facts': [{'id': 'F1', 'scope': {'condition': 'preserve'}}], 'sources': {},
                'user_feedback': 'test retry body', 'input_refs': ['long artifact refs']}
        template = {'input_refs': ['long artifact refs'], 'content_blocks': [{'id': 'b', 'role': 'body.explanation'}]}
        value = synthetic_snapshot(seed, profile, template)
        self.assertNotIn('input_refs', value['strategy'])
        self.assertNotIn('user_feedback', value)
        self.assertNotIn('input_refs', value)
        self.assertEqual(value['facts'][0]['scope'], seed['facts'][0]['scope'])

    def test_search_cache_usage_is_not_counted_again(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'web-research.json').write_text(json.dumps({'cache_hit': True, 'usage_metadata': {'promptTokenCount': 999}}), encoding='utf-8')
            report = audit_saved_run(root)
            self.assertEqual(report['actual_input_tokens_total'], 0)
            self.assertEqual(report['calls'][0]['status'], 'CACHE_REUSED')
            (root / 'web-research.json').write_text('{broken', encoding='utf-8')
            self.assertEqual(audit_saved_run(root)['calls'][0]['status'], 'INVALID_LOG')

if __name__ == '__main__':
    unittest.main()
