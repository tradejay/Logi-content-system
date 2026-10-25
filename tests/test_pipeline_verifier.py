import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import tests.test_content_pipeline as harness
from services.content_pipeline import atomic
from services.pipeline_verifier import verify_pipeline


class WholePipelineVerificationTests(unittest.TestCase):
    def setUp(self):
        harness.PipelineTests.setUp(self)

    def tearDown(self):
        harness.PipelineTests.tearDown(self)

    def run_pipeline(self):
        result = self.pipeline.run('CNT-test', max_revisions=2)
        return Path(result['run_directory'])

    def reseal(self, run):
        """Isolate semantic/link checks from independent artifact hash checks."""
        path = run / 'execution-contract.json'
        contract = json.loads(path.read_text(encoding='utf-8'))
        contract['artifacts'] = {str(p.relative_to(run)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in run.rglob('*') if p.is_file() and p.name != 'execution-contract.json'}
        atomic(path, contract)

    def trusted_run(self, mode='related_articles', failure=False):
        atomic(self.root / 'config/config.json', {'pipeline_web_research_enabled': True})
        original = self.provider.complete
        def select(stage, instruction, context):
            if stage == 'planning_research':
                if failure:
                    raise RuntimeError('offline test failure')
                result = {'mode': mode, 'reason': 'relatedness',
                          'article_source_ids': ['A'] if mode == 'related_articles' else [],
                          'points': [{'segment_id': context['segments'][0]['id'], 'use': 'criteria', 'notes': 'Check layout'}]}
                return json.dumps({'receipt': context['policy_receipt'], 'result': result})
            return original(stage, instruction, context)
        self.provider.complete = select
        research = {'status': 'trusted', 'source_policy': {'id': 'SYS-WEB-SOURCE-TRUST-003'},
                    'observed_query_count': 1, 'cache_hit': False,
                    'results': [{'document_id': 'A', 'title': 'Room planning', 'source_location': 'https://avixa.org/guide',
                                 'trust_policy_id': 'SYS-WEB-SOURCE-TRUST-003', 'trust_score': 1.0, 'grounding_chunk_indices': [0]}],
                    'trusted_segments': [{'text': 'Check the seating layout', 'source_ids': ['A']}],
                    'grounding_metadata': {'groundingSupports': [{'segment': {'text': 'Check the seating layout'}, 'groundingChunkIndices': [0]}]}}
        from services.web_research import INSTRUCTION
        research.update(request={'instruction': INSTRUCTION, 'query': 'Room layout', 'model': 'test-model'},
                        request_sha256=hashlib.sha256(('test-model' + INSTRUCTION + 'Room layout').encode()).hexdigest(),
                        finish_reason='STOP', search_queries=['site:avixa.org Room layout'])
        with patch('services.web_research.research_for_brief', return_value=research):
            return self.run_pipeline()

    def test_full_run_passes(self):
        report = verify_pipeline(self.run_pipeline())
        self.assertTrue(report['pipeline_complete'], report)
        self.assertEqual(report['semantic_compliance'], 'not_evaluated')

    def test_related_article_full_run_passes(self):
        report = verify_pipeline(self.trusted_run())
        self.assertTrue(report['pipeline_complete'], report)

    def test_fact_fallback_full_run_passes(self):
        report = verify_pipeline(self.trusted_run('fact_fallback'))
        self.assertTrue(report['pipeline_complete'], report)

    def test_optional_selection_failure_is_visible_and_does_not_fake_success(self):
        report = verify_pipeline(self.trusted_run(failure=True))
        self.assertTrue(report['valid'], report)
        self.assertEqual(report['status'], 'PASS_WITH_WARNINGS')
        self.assertTrue(report['warnings'])

    def test_invalid_selection_output_is_recorded_as_fallback(self):
        run = self.trusted_run('unknown_mode')
        report = verify_pipeline(run)
        self.assertTrue(report['pipeline_complete'], report)
        self.assertTrue(report['warnings'])

    def test_resume_official_passes_with_lineage(self):
        self.run_pipeline()
        result = self.pipeline.run('CNT-test', start_stage='official')
        report = verify_pipeline(result['run_directory'])
        self.assertTrue(report['pipeline_complete'], report)

    def test_web_reference_resume_preserves_provenance(self):
        self.trusted_run()
        result = self.pipeline.run('CNT-test', start_stage='write')
        report = verify_pipeline(result['run_directory'])
        self.assertTrue(report['pipeline_complete'], report)

    def test_reordered_calls_fail(self):
        run = self.run_pipeline()
        path = run / 'execution-contract.json'
        contract = json.loads(path.read_text(encoding='utf-8'))
        contract['calls'][0], contract['calls'][1] = contract['calls'][1], contract['calls'][0]
        atomic(path, contract)
        self.assertFalse(verify_pipeline(run)['valid'])

    def test_prepare_only_is_not_complete(self):
        result = self.pipeline.run('CNT-test', prepare_only=True)
        report = verify_pipeline(result['run_directory'])
        self.assertTrue(report['valid'], report)
        self.assertFalse(report['pipeline_complete'])

    def test_missing_call_artifact_fails(self):
        run = self.run_pipeline()
        (run / 'responses/strategy.json').unlink()
        self.assertFalse(verify_pipeline(run)['valid'])

    def test_tampered_draft_fails(self):
        run = self.run_pipeline()
        (run / 'revisions/r1.draft.md').write_text('changed draft', encoding='utf-8')
        self.assertFalse(verify_pipeline(run)['valid'])

    def test_forged_grounding_fails_even_if_file_hash_updated(self):
        run = self.trusted_run()
        path = run / 'web-research.json'
        research = json.loads(path.read_text(encoding='utf-8'))
        research['grounding_metadata']['groundingSupports'][0]['segment']['text'] = 'Different citation'
        atomic(path, research)
        self.reseal(run)
        report = verify_pipeline(run)
        self.assertTrue(any('grounding_provenance_mismatch' in f['detail'] for f in report['findings']), report)

    def test_dropped_stage_does_not_pass(self):
        run = self.run_pipeline()
        path = run / 'execution-contract.json'
        contract = json.loads(path.read_text(encoding='utf-8'))
        contract['calls'] = [c for c in contract['calls'] if c['stage'] != 'feedback']
        atomic(path, contract)
        self.assertFalse(verify_pipeline(run)['valid'])

    def test_completed_with_failed_official_does_not_pass(self):
        run = self.run_pipeline()
        path = run / 'reviews/r1.official.json'
        review = json.loads(path.read_text(encoding='utf-8'))
        review['claims'][0]['verdict'] = 'contradicted'
        atomic(path, review)
        self.reseal(run)
        report = verify_pipeline(run)
        self.assertTrue(any('unconfirmed_claim' in f['detail'] for f in report['findings']), report)

    def test_rejected_first_draft_then_repaired_is_reported_as_warning(self):
        original = self.provider.complete
        seen = {'write': 0}
        def complete(stage, instruction, context):
            raw = original(stage, instruction, context)
            if stage == 'write':
                seen['write'] += 1
                if seen['write'] == 1:
                    envelope = json.loads(raw)
                    value = envelope['result']
                    value['blocks'][0]['markdown'] = '수정이 필요한 원고'
                    value['markdown'] = '\n\n'.join(b['markdown'] for b in value['blocks'])
                    return json.dumps(envelope, ensure_ascii=False)
            return raw
        self.provider.complete = complete
        report = verify_pipeline(self.run_pipeline())
        self.assertTrue(report['pipeline_complete'], report)
        self.assertEqual(report['status'], 'PASS_WITH_WARNINGS')

    def test_legacy_logs_are_not_passed_as_complete(self):
        run = self.run_pipeline()
        (run / 'execution-contract.json').unlink()
        self.assertEqual(verify_pipeline(run)['status'], 'UNSUPPORTED')
