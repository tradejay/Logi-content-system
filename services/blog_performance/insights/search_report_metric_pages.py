"""Neutral metric-led page content; numeric source data is unchanged."""
import html
import json
import math

E=lambda value:html.escape(str(value))

def trend_cells(values,ceiling,unit="점",zero_is_missing=True):
    """One connected SVG strip across equal-width table cells; gaps stay gaps."""
    cells=[]
    for i,v in enumerate(values):
        if v is None or (zero_is_missing and not v):
            cells.append('<span class="empty">매칭 관측 없음</span>' if v is not None else '<span class="empty">대상 장비 없음</span>')
            continue
        y=65-55*v/ceiling
        lines=[]
        if i and values[i-1] is not None and (values[i-1] or not zero_is_missing):
            prev=65-55*values[i-1]/ceiling
            lines.append(f'<line x1="0" y1="{(prev+y)/2}" x2="50" y2="{y}"/>')
        if i+1<len(values) and values[i+1] is not None and (values[i+1] or not zero_is_missing):
            following=65-55*values[i+1]/ceiling
            lines.append(f'<line x1="50" y1="{y}" x2="100" y2="{(following+y)/2}"/>')
        cells.append('<svg class="row-trend" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="'+f'{v:.0f}{unit}'+ '"><g stroke="#087e86" stroke-width="1.8">'+''.join(lines)+f'</g><circle cx="50" cy="{y}" r="2.5" fill="#087e86"/><text x="50" y="94" text-anchor="middle" fill="#172b3a" font-size="12">{v:.0f}</text></svg>')
    return cells

def line_chart(label,values,periods,color,subtitle,ceiling,unit="점",zero_is_missing=True):
    xs=[34+i*49 for i in range(5)];bottom=120;top=24;graph=[]
    for tick in range(5):
        value=ceiling*tick/4;y=bottom-(bottom-top)*tick/4
        graph.append(f'<line x1="30" x2="242" y1="{y}" y2="{y}" stroke="#dce5e9" stroke-width="1"/><text x="24" y="{y+3}" text-anchor="end" font-size="8" fill="#6c7c88">{value:.0f}</text>')
    segments=[];current=[]
    for i,v in enumerate(values):
        if v is not None and (v or not zero_is_missing):current.append((xs[i],bottom-(bottom-top)*v/ceiling,v))
        else:
            if current:segments.append(current);current=[]
    if current:segments.append(current)
    for segment in segments:
        graph.append('<polyline points="'+' '.join(f'{x},{y:.2f}' for x,y,v in segment)+f'" fill="none" stroke="{color}" stroke-width="2.4"/>')
        for x,y,v in segment:
            graph.append(f'<circle cx="{x}" cy="{y:.2f}" r="3.5" fill="{color}"><title>{E(label)}: {v:.0f}{unit}</title></circle><text class="point-value" x="{x}" y="{y-9:.2f}" text-anchor="middle" font-size="12" font-weight="700" fill="{color}">{v:.0f}</text>')
    for i,v in enumerate(values):
        graph.append(f'<text x="{xs[i]}" y="139" text-anchor="middle" font-size="7" fill="#526777">{E(periods[i]["label"])}</text>')
        if v is None or (zero_is_missing and not v):graph.append(f'<text x="{xs[i]}" y="110" text-anchor="middle" font-size="9" fill="#8a969d">없음</text>')
    accessible=label+' / '+', '.join(p['label']+' '+(f'{v:.0f}{unit}' if v is not None and (v or not zero_is_missing) else '매칭 관측 없음') for p,v in zip(periods,values))
    return f'<figure class="brand-line"><figcaption><b style="color:{color}">{E(label)}</b><small>{E(subtitle)}</small></figcaption><svg viewBox="0 0 260 148" role="img" aria-label="{E(accessible)}">'+''.join(graph)+'</svg></figure>'

