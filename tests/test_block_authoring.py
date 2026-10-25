import json
from pathlib import Path
import tempfile
import unittest
from services.block_authoring import build_block_plan, validate_blocks, repair_targets, validate_preserved_blocks
from services.policy_call_audit import prepare_call


class BlockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        path = self.root / 'content-system/00_system/templates/articles/content-block-guides.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'workspace_revision': 27, 'blocks': [{'block_id': 'body.specification',
            'purpose': '수치를 설명', 'content_guide': '조건 보존', 'avoid': [], 'review_questions': ['범위가 맞는가'],
            'existing_policy_ids': ['RULE-NUMERIC-SCOPE-V2N0001']}]}), encoding='utf-8')
        self.context = {'strategy': {'content_blocks': [{'id': 'spec', 'role': 'body.specification', 'fact_ids': ['F1']}]},
                        'facts': [{'id': 'F1'}, {'id': 'F2'}], 'rules': [{'id': 'RULE-NUMERIC-SCOPE', 'body': '조건 보존'}]}
        self.plan, _ = build_block_plan(self.root, self.context)
        self.result = {'markdown': '화각 113도', 'claims': [{'id': 'C1', 'text': '화각 113도', 'fact_ids': ['F1']}],
                       'blocks': [{'id': 'spec', 'markdown': '화각 113도', 'claim_ids': ['C1']}]}
    def tearDown(self):
        self.tmp.cleanup()
    def test_role_guides_facts_and_rule_aliases(self):
        self.assertEqual(self.plan[0]['rule_ids'], ['RULE-NUMERIC-SCOPE'])
        self.assertEqual(self.plan[0]['fact_ids'], ['F1'])
        _, payload, ledger = prepare_call('write', 'write', {**self.context, 'block_plan': self.plan}, 'c1', 'r1', 'prompt', 'hash')
        self.assertEqual(payload['block_plan'][0]['rule_ids'], ['R01'])
        self.assertEqual(payload['block_plan'][0]['guide_roles'], ['body.specification'])
        self.assertEqual(payload['block_guides']['body.specification']['content_guide'], '조건 보존')
        self.assertEqual(ledger['block_assignments'][0]['rule_ids'], ['RULE-NUMERIC-SCOPE'])
        self.assertEqual(validate_blocks(self.result, self.plan), [])
    def test_missing_order_and_assembly(self):
        self.assertTrue(validate_blocks({**self.result, 'blocks': []}, self.plan))
        self.assertTrue(validate_blocks({**self.result, 'markdown': '다른 본문'}, self.plan))
        self.assertTrue(validate_blocks({**self.result, 'blocks': [{'id': 'other', 'markdown': '화각 113도', 'claim_ids': ['C1']}]}, self.plan))
    def test_outside_fact_and_duplicate_claim(self):
        self.result['claims'][0]['fact_ids'] = ['F2']
        self.assertTrue(validate_blocks(self.result, self.plan))
        self.result['blocks'][0]['claim_ids'] = ['C1', 'C1']
        self.assertTrue(validate_blocks(self.result, self.plan))
    def test_invalid_plan_fails_closed(self):
        self.context['strategy']['content_blocks'][0]['role'] = 'unknown'
        with self.assertRaises(ValueError):
            build_block_plan(self.root, self.context)
    def test_local_repair_preserves_unrelated_blocks(self):
        previous = {'blocks': [{'id': 'intro', 'markdown': '인사', 'claim_ids': []}, self.result['blocks'][0]]}
        self.assertEqual(repair_targets(previous, {'issues': [{'claim_id': 'C1'}]}), ['spec'])
        self.assertEqual(repair_targets(previous, {'issues': [{'detail': '글 전체 문제'}]}), [])
        self.assertEqual(validate_preserved_blocks(previous, previous, ['spec']), [])
        changed = {'blocks': [{'id': 'intro', 'markdown': '무단 수정', 'claim_ids': []}, self.result['blocks'][0]]}
        self.assertTrue(validate_preserved_blocks(changed, previous, ['spec']))

    def test_explicit_fact_refresh_keeps_outside_fact_check(self):
        self.context['fact_policy'] = {'excluded_fact_ids': ['F1'], 'block_fact_ids': {'spec': ['F2']}}
        plan, _ = build_block_plan(self.root, self.context)
        self.assertEqual(plan[0]['fact_ids'], ['F2'])
        self.assertTrue(validate_blocks(self.result, plan))
        self.result['claims'][0]['fact_ids'] = ['F2']
        self.assertEqual(validate_blocks(self.result, plan), [])


if __name__ == '__main__':
    unittest.main()
