import unittest
from unittest.mock import patch
from scripts.run_ide_article_batch import assemble, claim_map, prepare_plan, tick


class ArticleRerunTests(unittest.TestCase):
    def test_assembly_rejects_missing_block_content(self):
        with self.assertRaises(ValueError):
            assemble([{'markdown': ''}])

    def test_claim_binding_preserves_line_breaks_but_rejects_changed_value(self):
        blocks = [{'id': 'b1', 'markdown': '수음 거리는\n7m입니다.', 'claims': [{'text': '수음 거리는 7m입니다.', 'fact_ids': ['F1']}]}]
        self.assertEqual(claim_map(blocks, [{'id': 'F1'}])[0]['text'], '수음 거리는\n7m입니다.')
        blocks[0]['markdown'] = '수음 거리는 8m입니다.'
        with self.assertRaises(ValueError):
            claim_map(blocks, [{'id': 'F1'}])

    def test_homepage_citation_is_not_adopted_as_article_evidence(self):
        plan = prepare_plan({'ordered_blocks': [{'role': 'concept', 'purpose': '차이', 'fact_ids': []}], 'references': [{'url': 'https://www.avixa.org/', 'key_takeaway': 'unverified'}]})
        self.assertEqual(plan['references'], [])
        self.assertTrue(plan['unresolved_items'])
        roles = [b['role'] for b in plan['ordered_blocks']]
        self.assertEqual(roles[0], 'title')
        self.assertIn('opening.inquiry_banner', roles)
        self.assertEqual(roles[-1], 'closing.inquiry_banner')

    @patch('scripts.run_ide_article_batch.receive', return_value={'articles': []})
    def test_incomplete_planner_batch_cannot_start_writing(self, receive):
        with self.assertRaises(ValueError):
            tick(None, {'stage': 'planning', 'planner_task': {}, 'content_ids': ['a', 'b', 'c', 'd', 'e']})


if __name__ == '__main__':
    unittest.main()
