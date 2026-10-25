"""Collect RSS and three recent post samples for a bounded product-search panel."""
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import requests

from .collect_product_search import write_json, export_csv
from .competitor_engine import (Config, USER_AGENT, parse_rss, parse_post_html,
                                activity_metrics, activity_raw, minmax, compute_index)
from .blog_analyzer import post_identity

ROOT = Path(__file__).resolve().parents[2]


def select_panel(hits, products, mine):
    selection = {}
    for product in products:
        exposure = {}
        for row in hits:
            if row['product_id'] == product['product_id'] and row.get('blog_id') and row['rank'] <= 30:
                blog = row['blog_id']
                exposure[blog] = exposure.get(blog, 0) + 1 / row['rank']
        for blog in sorted(exposure, key=lambda b: (-exposure[b], b))[:3]:
            selection.setdefault(blog, []).append(product['product_id'])
    selection.setdefault(mine, []).append('own_blog')
    return selection


def collect_blog(blog, directory, terms, now):
    directory.mkdir(parents=True, exist_ok=True)
    result = {'blog_id': blog, 'observed_at': datetime.now(timezone.utc).isoformat(),
              'rss_status': 'failed', 'post_samples': [], 'measurement_status': 'unavailable'}
    session = requests.Session()
    session.headers.update({'User-Agent': USER_AGENT})
    try:
        response = session.get(f'https://rss.blog.naver.com/{blog}.xml', timeout=12)
        result['rss_http'] = response.status_code
        if response.status_code != 200:
            return result
        (directory/'rss.xml').write_bytes(response.content)
        posts = parse_rss(response.content)
        if not posts:
            result['rss_status'] = 'empty_or_unparseable'
            return result
        result.update(rss_status='success', rss_sample_count=len(posts),
                      oldest_published=posts[-1]['published'].isoformat(),
                      newest_published=posts[0]['published'].isoformat(),
                      focus_title_sample=min(20, len(posts)),
                      publication_count_basis='observed_RSS_sample_last_30_days',
                      **activity_metrics(posts, now, terms))
        write_json(directory/'rss-posts.json', [{**p, 'published': p['published'].isoformat()} for p in posts])
        for index, post in enumerate(posts[:3], 1):
            sample = {'original_url': post['link'], 'published': post['published'].isoformat(),
                      'title': post['title'], 'status': 'failed'}
            identity = post_identity(post['link'])
            if identity is None or identity[0] != blog:
                sample['reason'] = 'url_identity_mismatch'
            else:
                time.sleep(.6)
                try:
                    url = f'https://m.blog.naver.com/{identity[0]}/{identity[1]}'
                    response = session.get(url, timeout=12)
                    sample['http_status'] = response.status_code
                    if response.status_code == 200:
                        (directory/f'post-{index}.html').write_bytes(response.content)
                        meta = parse_post_html(response.text)
                        if meta and meta['char_count'] > 0:
                            sample.update(meta, status='success', fetched_url=url)
                        else:
                            sample['reason'] = 'body_container_missing_or_empty'
                except Exception as error:
                    sample['reason'] = type(error).__name__
            result['post_samples'].append(sample)
        successful = [s for s in result['post_samples'] if s['status']=='success']
        result['content_sample_requested'] = len(posts[:3])
        result['content_sample_success'] = len(successful)
        result['avg_chars'] = statistics.fmean(p['char_count'] for p in successful) if successful else None
        result['avg_images'] = statistics.fmean(p['image_count'] for p in successful) if successful else None
        result['measurement_status'] = 'complete' if len(successful)==len(posts[:3]) else 'partial'
    except Exception as error:
        result['error'] = type(error).__name__
    finally:
        session.close()
        write_json(directory/'observations.json', result)
    return result


