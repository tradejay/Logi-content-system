import unittest
from copy import deepcopy
from services.pipeline_payload import compact_payload


class PayloadTests(unittest.TestCase):
    def test_preserves_evidence_and_does_not_mutate_audit_input(self):
        fact = {'id': 'F1', 'value': 12, 'unit': 'm', 'scope': {'except': ['X']},
                'limitations': ['only Y'], 'source': {'id': 'S1', 'locator': {'section': 'limits'}}}
        original = {'facts': [fact], 'knowledge': ['duplicate'], 'input_refs': [{'sha256': 'secret-hash'}],
            'sources': {'S1': {'id': 'S1', 'body': 'full conditions', 'path': 'local/file'}},
            'cautions': [{'id': 'R1', 'body': 'rule', 'sha256': 'hash', 'match': {'any': []}}],
            'guides': {'03-writing.md': 'writing', '05-review.md': 'review', '06-console.md': 'console'},
            'strategy': {'opening': 'hello', 'asset_needs': ['image']}, 'asset_plan': ['image']}
        snapshot = deepcopy(original)
        value = compact_payload('write', original)
        self.assertEqual(value['facts'], [fact])
        self.assertEqual(value['sources']['S1']['body'], 'full conditions')
        self.assertNotIn('knowledge', value)
        self.assertNotIn('input_refs', value)
        self.assertEqual(value['cautions'], [{'id': 'R1', 'body': 'rule'}])
        self.assertEqual(value['guides'], {'03-writing.md': 'writing'})
        self.assertNotIn('asset_needs', value['strategy'])
        self.assertEqual(original, snapshot)

    def test_stage_boundaries_and_official_claim_selection(self):
        payload = {'facts': [{'id': 'F1'}, {'id': 'F2'}], 'claims': [{'id': 'C1', 'fact_ids': ['F2']}],
                   'playbooks': {'P1': {'id': 'P1', 'name': 'book', 'body': 'long text'}}}
        strategy = compact_payload('strategy', payload)
        self.assertNotIn('body', strategy['playbooks']['P1'])
        self.assertNotIn('playbooks', compact_payload('feedback', payload))
        self.assertEqual(compact_payload('official', payload)['facts'], [{'id': 'F2'}])

    def test_official_receives_entire_draft_source_and_locator(self):
        source = {'id': 'S1', 'url': 'https://example.com/spec', 'body': '# Camera\nHFOV is 113 degrees\n# Audio\nother'}
        payload = {'draft': {'markdown': '# Full article\nAll paragraphs'},
                   'claims': [{'id': 'C1', 'fact_ids': ['F1']}],
                   'facts': [{'id': 'F1', 'scope': {'applies_to': ['MeetUp2']}, 'source': {'id': 'S1', 'locator': {'heading': 'Camera'}}}],
                   'sources': {'S1': source, 'S2': {'id': 'S2', 'body': 'unrelated'}}}
        value = compact_payload('official', payload)
        self.assertEqual(value['draft'], payload['draft'])
        self.assertEqual(value['facts'][0]['source']['locator'], {'heading': 'Camera'})
        self.assertEqual(value['sources']['S1']['url'], source['url'])
        self.assertIn('HFOV is 113', value['sources']['S1']['body'])
        self.assertNotIn('S2', value['sources'])
