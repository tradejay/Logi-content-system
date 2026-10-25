import csv
from pathlib import Path
import tempfile
import unittest
import copy

from services.taiga_blog_catalog import render_catalog, synchronize_catalog


class WikiClient:
    base='https://example.com/api/v1'
    def __init__(self):
        self.links=[]; self.pages={}; self.project={'description':''}
    def request(self, method, path, payload=None, **kwargs):
        if path=='wiki-links':
            if method=='POST':
                self.links.append({'id':1,'title':payload['title'],'href':'actual-generated-slug'})
                self.pages[1]={'id':1,'slug':'actual-generated-slug','content':'','version':1}
                return copy.deepcopy(self.links[0])
            return copy.deepcopy(self.links)
        if path=='wiki':
            if method=='POST':
                key=len(self.pages)+1
                self.pages[key]={'id':key,'version':1,**payload}
                return copy.deepcopy(self.pages[key])
            return copy.deepcopy(list(self.pages.values()))
        if path.startswith('wiki/'):
            page=self.pages[int(path.split('/')[-1])]
            if method=='PATCH': page.update(payload); page['version']+=1
            return copy.deepcopy(page)
        if path.startswith('projects/'):
            if method=='PATCH': self.project.update(payload)
            return copy.deepcopy(self.project)
        raise AssertionError(path)


class BlogCatalogTests(unittest.TestCase):
    def test_menu_generated_slug_is_used_without_duplicate_links(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); path=root/'content-system/registry/CONTENT_REGISTRY.csv'
            path.parent.mkdir(parents=True); path.write_text('content_id,status\n',encoding='utf-8')
            client=WikiClient(); report={'tickets':[],'board_url':'https://example.com/board'}
            for _ in range(2):
                synchronize_catalog(root,client,{'id':1,'slug':'test'},[],report)
            self.assertEqual(len(client.links),1)
            self.assertIn('블로그 글 목록',client.pages[1]['content'])
            self.assertTrue(report['blog_catalog_url'].endswith('/wiki/actual-generated-slug'))

    def test_catalog_contains_only_articles_and_does_not_infer_publication(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            path=root/'content-system/registry/CONTENT_REGISTRY.csv'
            path.parent.mkdir(parents=True)
            with path.open('w',encoding='utf-8',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=['content_id','status','primary_keyword'])
                writer.writeheader(); writer.writerow({'content_id':'CNT-TEST','status':'READY_FOR_QA','primary_keyword':'회의실'})
            tasks=[{'key':'content:CNT-TEST','category':'글','title':'테스트 원고','state':'완료',
                'refs':{'content_id':'CNT-TEST'},'details':{'draft_chars':42},
                'editor_url':'https://example.com/editor','console_url':'https://example.com/console'},
                {'key':'fact:1','category':'Fact','title':'노출하면 안 되는 과거 Fact'}]
            result=render_catalog(root,tasks,{'tickets':[{'key':'content:CNT-TEST','url':'https://example.com/article','state':'완료'}],
                'board_url':'https://example.com/board'})
            self.assertIn('등록 글 **1개**',result)
            self.assertIn('발행 기록 **0개**',result)
            self.assertIn('[원고 수정](https://example.com/editor)',result)
            self.assertNotIn('과거 Fact',result)


if __name__=='__main__':
    unittest.main()
