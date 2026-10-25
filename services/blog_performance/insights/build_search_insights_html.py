from services.blog_performance.insights.search_report_blog_directory import blog_link
"""Standalone, paged HTML report from the saved diagnostic observations."""
import html
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'data/blog_performance/product-search/20261021T054347Z/name-matched-diagnostic/report.json'
OUT=ROOT/'static/reports/blog-search-insights-20261022.html'
e=lambda x:html.escape(str(x))

def build(source=SOURCE, out=OUT, common_path=None, products_path=None):
    source=Path(source); out=Path(out)
    r=json.loads(source.read_text(encoding='utf-8'))
    products={p['product_id']:p for p in r['products']}
    slides=[]
    titles=[]
    def page(kicker,title,lead,body,note='장비명 매칭 기반 잠정 관측입니다. 제품 품질·시장점유율·네이버 공식 점수가 아닙니다.'):
        titles.append(title)
        slides.append(f'<section class="slide"><header><span class="eyebrow">{e(kicker)}</span><span class="stamp">OCEANTECH · SEARCH METRICS</span></header><h1>{title}</h1><p class="lead">{lead}</p><div class="content">{body}</div><footer><span>{e(note)}</span><span class="folio">{len(slides)+1:02}</span></footer></section>')
    def metric(value,label,sub=''):
        return f'<div class="metric"><strong>{e(value)}</strong><span>{e(label)}</span><small>{e(sub)}</small></div>'
    def callout(title,text):return f'<div class="callout"><b>{title}</b><p>{text}</p></div>'
    bloglink=blog_link
    def compare(text,mode='조건부 비교'):
        tone='direct' if mode=='직접 비교 가능' else 'conditional'
        return f'<div class="comparison {tone}"><b>{e(mode)}</b><span>{text}</span></div>'
    def column(label):
        definitions={
          '매칭 글':'매칭 게시글 수<small>중복 URL 제거 · 개</small>',
          '매칭 글 수':'매칭 게시글 수<small>중복 URL 제거 · 개</small>',
          '글':'매칭 게시글 수<small>중복 URL 제거 · 개</small>',
          '현재 매칭 글':'현재 검색에 남은 글<small>해당 반기에 발행 · 개</small>',
          '블로그':'매칭 블로그 수<small>블로그 ID 중복 제거 · 곳</small>',
          '현재 매칭 블로그':'해당 글의 블로그 수<small>해당 반기 · ID 중복 제거</small>',
          '블로그당 평균 글':'블로그당 매칭 글<small>게시글 수 ÷ 블로그 수</small>',
          '블로그 제품점수 /100':'오우션 검색점수<small>제품별 별칭 순위 · 0~100</small>',
          '블로그 제품점수':'해당 블로그 검색점수<small>제품별 별칭 순위 · 0~100</small>',
          '제품점수 /100':'블로그 검색점수<small>같은 제품 · 0~100</small>',
          '한글 검색':'한글 검색 최고 순위<small>API 원래 순위 · 낮을수록 상위</small>',
          '영문 검색':'영문 검색 최고 순위<small>API 원래 순위 · 낮을수록 상위</small>',
          '노출점 합산':'모든 블로그 점수 합계<small>해당 제품 · 100 초과 가능</small>',
          '오우션 /100':'오우션 검색점수<small>해당 제품 · 0~100</small>',
          '최대 기여 블로그':'점수 기여가 가장 큰 블로그<small>해당 제품 검색점수 기준</small>',
          '주요 기여 블로그':'점수 기여가 가장 큰 블로그<small>해당 제품 검색점수 기준</small>',
          '전체 지표':'브랜드 제품평균 합산점<small>제품별 합계의 평균</small>',
          '대형 비디오바':'대형 비디오바<small>해당 브랜드 제품평균 합산점</small>',
          '소형':'소형 비디오바 평균<small>해당 브랜드 제품평균 합산점</small>',
          '모듈형':'모듈형 평균<small>해당 브랜드 제품평균 합산점</small>',
          '해당 글 집단 내 지표가 큰 브랜드':'평균 합산점이 큰 브랜드<small>그 반기 글만 집계 · 우열 확정 아님</small>',
        }
        return definitions.get(label,label)
    def table(headers,rows,cls='',reading='동일 단위의 관측량은 비교할 수 있지만, 제품·검색어가 다르면 동일 경쟁 조건은 아닙니다.',mode='조건부 비교'):
        return compare(reading,mode)+f'<table class="{cls}"><thead><tr>'+''.join(f'<th scope="col">{column(h)}</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{x}</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'
    from services.blog_performance.insights.search_report_metric_pages import build_pages
    halfyear=json.loads((source.parent/'halfyear-report.json').read_text(encoding='utf-8'))
    browser_pointer=json.loads((ROOT/'data/blog_performance/browser-search/latest-common.json').read_text(encoding='utf-8')) if not common_path else {}
    browser_report=json.loads((Path(common_path) if common_path else ROOT/browser_pointer['report']).read_text(encoding='utf-8'))
    product_pointer=ROOT/'data/blog_performance/browser-search/latest-products-ko.json'
    product_metadata=json.loads(product_pointer.read_text(encoding='utf-8')) if product_pointer.exists() else {}
    product_report=json.loads((Path(products_path) if products_path else ROOT/product_metadata['report']).read_text(encoding='utf-8')) if products_path or product_metadata.get('report') else None
    build_pages(r,halfyear,source,page,table,compare,browser_report,product_report)
    from services.blog_performance.insights.search_report_matrices import build_matrices
    build_matrices(r,source,page,table,common_path=common_path,products_path=products_path)
    from services.blog_performance.insights.search_report_activity import build_activity
    build_activity(r,halfyear,page,table,compare,source=source.parent/'matched-hits.json')

    # Explain the measures before comparing them; move from overview to detail.
    find_pages=lambda predicate:[i+1 for i,t in enumerate(titles) if predicate(t)]
    sections=[
        ('실제 블로그 탭 · 브랜드 매칭',find_pages(lambda t:t=='블로그 탭 검색 순서 · 브랜드별 기존 글 매칭'),'7개 공통 검색어의 제공 화면 순서입니다.'),
        ('장비별 검색 위치 · 대형 → 중형 → 소형 → 모듈형',find_pages(lambda t:'블로그별 한글 검색 화면 위치' in t),'장비별 실제 한글 검색 위치입니다. 영문 순위는 미수집입니다.'),
        ('발행 반기별 활동량 · 글 수',[14]+find_pages(lambda t:'발행 반기별 매칭 글 수' in t),'전체·브랜드·장비 종류·개별 장비의 발행 시기별 글 수입니다.'),
    ]
    original_slides=slides[:];original_titles=titles[:]
    order=[n for _,numbers,_ in sections for n in numbers]
    assert len(order)==len(set(order)) and all(1<=n<=len(slides) for n in order)
    toc=[];next_page=2
    for name,numbers,description in sections:
        links=''.join(f'<a href="#page-{next_page+i}"><span>{next_page+i:02}</span>{original_titles[n-1]}</a>' for i,n in enumerate(numbers))
        toc.append(f'<section class="toc-group"><h2>{e(name)} <small>{next_page:02}–{next_page+len(numbers)-1:02}</small></h2><p>{e(description)}</p><div>{links}</div></section>')
        next_page+=len(numbers)
    slides.clear();titles.clear()
    page('목차','보고서 목차·읽는 순서','실제 블로그 탭의 브랜드 매칭 → 장비명 검색 위치 → 발행 시기별 글 수 순서입니다.',
         '<div class="toc-grid">'+''.join(toc)+'</div>',
         '발행 시기별 집계는 현재 검색 결과의 발행일 구분이며, 과거 당시의 검색 순위 변화가 아닙니다.')
    for position,old in enumerate(order,2):
        slide=original_slides[old-1]
        slide=re.sub(r'(<span class="eyebrow">).*?(</span>)',lambda m:m[1]+f'{position:02} / 지표 집계'+m[2],slide,count=1)
        slide=re.sub(r'(<span class="folio">).*?(</span>)',lambda m:m[1]+f'{position:02}'+m[2],slide,count=1)
        slides.append(slide)

    css='''
    .top5-audit{border-top:4px solid #172b3a;margin-top:52px;padding:36px 24px 24px;background:#f0f1f2}.top5-audit .annotation-label{display:block;color:#536777;font-size:12px;font-weight:700;margin-bottom:12px}.top5-audit tbody tr:nth-child(even){background:#e7e9eb}.top5-audit>h2:first-child{margin-top:0}.top5-audit h2{margin-top:28px}.top5-audit td{vertical-align:top}.top5-audit td:first-child{width:55px}.top5-audit td:nth-child(2){width:38%}.top5-audit td:last-child{width:37%}@media print{.slide:has(.top5-audit){height:auto;min-height:210mm}.top5-audit tr{break-inside:avoid}.top5-audit h2{break-after:avoid}}
    .common-brand-matrix{table-layout:fixed}.common-brand-matrix th,.common-brand-matrix td{text-align:center;padding:9px 4px}.common-brand-matrix th:first-child{width:95px}.common-brand-matrix th:first-child,.common-brand-matrix td:first-child{text-align:left}.common-brand-matrix th{font-size:10px;word-break:keep-all}.common-brand-matrix .rank-pill{font-size:12px;padding:5px}.common-brand-matrix td:last-child{font-size:12px}
    .heat-legend{display:flex;align-items:center;gap:24px;font-size:11px;margin-top:18px}.heat-legend>span{min-width:55px}.heat-legend .matrix-value{margin-top:4px}
    .matrix-value{display:block;padding:5px 7px;background:rgba(8,126,134,var(--shade));border-radius:4px;text-align:center;font-weight:700}.matrix-none{color:#87949b;font-size:10px}.integrated td small{display:block;font-size:9px;color:#526777}.rank-matrix{table-layout:fixed}.rank-matrix th:first-child{width:150px}.rank-matrix th,.rank-matrix td{text-align:center;padding:7px 3px}.rank-matrix th:first-child,.rank-matrix td:first-child{text-align:left}.rank-matrix th{font-size:9px}.rank-matrix th small{font-size:9px}.rank-pair{display:flex;gap:3px;justify-content:center;white-space:nowrap}.rank-pill{display:inline-block;padding:3px;border-radius:4px;font-size:10px;font-weight:700}.rank-pill.top1{background:#08754d;color:white}.rank-pill.top3{background:#c2e8d5;color:#154e39}.rank-pill.top10{background:#d2e5fa;color:#214c7d}.rank-pill.other{background:#e9edf0;color:#556574}.matrix-legend{font-size:11px;line-height:1.6}.query-details{font-size:10px;color:#536777;margin-top:12px}.query-details p{margin-top:5px}table tbody tr:has(a[data-ocean-own="true"]){background:#fff5d8}.rank-matrix td:first-child small{display:block;font-size:9px;color:#8e651d}
    @media print{.rank-matrix th:first-child{width:115px}.rank-matrix th,.rank-matrix td{padding:6px 2px}.rank-pill{font-size:8px;padding:2px}.rank-pair{gap:2px}.matrix-legend{font-size:9px}.query-details{display:none}.matrix-value{padding:3px}.integrated td{padding:5px!important}}
    .rank-stack{display:flex;flex-wrap:wrap;justify-content:center;gap:5px}.expanded-top10 td{padding-top:11px!important;padding-bottom:11px!important;vertical-align:middle}
    @media print{.slide:has(.expanded-top10),.slide[hidden]:has(.expanded-top10){display:block!important;height:auto;min-height:210mm}.expanded-top10 tr{break-inside:avoid}}
    .row-trends{table-layout:fixed}.row-trends th:nth-child(1){width:10%}.row-trends th:nth-child(2){width:23%}.row-trends td:nth-child(n+3){padding:4px 0!important}.row-trends.categorical th:nth-child(2){width:11%}.row-trends.categorical th:nth-child(3){width:11%}.row-trend{display:block;width:100%;height:110px}.row-trends td{vertical-align:middle}.row-trends .empty{display:block;text-align:center;font-size:9px}
    .toc-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px 32px}.toc-group{border-top:2px solid #087e86;padding-top:8px}.toc-group h2{font-size:17px;margin:0 0 4px}.toc-group h2 small{float:right;font-size:12px;color:#536777}.toc-group p{font-size:11px;color:#536777;margin:0 0 6px;line-height:1.5}.toc-group a{display:flex;gap:10px;font-size:12px;line-height:1.5;padding:2px 0}.toc-group a span{font-weight:700;min-width:20px}.toc-group a:hover{background:#edf5f4}
    @media(max-width:800px){.toc-grid{grid-template-columns:1fr}}
    @media print{.toc-grid{gap:10px 25px}.toc-group h2{font-size:14px}.toc-group p{font-size:9px}.toc-group a{font-size:10px;padding:1px 0}}
    :root{--ink:#172b3a;--muted:#536777;--teal:#087e86;--lime:#dfe9b0;--line:#d8e1e5;--paper:#fff;--bg:#e8eef0}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 "Malgun Gothic","Apple SD Gothic Neo",sans-serif}a{color:#087580;text-decoration:none}a:hover{text-decoration:underline}
    .toolbar{height:62px;background:#172b3a;color:white;display:flex;align-items:center;gap:12px;padding:0 24px;position:sticky;top:0;z-index:10}.toolbar strong{margin-right:auto;font-size:14px}.toolbar button,.toolbar select{font:inherit;font-size:13px;border:1px solid #5c727f;background:#233d4c;color:#fff;border-radius:6px;padding:6px 12px;cursor:pointer}.toolbar .count{font-size:12px;color:#d3dfe4;min-width:48px;text-align:center}
    main{padding:24px 20px}.slide{width:min(1240px,100%);min-height:800px;margin:0 auto 28px;background:var(--paper);padding:42px 58px 28px;display:flex;flex-direction:column;box-shadow:0 8px 35px #182f4014;border-top:6px solid var(--teal)}.slide[hidden]{display:none!important}
    header{display:flex;justify-content:space-between;align-items:center;margin-bottom:22px;gap:20px}.eyebrow{font:700 12px/1.2 sans-serif;letter-spacing:1.7px;color:var(--teal)}.stamp{font:10px/1.2 sans-serif;letter-spacing:1.2px;color:#74858f}
    h1{font-size:36px;line-height:1.4;letter-spacing:-1.8px;margin:0 0 14px;font-weight:800}h2{font-size:19px;line-height:1.5;margin:0 0 10px}p{margin:0 0 12px}.lead{font-size:17px;color:var(--muted);max-width:1010px;margin-bottom:26px}.lead b{color:var(--ink)}.content{flex:1}footer{display:flex;align-items:flex-end;justify-content:space-between;border-top:1px solid var(--line);margin-top:22px;padding-top:12px;gap:24px;color:#657783;font-size:11px;line-height:1.5}.folio{font:700 22px/1 sans-serif;color:var(--teal)}
    .metrics{display:grid;gap:24px;margin:8px 0 32px}.four{grid-template-columns:repeat(4,1fr)}.three{grid-template-columns:repeat(3,1fr)}.metric{border-left:3px solid var(--teal);padding-left:18px;display:flex;flex-direction:column}.metric strong{font:700 44px/1.3 sans-serif;letter-spacing:-1.5px}.metric span{font-size:14px;font-weight:700;margin-top:8px}.metric small{font-size:11px;color:var(--muted);margin-top:5px}.columns{display:grid;grid-template-columns:1fr 1fr;gap:34px;margin-top:25px}.columns>div{padding:20px 0}.columns>.tint{padding:20px 24px}.tint{background:#edf5f4;border-radius:3px}ul{padding-left:20px;margin:0}li{margin:8px 0}.callout{border-left:4px solid var(--teal);background:#edf5f4;padding:18px 22px;margin-top:25px}.callout b{font-size:18px}.callout p{margin:8px 0 0;font-size:15px}.takeaway{border-top:2px solid var(--teal);padding-top:16px;margin-top:26px;font-size:16px}.micro{font-size:11px;color:var(--muted);line-height:1.6;margin-top:18px}
    table{border-collapse:collapse;width:100%;font-size:14px}th{text-align:left;font-weight:700;color:var(--muted);font-size:12px;border-bottom:2px solid var(--ink);padding:10px 12px}td{border-bottom:1px solid var(--line);padding:12px}tbody tr:nth-child(even){background:#f6f9f9}td:not(:first-child){font-variant-numeric:tabular-nums}.heatmap td{padding:6px 12px}.heat{display:block;padding:10px 16px;background:rgba(8,126,134,var(--heat));border-radius:3px;color:#122f34;font-weight:700}.heatmap tbody tr:nth-child(even){background:none}.empty{font-size:11px;color:#80919b}.compact{font-size:12px}.compact th{font-size:10px;padding:8px}.compact td{padding:9px 8px}.compact td:last-child{font-size:11px;white-space:nowrap}
    th small,td>small{display:block;color:#6b7a83;font-size:10px;font-weight:400;line-height:1.45;margin-top:4px}.heat small{font-size:9px;font-weight:400;white-space:nowrap}.comparison{display:flex;gap:12px;align-items:flex-start;border-left:3px solid #bb8a27;background:#fbf7ed;padding:10px 13px;margin:0 0 12px;font-size:12px;line-height:1.6}.comparison>b{white-space:nowrap;color:#805b16}.comparison.direct{background:#eaf4f0;border-left-color:#168060}.comparison.direct>b{color:#156448}.comparison span{color:#455964}.compact td:last-child{white-space:normal}.barhead{grid-template-columns:110px 1fr 64px 90px}.barrow{grid-template-columns:110px 1fr 64px 90px}
    .barhead,.barrow{display:grid;grid-template-columns:110px 1fr 50px 80px;gap:18px;align-items:center}.barhead{font-size:11px;color:var(--muted);margin-bottom:12px}.barrow{margin:13px 0;font-size:14px}.barrow>strong,.barrow>span{text-align:right;font-variant-numeric:tabular-nums}.barrow>span{color:var(--teal);font-weight:700}.track{height:22px;background:#edf1f2}.track i{display:block;height:100%;background:#087e86;border-radius:0 2px 2px 0}
    .steps article{display:flex;align-items:flex-start;gap:22px;border-bottom:1px solid var(--line);padding:22px 0}.steps article>span{font:700 32px/1.2 sans-serif;color:var(--teal)}.steps article>div{flex:1}.steps article h2{margin:0 0 5px}.steps article p{margin:0;font-size:14px;color:var(--muted)}.steps article>b{font-size:11px;background:#e7efcb;padding:5px 10px;white-space:nowrap}.formula{border:1px solid var(--line);padding:24px!important}.formula p{font-size:20px;line-height:1.6;font-weight:700;color:var(--teal)}.formula small{font-size:12px;color:var(--muted)}.method-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px 32px;margin-top:24px;font-size:13px}.method-grid p{color:var(--muted);margin-top:5px}
    @media(max-width:800px){main{padding:12px 8px}.slide{padding:25px 20px;min-height:0}h1{font-size:27px}.stamp{display:none}.columns,.method-grid{grid-template-columns:1fr;gap:8px}.four,.three{grid-template-columns:repeat(2,1fr)}.metric strong{font-size:34px}.lead{font-size:15px}.toolbar{padding:0 10px;gap:6px}.toolbar strong{font-size:11px}.toolbar select{max-width:125px}.content{overflow-x:auto}.barhead,.barrow{grid-template-columns:78px 1fr 36px 54px;gap:8px;font-size:11px}table{font-size:11px;min-width:530px}.compact{min-width:760px}}
    @media(max-width:800px){.toolbar{flex-wrap:wrap;height:auto;min-height:62px;padding:8px 10px}.toolbar strong{flex-basis:100%}.toolbar select{max-width:110px}.toolbar button,.toolbar select{font-size:11px;padding:5px 8px}.toolbar .count{min-width:36px}}
    .brand-lines{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:22px 20px;margin-top:20px}.brand-line{margin:0;min-width:0;border-bottom:1px solid var(--line);padding-bottom:7px}.brand-line figcaption{display:flex;align-items:baseline;justify-content:space-between;gap:5px;margin:0 0 6px;font-size:14px}.brand-line figcaption small{font-size:10px;color:var(--muted)}.brand-line svg{display:block;width:100%;height:auto;font-family:"Malgun Gothic",sans-serif}
    @media(max-width:800px){.brand-lines{grid-template-columns:repeat(2,minmax(0,1fr));gap:20px 12px}.brand-line figcaption{display:block}.brand-line figcaption small{display:block}.brand-line figcaption b{font-size:13px}}
    .theme-lines{grid-template-columns:repeat(3,minmax(0,1fr));margin-top:38px;gap:24px}
    @media(max-width:800px){.theme-lines{grid-template-columns:1fr}}
    @media print{.row-trends .row-trend{height:100px}.row-trends td{padding-top:6px!important;padding-bottom:6px!important}.row-trends tr{break-inside:avoid}.slide:has(.row-trends),.slide[hidden]:has(.row-trends){display:block!important;height:auto;min-height:210mm}.slide:has(.row-trends) .content{overflow:visible}}
    @page{size:A4 landscape;margin:0}
    @media print{html,body{background:white;font-size:12px;-webkit-print-color-adjust:exact;print-color-adjust:exact}.toolbar{display:none}main{padding:0}.slide,.slide[hidden]{display:flex!important;width:297mm;height:210mm;min-height:0;margin:0;padding:12mm 15mm 8mm;border-top:2mm solid var(--teal);box-shadow:none;break-after:page;page-break-after:always;overflow:visible}.slide:last-child{break-after:auto;page-break-after:auto}h1{font-size:27px;line-height:1.35;margin-bottom:9px;letter-spacing:-1.1px}header{margin-bottom:14px}.lead{font-size:13px;line-height:1.65;margin-bottom:16px}.metrics{margin-bottom:20px;gap:18px}.metric strong{font-size:36px}.metric span{font-size:12px}.metric small{font-size:9px}.columns{gap:25px;margin-top:15px}.columns>div{padding:13px 0}.columns>.tint{padding:15px 18px}h2{font-size:16px}li{margin:5px 0}.callout{padding:12px 17px;margin-top:17px}.callout b{font-size:15px}.callout p{font-size:12px}.takeaway{font-size:12px;margin-top:18px;padding-top:12px}.micro{font-size:9px;margin-top:12px}table{font-size:12px;min-width:0}th{font-size:10px;padding:8px 10px}td{padding:9px 10px}.heatmap td{padding:4px 10px}.heat{padding:7px 13px}.barrow{margin:9px 0}.track{height:18px}.steps article{padding:15px 0}.steps article h2{font-size:16px}.steps article p{font-size:12px}.formula{padding:17px!important}.formula p{font-size:16px}.method-grid{font-size:11px;gap:15px 25px;margin-top:18px}.compact{font-size:10px}.compact th{font-size:9px;padding:6px}.compact td{padding:7px 6px}.compact td:last-child{font-size:9px}footer{font-size:9px;margin-top:13px;padding-top:9px}.folio{font-size:18px}}
    @media print{.comparison{font-size:10px;padding:7px 10px;gap:10px;margin-bottom:9px;line-height:1.5}th small,td>small{font-size:8px;margin-top:2px}.compact td{padding:4px 6px}.compact th{padding:5px 6px}.heat small{font-size:8px}.heat{padding:5px 10px}.slide:nth-child(15) td{padding:5px 9px}.slide:nth-child(15) .columns{font-size:11px;margin-top:10px}.slide:nth-child(15) .columns>div{padding:10px 0}.slide:nth-child(15) .columns>.tint{padding:10px 16px}}
    @media print{.brand-lines{grid-template-columns:repeat(4,minmax(0,1fr));gap:18px 16px;margin-top:14px}.brand-line figcaption{font-size:12px}.brand-line figcaption small{font-size:8px}.theme-lines{grid-template-columns:repeat(3,minmax(0,1fr));margin-top:28px}}
    '''
    js='''const slides=[...document.querySelectorAll('.slide')];const select=document.querySelector('#jump');let current=0;let all=false;slides.forEach((s,i)=>{let o=document.createElement('option');o.value=i;o.textContent=String(i+1).padStart(2,'0')+' · '+s.querySelector('h1').innerText.replace(/\\n/g,' ');select.appendChild(o)});function show(n){current=Math.max(0,Math.min(slides.length-1,n));slides.forEach((s,i)=>s.hidden=!all&&i!==current);select.value=current;document.querySelector('#count').textContent=(current+1)+' / '+slides.length;document.querySelector('#prev').disabled=current===0;document.querySelector('#next').disabled=current===slides.length-1;location.hash='page-'+(current+1)}document.querySelector('#prev').onclick=()=>show(current-1);document.querySelector('#next').onclick=()=>show(current+1);select.onchange=()=>show(Number(select.value));document.querySelector('#all').onclick=()=>{all=!all;document.querySelector('#all').textContent=all?'한 장씩 보기':'전체 보기';show(current)};document.querySelector('#print').onclick=()=>window.print();document.addEventListener('keydown',ev=>{if(['SELECT','INPUT','TEXTAREA'].includes(document.activeElement.tagName))return;if(ev.key==='ArrowRight'||ev.key==='PageDown'){ev.preventDefault();show(current+1)}if(ev.key==='ArrowLeft'||ev.key==='PageUp'){ev.preventDefault();show(current-1)}});window.addEventListener('hashchange',()=>{const n=(Number(location.hash.replace('#page-',''))||1)-1;if(n!==current)show(n)});const initial=Number(location.hash.replace('#page-',''))||1;show(initial-1);'''
    document='<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>브랜드·장비별 블로그 검색 지표 집계</title><style>'+css+'</style></head><body><nav class="toolbar" aria-label="보고서 이동"><strong>블로그 검색 지표 집계 · 잠정</strong><button id="toc" onclick="location.hash=&quot;page-1&quot;">목차</button><button id="prev" aria-label="이전 장">←</button><span class="count" id="count"></span><button id="next" aria-label="다음 장">→</button><select id="jump" aria-label="페이지 선택"></select><button id="all">전체 보기</button><button id="print">인쇄 / PDF</button></nav><main>'+''.join(slides)+'</main><script>'+js+'</script></body></html>'
    out.parent.mkdir(exist_ok=True,parents=True);out.write_text(document,encoding='utf-8')
    print(json.dumps({'html':str(out),'pages':len(slides),'bytes':out.stat().st_size},ensure_ascii=False))

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=OUT);p.add_argument('--common',type=Path);p.add_argument('--products',type=Path);p.add_argument('--activity-source',type=Path,default=SOURCE);a=p.parse_args()
    build(a.activity_source,a.out,a.common,a.products)

if __name__=='__main__':main()
