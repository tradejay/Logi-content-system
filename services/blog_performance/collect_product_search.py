"""Collect the approved 27-product/54-query panel; no scoring or model API."""
import csv
import html
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from .blog_analyzer import post_identity
from services.keyword_volume import SearchAdClient, _key

ROOT = Path(__file__).resolve().parents[2]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def clean(value):
    return html.unescape(re.sub('<[^>]+>', '', value or ''))


def export_csv(path, rows, columns):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def main():
    catalog = json.loads(Path(__file__).with_name('product-search-catalog.json').read_text(encoding='utf-8'))
    cfg = json.loads((ROOT/'config/config.json').read_text(encoding='utf-8-sig'))
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = ROOT/'data/blog_performance/product-search'/stamp
    (out/'raw/search').mkdir(parents=True)
    (out/'raw/searchad').mkdir()
    write_json(out/'catalog.json', catalog)
    search_headers = {'X-Naver-Client-Id': cfg['naver_client_id'], 'X-Naver-Client-Secret': cfg['naver_client_secret']}
    hub_headers = {'X-NCP-APIGW-API-KEY-ID': cfg['naver_client_id'], 'X-NCP-APIGW-API-KEY': cfg['naver_client_secret']}
    endpoints = [('legacy', 'https://openapi.naver.com/v1/search/blog.json', search_headers),
                 ('hub', 'https://naverapihub.apigw.ntruss.com/search/v1/blog', hub_headers)]
    chosen = None
    query_rows, hits = [], []
    query_index = 0
    for product in catalog:
        for query in product['queries']:
            query_index += 1
            qid = f'Q{query_index:03}'
            base = {k: product[k] for k in ['product_id', 'group', 'brand', 'product']}
            row = {**base, 'query_id': qid, 'query': query, 'observed_at': datetime.now(timezone.utc).isoformat(),
                   'status': 'failed', 'api_total': None, 'retrieved': None, 'source': None}
            for name, url, headers in ([chosen] if chosen else endpoints):
                try:
                    response = requests.get(url, headers=headers, params={'query': query, 'display': 100, 'start': 1, 'sort': 'sim'}, timeout=12)
                    if response.status_code != 200:
                        row['error'] = f'HTTP_{response.status_code}'
                        continue
                    data = response.json()
                    if not isinstance(data.get('items'), list):
                        row['error'] = 'INVALID_RESPONSE'
                        continue
                    write_json(out/f'raw/search/{qid}.json', {'query': query, 'observed_at': row['observed_at'], 'source': name, 'response': data})
                    chosen = (name, url, headers)
                    row.update(status='success', source=name, api_total=data.get('total'), retrieved=len(data['items']))
                    row.pop('error', None)
                    for rank, item in enumerate(data['items'], 1):
                        identity = post_identity(item.get('link'))
                        key = '/'.join(identity) if identity else item.get('link', '')
                        hits.append({**base, 'query_id': qid, 'query': query, 'rank': rank,
                                     'post_key': key, 'blog_id': identity[0] if identity else None,
                                     'url': item.get('link'), 'title': clean(item.get('title')),
                                     'description': clean(item.get('description')), 'blog_name': clean(item.get('bloggername')),
                                     'published_date': item.get('postdate'), 'observed_at': row['observed_at'], 'source': name})
                    break
                except Exception as error:
                    row['error'] = type(error).__name__  # Never log credential-bearing request exceptions.
            query_rows.append(row)
            write_json(out/'query-results.json', query_rows)
            if query_index % 6 == 0:
                print(f'Search {query_index}/54; success={sum(r["status"]=="success" for r in query_rows)}', flush=True)
            time.sleep(.25)

    ad = SearchAdClient(customer_id=cfg.get('ad_customer_id'), api_key=cfg.get('ad_api_key'), secret_key=cfg.get('ad_secret_key'))
    for index, row in enumerate(query_rows, 1):
        row.update(volume_status='failed', monthly_pc=None, monthly_mobile=None, monthly_total=None)
        try:
            response = requests.get(ad.BASE+ad.URI, headers=ad._headers(),
                                    params={'hintKeywords': row['query'].replace(' ', ''), 'showDetail': '1'}, timeout=12)
            if response.status_code != 200:
                row['volume_error'] = f'HTTP_{response.status_code}'
            else:
                data = response.json()
                write_json(out/f'raw/searchad/{row["query_id"]}.json', {'query': row['query'], 'observed_at': datetime.now(timezone.utc).isoformat(), 'response': data})
                match = next((r for r in data.get('keywordList', []) if _key(r.get('relKeyword', '')) == _key(row['query'])), None)
                if match is None:
                    row['volume_status'] = 'not_returned'
                else:
                    pc, mobile = match.get('monthlyPcQcCnt'), match.get('monthlyMobileQcCnt')
                    row.update(volume_status='success', monthly_pc=pc, monthly_mobile=mobile,
                               monthly_total=pc+mobile if type(pc) is int and type(mobile) is int else None)
        except Exception as error:
            row['volume_error'] = type(error).__name__
        write_json(out/'query-results.json', query_rows)
        if index % 6 == 0:
            print(f'Volume {index}/54; success={sum(r.get("volume_status")=="success" for r in query_rows)}', flush=True)
        time.sleep(.4)

    products, blog_rows = [], []
    for product in catalog:
        selected = [r for r in hits if r['product_id'] == product['product_id']]
        unique = {r['post_key'] for r in selected}
        queries = [r for r in query_rows if r['product_id'] == product['product_id']]
        products.append({**{k: product[k] for k in ['product_id', 'group', 'brand', 'product']},
                         'queries_ok': sum(r['status']=='success' for r in queries),
                         'retrieved_hits': len(selected), 'unique_posts': len(unique),
                         'duplicate_hits': len(selected)-len(unique),
                         'unique_blogs': len({r['blog_id'] for r in selected if r['blog_id']})})
        for blog in sorted({r['blog_id'] for r in selected if r['blog_id']}):
            posts = [r for r in selected if r['blog_id']==blog]
            blog_rows.append({'product_id': product['product_id'], 'product': product['product'], 'blog_id': blog,
                              'unique_posts': len({r['post_key'] for r in posts}), 'best_rank': min(r['rank'] for r in posts),
                              'top10_queries': len({r['query_id'] for r in posts if r['rank']<=10}),
                              'top30_queries': len({r['query_id'] for r in posts if r['rank']<=30})})
    write_json(out/'search-hits.json', hits)
    write_json(out/'product-summary.json', products)
    export_csv(out/'queries.csv', query_rows, list(query_rows[0])+['volume_error'])
    export_csv(out/'search-hits.csv', hits, list(hits[0]) if hits else ['query', 'url'])
    export_csv(out/'products.csv', products, list(products[0]))
    export_csv(out/'product-blogs.csv', blog_rows, list(blog_rows[0]) if blog_rows else ['product_id','blog_id'])
    summary = {'directory': str(out), 'products': len(catalog), 'queries': len(query_rows),
               'search_success': sum(r['status']=='success' for r in query_rows),
               'volume_success': sum(r.get('volume_status')=='success' for r in query_rows),
               'hits': len(hits), 'unique_posts_global': len({r['post_key'] for r in hits}),
               'unique_blogs_global': len({r['blog_id'] for r in hits if r['blog_id']}),
               'score_computed': False}
    write_json(out/'summary.json', summary)
    lines = ['# 제품 검색 원자료 수집 결과', '', json.dumps(summary, ensure_ascii=False), '',
             '제품별 두 검색어의 상위 최대 100개씩 수집. 검색 API 목록 순서이며 통합검색 순위가 아니다.',
             '검색 결과는 후보 자료이며 실제 해당 제품인지 의미 검토하지 않았다. Rally/Bar/Pro 등 파생제품 혼입 가능.',
             '검색량은 공백 제거된 동일 검색어의 응답만 연결하며 별칭 합산 금지. 구간값은 원문 보존. 미반환/실패는 0이 아니다.',
             '본문·이미지 수집 및 블로그 점수 계산은 이번 실행에 포함하지 않았다.', '',
             '|제품|성공 검색어|결과 수|중복 제거 글|블로그 수|', '|---|---:|---:|---:|---:|']
    lines += [f'|{r["brand"]} {r["product"]}|{r["queries_ok"]}/2|{r["retrieved_hits"]}|{r["unique_posts"]}|{r["unique_blogs"]}|' for r in products]
    (out/'README.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    from .product_competitiveness import generate
    generate(out)


if __name__ == '__main__':
    main()
