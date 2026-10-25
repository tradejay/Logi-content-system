import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from services.article_publish_checks import inspect_article
from services.pipeline_provider import ModelProvider


class ExtensionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'config').mkdir()
        (self.root / 'config/config.json').write_text(json.dumps({'gemini_api_keys': ['test-a', 'test-b', 'test-b'],
                   'gemini_api_key_tiers': ['paid', 'free'], 'gemini_model': 'test-model', 'pipeline_input_token_budget': 50000}), encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def test_free_only_excludes_paid_key_and_preserves_original_slot(self):
        with patch.dict('os.environ', {}, clear=True):
            p = ModelProvider(self.root)
            p.config['gemini_key_policy'] = 'free_only'
            self.assertEqual(p.configured_keys(), ['test-b'])
            self.assertEqual(p.key_slot(1), 2)
            self.assertEqual(p.key_tier(1), 'free')

    def test_key_failover_keeps_prompt_and_counts_alternate(self):
        with patch.dict('os.environ', {}, clear=True):
            p = ModelProvider(self.root)
            count_calls, sent = [], []
            def count(stage, instruction, context):
                count_calls.append(p._key_index)
                return 100
            def complete(stage, instruction, context):
                sent.append((p._key_index, instruction, context))
                if p._key_index == 0:
                    raise RuntimeError('Gemini: HTTP 402 at write')
                p.last_metadata = {'usage_metadata': {'promptTokenCount': 100}}
                return 'result'
            count.__name__ = '_count_tokens_once'
            complete.__name__ = '_complete_once'
            p._count_tokens_once = count
            p._complete_once = complete
            p.count_tokens('write', 'same instructions', {'rules': ['same rule']})
            self.assertEqual(p.complete('write', 'same instructions', {'rules': ['same rule']}), 'result')
            self.assertEqual(count_calls, [0, 1])
            self.assertEqual(sent[0][1:], sent[1][1:])
            self.assertEqual(p.last_metadata['key_slot'], 2)
            self.assertEqual(p.last_metadata['key_tier'], 'free')
            self.assertEqual(p.last_metadata['routing_attempts'][0]['key_tier'], 'paid')
            self.assertNotIn('test-a', json.dumps(p.last_metadata))

    def test_generation_failure_does_not_skip_validation_or_budget(self):
        with patch.dict('os.environ', {}, clear=True):
            p = ModelProvider(self.root)
            def count(*args): return 51000
            count.__name__ = '_count_tokens_once'
            p._count_tokens_once = count
            def complete(*args): raise RuntimeError('Gemini: HTTP 402 at write')
            complete.__name__ = '_complete_once'
            p._complete_once = complete
            with self.assertRaises(ValueError): p.complete('write', 'x', {})
            self.assertEqual(p._key_index, 1)

    def test_publish_checker_reports_actionable_items_without_score(self):
        text = '# 카메라 카메라\n\n## 점검\n\n' + ('동일 문단 내용입니다. ' * 10) + '\n\n' + ('동일 문단 내용입니다. ' * 10) + '\n\n{{asset:NEED-1}}'
        report = inspect_article(text, {'search': {'primary_keyword': '카메라'}})
        self.assertIn('PUB-KEYWORD-REPEAT', [i['rule_id'] for i in report['issues']])
        self.assertIn('PUB-DUPLICATE-PARAGRAPH', [i['rule_id'] for i in report['issues']])
        self.assertIn('PUB-ASSET-REVIEW', [i['rule_id'] for i in report['issues']])
        self.assertNotIn('score', report)

    def test_assets_generate_once_stay_candidates_and_do_not_render_product(self):
        from PIL import Image
        from services.article_assets import acquire_assets
        image = io.BytesIO()
        Image.new('RGB', (16, 16)).save(image, format='PNG')
        calls = []
        def generator(request):
            calls.append(request)
            return image.getvalue(), 'image/png', {'promptTokenCount': 20}
        needs = [{'id': 'NEED-1', 'mode': 'generation_request', 'purpose': '상황 설명', 'prompt': 'outdated claim 1m'},
                 {'id': 'NEED-PRODUCT', 'mode': 'existing', 'asset_id': 'AST-PRODUCT'}]
        bindings = [{'need': n, 'candidate': None, 'status': 'pending_review'} for n in needs]
        text = '# 제목\n\n좌석을 조정합니다.\n\n{{asset:NEED-1}}\n\n{{asset:NEED-PRODUCT}}'
        report = acquire_assets(self.root, 'CNT-test', 'run-1', text, needs, bindings, generator)
        self.assertEqual(report['generated_count'], 1)
        self.assertNotIn('outdated claim', json.dumps(calls))
        self.assertEqual(bindings[0]['candidate']['review_status'], 'candidate')
        self.assertIsNone(bindings[0]['candidate']['public_url'])
        self.assertEqual(report['items'][1]['status'], 'source_required')
        again = acquire_assets(self.root, 'CNT-test', 'run-2', text, needs,
                               [{'need': n, 'candidate': None} for n in needs], generator)
        self.assertEqual(again['generated_count'], 0)
        self.assertEqual(len(calls), 1)


if __name__ == '__main__': unittest.main()
