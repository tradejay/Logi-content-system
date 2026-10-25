"""Observed product-search competitiveness, not an estimate of Naver's internal score."""
import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .collect_product_search import write_json, export_csv

ROOT = Path(__file__).resolve().parents[2]
VERSION = 'product-search-competitiveness-v1'


def calculate(catalog, queries, hits, own_blog='oceantech01', auxiliary=None):
    query_map = {r['query_id']: r for r in queries}
    products = {r['product_id']: r for r in catalog}
    product_queries = {pid: [q for q in queries if q['product_id']==pid] for pid in products}
    # Only successful observations may produce a measured nonappearance (zero).
    best = {}
    posts = defaultdict(set)
    for hit in hits:
        query = query_map.get(hit['query_id'])
        blog = hit.get('blog_id')
        if not query or query['status']!='success' or not blog:
            continue
        rank = hit['rank']
        if rank < 1:
            raise ValueError('Rank must be positive')
        key = (hit['query_id'], blog)
        best[key] = min(rank, best.get(key, rank))
        posts[(hit['product_id'], blog)].add(hit['post_key'])
    blogs = sorted({b for _, b in best} | {own_blog})
    valid_count = sum(q['status']=='success' for q in queries)
    # Compare one fixed panel; no renormalization over a lucky subset of successful queries.
    panel_complete = len(queries)==sum(len(p['queries']) for p in catalog) and all(
        len(product_queries[p])==len(products[p]['queries']) and all(q['status']=='success' for q in product_queries[p]) for p in products)
    by_product, output = [], []
    aux_map = {r['blog_id']:r for r in (auxiliary or [])}
    for blog in blogs:
        values = []
        product_scores = []
        ranked_products, distinct_posts = set(), set()
        for pid, product in products.items():
            qs = product_queries[pid]
            complete = len(qs)==len(product['queries']) and all(q['status']=='success' for q in qs)
            ranks = [best.get((q['query_id'],blog)) for q in qs]
            score = round(100*sum(1/r if r else 0 for r in ranks)/len(qs), 4) if complete and qs else None
            if any(ranks): ranked_products.add(pid)
            distinct_posts.update(posts[(pid,blog)])
            by_product.append({'blog_id':blog, 'product_id':pid, 'brand':product['brand'], 'product':product['product'],
                               'group':product['group'], 'search_competitiveness':score,
                               'observed_queries':sum(q['status']=='success' for q in qs), 'planned_queries':len(product['queries']),
                               'ranked_queries':sum(r is not None for r in ranks), 'best_rank':min((r for r in ranks if r),default=None),
                               'unique_posts':len(posts[(pid,blog)])})
            if score is not None: product_scores.append(score)
            values.extend(r for r in ranks if r is not None)
        auxiliary_row = aux_map.get(blog)
        output.append({'blog_id':blog, 'is_own':blog==own_blog,
                       'search_competitiveness':round(sum(product_scores)/len(products),4) if panel_complete else None,
                       'ranked_products':len(ranked_products), 'ranked_queries':len(values),
                       'top10_queries':sum(r<=10 for r in values), 'top30_queries':sum(r<=30 for r in values),
                       'unique_posts':len(distinct_posts),
                       'observation':{'successful_queries':valid_count, 'planned_queries':len(queries),
                                      'collection_coverage':round(valid_count/len(queries),4) if queries else None,
                                      'snapshot_count':1, 'temporal_stability':'not_measured',
                                      'product_relevance':'not_semantically_verified',
                                      'evidence_scope':'search_API_top100_candidate_panel'},
                       'auxiliary':auxiliary_row})
    output.sort(key=lambda r:(r['search_competitiveness'] is None,-(r['search_competitiveness'] or 0),r['blog_id']))
    # Tied observed scores share a position; not percentile-calibrated Naver grades.
    previous = None
    for index, row in enumerate(output,1):
        if row['search_competitiveness'] is None:
            row['panel_position'] = None
        else:
            if row['search_competitiveness'] != previous:
                position = index
            row['panel_position'] = position
            previous = row['search_competitiveness']
    return {'version':VERSION, 'status':'provisional_observed_competitiveness',
            'panel_complete':panel_complete, 'product_count':len(products), 'query_count':len(queries),
            'formula':'100 * mean_over_products(mean_over_alias_queries(1/best_rank; observed_absence=0))',
            'source_grade':None, 'temporal_score':None, 'blogs':output, 'product_scores':by_product}


