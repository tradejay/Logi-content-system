from copy import deepcopy
import unittest
from services.context_transport import pack_fact_scopes, expand_fact_scopes, pack_review_draft, restore_review_draft
from services.policy_call_audit import prepare_call


class TransportTests(unittest.TestCase):
    def test_scope_roundtrip_and_exception_preservation(self):
        scope = {'applies_to': ['device'], 'conditions': ['room condition ' * 15], 'exceptions': ['unsupported mode']}
        facts = [{'id': 'F1', 'scope': scope, 'value': 7, 'unit': 'm'},
                 {'id': 'F2', 'scope': deepcopy(scope), 'value': 3, 'unit': 'm'},
                 {'id': 'F3', 'scope': {'conditions': ['a different condition']}}]
        original = deepcopy(facts)
        payload = {'facts': deepcopy(facts)}
        self.assertTrue(pack_fact_scopes(payload))
        self.assertEqual(len(payload['fact_scopes']), 1)
        self.assertEqual(payload['facts'][0]['scope_ref'], payload['facts'][1]['scope_ref'])
        self.assertIn('scope', payload['facts'][2])
        self.assertEqual(expand_fact_scopes(payload), original)
        self.assertEqual(facts, original)
        del payload['fact_scopes']['SC01']
        with self.assertRaises(ValueError):
            expand_fact_scopes(payload)

    def test_unique_and_small_scopes_stay_inline(self):
        payload = {'facts': [{'id': 'F1', 'scope': {}}, {'id': 'F2', 'scope': {}}, {'id': 'F3'}]}
        original = deepcopy(payload)
        self.assertFalse(pack_fact_scopes(payload))
        self.assertEqual(payload, original)
        self.assertEqual(expand_fact_scopes(payload), original['facts'])

    def test_ambiguous_reference_fails(self):
        with self.assertRaises(ValueError):
            expand_fact_scopes({'facts': [{'id': 'F', 'scope': {}, 'scope_ref': 'SC01'}], 'fact_scopes': {'SC01': {}}})

    def test_review_body_once_and_exact_unicode_roundtrip(self):
        blocks = [{'id': 'intro', 'markdown': '안녕하세요 😀', 'claim_ids': []},
                  {'id': 'body', 'markdown': '## 화각\n113도', 'claim_ids': ['C1']}]
        draft = {'markdown': '\n\n'.join(b['markdown'] for b in blocks), 'blocks': blocks, 'claims': [{'id': 'C1'}]}
        payload = {'draft': deepcopy(draft)}
        self.assertEqual(pack_review_draft(payload), 'body_spans_v1')
        self.assertNotIn('markdown', payload['draft']['blocks'][0])
        self.assertEqual(restore_review_draft(payload), draft)
        payload['draft']['blocks'][1]['body_span'][1] -= 1
        with self.assertRaises(ValueError):
            restore_review_draft(payload)

    def test_mismatched_body_retained_for_error_review(self):
        payload = {'draft': {'markdown': 'whole', 'blocks': [{'id': 'b', 'markdown': 'different'}]}}
        original = deepcopy(payload)
        self.assertEqual(pack_review_draft(payload), 'kept_assembly_mismatch_for_review')
        self.assertEqual(payload, original)

    def test_transport_integration_and_official_boundary(self):
        scope = {'condition': 'keep this condition ' * 30}
        payload = {'facts': [{'id': 'F1', 'scope': scope}, {'id': 'F2', 'scope': scope}],
                   'draft': {'markdown': '본문', 'blocks': [{'id': 'b', 'markdown': '본문', 'claim_ids': []}]}}
        snapshot = deepcopy(payload)
        instruction, sent, ledger = prepare_call('feedback', 'review', payload, 'c', 'r', 'p', 'h')
        self.assertIn('scope_ref', instruction)
        self.assertIn('body_span', instruction)
        self.assertEqual(ledger['draft_transport'], 'body_spans_v1')
        self.assertEqual(expand_fact_scopes(sent), payload['facts'])
        self.assertEqual(restore_review_draft(sent), payload['draft'])
        _, sent, ledger = prepare_call('official', 'review', payload, 'c', 'r', 'p', 'h')
        self.assertEqual(sent['facts'], payload['facts'])
        self.assertEqual(sent['draft'], payload['draft'])
        self.assertEqual(payload, snapshot)

if __name__ == '__main__':
    unittest.main()
