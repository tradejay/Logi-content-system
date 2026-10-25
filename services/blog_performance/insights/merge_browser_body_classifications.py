"""Merge machine body matches and compact term decisions into browser-only scores."""
import argparse,csv,hashlib,json,re
from collections import Counter
from pathlib import Path
from services.blog_performance.insights.collect_common_query_ranks import ROOT,SOURCE,read,save,key,calculate
from services.blog_performance.insights.analyze_browser_search_bodies import paths,ALIASES

STRONG={
 'HP Poly':r'\bpolycom\b|\bpoly\s+(?:studio|[xg]\s*\d|tc\s*\d)|폴리콤|폴리\s*스튜디오',
 'AVer':r'(?<![a-z0-9])aver(?![a-z0-9])|에버\s*(?:vb|vc|cam)',
 'Neat':r'\bneat\s+(?:bar|board|center|pad|frame)\b|니트\s*(?:바|보드|센터|패드|프레임)'}

def build_classifications(out,result_path):
    ai=read(result_path);expected={x['id'] for x in read(out/'ai-terms.json')['items']}
    decisions=ai.get('decisions',[]);ids=[x['id'] for x in decisions]
    if set(ids)!=expected or len(ids)!=len(set(ids)):raise ValueError('AI term IDs missing, extra, or duplicated')
    if ai.get('passed') is not True:raise ValueError('AI work not completed')
    allowed={'catalog_model','outside_model','other_equipment','generic','uncertain'}
    if any(d['category'] not in allowed for d in decisions):raise ValueError('Unknown classification category')
    save(out/'ai-decisions.json',ai)
    terms=read(out/'model-terms.json')['items'];term_map={d['id']:d for d in decisions};catalog={p['product_id']:p for p in read(SOURCE/'catalog.json')}
    for t in terms:
        if t['id'] not in term_map:
            old=t['prior_decision'];term_map[t['id']]={**old,'id':t['id'],'brand':old.get('researched_brand') or old.get('brand'),'model':old.get('researched_model') or old.get('model'),'product_ids':[]}
    by_post={}
    for t in terms:
        d=term_map[t['id']]
        for pid in t['post_ids']:by_post.setdefault(pid,[]).append(d)
    bodies={b['candidate_id']:b for b in read(out/'bodies.json')};index={};records=[]
    for row in read(out/'classifications.json')['items']:
        b=bodies[row['id']];text=b.get('body_text','');products=set(row['product_ids']);brands={catalog[p]['brand'] for p in products}
        evidence=[]
        for brand in row['brand_candidates']:
            if brand not in STRONG or re.search(STRONG[brand],text,re.I):brands.add(brand);evidence.append({'brand':brand,'basis':'explicit_body_brand_name'})
        term_models=[]
        for d in by_post.get(row['id'],[]):
            if d['category'] not in ['catalog_model','outside_model','other_equipment'] or not d.get('brand') or not d.get('model'):continue
            term_models.append(d)
            if d['brand'] in ALIASES and d['brand'] in row['brand_candidates']:
                brands.add(d['brand']);evidence.append({'brand':d['brand'],'basis':'model_term_identification','term_id':d['id'],'model':d['model'],'category':d['category']})
            for p in d.get('product_ids',[]) or []:
                if p in catalog and catalog[p]['brand']==d['brand'] and d['brand'] in row['brand_candidates']:products.add(p)
        entry={'candidate_id':row['id'],'product_ids':sorted(products),'brands':sorted(brands),'classification_basis':'all_result_bodies_literal_brand_model_plus_term_review','body_status':b['status'],'body_sha256':b.get('body_sha256')}
        index[row['post_key']]=entry
        records.append({**row,**entry,'brand_evidence':evidence,'identified_other_models':term_models,'unresolved_terms':[d['id'] for d in by_post.get(row['id'],[]) if d['category']=='uncertain']})
    save(out/'final-classifications.json',{'status':'body_machine_matches_and_model_term_candidates','items':records})
    return index,records,bodies,terms,decisions,term_map,catalog

def main():
    a=argparse.ArgumentParser();a.add_argument('--result',type=Path,required=True);a.add_argument('--base',type=Path);a.add_argument('--no-activate',action='store_true');args=a.parse_args()
    base,out=(args.base.resolve(),args.base.resolve()/'body-analysis') if args.base else paths()
    index,records,bodies,terms,decisions,term_map,catalog=build_classifications(out,args.result)
    raw=read(base/'input.json');queries=[{'keyword':q['keyword'],'hits':[{'rank':h['rank'],'title':h['title'],'post_url':h['url'],'blog_id':key(h['url']).split('/')[0],'rank_source':'browser_capture'} for h in q['rows']]} for q in raw['results']]
    result=calculate(queries,index,catalog,include_brand_only=True)
    counts={k:len(result[k]) for k in ['matched','unmatched','unclassified']};counts['unique_matched_posts']=len({h['post_key'] for h in result['matched']})
    for field in ['matched','unmatched','unclassified']:save(out/(field+'-hits.json'),result.pop(field))
    prior=read(base/'report.json');report={**prior,'status':'browser_capture_all_bodies_classified_candidates','classification_scope':'all_browser_result_bodies','classification_method':'explicit_brand_names_and_catalog_matching_with_unknown_term_AI','coverage':counts,'new_body_fetches':sum(b['body_source']=='new_body_fetch' for b in bodies.values()),
       'body_collection':{'total':len(bodies),'success':sum(b['status']=='success' for b in bodies.values()),'reused':sum(b['body_source']=='reused_existing' for b in bodies.values())},
       'term_review':{'total':len(terms),'new_ai_decisions':len(decisions),'reused_prior':len(terms)-len(decisions),'counts':dict(Counter(d['category'] for d in term_map.values()))},
       'ai_result_sha256':hashlib.sha256(args.result.read_bytes()).hexdigest(),**result}
    report['limitations']=['순위는 사용자 제공 블로그 탭 첫 30개 일반 글의 화면 순서. 통합검색·API 순서가 아님.',
      '수집 글의 본문에서 브랜드·등록 장비를 기계 매칭하고, 미확정 글의 영문숫자 모델 후보를 AI가 식별했다. 글 전문의 의미·추천 여부를 전수 AI 판정한 것은 아니다.',
      '브랜드가 명시되면 장비가 기존 목록 밖이어도 브랜드 점수에 포함한다. 모델 미확정·다른 브랜드·일반 글은 별도 기록한다. 여러 브랜드 글은 각 브랜드에 중복될 수 있다.',
      '순위는 원래 화면 순서 유지. —는 이 표본에서 브랜드 분류 연결이 없다는 뜻이며 실제 미노출·30위 밖을 확정하지 않는다.',
      'PC/모바일·로그인 상태 미기록. 이전 API 점수와 상승·하락 비교하지 않는다.']
    save(out/'report.json',report)
    for field in ['brand_scores','product_scores','theme_brand_scores']:
        rows=[{**{k:v for k,v in r.items() if k!='keyword_ranks'},**{x['keyword']:x['best_rank'] for x in r['keyword_ranks']}} for r in report[field]]
        with (out/(field+'.csv')).open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    if not args.no_activate:save(base.parent/'latest-common.json',{'report':str((out/'report.json').relative_to(ROOT)),'raw_sha256':prior['raw_sha256'],'rank_source':report['rank_source']})
    print(json.dumps({'coverage':counts,'body_collection':report['body_collection'],'term_review':report['term_review'],'brands':[{k:r[k] for k in ['brand','observed_score','matched_posts']} for r in report['brand_scores']]},ensure_ascii=False))

if __name__=='__main__':main()
