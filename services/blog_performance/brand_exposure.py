"""Per-query blog ranks and brand-normalized search exposure profiles."""
from collections import Counter, defaultdict


def breakdown(catalog, queries, hits, blogs):
    products = {p['product_id']:p for p in catalog}
    by_brand = defaultdict(list)
    for p in catalog:
        by_brand[p['brand']].append(p['product_id'])
    best, urls, names = {}, defaultdict(set), defaultdict(Counter)
    for h in hits:
        blog = h.get('blog_id')
        if not blog:
            continue
        key=(h['query_id'],blog)
        if key not in best or h['rank'] < best[key]['rank']:
            best[key]=h
        urls[key].add(h['post_key'])
        names[blog][h.get('blog_name') or blog]+=1
    query_rows=[]
    for q in queries:
        observed=sorted([h for (qid,b),h in best.items() if qid==q['query_id'] and q['status']=='success'],key=lambda h:(h['rank'],h['blog_id']))
        positions={h['blog_id']:i for i,h in enumerate(observed,1)}
        product=products[q['product_id']]
        for blog in blogs:
            h=best.get((q['query_id'],blog)) if q['status']=='success' else None
            query_rows.append({'query_id':q['query_id'],'query':q['query'],'product_id':q['product_id'],
                'brand':product['brand'],'product':product['product'],'blog_id':blog,
                'blog_name':names[blog].most_common(1)[0][0] if names[blog] else blog,
                'api_rank':h['rank'] if h else None,'blog_position':positions.get(blog),
                'status':('ranked' if h else 'not_in_collected_results') if q['status']=='success' else 'collection_failed',
                'unique_posts':len(urls[(q['query_id'],blog)]) if h else None,
                'representative_url':h['url'] if h else None,
                'representative_title':h['title'] if h else None})
    brand_rows=[]
    for blog in blogs:
        strengths={}
        rows=[]
        for brand,pids in by_brand.items():
            qs=[q for q in queries if q['product_id'] in pids]
            complete=len(qs)==sum(len(products[p]['queries']) for p in pids) and all(q['status']=='success' for q in qs)
            per_product=[]
            for pid in pids:
                pq=[q for q in qs if q['product_id']==pid]
                per_product.append(sum(1/best[(q['query_id'],blog)]['rank'] if (q['query_id'],blog) in best else 0 for q in pq)/len(pq) if pq else 0)
            strength=100*sum(per_product)/len(pids) if complete else None
            strengths[brand]=strength
            ranks=[best[(q['query_id'],blog)]['rank'] for q in qs if (q['query_id'],blog) in best and q['status']=='success']
            rows.append({'blog_id':blog,'brand':brand,'brand_search_strength':round(strength,4) if strength is not None else None,
                         'products_in_panel':len(pids),'queries_in_panel':len(qs),'ranked_queries':len(ranks),
                         'top10_queries':sum(r<=10 for r in ranks),'best_rank':min(ranks,default=None)})
        total=sum(v for v in strengths.values() if v is not None)
        complete=all(v is not None for v in strengths.values())
        for row in rows:
            row['normalized_brand_exposure_share_pct']=round(100*strengths[row['brand']]/total,2) if complete and total>0 else None
        brand_rows.extend(rows)
    return query_rows,brand_rows