def build_pages(r,halfyear,source,page,table,compare,browser_report=None,product_report=None):
    brand_order=['Logitech','HP Poly','Yealink','Jabra','AVer','Neat','Cisco']
    groups=[('bar','대형 비디오바'),('small','소형 비디오바'),('modular','모듈형·분리형')]
    products={p['product_id']:p for p in r['products']}
    brands={b['brand']:b for b in r['brands']}
    periods=[{**p,'label':p['period'][:4]+' '+p['period'][4:]} for p in halfyear['periods']]
    hits=json.loads((source.parent/'matched-hits.json').read_text(encoding='utf-8'))
    def H(name,unit):return E(name)+f'<small>{E(unit)}</small>'
    def num(v):return f'{v:.2f}'
    def score(v):return num(v) if v else '<span class="empty">매칭 관측 없음</span>'
    def link(blog):return f'<a href="https://blog.naver.com/{E(blog)}" target="_blank" rel="noopener">{E(blog)} ↗</a>'
    def note(text):return f'<p class="micro">{text}</p>'
    def T(headers,rows,reading,mode='조건부 비교',compact=False,trend=False):
        return table(headers,rows,('compact' if compact else '')+(' row-trends'+(' categorical' if trend=='category' else '') if trend else ''),reading=reading,mode=mode)
    def P(number,title,description,body,footer=None):
        args=[f'{number:02} / 지표 집계',title,description,body]
        if footer:args.append(footer)
        page(*args)
    rank_note='점수는 2026-10-21 검색 API 원래 순위를 기준으로 계산했습니다. 통합검색 순위·네이버 공식 점수와 다릅니다.'
    period_note='발행일로 나눈 현재 노출 집계입니다. 반기별 과거 검색 순위나 당시 점수가 아닙니다.'

    scope=[
      ['장비명 API 자료 수집','2026-10-21','API 결과 위치이며 실제 검색 화면 순위 아님'],
      ['실제 블로그 탭 자료','2026-10-22 · 7개 검색어',f'첫 30개씩 · {browser_report["source_unique_posts"]}개 고유 글 중 기존 분류 {browser_report["coverage"]["unique_matched_posts"]}개 연결' if browser_report else '미등록'],
      ['보고서 작성일','2026-10-22','새로운 검색 수집은 수행하지 않음'],
      ['분석 브랜드 수','7개','브랜드 전체 시장을 대표하는 표본 아님'],
      ['분석 장비 수','27개','대형 비디오바 6개 · 소형 비디오바 12개 · 모듈형 9개'],
      ['검색어 수','54개','장비마다 한글·영문 별칭 2개'],
      ['수집 검색 결과 행 수',f'{r["original_hits"]:,}행','같은 글이 여러 검색어에서 반복될 수 있음'],
      ['이번 집계에 포함한 결과 행 수',f'{r["retained_hits"]:,}행','브랜드·장비명 매칭 및 일부 본문 검토 적용'],
      ['중복 제거한 매칭 게시글 수',f'{len({h["post_key"] for h in hits}):,}개','게시글 URL 기준 중복 제거'],
    ]
    if product_report:
        scope.insert(2,['한글 장비명 실제 화면',str(product_report.get('queries', 0) if isinstance(product_report.get('queries', 0), int) else len(product_report.get('queries', [])))+'개 수집 검색어',f'{product_report["rows"]}건 / 고유 {product_report["unique_posts"]}개 · 본문 {product_report["body_collection"]["success"]}개 확보'])
    P(1,'수집 범위와 집계 대상 수','장비명 검색 자료와 공통 검색어 추가 수집을 구분합니다. 아래 글·검색어 수는 별도 표시가 없으면 기존 장비명 검색 표본입니다.',
      T(['항목','값','집계 기준'],scope,'검색 결과 행 수와 고유 글 수는 다릅니다. 검색어별로 중복된 글은 고유 글 수에서 한 번만 셉니다.','집계 기준',True))

    P(2,'브랜드별 매칭 게시글 수·블로그 수','단위는 게시글 개수와 블로그 ID 개수입니다. 검색 노출 순위 점수를 포함하지 않은 수량표입니다.',
      T(['브랜드',H('선정 장비 수','개'),H('검색어 수','개'),H('매칭 게시글 수','고유 URL · 개'),H('매칭 블로그 수','고유 ID · 곳')],
        [[b,brands[b]['products'],brands[b]['products']*2,brands[b]['matched_posts'],brands[b]['matched_blogs']] for b in brand_order],
        '현재 수집 표본의 수량 비교입니다. 브랜드별 검색어·장비 구성이 달라 전체 발행량이나 시장 규모의 1:1 비교는 아닙니다.')+
      note('같은 게시글이 여러 장비·브랜드를 다루면 각 브랜드에 포함될 수 있습니다. 블로그 ID 수는 회사 수가 아닙니다.'))

    P(3,'브랜드·장비 분류별 노출 순위 점수 합계의 제품평균',
      '각 셀 = 장비별 모든 블로그의 노출 순위 점수 합계 ÷ 해당 브랜드·분류의 선정 장비 수입니다. 100점 만점이 아닙니다.',
      T(['브랜드',*[H(label,'장비별 합계의 평균 · 점') for _,label in groups]],
        [[b,*[(f'{x["observed_exposure_index"]:.0f}<small>{x["products"]}개 장비 평균</small>' if x else '<span class="empty">대상 장비 없음</span>')
          for x in [next((t for t in r['theme_brands'] if t['brand']==b and t['group']==g),None) for g,_ in groups]]] for b in brand_order],
        '수치는 같은 계산 단위지만 장비·검색어가 다릅니다. 브랜드 전체 경쟁력의 직접 비교가 아니라 선정 장비군의 기술통계입니다.')+
      note('예: Logitech 소형 열은 MeetUp 2·Rally Bar Huddle·Rally Bar Mini의 점수 합계를 평균낸 값입니다.'))

    ownrows=[]
    for pid in ['VC-001','VC-007','VC-008','VC-009','VC-019','VC-020']:
        p=products[pid]
        top=p['top_blogs'][0] if p['top_blogs'] else None
        ranks=[]
        for korean in [True,False]:
            rank=min((h['rank'] for h in hits if h['product_id']==pid and top and h['blog_id']==top['blog_id'] and any('가'<=c<='힣' for c in h['query'])==korean),default=None)
            ranks.append(f'{rank}위' if rank else '관측 없음')
        ownrows.append([E(p['product']),link(top['blog_id']) if top else '매칭 관측 없음',
          ' / '.join(ranks),num(top['score']) if top else '매칭 관측 없음',
          score(p['own_observed_score']),num(top['score']-p['own_observed_score']) if top else '계산 불가'])
    P(4,'Logitech 장비별 최고점 블로그·오우션 노출 순위 점수',
      '로지텍 6개 장비 각각에 대해 현재 매칭 표본에서 점수가 가장 높은 블로그를 표시합니다. 최고점과 오우션 점수는 모두 0~100점 척도입니다.',
      T(['장비','최고점 블로그 ID',H('최고점 블로그 검색 순위','한글 / 영문 · API 순위'),H('장비별 최고점','블로그 1곳 · 0~100점'),H('오우션 점수','oceantech01 · 0~100점'),H('최고점과 차이','최고점 − 오우션 · 점')],ownrows,
        '같은 행에서는 장비·두 검색어·수집일·계산식이 같아 블로그 간 점수와 차이를 직접 비교할 수 있습니다. 다른 장비 행 간에는 검색어가 다릅니다.',mode='직접 비교 가능',compact=True)+
      note('최고점은 과거 최고 기록이나 로지텍 브랜드 합계가 아니라 현재 수집 표본의 최고 블로그 점수입니다. 동점이면 대표 블로그 한 곳을 표시합니다. 차이는 백분율이 아닌 점수 차이입니다.')+
      note('노출 순위 점수 = 100 × [(1÷한글 최고 순위)+(1÷영문 최고 순위)] ÷2. 매칭 글이 없는 별칭의 집계 기여는 0이며, 미확인 글의 실제 관련성까지 확정한 것은 아닙니다.'),rank_note)

    hp=[]
    for pid in ['VC-002','VC-010','VC-021']:
        p=products[pid];top=p['top_blogs'][0]
        hp.append([E(p['product']),p['matched_posts'],p['matched_blogs'],link(top['blog_id']),num(top['score'])])
    P(5,'HP Poly 장비별 게시글 수·최고점 블로그',
      '선정 장비는 Studio X52·Studio X32·Studio G62입니다. 마지막 칼럼은 각 장비 검색에서 점수가 가장 큰 1개 블로그의 점수입니다.',
      T(['장비',H('매칭 게시글 수','개'),H('매칭 블로그 수','곳'),'최고점 블로그 ID',H('해당 블로그 노출 순위 점수','0~100점')],hp,
        '100점은 해당 장비의 두 검색어에서 모두 1위라는 뜻입니다. 제품 품질 만점이나 브랜드 전체 점수가 아닙니다.')+
      note('검색 순위 점수 합계는 모든 블로그를 더한 값이고, 이 표의 마지막 칼럼은 최고점 블로그 한 곳의 값입니다.'))

    yr=[]
    for pid in ['VC-022','VC-023']:
        p=products[pid];yr.append([p['product'],p['matched_posts'],p['matched_blogs'],f'{p["matched_posts"]/p["matched_blogs"]:.2f}'])
    P(6,'Yealink 모듈형 장비별 글 수·블로그당 평균 글 수',
      '선정 장비는 UVC84·UVC86입니다. 블로그당 평균 글 수는 매칭 게시글 수를 매칭 블로그 수로 나눈 값입니다.',
      T(['장비',H('매칭 게시글 수','고유 URL · 개'),H('매칭 블로그 수','고유 ID · 곳'),H('블로그당 평균 글 수','개/블로그')],yr,
        '현재 검색 표본에서의 글 분포를 비교합니다. 전체 누적 발행량·내용 품질·전문성을 비교하는 지표는 아닙니다.')+
      note('같은 글이 한글·영문 두 검색어에 모두 나타나도 게시글 수는 한 번만 셉니다.'))

    plus=products['VC-020'];bl=[x['blog_id'] for x in plus['top_blogs']]
    if 'oceantech01' not in bl:bl.append('oceantech01')
    rows=[]
    for b in bl:
        ranks=[]
        for korean in [True,False]:
            rank=min((h['rank'] for h in hits if h['product_id']=='VC-020' and h['blog_id']==b and any('가'<=c<='힣' for c in h['query'])==korean),default=None)
            ranks.append(f'{rank}위' if rank else '매칭 관측 없음')
        value=next((x['score'] for x in plus['top_blogs'] if x['blog_id']==b),plus['own_observed_score'] if b=='oceantech01' else 0)
        rows.append([link(b),*ranks,num(value)])
    P(7,'Rally Plus 검색어별 블로그 순위·노출 순위 점수',
      '검색어는 “로지텍 랠리 플러스”, “Logitech Rally Plus”입니다. 모든 행이 같은 장비·검색어·수집일 기준입니다.',
      T(['블로그 ID',H('한글 검색 최고 순위','위'),H('영문 검색 최고 순위','위'),H('노출 순위 점수','0~100점')],rows,
        '동일 제품·동일 검색어·동일 수집일의 블로그별 검색 성과이므로 직접 비교 가능합니다. 글 내용의 품질 평가는 포함하지 않습니다.','직접 비교 가능'),rank_note)

    neat=[products[pid] for pid in ['VC-004','VC-014']]
    P(8,'Neat 장비별 매칭 게시글 수·블로그 수',
      '분석 대상은 Bar Pro·Bar Gen 2입니다. 브랜드 합계는 두 장비에 동시에 포함된 URL과 블로그 ID를 다시 중복 제거한 값입니다.',
      T(['집계 대상',H('매칭 게시글 수','개'),H('매칭 블로그 수','곳')],
        [[E(p['product']),p['matched_posts'],p['matched_blogs']] for p in neat]+[['Neat 브랜드 전체 · 중복 제거',brands['Neat']['matched_posts'],brands['Neat']['matched_blogs']]],
        '장비별 행을 단순히 더하면 브랜드 전체 고유 글 수·블로그 수와 다를 수 있습니다. 전문 업체 수나 시장점유율은 산출하지 않았습니다.')+
      note('의류 글로 확인된 aqualon은 이 집계 대상에서 제외됐습니다.'))

    P(9,'Logitech 장비별 매칭 게시글 수·블로그 수',
      '분석 대상은 Rally Bar·MeetUp 2·Rally Bar Huddle·Rally Bar Mini·Rally·Rally Plus입니다. 순위 점수를 포함하지 않은 수량표입니다.',
      T(['장비',H('매칭 게시글 수','고유 URL · 개'),H('매칭 블로그 수','고유 ID · 곳')],
        [[E(p['product']),p['matched_posts'],p['matched_blogs']] for p in r['products'] if p['brand']=='Logitech']+
        [['Logitech 전체 · 중복 제거',brands['Logitech']['matched_posts'],brands['Logitech']['matched_blogs']]],
        '각 장비의 두 검색어에서 수집된 표본 기준입니다. 장비별 검색어가 달라 전체 콘텐츠 보유량이나 수요를 동일 조건으로 비교한 값은 아닙니다.')+
      note('여러 장비를 다룬 글이 각 장비에 중복 포함될 수 있어 장비별 글 수 합계는 브랜드 고유 글 수보다 큽니다.'))

    formulas=[
      ['공통 검색어 브랜드 관측점','100 × 공통 검색어 7개 최고 순위 역수 평균','0~100점 · 제한 표본','브랜드별 기존 매칭 글의 최고 순위. 미관측은 계산 기여만 0'],
      ['블로그별 노출 순위 점수','100 × 두 검색어의 최고 순위 역수 평균','0~100점','한글 3위·영문 4위 → 100×(1/3+1/4)/2 = 29.17'],
    ]
    P(10,'공통 검색어 관측점·장비명 검색 지표 계산식',
      '브랜드 비교와 한글 장비명 표는 제공된 블로그 탭 화면 순서를 사용합니다. 장비명 영어 검색 순서는 미수집이며 API와 혼합하지 않습니다.' if product_report else '브랜드 비교는 제공된 블로그 탭 화면 순서를 사용합니다. 장비명 검색 표는 아직 API 결과 위치이며 실제 화면 순위가 아닙니다. 두 출처를 섞지 않습니다.',
      T(['점수 항목','계산식','단위','계산 예시'],formulas,'서로 다른 집계 수준의 숫자는 직접 대소 비교하지 않습니다. 예시의 A·B 값은 계산 설명용이며 관측 데이터가 아닙니다.','계산 기준',True)+
      note('장비명 검색 합산점은 브랜드 경쟁력·운영 품질 점수가 아닙니다. 공통 검색어 관측점도 기존 글만 연결한 제한 표본이며, 전체 브랜드 노출·네이버 공식 지수로 환산하지 않습니다.'))

    for number,(g,label) in enumerate(groups,11):
        ps=[p for p in r['products'] if p['group']==g]
        if number==13:
            ps=sorted(ps,key=lambda p:-p['observed_blog_score_sum'])
        rows=[[E(p['brand']),E(p['product']),p['matched_blogs'],num(p['observed_blog_score_sum'])] for p in ps]
        P(number,f'{label} · 장비별 노출 순위 점수 합계',
          '각 행은 한 장비입니다. 마지막 칼럼은 그 장비에 연결된 모든 블로그의 노출 순위 점수를 더한 값이며 100점 만점이 아닙니다.',
          T(['브랜드','장비',H('합산 대상 블로그 수','곳'),H('노출 순위 점수 합계','모든 블로그 점수 합산 · 점')],rows,
            '같은 합산 단위이지만 장비별 검색어와 참여 블로그 수가 다릅니다. 제품 성능이나 브랜드 전체 경쟁력의 1:1 비교는 아닙니다.',compact=True),rank_note)

    P(14,'발행 반기별 매칭 게시글 수·블로그 수',
      '열의 반기는 검색 순위를 측정한 시점이 아니라 글의 발행 시기입니다. 모든 글의 검색 순위 수집일은 2026-10-21로 같습니다.',
      T(['글 발행 시기',H('매칭 게시글 수','고유 URL · 개'),H('매칭 블로그 수','고유 ID · 곳')],
        [[p['label'],p['posts'],p['blogs']] for p in periods],
        '현재 검색 표본의 발행 시기 분포입니다. 당시 전체 발행량이나 반기별 검색 점수 변화는 측정하지 않았습니다.')+
      note(f'2024 H1~2026 H1 합계 {sum(p["posts"] for p in periods)}개 글. 2026 H2 {halfyear["outside_period_posts"].get("2026H2",0)}개 및 2024년 이전 글은 이 기간표에서 제외했습니다.'),period_note)

    time_headers=[E(p['label'])+'<small>이 시기에 발행한 글</small>' for p in periods]
    chart_colors=['#087e86','#3364a0','#ac6b16','#7255a6','#3c7c4d','#b84f61','#506472']
    series={b:[next(x['index'] for x in p['brands'] if x['brand']==b) for p in periods] for b in brand_order}
    ceiling=max(25,math.ceil(max(v for values in series.values() for v in values)/25)*25)
    charts=[]
    for b,color in zip(brand_order,chart_colors):
        charts.append(line_chart(b,series[b],periods,color,f'{brands[b]["products"]}개 장비 평균',ceiling))
    P(15,'브랜드별 제품평균 합산점 · 발행 반기 구분',
      '브랜드별 숫자를 정수로 반올림하고 발행 반기 순서대로 연결했습니다. 단위는 장비별 노출 순위 점수 합계의 제품평균입니다.',
      compare('가로축: 글 발행 반기 · 세로축: 현재 노출 점수의 제품평균. 모든 그래프에 같은 세로축을 사용합니다. 과거 당시 점수 변화가 아닙니다.')+
      '<div class="brand-lines">'+''.join(charts)+'</div>'+
      note(f'세로축 공통 범위: 0~{ceiling}점(그림 눈금이며 만점 아님). 숫자는 반올림 표시, 선 위치는 원값 기준입니다. 매칭 관측이 없는 반기는 점을 그리거나 선으로 연결하지 않습니다.'),period_note)

    theme_series={g:[next(x['index'] for x in p['themes'] if x['group']==g) for p in periods] for g,label in groups}
    theme_ceiling=max(25,math.ceil(max(v for values in theme_series.values() for v in values)/25)*25)
    theme_charts=[]
    for (g,label),color in zip(groups,['#087e86','#3364a0','#ac6b16']):
        n=sum(p['group']==g for p in r['products'])
        theme_charts.append(line_chart(label,theme_series[g],periods,color,f'{n}개 장비 평균',theme_ceiling))
    P(16,'장비 분류별 제품평균 합산점 · 발행 반기 구분',
      '대형 비디오바·소형 비디오바·모듈형의 숫자를 정수로 반올림하고 발행 반기 순서대로 연결했습니다. 단위는 평균 합산점입니다.',
      compare('가로축: 글 발행 반기 · 세로축: 현재 노출 점수의 제품평균. 세 분류에 같은 세로축을 적용합니다. 과거 당시 점수 변화가 아닙니다.')+
      '<div class="brand-lines theme-lines">'+''.join(theme_charts)+'</div>'+
      note(f'세로축 공통 범위: 0~{theme_ceiling}점(그림 눈금이며 만점 아님). 숫자는 반올림 표시, 선 위치는 원값 기준입니다. 매칭 관측이 없는 반기는 선으로 연결하지 않습니다.'),period_note)

    cohort_ceiling=max(1,max(x["index"] for period in periods for x in period["brands"]+period["theme_brands"]))
    for number,p in enumerate(periods,17):
        rows=[]
        for b in brand_order:
            whole=next(x for x in p['brands'] if x['brand']==b)
            subset={x['group']:x for x in p['theme_brands'] if x['brand']==b}
            values=[whole['index'],*[subset[g]['index'] if g in subset else None for g,_ in groups]]
            cells=trend_cells(values,cohort_ceiling)
            rows.append([b,whole['posts'],whole['blogs'],*cells])
        P(number,f'{p["label"]} 발행 글 · 브랜드별 수량·점수 집계',
          '앞의 두 숫자는 글 수·블로그 수입니다. 뒤 네 숫자는 장비별 노출 순위 점수 합계의 제품평균이며 같은 점수 단위입니다.',
          T(['브랜드',H('매칭 글 수','개'),H('매칭 블로그 수','곳'),H('브랜드 전체','평균 합산점'),*[H(label,'평균 합산점') for _,label in groups]],rows,
            '개수와 점수는 직접 비교하지 않습니다. 선은 점수 칼럼만 연결하며 시간 변화가 아닙니다. 모든 반기 장표에 같은 세로축을 적용했습니다. 숫자는 정수로 반올림하고 선 위치는 원값을 사용합니다. 브랜드마다 선정 장비 구성이 다릅니다.',compact=True,trend='category')+
          note(f'해당 반기 글 집단 전체: {p["posts"]}개 고유 글·{p["blogs"]}개 고유 블로그. 브랜드별 행을 합하면 중복 글·블로그가 포함될 수 있습니다.'),period_note)

    for number,(g,label) in enumerate(groups,22):
        rows=[]
        ceiling=max(1,max(x['observed_score_sum'] for p in periods for x in p['products'] if products[x['product_id']]['group']==g))
        for product in [x for x in r['products'] if x['group']==g]:
            rows.append([E(product['brand']),E(product['product']),
              *trend_cells([next(x['observed_score_sum'] for x in p['products'] if x['product_id']==product['product_id']) for p in periods],ceiling)])
        P(number,f'{label} · 장비별 점수 합계·발행 반기 구분',
          '각 숫자는 해당 반기에 발행된 글을 대상으로 계산한 “장비별 모든 블로그의 노출 순위 점수 합계”입니다. 제품평균을 적용하지 않았습니다.',
          T(['브랜드','장비',*time_headers],rows,
            '숫자는 정수로 반올림해 선 아래 표시합니다. 같은 표의 모든 행은 같은 세로축을 사용하며 선 위치는 원값 기준입니다. 매칭 관측이 없는 칸은 연결하지 않습니다. 과거 당시 점수 변화가 아닙니다.',compact=True,trend=True),period_note)

    glossary=[
      ['매칭 게시글 수','해당 브랜드·장비와 연결된 고유 게시글 URL 수','개','현재 검색에 잡힌 표본. 전체 발행량 아님.'],
      ['매칭 블로그 수','매칭 글의 작성 블로그 ID 수','곳','ID 중복 제거. 회사 수·전문 업체 수 아님.'],
      ['검색 최고 순위','해당 검색어에서 그 블로그의 가장 앞선 매칭 글 위치','위','낮을수록 상위. 검색 API 결과 기준.'],
      ['노출 순위 점수','한 장비의 한글·영문 검색 최고 순위 역수 평균 ×100','0~100점','블로그 1곳·장비 1개 단위.'],
      ['공통 검색어 브랜드 관측점','7개 공통 검색어의 브랜드별 기존 매칭 글 최고 순위 역수 평균 ×100','0~100점','기존 표본 한정. 점유율·운영 품질 아님.'],
      ['매칭 관측 없음','집계 대상의 매칭 글이 현재 표본에 없음','결측 표기','과거 0점·전체 게시글 부재를 뜻하지 않음.'],
      ['대상 장비 없음','해당 브랜드·분류의 장비를 선정하지 않음','대상 제외','분석한 제품의 0점과 구분.'],
    ]
    P(25,'칼럼별 정의·집계 단위',
      '개수·검색 순위·공통 검색어 관측점을 구분합니다. 기존 합계·제품평균 점수 칼럼은 제거했습니다.',
      T(['칼럼 이름','정의','단위','집계 수준'],glossary,'서로 다른 단위 사이에 공통 만점이나 환산 비율은 없습니다.','칼럼 정의',True))

    comparisons=[
      ['같은 장비·같은 검색어에서 블로그 A와 B의 순위','직접 비교 가능','동일 시점·동일 검색 결과 안의 노출 위치 비교'],
      ['같은 장비의 블로그별 노출 순위 점수','직접 비교 가능','동일한 한글·영문 검색어 및 계산식 적용'],
      ['공통 검색어별 브랜드 최고 순위·관측점','기존 표본 내 비교','동일 검색어·동일 시점. 새 글·미분류 글 제외 및 브랜드별 표본 차이 존재'],
      ['2024년·2026년 발행 글 열의 숫자','현재 분포만 비교','과거 측정값이 아니라 같은 현재 순위를 발행 시기로 구분'],
      ['글 수와 노출 순위 점수','직접 비교 불가','수량과 순위 기반 계산값으로 단위가 다름'],
    ]
    P(26,'지표별 정량 비교 가능 범위',
      '비교 가능 여부는 장비·검색어·수집 시점·계산식·집계 수준이 같은지를 기준으로 구분합니다.',
      T(['비교 항목','비교 범위','기준'],comparisons,'직접 비교 가능은 현재 검색 성과의 비교를 뜻합니다. 글의 품질이나 장비 관련성 검토 완료를 의미하지 않습니다.','비교 기준',True)+
      note('장비명 검색에서 서로 다른 블로그 점수를 합산·평균한 장표는 제거했습니다. 공통 검색어 결과도 기존 수집 범위에 한정되며 전체 브랜드 품질 평가가 아닙니다.'))
