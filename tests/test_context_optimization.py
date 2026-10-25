import json
import unittest
from copy import deepcopy
from services.context_optimization import apply_fact_policy, optimize_context, field_sizes
from services.guide_contracts import GuideReleaseManifest
from services.context_assembler import ContextAssembler


class OptimizationTests(unittest.TestCase):
    def test_fact_refresh_preserves_scope_and_snapshot(self):
        source = {'brief': {'fact_policy': {'excluded_fact_ids': ['F2'], 'block_fact_ids': {'check': ['F1', 'F3']}}},
                  'facts': [{'id': 'F1', 'scope': {'except': ['X']}}, {'id': 'F2'}, {'id': 'F3', 'source': {'id': 'S', 'locator': {'section': 'limits'}}}],
                  'strategy': {'content_blocks': [{'id': 'check', 'fact_ids': ['F2']}, {'id': 'other', 'fact_ids': ['F1', 'F2']}]}}
        before = deepcopy(source)
        result, audit = apply_fact_policy(source)
        self.assertEqual(result['strategy']['content_blocks'][0]['fact_ids'], ['F1', 'F3'])
        self.assertEqual(result['strategy']['content_blocks'][1]['fact_ids'], ['F1'])
        self.assertEqual([f['id'] for f in result['facts']], ['F1', 'F3'])
        self.assertEqual(result['facts'][0]['scope'], source['facts'][0]['scope'])
        self.assertEqual(audit['excluded_fact_ids'], ['F2'])
        self.assertEqual(source, before)

    def test_bad_overrides_fail_closed(self):
        for policy in [{'excluded_fact_ids': ['unknown']}, {'block_fact_ids': {'unknown': ['F1']}},
                       {'excluded_fact_ids': ['F1'], 'block_fact_ids': {'b': ['F1']}}, {'new_field': True}]:
            with self.assertRaises(ValueError):
                apply_fact_policy({'fact_policy': policy, 'facts': [{'id': 'F1'}], 'strategy': {'content_blocks': [{'id': 'b'}]}})

    def test_catalog_only_and_new_guide_revision_fallback(self):
        payload = {'guides': {'GUIDE-07-CONTRACTS': 'new text must remain'}, 'rules': [{'id': 'R', 'body': '조건·예외'}],
                   'facts': [{'id': 'F', 'value': 7, 'scope': {'except': ['X']}}],
                   'playbooks': {'P': {'id': 'P', 'name': 'Problem', 'suitable_for': ['a'], 'body': 'long body'}}}
        value, report = optimize_context('strategy', payload)
        self.assertNotIn('body', value['playbooks']['P'])
        self.assertEqual(value['rules'], payload['rules'])
        self.assertEqual(value['facts'], payload['facts'])
        self.assertEqual(value['guides'], payload['guides'])
        self.assertIn('body', payload['playbooks']['P'])
        self.assertEqual(report['unit'], 'characters_not_tokens')
        self.assertEqual(field_sizes({'x': 'abc'})['x'], 5)

    def test_only_identical_block_plan_duplicate_is_removed(self):
        blocks = [{'id': 'b', 'fact_ids': ['F1']}]
        payload = {'brief': {'content_blocks': blocks}, 'strategy': {'content_blocks': blocks}}
        value, _ = optimize_context('write', payload)
        self.assertNotIn('content_blocks', value['brief'])
        self.assertEqual(value['strategy']['content_blocks'], blocks)
        payload['strategy'] = {'content_blocks': [{'id': 'different'}]}
        value, _ = optimize_context('write', payload)
        self.assertEqual(value['brief']['content_blocks'], blocks)

    def test_explicit_element_scope_and_core_preservation(self):
        manifest = GuideReleaseManifest(release_id='r', created_at='now', bundle_sha256='x', code_revision='x', guides={
            'CORE': {'status': 'active', 'kind': 'core', 'stages': ['write'], 'body': 'safety'},
            'OTHER': {'status': 'active', 'stages': ['write'], 'body': 'other', 'applies_to_elements': ['closing.summary']},
            'BODY': {'status': 'active', 'stages': ['write'], 'body': 'body', 'applies_to_elements': ['body.explanation']}})
        snapshot = {'brief': {}, 'strategy': {'primary_playbook': 'P', 'content_blocks': [{'id': 'b', 'roles': ['body.explanation']}]},
                    'playbooks': {'P': {'body': 'selected full body'}, 'Q': {'body': 'not selected'}}, 'facts': []}
        payload, report = ContextAssembler(manifest).assemble_context('write', None, snapshot)
        self.assertEqual(set(payload['guides']), {'CORE', 'BODY'})

    def test_selected_guide_rule_dependency_is_not_lost(self):
        manifest = GuideReleaseManifest(release_id='r', created_at='now', bundle_sha256='x', code_revision='x',
            guides={'BODY': {'status': 'active', 'stages': ['write'], 'body': 'body'}},
            rules={'DEPENDENCY': {'status': 'active', 'stages': ['write'], 'body': 'condition', 'match': {'any': [{'field': 'product_ids', 'values': ['OTHER']}]}}},
            dependencies={'BODY': ['DEPENDENCY']})
        payload, report = ContextAssembler(manifest).assemble_context('write', None, {'facts': [], 'brief': {}})
        self.assertEqual(payload['rules'][0]['id'], 'DEPENDENCY')
        self.assertEqual(report.selected_rules[0]['id'], 'DEPENDENCY')
        self.assertEqual(report.omitted_rules, [])

if __name__ == '__main__':
    unittest.main()
