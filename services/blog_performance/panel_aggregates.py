"""Descriptive aggregation of existing scores, with one fixed blog denominator."""
from collections import defaultdict
from .collect_product_search import export_csv

GROUPS = {'bar':'대형 비디오바', 'small':'소형 비디오바', 'modular':'모듈형·분리형'}


def aggregate(result):
    n=len(result['blogs'])
    def summarise(rows):
        by_product=defaultdict(list)
        active=set()
        for r in rows:
            by_product[r['product_id']].append(r['search_competitiveness'])
            if r['search_competitiveness'] is not None and r['search_competitiveness']>0:
                active.add(r['blog_id'])
        complete=bool(by_product) and all(len(v)==n and all(x is not None for x in v) for v in by_product.values())
        total=sum(sum(v) for v in by_product.values())/len(by_product) if complete else None
        return {'products':len(by_product),'blogs_denominator':n,'observed_blogs':len(active),
                'product_normalized_sum':round(total,4) if total is not None else None,
                'mean_all_blogs':round(total/n,6) if total is not None and n else None}
    rows=result['product_scores']
    brands=[{'brand':b,**summarise([r for r in rows if r['brand']==b])} for b in sorted({r['brand'] for r in rows})]
    themes=[{'group':g,'theme':GROUPS[g],**summarise([r for r in rows if r['group']==g])} for g in GROUPS]
    products=[{'product_id':pid,'brand':p[0]['brand'],'product':p[0]['product'],'group':p[0]['group'],**summarise(p)}
              for pid in sorted({r['product_id'] for r in rows}) for p in [[r for r in rows if r['product_id']==pid]]]
    cross=[{'group':g,'theme':GROUPS[g],'brand':b,**summarise([r for r in rows if r['group']==g and r['brand']==b])}
           for g in GROUPS for b in sorted({r['brand'] for r in rows if r['group']==g})]
    return {'brands':brands,'themes':themes,'products':products,'theme_brands':cross}


def export_aggregates(result,target):
    tables=aggregate(result)
    for name,rows in tables.items():
        export_csv(target/f'aggregate-{name}.csv',rows,list(rows[0]))
    lines=['# 브랜드·장비 테마별 검색 관측 집계', '',
           '기존'+' 제품 검색 점수를 그대로 집계했다. 블로그 603곳 등 해당 실행의 전체 동일 비교군을 분모로 사용한다.',
           '제품별 블로그 점수 합산 → 브랜드/테마 내 제품 평균 → 전체 블로그 수로 나눈 평균을 표시한다. 제품 수가 많다는 이유로 가산하지 않는다.',
           '합산값은 100점 상한이 없고 평균은 0~100이다. 낮은 평균은 대부분 블로그가 해당 제품 검색에서 관측되지 않았기 때문이다.',
           '이 값은 제품 품질·시장점유율·브랜드 신뢰도가 아니다. 상위 검색 결과의 여러 블로그 분포, 동일 블로그의 반복 점유, 제품 혼입에 영향을 받는다.',
           '특히 Neat·Rally 등 넓은 명칭과 파생제품 혼입을 의미 검토하지 않았으므로 브랜드 우열 결론은 보류한다. 관측 비중에 대한 기술통계다.', '']
    for name,label in [('brands','브랜드 전체'),('themes','테마 전체'),('theme_brands','테마별 브랜드'),('products','제품별')]:
        lines += [f'## {label}', '', '|대상|제품 수|노출 블로그|제품수 보정 합산|전체 블로그 평균|', '|---|---:|---:|---:|---:|']
        selected=sorted(tables[name],key=lambda r:(r['mean_all_blogs'] is None,-(r['mean_all_blogs'] or 0)))
        for r in selected:
            title=' / '.join(str(r[k]) for k in ['theme','brand','product'] if k in r)
            lines.append(f'|{title}|{r["products"]}|{r["observed_blogs"]}|{r["product_normalized_sum"]}|{r["mean_all_blogs"]}|')
        lines.append('')
    (target/'brand-theme-comparison.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return tables