def main():
    source = sorted((ROOT/'data/blog_performance/product-search').glob('*/summary.json'))[-1].parent
    hits = json.loads((source/'search-hits.json').read_text(encoding='utf-8'))
    products = json.loads((source/'catalog.json').read_text(encoding='utf-8'))
    cfg = Config.load()
    selection = select_panel(hits, products, cfg.my_blog_id)
    now = datetime.now(timezone.utc)
    out = source/'enrichment'/now.strftime('%Y%m%dT%H%M%SZ')
    out.mkdir(parents=True)
    write_json(out/'selection.json', {'rule': 'top3_blogs_per_product_sum_reciprocal_rank_within_top30_plus_own',
                                      'search_source': str(source), 'blogs': selection,
                                      'semantic_product_filter': False, 'weights': cfg.index_weights,
                                      'terms': cfg.topic_terms})
    print(f'Panel: {len(selection)} blogs', flush=True)
    observations = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = {pool.submit(collect_blog, b, out/'raw'/b, cfg.topic_terms, now): b for b in selection}
        for future in as_completed(pending):
            row = future.result()
            observations.append(row)
            write_json(out/'observations.json', observations)
            print(f'{len(observations)}/{len(selection)} {row["blog_id"]}: {row["rss_status"]}, body={row.get("content_sample_success",0)}', flush=True)
    complete = [r for r in observations if r['measurement_status']=='complete']
    # Keep the existing min-max features and 40/25/20/15 weights; incomplete blogs have no score.
    chars = minmax({r['blog_id']:r['avg_chars'] for r in complete})
    images = minmax({r['blog_id']:r['avg_images'] for r in complete})
    exposure = {b:sum(1/r['rank'] for r in hits if r.get('blog_id')==b and r['rank']<=30) for b in selection}
    raw = {r['blog_id']:{'exposure':exposure[r['blog_id']], 'activity':activity_raw(r),
                         'focus':r['focus_ratio'], 'content':.7*chars[r['blog_id']]+.3*images[r['blog_id']]}
           for r in complete}
    scored = compute_index(raw, cfg.index_weights) if len(raw)>=2 else {}
    flat=[]
    for row in observations:
        blog = row['blog_id']
        flat.append({k:row.get(k) for k in ['blog_id','rss_status','measurement_status','rss_sample_count',
                    'oldest_published','newest_published','count_30d','regularity','focus_ratio','focus_title_sample',
                    'content_sample_requested','content_sample_success','avg_chars','avg_images']} |
                    {'selected_for':','.join(selection[blog]), 'exposure_raw':exposure[blog],
                     'provisional_total':scored.get(blog,{}).get('total')})
    flat.sort(key=lambda r: (r['provisional_total'] is None, -(r['provisional_total'] or 0), r['blog_id']))
    write_json(out/'provisional-scores.json', {'cohort':sorted(raw), 'weights':cfg.index_weights,
                    'status':'legacy_diagnostic_not_active_score', 'scores':scored,
                    'incomplete_blogs_excluded':len(observations)-len(complete)})
    export_csv(out/'blog-observations.csv', flat, list(flat[0]))
    summary = {'directory':str(out), 'blogs_selected':len(selection), 'rss_success':sum(r['rss_status']=='success' for r in observations),
               'body_requested':sum(r.get('content_sample_requested',0) for r in observations),
               'body_success':sum(r.get('content_sample_success',0) for r in observations),
               'complete_blogs':len(complete), 'scored_blogs':len(scored),
               'own_blog':next((r for r in flat if r['blog_id']==cfg.my_blog_id),None)}
    write_json(out/'summary.json',summary)
    lines=['# 제품 검색 비교군 RSS·본문 수집', '',
           '제품별 상위 노출 블로그 3곳의 합집합과 오우션. 검색어는 동일한 54개이며 상위30위 안의 1/순위 합계로 선정.',
           '기존 가중치 유지. 제품 혼입과 업종 적합성 미검토로 점수는 잠정 실험값이다. 운영 DB·설정을 변경하지 않았다.',
           '점수는 완전 수집된 비교군 내 상대값이다. 제외 블로그와 비교하거나 네이버 지수로 해석하지 않는다.',
           'RSS는 최근 표본이며 전체 월간 발행량이 아니다. 본문은 최근 최대3개로 제품 관련 글을 보장하지 않는다.',
           '주제 집중도는 기존 로지텍·화상회의 주제어를 유지했다. 타 브랜드에 불리할 수 있어 브랜드 중립 평가로 확정하면 안 된다.',
           '', '|블로그|RSS 표본|본문 성공|주제어 비율|잠정 점수|', '|---|---:|---:|---:|---:|']
    lines += [f'|{r["blog_id"]}|{r["rss_sample_count"]}|{r["content_sample_success"]}|{r["focus_ratio"]}|{r["provisional_total"]}|' for r in flat]
    (out/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    from .product_competitiveness import generate
    generate(source)


if __name__ == '__main__':
    main()
