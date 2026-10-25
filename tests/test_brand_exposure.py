import unittest
from services.blog_performance.brand_exposure import breakdown


class BrandExposureTests(unittest.TestCase):
    def test_best_post_rank_and_brand_product_count_normalization(self):
        catalog=[dict(product_id=p,brand=b,product=p,queries=[p]) for p,b in [('a','A'),('b','B'),('c','B')]]
        queries=[dict(query_id=p,query=p,product_id=p,status='success') for p in ['a','b','c']]
        hits=[dict(query_id=p,product_id=p,blog_id='mine',rank=2,post_key='mine/1',url='url',title='t',blog_name='name') for p in ['a','b','c']]
        hits.append(dict(hits[0],rank=10,post_key='mine/2'))
        query_rows,brands=breakdown(catalog,queries,hits,['mine','absent'])
        mine=[r for r in brands if r['blog_id']=='mine']
        self.assertEqual([r['normalized_brand_exposure_share_pct'] for r in mine],[50,50])
        self.assertEqual(query_rows[0]['api_rank'],2)
        self.assertEqual(query_rows[0]['unique_posts'],2)
        self.assertEqual(query_rows[1]['status'],'not_in_collected_results')
        self.assertIsNone(next(r for r in brands if r['blog_id']=='absent')['normalized_brand_exposure_share_pct'])

    def test_failed_query_is_not_nonappearance(self):
        c=[dict(product_id='p',brand='A',product='p',queries=['p'])]
        q=[dict(query_id='p',query='p',product_id='p',status='failed')]
        rows,brands=breakdown(c,q,[],['mine'])
        self.assertEqual(rows[0]['status'],'collection_failed')
        self.assertIsNone(brands[0]['brand_search_strength'])
