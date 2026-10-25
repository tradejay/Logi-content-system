import unittest
from services.web_planning import planning_input, finalize, product_only


class WebPlanningTests(unittest.TestCase):
    def setUp(self):
        research = {'results': [{'document_id': 'A', 'title': 'Room guide', 'source_location': 'https://avixa.org/guide',
                                 'trust_policy_id': 'SYS-WEB-SOURCE-TRUST-003'},
                                {'document_id': 'X', 'source_location': 'https://example.com/guide',
                                 'trust_policy_id': 'SYS-WEB-SOURCE-TRUST-003'}],
                    'trusted_segments': [{'text': 'Check the seating layout', 'source_ids': ['A']},
                                         {'text': 'Mixed citation', 'source_ids': ['A', 'X']}]}
        self.payload = planning_input({'topic': 'Camera positioning'}, research)

    def selection(self, mode):
        return {'mode': mode, 'article_source_ids': ['A'] if mode == 'related_articles' else [],
                'reason': 'relevance', 'points': [{'segment_id': self.payload['segments'][0]['id'],
                                                  'use': 'criteria', 'notes': '先に配置条件を確認'}]}

    def test_allowlist_and_citation_filter(self):
        self.assertEqual(len(self.payload['sources']), 1)
        self.assertEqual(len(self.payload['segments']), 1)

    def test_related_article(self):
        result = finalize(self.selection('related_articles'), self.payload)
        self.assertEqual(result['article_source_ids'], ['A'])
        self.assertEqual(result['points'][0]['text'], 'Check the seating layout')
        self.assertEqual(result['points'][0]['quote_origin'], 'grounded_summary')

    def test_fact_fallback_preserves_source(self):
        result = finalize(self.selection('fact_fallback'), self.payload)
        self.assertEqual(result['sources'][0]['source_location'], 'https://avixa.org/guide')
        self.assertEqual(result['article_source_ids'], [])

    def test_no_data(self):
        result = finalize(product_only('No reference'), self.payload)
        self.assertEqual(result['mode'], 'product_facts_only')
        self.assertEqual(result['points'], [])

    def test_invented_reference_rejected(self):
        result = self.selection('related_articles')
        result['points'][0]['segment_id'] = 'invented'
        with self.assertRaises(ValueError):
            finalize(result, self.payload)

    def test_related_mode_requires_support(self):
        result = self.selection('related_articles')
        result['points'] = []
        with self.assertRaises(ValueError):
            finalize(result, self.payload)

    def test_unused_article_is_excluded_without_losing_supported_points(self):
        self.payload['sources'].append({'document_id': 'B', 'title': 'Unused article', 'source_location': 'https://psni.org/other'})
        selection = self.selection('related_articles')
        selection['article_source_ids'].append('B')
        result = finalize(selection, self.payload)
        self.assertEqual(result['article_source_ids'], ['A'])
        self.assertEqual(result['excluded_article_source_ids'], ['B'])
        self.assertEqual(len(result['points']), 1)
