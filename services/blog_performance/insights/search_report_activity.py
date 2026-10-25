"""Publication-cohort post counts, not exposure-score aggregates."""
from services.blog_performance.insights.search_report_metric_pages import E,line_chart,trend_cells
from services.blog_performance.insights.search_report_room_groups import GROUPS, grouped_report
from pathlib import Path
import json

def build_activity(r,halfyear,page,table,compare,source=None):
    periods=[{**p,'label':p['period'][:4]+' '+p['period'][4:]} for p in halfyear['periods']]
    groups=GROUPS
    r=grouped_report(r)
    source=source or Path(__file__).resolve().parents[3]/'data/blog_performance/product-search/20261021T054347Z/name-matched-diagnostic/matched-hits.json'
    hits=json.loads(source.read_text(encoding='utf-8'))
    product_group={p['product_id']:p['group'] for p in r['products']}
    def group_count(period, group):
        year=period['period'][:4]; half=int(period['period'][-1])
        return len({h['post_key'] for h in hits if product_group.get(h['product_id'])==group and len(h.get('published_date',''))==8 and h['published_date'][:4]==year and (1 if int(h['published_date'][4:6])<=6 else 2)==half})
    brands=['Logitech','HP Poly','Yealink','Jabra','AVer','Neat','Cisco']
    colors=['#087e86','#b66b25','#456fa4','#80539b','#638a30','#a74859','#4d697e']
    footer='활동량 표본: 2026-10-21 기준 고정 벤치마크 표본. 새 순위와 구분된 과거 검색 표본에 남은 글의 발행 시기별 분포입니다. 과거 전체 발행량이나 당시 검색 점수 변화가 아닙니다.'
    def charts_page(title,labels,series,css):
        ceiling=max(4,((max(v for values in series for v in values)+3)//4)*4)
        figures=[line_chart(label,values,periods,colors[i%len(colors)],'매칭 게시글 수 · 개',ceiling,unit='개',zero_is_missing=False) for i,(label,values) in enumerate(zip(labels,series))]
        page('발행 활동량 · 글 수',title,
             '발행 반기별 고유 글 수를 정수와 연결선으로 표시합니다. 활동량의 참고 지표이며 검색 노출 점수는 사용하지 않습니다.',
             compare('같은 그래프 묶음에 같은 세로축을 사용합니다. 0은 현재 표본에서 해당 반기 글이 0개라는 뜻입니다. 여러 브랜드·장비를 다룬 글은 각각에 포함될 수 있습니다.','글 수 비교')+
             '<div class="brand-lines '+css+'">'+''.join(figures)+'</div>',footer)
    charts_page('브랜드별 발행 반기별 매칭 글 수',brands,
                [[next(x['posts'] for x in p['brands'] if x['brand']==b) for p in periods] for b in brands],'')
    charts_page('장비 종류별 발행 반기별 매칭 글 수',[label for g,label in groups],
                [[group_count(p,g) for p in periods] for g,label in groups],'theme-lines')
    for g,label in groups:
        products=[x for x in r['products'] if x['group']==g]
        series=[[next(x['posts'] for x in p['products'] if x['product_id']==product['product_id']) for p in periods] for product in products]
        ceiling=max(1,max(v for values in series for v in values))
        rows=[[E(product['brand']),E(product['product']),*trend_cells(values,ceiling,unit='개',zero_is_missing=False)] for product,values in zip(products,series)]
        page('장비별 발행 활동량 · 글 수',label+' · 장비별 발행 반기별 매칭 글 수',
             '표의 칼럼과 장비별 행을 유지하고, 글 수를 선 아래에 표시합니다. 각 행은 같은 세로축을 사용하며 행 높이를 넉넉하게 유지합니다.',
             table(['브랜드','장비',*[E(p['label'])+'<small>고유 글 수 · 개</small>' for p in periods]],rows,'compact row-trends activity-counts',
                   reading='한 장비·한 반기 안에서 URL을 중복 제거한 글 수입니다. 장비 간 중복 글이 있어 행 합계는 고유 글 수와 다를 수 있습니다. 0은 현재 표본 관측값이며 실제 발행이 없었다는 확정이 아닙니다.',mode='글 수 비교'),footer)
