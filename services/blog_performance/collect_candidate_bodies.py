"""Fetch the exact candidate posts, preserving title decisions and full body evidence."""
import csv
import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from .blog_analyzer import post_identity
from .collect_product_search import write_json, export_csv
from .competitor_engine import POST_BODY_SELECTORS, parse_post_html

ROOT=Path(__file__).resolve().parents[2]
REVIEW=ROOT/'data/blog_performance/product-search/20261021T054347Z/relevance-review'
LOCK=threading.Lock()
LAST=0.0


def pace():
    global LAST
    with LOCK:
        delay=.5-(time.monotonic()-LAST)
        if delay>0:time.sleep(delay)
        LAST=time.monotonic()


def fetch(row,out,path_root=None):
    folder=out/'raw'/row['candidate_id'];folder.mkdir(parents=True,exist_ok=True)
    prior=folder/'body.json'
    if prior.exists():
        old=json.loads(prior.read_text(encoding='utf-8'))
        if old.get('status')=='success':return old
    result={'candidate_id':row['candidate_id'],'blog_id':row['blog_id'],'requested_url':row['url'],
            'status':'failed','fetched_at':datetime.now(timezone.utc).isoformat(),
            'title_review':row['title_review'],'eligible_for_scoring':False}
    identity=post_identity(row['url'])
    if identity is None or identity[0]!=row['blog_id']:
        result['reason']='candidate_url_identity_mismatch';write_json(prior,result);return result
    url=f'https://m.blog.naver.com/{identity[0]}/{identity[1]}'
    result['fetch_url']=url
    for attempt in range(2):
        try:
            pace()
            response=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=15)
            result['http_status']=response.status_code
            result['final_url']=response.url
            if response.status_code!=200:
                result['reason']='http_error'
                if response.status_code in [429,500,502,503,504] and attempt==0:
                    time.sleep(3);continue
                break
            if post_identity(response.url)!=identity:
                result['reason']='redirected_to_different_post';break
            soup=BeautifulSoup(response.content,'html.parser')
            body=None
            for selector in POST_BODY_SELECTORS:
                body=soup.select_one(selector)
                if body is not None:break
            if body is None:
                result['reason']='body_container_missing';break
            for junk in body.select('script,style,noscript'):junk.decompose()
            text=body.get_text('\n',strip=True)
            if len(text)<100:
                result['reason']='body_too_short';break
            og=soup.select_one('meta[property="og:title"]')
            title=og.get('content','') if og else row['titles'][0]
            html_path=folder/'post.html';html_path.write_bytes(response.content)
            (folder/'body.txt').write_text(text,encoding='utf-8')
            metrics=parse_post_html(response.text) or {}
            result.update(status='success',actual_title=title,body_text=text,
                          body_sha256=hashlib.sha256(text.encode()).hexdigest(),
                          html_sha256=hashlib.sha256(response.content).hexdigest(),
                          char_count=metrics.get('char_count'),image_count=metrics.get('image_count'),
                          body_file=str((folder/'body.txt').relative_to(path_root or REVIEW)),
                          html_file=str(html_path.relative_to(path_root or REVIEW)))
            result.pop('reason',None)
            break
        except Exception as error:
            result['reason']=type(error).__name__
    write_json(prior,result)
    return result


def main():
    source=json.loads((REVIEW/'title-review-queue.json').read_text(encoding='utf-8'))
    candidates=[r for r in source['items'] if r['title_review']['decision'] in ['keep','uncertain']]
    out=REVIEW/'body-review';out.mkdir(exist_ok=True)
    membership={'scope':'user_expanded_title_candidates','keep_title_count':433,'uncertain_promoted_count':513,
                'candidate_count':len(candidates),'items':[
                    {**r,'candidate_included':True,'inclusion_basis':'user_included_uncertain' if r['title_review']['decision']=='uncertain' else 'title_keep'} for r in candidates]}
    write_json(out/'candidates.json',membership)
    export_csv(out/'candidate-titles.csv',[{'candidate_id':r['candidate_id'],'title':r['titles'][0],
               'url':r['url'],'blog_id':r['blog_id'],'original_title_decision':r['title_review']['decision']} for r in candidates],
               ['candidate_id','title','url','blog_id','original_title_decision'])
    rows=[]
    write_json(out/'collection-progress.json',{'status':'running','total':len(candidates),'completed':0})
    print(f'Collecting exact post bodies: {len(candidates)} candidates',flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(fetch,r,out):r for r in candidates}
        for future in as_completed(futures):
            rows.append(future.result())
            progress={'status':'running','total':len(candidates),'completed':len(rows),
                      'success':sum(r['status']=='success' for r in rows),'failed':sum(r['status']!='success' for r in rows)}
            write_json(out/'collection-progress.json',progress)
            if len(rows)%50==0:print(json.dumps(progress),flush=True)
    rows.sort(key=lambda r:r['candidate_id'])
    write_json(out/'bodies.json',rows)
    progress['status']='completed';write_json(out/'collection-progress.json',progress)
    export_csv(out/'collection.csv',[{k:v for k,v in r.items() if k not in ['body_text','title_review']} for r in rows],
               ['candidate_id','blog_id','requested_url','fetch_url','final_url','status','reason','http_status','fetched_at',
                'actual_title','char_count','image_count','body_file','html_file','body_sha256','html_sha256','eligible_for_scoring'])
    print(json.dumps(progress),flush=True)


if __name__=='__main__':main()
