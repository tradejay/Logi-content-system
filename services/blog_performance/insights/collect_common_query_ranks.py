"""Common-query API ranks joined ONLY to saved body classifications. No crawling/AI."""
import argparse
import csv
import json
import hashlib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from services.blog_performance.competitor_engine import NaverBlogClient, extract_blog_id, extract_log_no

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'data/blog_performance/product-search/20261021T054347Z'
KEYWORDS=['화상회의','화상회의 장비','화상회의 구축','화상회의 솔루션','회의실 화상카메라','화상회의 장비 추천','화상회의 시스템 구축']

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,data):p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def key(url):
    blog=extract_blog_id(url);number=extract_log_no(url)
    return f'{blog}/{number}' if blog and number else None

def existing_index():
    base=SOURCE/'relevance-review/body-review'
    catalog={p['product_id']:p for p in read(SOURCE/'catalog.json')}
    candidates=read(base/'candidates.json')['items']
    names={x['candidate_id']:x for x in read(base/'equipment-name-candidates.json')['items']}
    reviews={x['candidate_id']:x for x in read(base/'reviewed-bodies.json')['items'] if x['decision'] in ['relevant','other_vc','irrelevant']}
    bodies={x['candidate_id']:x for x in read(base/'bodies.json')}
    index={}
    for c in candidates:
        cid=c['candidate_id'];m=names.get(cid,{});review=reviews.get(cid)
        body=bodies.get(cid,{})
        products=[]
        if body.get('status')=='success':
            products=review.get('product_ids',[]) if review else [pid for pid in m.get('catalog_product_candidates',[]) if catalog[pid]['brand'] in m.get('brand_candidates',[])]
            if review and review['decision']=='irrelevant':products=[]
        products=sorted(set(p for p in products if p in catalog))
        entry={'candidate_id':cid,'product_ids':products,'brands':sorted({catalog[p]['brand'] for p in products}),
               'classification_basis':'partial_ai_body_review' if review else 'literal_brand_model_match',
               'body_status':body.get('status'),'body_sha256':body.get('body_sha256')}
        for url in [c.get('url'),body.get('requested_url'),body.get('final_url')]:
            k=key(url) if url else None
            if k:index[k]=entry
        if c.get('post_key'):index[c['post_key']]=entry
    return index,catalog

