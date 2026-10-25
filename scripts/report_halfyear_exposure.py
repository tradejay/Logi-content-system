"""Publication-cohort views of one current snapshot; never historical ranks."""
import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from services.blog_performance.product_competitiveness import calculate

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/blog_performance/product-search/20261021T054347Z'
DEST=SOURCE/'name-matched-diagnostic'
PERIODS=[('2024H1','2024 H1'),('2024H2','2024 H2'),('2025H1','2025 H1'),('2025H2','2025 H2'),('2026H1','2026 H1')]
def read(path):return json.loads(path.read_text(encoding='utf-8'))

def main():
    hits=read(DEST/'matched-hits.json');catalog=read(SOURCE/'catalog.json');queries=read(SOURCE/'query-results.json')
    dates=defaultdict(set)
    for h in hits:dates[h['post_key']].add(h.get('published_date'))
    date_map={};date_issues=[]
    for key,values in dates.items():
        period=None
        try:
            if len(values)!=1:raise ValueError('conflicting publication dates')
            raw=next(iter(values))
            if raw in {None,'','19900101'}:raise ValueError('missing or placeholder date')
            day=datetime.strptime(raw,'%Y%m%d')
            if day>datetime(2026,10,21):raise ValueError('date after snapshot')
            period=f'{day.year}H{1 if day.month<=6 else 2}'
        except (ValueError,TypeError) as ex:date_issues.append({'post_key':key,'dates':list(values),'reason':str(ex)})
        date_map[key]=period
    periods=[]
    for code,label in PERIODS:
        subset=[h for h in hits if date_map[h['post_key']]==code]
        calc=calculate(catalog,queries,subset)
        ps=[]
        for p in catalog:
            hs=[h for h in subset if h['product_id']==p['product_id']]
            scores=[x for x in calc['product_scores'] if x['product_id']==p['product_id']]
            ps.append({**{k:p[k] for k in ['product_id','brand','group','product']},'posts':len({h['post_key'] for h in hs}),'blogs':len({h['blog_id'] for h in hs if h['blog_id']}),
              'observed_score_sum':round(sum(x['search_competitiveness'] for x in scores),2),
              'own_score':next((x['search_competitiveness'] for x in scores if x['blog_id']=='oceantech01'),0)})
        def aggregate(fields):
            rows=[]
            for key in sorted({tuple(p[f] for f in fields) for p in ps}):
                members=[p for p in ps if tuple(p[f] for f in fields)==key];ids={p['product_id'] for p in members};hs=[h for h in subset if h['product_id'] in ids]
                rows.append({**dict(zip(fields,key)),'products':len(members),'posts':len({h['post_key'] for h in hs}),'blogs':len({h['blog_id'] for h in hs if h['blog_id']}),
                  'index':round(sum(p['observed_score_sum'] for p in members)/len(members),2)})
            return sorted(rows,key=lambda row:-row['index'])
        periods.append({'period':code,'label':label,'posts':len({h['post_key'] for h in subset}),'blogs':len({h['blog_id'] for h in subset if h['blog_id']}),'hit_rows':len(subset),
          'brands':aggregate(['brand']),'themes':aggregate(['group']),'theme_brands':aggregate(['brand','group']),'products':ps,
          'top_blogs':[{'blog_id':x['blog_id'],'score':x['search_competitiveness'],'products':x['ranked_products']} for x in calc['blogs'][:5]]})
    excluded={}
    for period in sorted({v for v in date_map.values() if v and v not in dict(PERIODS)}):excluded[period]=sum(v==period for v in date_map.values())
    out={'status':'publication_cohort_of_current_snapshot_only','rank_snapshot':'2026-10-21','historical_ranks_available':False,
      'date_basis':'Search API published_date, not last-modified date','method':'Same 27-product/54-query panel and current original API ranks; recalculate best rank per blog within each publication cohort. Period scores are not additive.',
      'limitations':['현재 TOP100에 남은 글의 발행 반기 분포이며 과거 전체 발행량이 아님.','2024~2026년 당시의 순위나 점수 변화가 아님.','반기별 점수는 현재 관측 순위로 별도 계산했으므로 합산 불가.','고정된 27개 제품에는 당시 미출시 모델이 있을 수 있어 브랜드 성장률로 해석 불가.','0은 현재 표본에 매칭 관측이 없다는 뜻이며 당시 글이 없었다는 뜻이 아님.','발행일을 사용하며 실제 수정일·수집 누락은 반영하지 못함.'],
      'periods':periods,'outside_period_posts':excluded,'unknown_date_posts':len(date_issues),'date_issues':date_issues,
      'total_matched_unique_posts':len(date_map)}
    (DEST/'halfyear-report.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    for name,field in [('halfyear-brands','brands'),('halfyear-theme-brands','theme_brands'),('halfyear-products','products')]:
        flat=[{'period':p['period'],'label':p['label'],**row} for p in periods for row in p[field]]
        with (DEST/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
    assert sum(p['posts'] for p in periods)+sum(excluded.values())+len(date_issues)==len(date_map)
    print(json.dumps({'periods':[{'label':p['label'],'posts':p['posts'],'blogs':p['blogs'],'top_brand':p['brands'][0]['brand']} for p in periods],'outside_period_posts':excluded,'unknown_dates':len(date_issues)},ensure_ascii=False))

if __name__=='__main__':main()
