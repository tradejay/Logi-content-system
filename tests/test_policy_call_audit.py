import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch, Mock

from services.policy_call_audit import prepare_call, verify_receipt
from services.pipeline_provider import ModelProvider


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.context = {'rules': [{'id': 'RULE-LONG', 'body': '원문 조건 그대로', 'severity': 'blocking'}],
                        'guides': {'GUIDE-LONG': '가이드 원문'}}
        self.context['cautions'] = self.context['rules']
        self.instruction, self.payload, self.ledger = prepare_call(
            'write', '작성하라', self.context, 'call1', 'rel1', 'write.md', 'hash')

    def response(self):
        return {'receipt': self.payload['policy_receipt'], 'result': {'markdown': '본문'}}

    def test_lossless_body_and_no_mutation(self):
        self.assertNotIn('cautions', self.payload)
        self.assertEqual(self.payload['rules'][0]['body'], self.context['rules'][0]['body'])
        self.assertEqual(self.payload['guides']['G01'], '가이드 원문')
        self.assertEqual(self.context['rules'][0]['id'], 'RULE-LONG')
        self.assertEqual(self.ledger['entries'][1]['id'], 'RULE-LONG')

    def test_receipt_is_not_compliance(self):
        checked = verify_receipt(self.response(), self.ledger)
        self.assertEqual(checked['receipt_status'], 'verified')
        self.assertEqual(checked['compliance_status'], 'not_evaluated')

    def test_missing_unknown_duplicate_and_invalid_ids(self):
        for ids in (['P01'], ['P01', 'R01', 'G01', 'X01'], ['P01', 'R01', 'G01', 'G01'], 'P01', [None], None):
            with self.subTest(ids=ids):
                response = self.response()
                response['receipt'] = {'bundle': self.ledger['bundle'], 'ids': ids}
                self.assertEqual(verify_receipt(response, self.ledger)['receipt_status'], 'failed')

    def test_cross_call_and_legacy_result_rejected(self):
        _, payload, _ = prepare_call('write', '작성하라', self.context, 'call2', 'rel1', 'write.md', 'hash')
        self.assertNotEqual(payload['policy_receipt']['bundle'], self.ledger['bundle'])
        self.assertEqual(verify_receipt({'receipt': payload['policy_receipt'], 'result': {}}, self.ledger)['receipt_status'], 'failed')
        self.assertEqual(verify_receipt({'markdown': '본문'}, self.ledger)['receipt_status'], 'failed')

    def test_distinct_cautions_kept(self):
        self.context['cautions'] = [{'id': 'RULE-OTHER', 'body': '별도 제약'}]
        _, payload, ledger = prepare_call('write', '작성', self.context, 'call1', 'rel1', 'write.md', 'hash')
        self.assertEqual(payload['cautions'][0]['body'], '별도 제약')
        self.assertEqual(ledger['entries'][-1]['alias'], 'C01')


class TokenTests(unittest.TestCase):
    def test_stage_output_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider = ModelProvider(Path(tmp))
            self.assertEqual(provider.generation_config('write', 'test')['maxOutputTokens'], 8192)
            self.assertEqual(provider.generation_config('feedback', 'test')['maxOutputTokens'], 4096)
            provider.config['pipeline_output_token_budgets'] = {'write': 12000}
            self.assertEqual(provider.generation_config('write', 'test')['maxOutputTokens'], 12000)
            provider.config['pipeline_output_token_budgets'] = {'write': True}
            with self.assertRaises(ValueError):
                provider.generation_config('write', 'test')

    def test_output_exhaustion_never_becomes_success(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ', {'GEMINI_API_KEY': 'test', 'GEMINI_MODEL': 'test-model'}):
            provider = ModelProvider(Path(tmp))
            reply = Mock(status_code=200)
            reply.json.return_value = {'candidates': [{'finishReason': 'MAX_TOKENS', 'content': {'parts': [{'text': '{}'}]}}], 'usageMetadata': {'candidatesTokenCount': 4096}}
            with patch('requests.post', return_value=reply):
                with self.assertRaises(RuntimeError):
                    provider.complete('feedback', '지시', {})
                self.assertEqual(provider.last_metadata['finish_reason'], 'MAX_TOKENS')

    def test_counter_uses_exact_generation_body_with_system_instruction(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ', {'GEMINI_API_KEY': 'test', 'GEMINI_MODEL': 'test-model'}):
            provider = ModelProvider(Path(tmp))
            reply = Mock(status_code=200)
            reply.json.return_value = {'totalTokens': 2345}
            with patch('requests.post', return_value=reply) as post:
                self.assertEqual(provider.count_tokens('write', '지시', {'한글': '자료'}), 2345)
                counted = post.call_args.kwargs['json']['generateContentRequest']
                self.assertEqual(counted, {'model': 'models/test-model', **provider.request_body('write', '지시', {'한글': '자료'}, 'test-model')})
                self.assertIn('지시', json.dumps(counted, ensure_ascii=False))
                for invalid in (None, True, '2345', -1):
                    reply.json.return_value = {'totalTokens': invalid}
                    with self.assertRaises(ValueError):
                        provider.count_tokens('write', '지시', {})
                reply.status_code = 400
                with self.assertRaises(RuntimeError):
                    provider.count_tokens('write', '지시', {})


if __name__ == '__main__':
    unittest.main()
