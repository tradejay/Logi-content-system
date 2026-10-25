import unittest
from scripts.correct_official_reviews import merge_edits


class CorrectionContractTests(unittest.TestCase):
    def setUp(self):
        self.original = [{'id': 'B1', 'role': 'feature', 'markdown': '제품 지원. {{asset:N1}}',
                          'claims': [{'text': '제품 지원', 'fact_ids': ['F1']}]}]
        self.facts = [{'id': 'F1'}]

    def test_changed_claim_must_match_actual_revised_text(self):
        result = {'blocks': [{'id': 'B1', 'markdown': '조건부 지원. {{asset:N1}}',
                              'claims': [{'text': '조건부 지원', 'fact_ids': ['F1']}]}]}
        blocks, claims = merge_edits(self.original, result, self.facts)
        self.assertEqual(claims[0]['text'], '조건부 지원')
        self.assertEqual(self.original[0]['markdown'], '제품 지원. {{asset:N1}}')
        result['blocks'][0]['claims'][0]['text'] = '다른 주장'
        with self.assertRaises(ValueError):
            merge_edits(self.original, result, self.facts)

    def test_asset_slot_changes_are_blocked(self):
        result = {'blocks': [{**self.original[0], 'markdown': '제품 지원. {{asset:N2}}'}]}
        with self.assertRaises(ValueError):
            merge_edits(self.original, result, self.facts)

    def test_unknown_fact_and_missing_block_are_blocked(self):
        with self.assertRaises(ValueError):
            merge_edits(self.original, {'blocks': []}, self.facts)
        result = {'blocks': [{**self.original[0], 'claims': [{'text': '제품 지원', 'fact_ids': ['UNKNOWN']}]}]}
        with self.assertRaises(ValueError):
            merge_edits(self.original, result, self.facts)


if __name__ == '__main__':
    unittest.main()
