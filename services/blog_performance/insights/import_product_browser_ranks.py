"""Validate and preserve user-provided Korean device-name browser captures."""
import argparse,hashlib,json
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from services.blog_performance.insights.collect_common_query_ranks import ROOT,SOURCE,read,save,key


def identity(url):
    n=key(url)
    if n:return n
    p=urlparse(url)
    if p.scheme=='https' and p.hostname and p.hostname.endswith('.tistory.com') and p.path.strip('/').isdigit():return p.hostname+'/'+p.path.strip('/')
    raise ValueError('Unsupported result post URL')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('input',type=Path)
    p.add_argument('--out',type=Path)
    p.add_argument('--no-activate',action='store_true')
    p.add_argument('--test',action='store_true')
    p.add_argument('--expected-queries',nargs='*')
    a=p.parse_args();raw=a.input.read_bytes();x=json.loads(raw.decode('utf-8-sig'))
    catalog=read(SOURCE/'catalog.json');all_expected={next(q for q in product['queries'] if any('가'<=c<='힣' for c in q)):product for product in catalog}
    if a.expected_queries:
        expected = {k: v for k, v in all_expected.items() if k in a.expected_queries}
        if len(x['results']) != len(expected) or {q['keyword'] for q in x['results']} != set(expected):
            raise ValueError(f'Device query panel mismatch for test: expected {set(expected)}')
    else:
        expected = all_expected
        if len(x['results'])!=27 or {q['keyword'] for q in x['results']}!=set(expected):
            raise ValueError('Device query panel mismatch')
    keys=[]
    for q in x['results']:
        u=urlparse(q['searchUrl']);params=parse_qs(u.query)
        if u.hostname!='search.naver.com' or params.get('ssc')!=['tab.blog.all'] or params.get('query')!=[q['keyword']]:raise ValueError('Capture surface mismatch')
        if [h['rank'] for h in q['rows']]!=list(range(1,len(q['rows'])+1)) or len(q['rows'])>30:raise ValueError('Invalid captured rank order')
        rowkeys=[identity(h['url']) for h in q['rows']]
        if len(rowkeys)!=len(set(rowkeys)):raise ValueError('Duplicate within query')
        keys+=rowkeys
    if len(keys)!=x['total'] or len(set(keys))!=x['uniqueCount']:raise ValueError('Capture total mismatch')
    sha=hashlib.sha256(raw).hexdigest();out=a.out.resolve() if a.out else ROOT/'data/blog_performance/browser-search'/('20261022-products-ko-'+sha[:10]);out.mkdir(parents=True,exist_ok=True)
    (out/'input.json').write_bytes(raw)
    rows=[{'keyword':q['keyword'],'product_id':expected[q['keyword']]['product_id'],'brand':expected[q['keyword']]['brand'],'group':expected[q['keyword']]['group'],'product':expected[q['keyword']]['product'],'captured_at':q['capturedAt'],'rows':q['rows']} for q in x['results']]
    save(out/'query-panel.json',{'rank_source':'user_supplied_browser_capture','search_surface':'naver_blog_tab','language':'ko_only','scope':x['scope'],'rows':rows})
    save(out/'manifest.json',{'rank_source':'user_supplied_browser_capture','raw_sha256':sha,'queries':len(expected),'rows':x['total'],'unique_posts':x['uniqueCount'],'naver_posts':sum('.tistory.com/' not in k for k in set(keys)),'external_tistory_posts':sum('.tistory.com/' in k for k in set(keys)),'english_capture_available':False})
    rel_base = str(out.relative_to(ROOT)) if out.is_relative_to(ROOT) else str(out)
    if not a.no_activate and not a.test:save(out.parent/'latest-products-ko.json',{'base':rel_base,'raw_sha256':sha})
    print(json.dumps({'base':rel_base,'queries':len(expected),'rows':len(keys),'unique_posts':len(set(keys))},ensure_ascii=False))

if __name__=='__main__':main()