def calculate(query_results,index,catalog,include_brand_only=False):
    matched=[];unmatched=[];unclassified=[]
    for q in query_results:
        seen=set()
        for h in q.get('hits',[]):
            k=key(h['post_url'])
            if k and k in seen:continue
            if k:seen.add(k)
            row={**h,'keyword':q['keyword'],'post_key':k}
            if k not in index:unmatched.append(row);continue
            row.update(index[k])
            if not row['product_ids'] and not (include_brand_only and row.get('brands')):unclassified.append(row);continue
            matched.append(row)
    def aggregate(mode):
        best={};posts=defaultdict(set);blogs=defaultdict(set)
        for h in matched:
            entities=h['brands'] if mode=='brand' else h['product_ids'] if mode=='product' else sorted({(catalog[p]['group'],catalog[p]['brand']) for p in h['product_ids']})
            for entity in entities:
                k=(entity,h['keyword'])
                if k not in best or h['rank']<best[k]['rank']:best[k]=h
                posts[entity].add(h['post_key']);blogs[entity].add(h['blog_id'])
        universe=sorted({p['brand'] for p in catalog.values()}) if mode=='brand' else list(catalog) if mode=='product' else sorted({(p['group'],p['brand']) for p in catalog.values()})
        output=[]
        for entity in universe:
            ranks=[]
            for q in query_results:
                h=best.get((entity,q['keyword']))
                ranks.append({'keyword':q['keyword'],'best_rank':h['rank'] if h else None,'url':h['post_url'] if h else None})
            score=100*sum(1/x['best_rank'] for x in ranks if x['best_rank'])/len(query_results)
            identity={'brand':entity} if mode=='brand' else {k:catalog[entity][k] for k in ['product_id','brand','product','group']} if mode=='product' else {'group':entity[0],'brand':entity[1]}
            output.append({**identity,'observed_score':round(score,6),'matched_posts':len(posts[entity]),'matched_blogs':len(blogs[entity]),'keyword_ranks':ranks})
        return sorted(output,key=lambda x:-x['observed_score'])
    return {'matched':matched,'unmatched':unmatched,'unclassified':unclassified,'brand_scores':aggregate('brand'),'product_scores':aggregate('product'),'theme_brand_scores':aggregate('theme_brand')}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path);parser.add_argument('--depth',type=int,default=1000);args=parser.parse_args()
    if not 1<=args.depth<=1000:raise SystemExit('depth must be 1..1000')
    out=args.out or ROOT/'data/blog_performance/common-query-search'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out.mkdir(parents=True,exist_ok=True);(out/'queries').mkdir(exist_ok=True)
    client=NaverBlogClient();results=[]
    save(out/'manifest.json',{'keywords':KEYWORDS,'depth':args.depth,'sort':'sim','classification_source':str(SOURCE.relative_to(ROOT)),'new_body_fetches':0,'model_api_calls':0})
    for i,kw in enumerate(KEYWORDS,1):
        path=out/'queries'/f'Q{i:02}.json'
        q=read(path) if path.exists() else None
        if not q or q.get('status')!='success':
            try:q={'keyword':kw,'depth':args.depth,'sort':'sim','observed_at':datetime.now(timezone.utc).isoformat(),'status':'success','hits':client.search_hits(kw,depth=args.depth,sort='sim')}
            except Exception as exc:
                save(path,{'keyword':kw,'status':'failed','error_type':type(exc).__name__})
                raise SystemExit(f'{kw}: collection failed ({type(exc).__name__}); no score published')
            save(path,q)
        if q['keyword']!=kw or q['depth']!=args.depth:raise SystemExit('incompatible cached query')
        results.append(q);print(json.dumps({'keyword':kw,'hits':len(q['hits']),'status':q['status']},ensure_ascii=False),flush=True)
    index,catalog=existing_index();result=calculate(results,index,catalog)
    for field in ['matched','unmatched','unclassified']:save(out/(field+'-hits.json'),result.pop(field))
    counts={field:len(read(out/(field+'-hits.json'))) for field in ['matched','unmatched','unclassified']}
    matched=read(out/'matched-hits.json')
    counts['unique_matched_posts']=len({h['post_key'] for h in matched})
    counts['duplicate_result_rows_skipped']=sum(len(q['hits']) for q in results)-sum(counts[k] for k in ['matched','unmatched','unclassified'])
    inputs=[SOURCE/'catalog.json']
    inputs += [SOURCE/'relevance-review/body-review'/name for name in ['candidates.json','equipment-name-candidates.json','reviewed-bodies.json','bodies.json']]
    report={'status':'existing_corpus_only_diagnostic','keywords':KEYWORDS,'depth':args.depth,'collected_at':[q['observed_at'] for q in results],
        'source_corpus':str(SOURCE.relative_to(ROOT)),'input_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},'new_body_fetches':0,'api_hit_rows':sum(len(q['hits']) for q in results),'coverage':counts,
        'formula':'100 * mean_over_7_queries(1 / best_original_api_rank_of_existing_classified_post); no match contributes 0 to observed lower bound only',
        'limitations':['기존 수집·분류된 글만의 관측 점수이며 전체 브랜드 검색 점수가 아님',
            '새 글·기존 미분류 글은 제외. 미노출 확정이나 0점 확정이 아님. 브랜드별 기존 표본 범위가 다름.',
            '같은 글의 여러 브랜드·장비는 각각 최고 순위 후보에 포함. 점수는 점유율이 아니며 브랜드 합계 100이 아님.',
            'AI 문맥 검토는 일부이며 나머지는 기존 브랜드·모델 문자열 매칭. API 원래 순위 유지, 필터 후 순위 당김 없음.',
            '브랜드와 제품군 점수는 해당 집단의 최고 순위로 직접 계산하며 장비 점수 평균이 아님. 신규 본문·AI 호출 없음.'],**result}
    save(out/'report.json',report)
    for field in ['brand_scores','product_scores','theme_brand_scores']:
        rows=[]
        for row in report[field]:rows.append({**{k:v for k,v in row.items() if k!='keyword_ranks'},**{x['keyword']:x['best_rank'] for x in row['keyword_ranks']}})
        with (out/(field+'.csv')).open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    lines=['# 공통 검색어 순위 · 기존 글 매칭 결과','','신규 본문 수집 없이 기존 본문 분류만 재사용한 제한 표본입니다. 전체 브랜드 노출 점수가 아닙니다.','',f'검색어 7개 × 상위 최대 {args.depth}개 · 원래 API 순위 보존',f'수집 결과 {report["api_hit_rows"]}행 · 분류 매칭 {counts["matched"]}행 ({counts["unique_matched_posts"]}개 고유 글) · 기존 미분류 {counts["unclassified"]}행 · 기존 후보 목록 밖 {counts["unmatched"]}행 · 동일 검색어 내 URL 중복 {counts["duplicate_result_rows_skipped"]}행 제외','','점수 = 100 × 7개 공통 검색어에서의 최고 순위 역수 평균. 관측되지 않은 검색어는 관측점 기여만 0이며 실제 미노출 확정은 아닙니다.','','|브랜드|기존 표본 관측점 /100|매칭 글|'+ '|'.join(KEYWORDS)+'|','|---|---:|---:|'+ '|'.join(['---:']*7)+'|']
    for row in report['brand_scores']:lines.append('|'+row['brand']+f'|{row["observed_score"]:.2f}|{row["matched_posts"]}|'+ '|'.join(str(x['best_rank']) if x['best_rank'] else '—' for x in row['keyword_ranks'])+'|')
    lines+=['','## 해석 한계',*['- '+x for x in report['limitations']]]
    (out/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(out),'coverage':counts,'brand_scores':[{k:r[k] for k in ['brand','observed_score','matched_posts']} for r in report['brand_scores']]},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
