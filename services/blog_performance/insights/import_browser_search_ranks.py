"""Import user-provided browser SERP order, without API calls or new body fetches."""
import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs,urlparse
from services.blog_performance.insights.collect_common_query_ranks import ROOT,SOURCE,KEYWORDS,key,existing_index,calculate,save,read


def validate(data, expected_keywords=None):
    expected = expected_keywords if expected_keywords is not None else KEYWORDS
    if set(q['keyword'] for q in data['results']) != set(expected) or len(data['results']) != len(expected):
        raise ValueError(f'Expected the {len(expected)} distinct queries: {expected}')
    depths=[];all_keys=[]
    for q in data['results']:
        u=urlparse(q['searchUrl']);params=parse_qs(u.query)
        if u.hostname!='search.naver.com' or params.get('ssc')!=['tab.blog.all'] or params.get('query')!=[q['keyword']]:
            raise ValueError('Search surface/query mismatch')
        datetime.fromisoformat(q['capturedAt'].replace('Z','+00:00'))
        ranks=[r['rank'] for r in q['rows']]
        if ranks!=list(range(1,len(ranks)+1)):raise ValueError('Ranks must preserve consecutive captured order')
        keys=[key(r['url']) for r in q['rows']]
        if None in keys or len(set(keys))!=len(keys):raise ValueError('Missing post identity or duplicate within query')
        depths.append(len(ranks));all_keys+=keys
    if len(set(depths))!=1 or depths[0]<1:raise ValueError('Inconsistent capture depths')
    if data['total']!=len(all_keys) or data['uniqueCount']!=len(set(all_keys)):raise ValueError('Capture totals mismatch')
    return depths[0]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('input',type=Path)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--no-activate',action='store_true')
    parser.add_argument('--test',action='store_true')
    parser.add_argument('--expected-keywords',nargs='*')
    args=parser.parse_args()
    raw=args.input.read_bytes()
    data=json.loads(raw.decode('utf-8-sig'))
    depth=validate(data, expected_keywords=args.expected_keywords)
    sha=hashlib.sha256(raw).hexdigest()
    out=args.out.resolve() if args.out else ROOT/'data/blog_performance/browser-search'/('20261022-common-'+sha[:10])
    out.mkdir(parents=True,exist_ok=True)
    if (out/'input.json').exists() and (out/'input.json').read_bytes()!=raw:raise ValueError('Raw source collision')
    (out/'input.json').write_bytes(raw)
    index,catalog=existing_index();queries=[]
    for q in data['results']:
        queries.append({'keyword':q['keyword'],'status':'success','observed_at':q['capturedAt'],'hits':[
            {'rank':r['rank'],'title':r['title'],'post_url':r['url'],'blog_id':key(r['url']).split('/')[0],'rank_source':'browser_capture'} for r in q['rows']]})
    result=calculate(queries,index,catalog)
    counts={field:len(result[field]) for field in ['matched','unmatched','unclassified']}
    counts['unique_matched_posts']=len({h['post_key'] for h in result['matched']})
    counts['unique_unmatched_posts']=len({h['post_key'] for h in result['unmatched']})
    query_coverage=[]
    for q in queries:
        k=q['keyword']
        query_coverage.append({'keyword':k,'captured_rows':len(q['hits']),**{f:sum(h['keyword']==k for h in result[f]) for f in ['matched','unmatched','unclassified']}})
    input_paths=[SOURCE/'catalog.json',*[SOURCE/'relevance-review/body-review'/n for n in ['candidates.json','equipment-name-candidates.json','reviewed-bodies.json','bodies.json']]]
    for field in ['matched','unmatched','unclassified']:save(out/(field+'-hits.json'),result.pop(field))
    kws = args.expected_keywords if args.expected_keywords else KEYWORDS
    report={'status':'browser_capture_existing_corpus_only','rank_source':'user_supplied_browser_capture','search_surface':'naver_blog_tab','sort':'relevance','ads':'excluded_per_source',
        'capture_scope':data.get('scope', '공통 검색어'),'captured_at':[q['capturedAt'] for q in data['results']],'depth':depth,'keywords':kws,
        'device':'not_recorded','login_state':'not_recorded','raw_sha256':sha,'classification_input_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in input_paths},
        'new_body_fetches':0,'api_calls':0,'source_rows':data['total'],'source_unique_posts':data['uniqueCount'],'coverage':counts,'query_coverage':query_coverage,
        'formula':f'100 * mean_over_{len(kws)}_queries(1 / best_captured_organic_blog_rank_of_existing_classified_post); unmatched contribution 0 is not confirmed absence',
        'limitations':[],**result}
    report['limitations']=['순위는 제공 파일의 블로그 탭 관련도순 첫 30개 일반 글 순서. 통합검색·스마트블록 순위가 아님.',
        '새 글은 수집·분류하지 않고 기존 27장비 본문 분류만 재사용. 기존 표본에 없는 글은 브랜드가 있어도 제외하므로 전체 브랜드 순위·점수 아님.',
        'AI 문맥 검토는 일부이고 나머지는 기존 브랜드·모델 문자열 매칭. 여러 브랜드를 다룬 글은 각 브랜드의 후보가 될 수 있음.',
        '—는 기존 분류 매칭 관측 없음. 실제 30위 밖·미노출·0점 확정이 아님.',
        'PC/모바일·로그인 상태는 파일에 미기록. 다른 시각·검색 영역·API 결과와 상승/하락 비교하지 않음.']
    save(out/'report.json',report)
    for field in ['brand_scores','product_scores','theme_brand_scores']:
        rows=[{**{k:v for k,v in r.items() if k!='keyword_ranks'},**{x['keyword']:x['best_rank'] for x in r['keyword_ranks']}} for r in report[field]]
        with (out/(field+'.csv')).open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    for field in ['unmatched','unclassified']:
        rows=read(out/(field+'-hits.json'))
        if rows:
            with (out/(field+'-results.csv')).open('w',newline='',encoding='utf-8-sig') as f:
                w=csv.DictWriter(f,fieldnames=['keyword','rank','blog_id','title','post_url']);w.writeheader();w.writerows({k:r.get(k) for k in w.fieldnames} for r in rows)
    lines=['# 실제 블로그 탭 검색 순서 · 기존 글 매칭','','제공 파일을 그대로 보존하고, 기존 분류만 연결했습니다. 새 본문 수집·API 호출은 없습니다.','',
        f'검색어 {len(kws)}개 × 첫 {depth}개 · 결과 {data["total"]}건 · 고유 글 {data["uniqueCount"]}개',
        f'장비 분류 매칭 {counts["matched"]}건 / 고유 글 {counts["unique_matched_posts"]}개 · 기존 미분류 {counts["unclassified"]}건 · 기존 후보 밖 {counts["unmatched"]}건','',
        '|브랜드|제한 표본 관측점|'+ '|'.join(kws)+'|','|---|---:|'+ '|'.join(['---:']*len(kws))+'|']
    for r in report['brand_scores']:lines.append('|'+r['brand']+f'|{r["observed_score"]:.2f}|'+ '|'.join(str(x['best_rank']) if x['best_rank'] else '—' for x in r['keyword_ranks'])+'|')
    lines+=['','## 수집 범위',*['- '+s for s in report['limitations']]]
    (out/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    rel_report = str((out/'report.json').relative_to(ROOT)) if (out/'report.json').is_relative_to(ROOT) else str(out/'report.json')
    rel_out = str(out.relative_to(ROOT)) if out.is_relative_to(ROOT) else str(out)
    if not args.no_activate and not args.test:
        save(out.parent/'latest-common.json',{'report':rel_report,'raw_sha256':sha,'rank_source':report['rank_source']})
    print(json.dumps({'output':rel_out,'coverage':counts,'query_coverage':query_coverage,'brands':[{k:r[k] for k in ['brand','observed_score','matched_posts']} for r in report['brand_scores']]},ensure_ascii=False))
    print(json.dumps({'output':rel_out,'coverage':counts,'query_coverage':query_coverage,'brands':[{k:r[k] for k in ['brand','observed_score','matched_posts']} for r in report['brand_scores']]},ensure_ascii=False))

if __name__=='__main__':main()
