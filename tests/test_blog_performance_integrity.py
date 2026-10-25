import unittest
from services.blog_performance.blog_analyzer import parse_search_api_items, post_identity
from services.blog_performance.competitor_engine import compute_index, build_matrix
from services.keyword_volume import _to_int
from unittest.mock import Mock


class IntegrityTests(unittest.TestCase):
    def test_blog_prefix_is_not_same_blog(self):
        rows = [{'link': 'https://blog.naver.com/oceantech010/123',
                 'bloggerlink': 'https://blog.naver.com/oceantech010'}]
        self.assertIsNone(parse_search_api_items(rows, 'kw', 'oceantech01')['rank'])

    def test_published_post_is_found_after_another_post_from_same_blog(self):
        rows = [{'link': 'https://blog.naver.com/mine/111'},
                {'link': 'https://m.blog.naver.com/mine/222'}]
        result = parse_search_api_items(rows, 'kw', 'mine', target_url='https://blog.naver.com/mine/222')
        self.assertEqual(result['rank'], 2)
        self.assertEqual(post_identity(result['target_link']), ('mine', '222'))

    def test_query_style_post_url_and_path_url_have_same_identity(self):
        self.assertEqual(post_identity('https://blog.naver.com/PostView.naver?blogId=mine&logNo=222'),
                         post_identity('https://m.blog.naver.com/mine/222'))

    def test_missing_value_is_not_a_zero_score(self):
        weights = dict(exposure=.4, activity=.25, focus=.2, content=.15)
        raw = {'missing': dict(exposure=1, activity=1, focus=1, content=None),
               'observed': dict(exposure=1, activity=1, focus=1, content=10)}
        out = compute_index(raw, weights)
        self.assertIsNone(out['missing']['content'])
        self.assertIsNone(out['missing']['total'])
        self.assertIsNotNone(out['observed']['total'])

    def test_partial_or_legacy_context_cannot_produce_comparison(self):
        from services.blog_performance.competitor_engine import Config
        for context in [None, {'complete': False}]:
            store = Mock()
            store.get_run_context.return_value = context
            result = build_matrix(store, Config(), '2026-10-21')
            self.assertFalse(result['comparison_available'])
            self.assertNotIn('leaderboard', result)

    def test_search_volume_range_is_not_a_fabricated_midpoint(self):
        self.assertEqual(_to_int('< 10'), '< 10')
        self.assertEqual(_to_int(0), 0)
