import unittest
from scripts.analyze_browser_search_bodies import brands_in,classify,terms
from scripts.collect_common_query_ranks import calculate

class BrowserBodyMatchingTest(unittest.TestCase):
    def test_naver_is_not_aver(self):
        self.assertNotIn('AVer',brands_in('NAVER naver 네이버'))
        self.assertIn('AVer',brands_in('AVer VB350'))

    def test_longer_device_alias_wins(self):
        catalog=[{'product_id':'A','brand':'Logitech','product':'Rally Bar','queries':['로지텍 랠리바']},
                 {'product_id':'B','brand':'Logitech','product':'Rally Bar Mini','queries':['로지텍 랠리바 미니']}]
        self.assertEqual(classify('로지텍 Rally Bar Mini 설치',catalog)[1],['B'])
        self.assertEqual(classify('로지텍 Rally Bar 2 신규 장비',catalog)[1],[])

    def test_english_digit_candidates(self):
        result=terms('로지텍 C270 웹캠 UVC 34 설치 hello world')
        self.assertIn('c270',result);self.assertIn('uvc34',result);self.assertNotIn('hello',result)

    def test_brand_without_catalog_device_is_not_dropped(self):
        catalog={'P':{'product_id':'P','product':'Model','brand':'Logitech','group':'bar'}}
        index={'abc/123':{'brands':['Logitech'],'product_ids':[]}}
        query=[{'keyword':'q','hits':[{'post_url':'https://blog.naver.com/abc/123','rank':5,'blog_id':'abc'}]}]
        old=calculate(query,index,catalog)
        new=calculate(query,index,catalog,include_brand_only=True)
        self.assertEqual(len(old['matched']),0);self.assertEqual(len(new['matched']),1)
        self.assertEqual(new['brand_scores'][0]['observed_score'],20)
        self.assertEqual(new['product_scores'][0]['observed_score'],0)

    def test_ambiguous_model_does_not_invent_a_brand(self):
        import json,tempfile
        from pathlib import Path
        from scripts.merge_browser_body_classifications import build_classifications
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'scratch') as folder:
            out=Path(folder)
            files={
             'ai-terms.json':{'items':[{'id':'T1'}]},
             'result.json':{'passed':True,'issues':[],'decisions':[{'id':'T1','category':'outside_model','brand':'HP Poly','model':'Studio A2','product_ids':[]}]},
             'model-terms.json':{'items':[{'id':'T1','term':'a2','post_ids':['B1']}]},
             'bodies.json':[{'candidate_id':'B1','status':'success','body_text':'Microsoft Teams Q&A 2 안내','body_sha256':'test'}],
             'classifications.json':{'items':[{'id':'B1','post_key':'test/123','product_ids':[],'brand_candidates':[]}]}}
            for name,data in files.items():(out/name).write_text(json.dumps(data),encoding='utf-8')
            index,*_=build_classifications(out,out/'result.json')
            self.assertNotIn('HP Poly',index['test/123']['brands'])

if __name__=='__main__':unittest.main()
