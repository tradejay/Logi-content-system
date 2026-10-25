"""Common-query scores must preserve source ranks and exact post identity."""
import unittest
from scripts.collect_common_query_ranks import calculate,key

class CommonQueryRanksTest(unittest.TestCase):
    def test_url_aliases_and_external_urls(self):
        self.assertEqual(key('https://m.blog.naver.com/PostView.naver?blogId=ABC&logNo=123'),'abc/123')
        self.assertEqual(key('https://blog.naver.com/abc/123?x=1'),'abc/123')
        self.assertIsNone(key('https://example.com/abc/123'))

    def test_original_rank_unmatched_and_multiple_products(self):
        catalog={pid:{'product_id':pid,'brand':'A','product':pid,'group':'bar'} for pid in ['P1','P2']}
        index={'abc/123':{'product_ids':['P1','P2'],'brands':['A']}}
        queries=[{'keyword':'q1','hits':[
            {'post_url':'https://blog.naver.com/new/456','rank':1,'blog_id':'new'},
            {'post_url':'https://blog.naver.com/abc/123','rank':20,'blog_id':'abc'},
            {'post_url':'https://m.blog.naver.com/abc/123','rank':21,'blog_id':'abc'}]}, {'keyword':'q2','hits':[]}]
        r=calculate(queries,index,catalog)
        self.assertEqual(len(r['matched']),1)
        self.assertEqual(len(r['unmatched']),1)
        self.assertEqual(r['brand_scores'][0]['observed_score'],2.5)
        self.assertEqual(r['brand_scores'][0]['keyword_ranks'][0]['best_rank'],20)
        self.assertIsNone(r['brand_scores'][0]['keyword_ranks'][1]['best_rank'])
        self.assertEqual(len(r['product_scores']),2)

if __name__=='__main__':unittest.main()
