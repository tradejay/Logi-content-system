"""Read-only analytical report, not the blocked/active production score release."""
import json
from collections import defaultdict
from pathlib import Path
from services.blog_performance.product_competitiveness import calculate

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/blog_performance/product-search/20261021T054347Z'
def read(p):return json.loads(p.read_text(encoding='utf-8'))

def main():
    base=SOURCE/'relevance-review/body-review'
    catalog=read(SOURCE/'catalog.json');queries=read(SOURCE/'query-results.json');hits=read(SOURCE/'search-hits.json')
    products={p['product_id']:p for p in catalog}
    match={x['candidate_id']:x for x in read(base/'equipment-name-candidates.json')['items']}
    candidates=read(base/'candidates.json')['items'];by_key={r['post_key']:r['candidate_id'] for r in candidates}
    reviewed={r['candidate_id']:r for r in read(base/'reviewed-bodies.json')['items'] if r['decision'] in ['relevant','other_vc','irrelevant']}
    selected=[]
    for h in hits:
        cid=by_key.get(h['post_key']);m=match.get(cid)
        if not m:continue
        if cid in reviewed:
            if h['product_id'] in reviewed[cid]['product_ids']:selected.append(h)
        elif h['product_id'] in m['catalog_product_candidates'] and products[h['product_id']]['brand'] in m['brand_candidates']:
            selected.append(h)
    result=calculate(catalog,queries,selected)
    rows=[]
    for p in catalog:
        subset=[h for h in selected if h['product_id']==p['product_id']]
        scores=[r for r in result['product_scores'] if r['product_id']==p['product_id']]
        own=next((r for r in scores if r['blog_id']=='oceantech01'),None)
        top=sorted([r for r in scores if r['search_competitiveness']>0],key=lambda r:-r['search_competitiveness'])[:3]
        mine=[{'query':h['query'],'rank':h['rank'],'url':h['url']} for h in subset if h['blog_id']=='oceantech01']
        rows.append({**{k:p[k] for k in ['product_id','brand','product','group']},
          'matched_posts':len({h['post_key'] for h in subset}),'matched_blogs':len({h['blog_id'] for h in subset if h['blog_id']}),
          'observed_blog_score_sum':round(sum(r['search_competitiveness'] for r in scores),2),
          'own_observed_score':own['search_competitiveness'] if own else 0,
          'own_ranks':mine,'top_blogs':[{'blog_id':r['blog_id'],'score':r['search_competitiveness']} for r in top]})
    def group(fields):
        out=[];keys=sorted({tuple(r[f] for f in fields) for r in rows})
        for key in keys:
            ps=[r for r in rows if tuple(r[f] for f in fields)==key];ids={r['product_id'] for r in ps};hs=[h for h in selected if h['product_id'] in ids]
            out.append({**dict(zip(fields,key)),'products':len(ps),
             'matched_posts':len({h['post_key'] for h in hs}),'matched_blogs':len({h['blog_id'] for h in hs if h['blog_id']}),
             'observed_exposure_index':round(sum(r['observed_blog_score_sum'] for r in ps)/len(ps),2)})
        return sorted(out,key=lambda r:-r['observed_exposure_index'])
    report={'status':'diagnostic_only_not_validated_brand_score','snapshot':'2026-10-21','generated':'2026-10-22',
      'formula':'blog_product=100*mean(1/best_query_rank); brand=mean_over_products(sum_over_blogs(blog_product))',
      'formula_ko':'기존식 유지: 블로그별 제품점수=100×별칭 검색별 최고순위 역수 평균. 브랜드 지표=제품별 블로그점수 합계의 제품 평균. 합산 지표이므로 100점 상한 없음.',
      'limitations':['AI 본문 검토는 일부만 완료. 나머지는 브랜드·모델 문자열 매칭 후보다.','본문 부족 14개와 브랜드만 발견된 글은 해당 제품 확인이 안 돼 이 집계에 포함하지 않음. 0점 확정이 아님.','네이버 공식 점수·글 품질·판매량·충성도·시장점유율을 나타내지 않음.','API 원래 순위 유지. 통합검색/스마트블록 순위와 다름.','후보 946개 대상. 제외된 865개 제목 판정의 누락 가능성 잔존.'],
      'original_hits':len(hits),'retained_hits':len(selected),'products':rows,'brands':group(['brand']),'themes':group(['group']),'theme_brands':group(['group','brand'])}
    dest=SOURCE/'name-matched-diagnostic';dest.mkdir(exist_ok=True)
    (dest/'matched-hits.json').write_text(json.dumps(selected,ensure_ascii=False,indent=2),encoding='utf-8')
    (dest/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 장비명 기반 잠정 검색 노출 집계','','최종 브랜드 점수 아님. 수집: 2026-10-21, 분석: 2026-10-22. 기존 점수 릴리스는 변경하지 않았다.','',report['formula_ko'],'',*['- '+s for s in report['limitations']]]
    for field,label in [('brands','브랜드별'),('theme_brands','분류별 브랜드')]:
        lines+=['','## '+label,'','|분류|브랜드|제품수|매칭 글|블로그|잠정 노출 지표|','|---|---|---:|---:|---:|---:|']
        for r in report[field]:lines.append(f"|{r.get('group','전체')}|{r['brand']}|{r['products']}|{r['matched_posts']}|{r['matched_blogs']}|{r['observed_exposure_index']}|")
    lines+=['','## 제품별','','|분류|브랜드|제품|매칭 글|블로그|노출점 합산|오우션 관측점|주요 기여 블로그|','|---|---|---|---:|---:|---:|---:|---|']
    for r in rows:
        blogs=' · '.join(f"[{x['blog_id']}](https://blog.naver.com/{x['blog_id']}) {x['score']:.2f}" for x in r['top_blogs'])
        lines.append(f"|{r['group']}|{r['brand']}|{r['product']}|{r['matched_posts']}|{r['matched_blogs']}|{r['observed_blog_score_sum']}|{r['own_observed_score']}|{blogs}|")
    (dest/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['retained_hits','brands','theme_brands','products']},ensure_ascii=False))

if __name__=='__main__':main()
