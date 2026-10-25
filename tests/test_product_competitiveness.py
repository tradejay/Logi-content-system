import unittest
from services.blog_performance.product_competitiveness import calculate


class ProductScoreTests(unittest.TestCase):
    def panel(self):
        catalog=[dict(product_id='p',brand='brand',product='one',group='bar',queries=['ko','en'])]
        queries=[dict(query_id=q,product_id='p',status='success') for q in ['a','b']]
        hits=[dict(query_id='a',product_id='p',blog_id='mine',rank=1,post_key='mine/1'),
              dict(query_id='b',product_id='p',blog_id='mine',rank=2,post_key='mine/1')]
        return catalog,queries,hits

    def test_exact_score_and_unique_post(self):
        r=calculate(*self.panel(),own_blog='mine')['blogs'][0]
        self.assertEqual(r['search_competitiveness'],75)
        self.assertEqual(r['unique_posts'],1)

    def test_more_posts_do_not_inflate_score(self):
        c,q,h=self.panel()
        before=calculate(c,q,h,own_blog='mine')['blogs'][0]['search_competitiveness']
        h.append(dict(query_id='a',product_id='p',blog_id='mine',rank=10,post_key='mine/2'))
        self.assertEqual(calculate(c,q,h,own_blog='mine')['blogs'][0]['search_competitiveness'],before)

    def test_failed_query_is_not_zero_or_rescaled(self):
        c,q,h=self.panel();q[1]['status']='failed'
        result=calculate(c,q,h,own_blog='mine')
        self.assertFalse(result['panel_complete'])
        self.assertIsNone(result['blogs'][0]['search_competitiveness'])

    def test_no_results_after_success_is_observed_zero(self):
        c,q,_=self.panel()
        r=calculate(c,q,[],own_blog='mine')['blogs'][0]
        self.assertEqual(r['search_competitiveness'],0)
        self.assertEqual(r['observation']['temporal_stability'],'not_measured')

    def test_auxiliary_does_not_change_search_score(self):
        c,q,h=self.panel()
        a=calculate(c,q,h,own_blog='mine')['blogs'][0]
        b=calculate(c,q,h,own_blog='mine',auxiliary=[dict(blog_id='mine',avg_chars=999999,count_30d=99)])['blogs'][0]
        self.assertEqual(a['search_competitiveness'],b['search_competitiveness'])

    def test_ties_share_position(self):
        c,q,h=self.panel()
        h += [dict(query_id=r['query_id'],product_id='p',blog_id='other',rank=r['rank'],post_key='other/1') for r in h[:]]
        result=calculate(c,q,h,own_blog='mine')
        self.assertEqual([r['panel_position'] for r in result['blogs']],[1,1])