def generate(source):
    source = Path(source)
    catalog = json.loads((source/'catalog.json').read_text(encoding='utf-8'))
    queries = json.loads((source/'query-results.json').read_text(encoding='utf-8'))
    hits = json.loads((source/'search-hits.json').read_text(encoding='utf-8'))
    review_folder = source/'relevance-review'
    verified_file = review_folder/'body-review/reviewed-bodies.json'
    body_review = None
    source_hit_count = len(hits)
    if review_folder.exists():
        if not verified_file.exists():
            raise ValueError('Body relevance review is required before product scores can be generated')
        body_review = json.loads(verified_file.read_text(encoding='utf-8'))
        if body_review.get('status') != 'completed' or body_review.get('counts', {}).get('pending', 1):
            raise ValueError('Body relevance review has not completed')
        if body_review.get('counts', {}).get('fetch_failed', 0) or body_review.get('counts', {}).get('uncertain', 0):
            raise ValueError('Unresolved body evidence remains; do not score failed or uncertain posts as zero')
        membership = json.loads((review_folder/'body-review/candidates.json').read_text(encoding='utf-8'))
        by_id = {r['candidate_id']: r for r in body_review['items']}
        by_key = {r['post_key']: by_id.get(r['candidate_id']) for r in membership['items']}
        hits = [h for h in hits if by_key.get(h['post_key']) and by_key[h['post_key']].get('eligible_for_scoring')
                and h['product_id'] in by_key[h['post_key']]['product_ids']]
    aux_paths = sorted(source.glob('enrichment/*/observations.json'))
    auxiliary = json.loads(aux_paths[-1].read_text(encoding='utf-8')) if aux_paths else []
    result = calculate(catalog,queries,hits,auxiliary=auxiliary)
    if body_review is not None:
        result.update(version='product-search-competitiveness-v2-body-verified',
                      status='body_reviewed_observed_competitiveness',
                      relevance_scope='AI body relevance with matched evidence; not factual spec verification',
                      original_search_hits=source_hit_count, verified_search_hits=len(hits),
                      body_review_counts=body_review['counts'])
        for row in result['blogs']:
            row['observation']['product_relevance']='body_reviewed_for_catalog_product'
            row['observation']['evidence_scope']='search_API_top100_filtered_by_exact_post_body'
    result['source_directory'] = str(source.resolve())
    result['generated_at'] = datetime.now(timezone.utc).isoformat()
    result['input_hashes'] = {name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in ['catalog.json','query-results.json','search-hits.json']}
    if aux_paths:
        result['auxiliary_source'] = str(aux_paths[-1].resolve())
    target = source/('competitiveness-v2-verified' if body_review is not None else 'competitiveness-v1')
    target.mkdir(exist_ok=True)
    from .panel_aggregates import export_aggregates
    export_aggregates(result,target)
    from .brand_exposure import breakdown
    query_rows, brand_rows = breakdown(catalog,queries,hits,[r['blog_id'] for r in result['blogs']])
    result['query_rankings'] = [r for r in query_rows if r['status']=='ranked']
    result['brand_exposure'] = brand_rows
    result['brand_profile_interpretation'] = 'Blog-level observed search exposure, not verified company identity, sales share or brand loyalty'
    write_json(target/'results.json',result)
    if body_review is not None:
        write_json(target/'verified-search-hits.json', hits)
    export_csv(target/'query-blog-ranks.csv',query_rows,list(query_rows[0]))
    export_csv(target/'brand-exposure.csv',brand_rows,list(brand_rows[0]))
    report=['# 검색어별 블로그 순위와 브랜드 노출 편중', '',
            '업체 단위는 현재 블로그 ID다. 같은 회사의 여러 블로그를 자동 합치지 않았다. 표시 이름은 검색 API 블로그명이며 법인명이 아니다.',
            'API 순위는 게시글의 검색 API 결과 위치, 블로그 위치는 해당 검색어에서 중복 블로그를 제거한 순서다.',
            '브랜드 검색 강도는 제품별 별칭 최고순위 역수 평균 ×100. 브랜드별 제품 수를 평균으로 보정한 뒤 강도 합계 대비 비중을 계산한다.',
            '비중은 검색 노출 편중이며 실제 충성도·취급 제품·판매량·긍정적 언급을 의미하지 않는다. 제품 혼입도 미검토다.', '']
    for q in queries:
        ranked=sorted([r for r in query_rows if r['query_id']==q['query_id'] and r['status']=='ranked'],key=lambda r:r['api_rank'])
        shown=ranked[:10]
        mine=next((r for r in ranked if r['blog_id']=='oceantech01'),None)
        if mine and mine not in shown: shown.append(mine)
        report += [f'## {q["query"]}', '', '|API 순위|블로그 위치|블로그|대표 글|', '|---:|---:|---|---|']
        report += [f'|{r["api_rank"]}|{r["blog_position"]}|{r["blog_id"]}|[{r["representative_title"].replace("|"," ")}]({r["representative_url"]})|' for r in shown]
        if not mine: report.append('\n오우션: 수집 범위 내 미노출' if q['status']=='success' else '\n수집 실패: 순위 판정 불가')
        report.append('')
    (target/'query-rankings.md').write_text('\n'.join(report),encoding='utf-8')
    flat = [{k:v for k,v in row.items() if k not in {'auxiliary','observation'}} for row in result['blogs']]
    export_csv(target/'blog-scores.csv', flat, list(flat[0]))
    export_csv(target/'product-scores.csv',result['product_scores'],list(result['product_scores'][0]))
    lines=['# 제품 검색 경쟁력 — 관측 기반 잠정 평가', '',
           '과거 40/25/20/15 종합점수를 대체하는 제품 검색 비교 프로필. C-Rank·준최·최적 등급으로 환산하지 않는다.',
           '각 검색어에서 블로그의 최고 순위만 사용한다. 제품별 별칭 평균 후 27제품을 동일 비중으로 평균하고 100을 곱한다.',
           '동일 글·여러 글을 추가 가산하지 않는다. 검색 성공 후 관측 범위 내 미노출만 0이며 수집 실패가 있으면 전체 점수는 보류한다.',
           '100점은 모든 제품·별칭 검색에서 1위인 경우다. 특정 브랜드 전문 블로그는 자기 제품에서 강해도 전체 패널 점수는 낮을 수 있다. 제품별 점수를 반드시 함께 본다.',
           '검색량은 구간·별칭 중복 문제로 가중하지 않았다. 발행량·본문 길이·이미지 수·제목 주제어 비율은 보조 원자료일 뿐 가산하지 않는다.',
           '관측 신뢰도는 수집 범위/표본/횟수이며 통계적 정확도 확률이 아니다. 현재 한 시점이므로 지속성·변화는 미측정이다.',
           ('실제 게시글 본문과 AI 관련성 판정으로 해당 제품 연결을 확인했다. 사양 사실확정·브랜드 충성도 검증과는 다르다.' if body_review is not None else '브랜드·파생제품 혼입이 미검토된 후보 검색 결과다.'),
           '검색 API 원래 순위를 유지하고 제외 글 때문에 순위를 당겨 다시 매기지 않는다. 통합검색 순위와 다르다.',
           '', f'비교 대상 {len(flat)}개 블로그 / {len(catalog)}제품 / {len(queries)}검색어', '',
           '|패널 내 위치|블로그|검색 경쟁력 /100|노출 제품 수|TOP10 검색어 수|', '|---:|---|---:|---:|---:|']
    shown = result['blogs'][:30]
    own = next(r for r in result['blogs'] if r['is_own'])
    if own not in shown: shown.append(own)
    lines += [f'|{r["panel_position"]}|{r["blog_id"]}|{r["search_competitiveness"]}|{r["ranked_products"]}|{r["top10_queries"]}|' for r in shown]
    (target/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(target),'blogs':len(flat),'own_score':own['search_competitiveness'],
                      'own_position':own['panel_position'],'panel_complete':result['panel_complete']},ensure_ascii=False))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path)
    args=parser.parse_args()
    source=args.source or sorted((ROOT/'data/blog_performance/product-search').glob('*/summary.json'))[-1].parent
    generate(source)
