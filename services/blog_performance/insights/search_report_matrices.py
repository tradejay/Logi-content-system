from services.blog_performance.insights.search_report_blog_directory import blog_link
"""Integrated matrices from the same saved observations; no new scoring."""
import html
import json
from pathlib import Path
from collections import defaultdict

E=lambda x:html.escape(str(x))

def build_matrices(r,source,page,table,common_path=None,products_path=None):
    groups=[('bar','대형 비디오바'),('small','소형 비디오바'),('modular','모듈형·분리형')]
    hits=json.loads((source.parent/'matched-hits.json').read_text(encoding='utf-8'))
    def heat(v,ceiling=100):
        if not v:return '<span class="matrix-none">—</span>'
        ratio=min(v/ceiling,1)
        shade=.04+.96*ratio**3
        ink='#fff' if shade>=.6 else '#172b3a'
        return f'<span class="matrix-value" style="--shade:{shade:.3f};color:{ink}" title="원값 {v} · 색상 기준 상한 {ceiling:.2f} · 고점 강조 곡선">{v:.0f}</span>'
    link=blog_link
    def rank(v):
        if not v:return '<span class="matrix-none">—</span>'
        cls='top1' if v==1 else 'top3' if v<=3 else 'top10' if v<=10 else 'other'
        return f'<span class="rank-pill {cls}">{v}위</span>'
    note='2026-10-21 검색 API 기준 · 장비명 매칭 기반 잠정 관측 · 통합검색 순위·공식 점수·시장점유율이 아닙니다.'
    product_pointer=Path(__file__).resolve().parents[3]/'data/blog_performance/browser-search/latest-products-ko.json'
    product_data=json.loads(product_pointer.read_text(encoding='utf-8')) if product_pointer.exists() else {}
    if products_path or product_data.get('report'):
        from services.blog_performance.insights.search_report_device_browser import build_device_browser_matrices
        product_report=json.loads((Path(products_path) if products_path else Path(__file__).resolve().parents[3]/product_data['report']).read_text(encoding='utf-8'))
        build_device_browser_matrices(product_report,page,table)
    for g,label in ([] if products_path or product_data.get('report') else groups):
        products=[p for p in r['products'] if p['group']==g]
        ceiling=max(p['observed_blog_score_sum'] for p in products)
        rows=[]
        for p in products:
            top=p['top_blogs'][0] if p['top_blogs'] else None
            rows.append([E(p['brand']),E(p['product']),p['matched_posts'],p['matched_blogs'],
                heat(p['observed_blog_score_sum'],ceiling),link(top['blog_id']) if top else '—',
                heat(top['score']) if top else '—',heat(p['own_observed_score'])])
        page('장비 통합 매트릭스',label+' · 장비별 수량·노출 점수 매트릭스',
             '여러 브랜드 상세표를 한 표로 통합했습니다. 행은 장비, 열은 글 수·블로그 수·점수·최고점 블로그·오우션입니다.',
             table(['브랜드','장비','글 수<small>고유 URL · 개</small>','블로그 수<small>ID · 곳</small>',
                    '점수 합계<small>모든 블로그 합산</small>','최고점 블로그','최고점<small>1곳 · 0~100</small>','오우션<small>0~100</small>'],rows,'compact integrated',
                reading='합계 열은 표 안 최대값 기준, 최고점·오우션 열은 0~100 기준입니다. 색상은 고점에서 빠르게 짙어지는 3제곱 곡선이며 숫자 차이에 비례하지 않습니다. —는 매칭 관측 없음입니다. 장비마다 검색어가 다릅니다.') ,note)
        best={}
        for h in hits:
            if h['group']!=g or not h.get('blog_id'):continue
            k=(h['blog_id'],h['product_id'],h['query_id'])
            if k not in best or h['rank']<best[k]['rank']:best[k]=h
        blog_ranks=defaultdict(list)
        for (b,pid,q),h in best.items():blog_ranks[b].append(h['rank'])
        selected=sorted(blog_ranks,key=lambda b:(min(blog_ranks[b]),-sum(v<=10 for v in blog_ranks[b]),b))[:8]
        if 'oceantech01' not in selected:selected.append('oceantech01')
        rows=[]
        for b in selected:
            cells=[]
            for p in products:
                hs=[h for (blog,pid,q),h in best.items() if blog==b and pid==p['product_id']]
                ko=min((h['rank'] for h in hs if any('가'<=c<='힣' for c in h['query'])),default=None)
                en=min((h['rank'] for h in hs if not any('가'<=c<='힣' for c in h['query'])),default=None)
                cells.append('<span class="rank-pair">'+rank(ko)+' '+rank(en)+'</span>')
            rows.append([link(b)+('<small>내 블로그</small>' if b=='oceantech01' else ''),*cells])
        legend='<p class="matrix-legend"><b>칸 안 순서: 한글 / 영문 검색 최고 순위</b> · 진한 초록 1위 · 초록 2~3위 · 파랑 4~10위 · 회색 11위 이하 · — 매칭 관측 없음</p>'
        query_note=' / '.join(E(p['product'])+': '+', '.join(E(q) for q in sorted({h['query'] for h in hits if h['product_id']==p['product_id']})) for p in products)
        page('API 결과 위치 · 실제 화면 순위 아님',label+' · 블로그 × 장비 API 결과 위치',
             f'해당 분류의 블로그 {len(blog_ranks)}곳 중 최고 검색 순위가 앞선 8곳과 오우션입니다. 동순위는 상위 10위권 등장 검색어 수, ID 순으로 선택합니다. 행은 블로그, 열은 장비입니다.',
             legend+table(['블로그 ID',*[E(p['brand'])+'<small>'+E(p['product'])+'</small>' for p in products]],rows,'compact rank-matrix',
                 reading='같은 칼럼의 블로그끼리 동일 검색어 순위를 비교할 수 있습니다. 한글·영문 순위를 합치거나 재정렬하지 않았습니다. 시계열이 없어 전일 대비는 표시하지 않습니다. 순위 기반 SoV 비율을 새로 계산한 표는 아닙니다.',mode='직접 비교 가능')+
             '<details class="query-details"><summary>실제 검색어 확인</summary><p>'+query_note+'</p></details>',note)
    root=Path(__file__).resolve().parents[3]
    pointer=root/'data/blog_performance/browser-search/latest-common.json'
    common_path=Path(common_path) if common_path else root/json.loads(pointer.read_text(encoding='utf-8'))['report']
    common=json.loads(common_path.read_text(encoding='utf-8'))
    audit_path=common_path.parent/'top5-audit.json'
    if not audit_path.exists():audit_path=common_path.parent/'audits/20261023-top5/audit.json'
    audit_note=''
    if audit_path.exists():
        audit=json.loads(audit_path.read_text(encoding='utf-8'))
        parts=['<div class="top5-audit" role="note" aria-label="검색 결과 보충 주석"><span class="annotation-label">주석 · 검색 결과 표시 여부에 대한 보충 설명</span><h2>검색어별 1~5위 · 표에 표시되거나 빠진 이유</h2><p class="micro">제공된 수집 화면의 원래 순서입니다. 브랜드별 최고 위치만 표시한 위 표와 대조합니다. 수집 본문 텍스트 기준이며 이미지 OCR 검토는 하지 않았습니다. Cisco Webex 등 소프트웨어 글도 현재 브랜드 언급 기준에 포함되어 있습니다.</p>']
        for keyword in common['keywords']:
            audit_rows=[]
            for item in audit['rows']:
                if item['keyword']!=keyword:continue
                audit_rows.append([str(item['rank'])+'위','<a href="'+E(item['url'])+'" target="_blank" rel="noopener">'+E(item['title'])+'</a>',E(item['topic']),('<b>표시</b> · ' if item['displayed'] else '<b>미표시</b> · ')+E(item['reason'])])
            parts.append('<h2>'+E(keyword)+'</h2>'+table(['원래 순위','글 · 클릭하여 열기','내용','표시 여부·이유'],audit_rows,'compact',reading='위 브랜드 표는 브랜드별 최고 순위만 표시합니다. 이 목록은 해당 검색어의 원래 1~5위 전체를 유지합니다.'))
        audit_note=''.join(parts)+'</div>'
    assert common['search_surface']=='naver_blog_tab' and common['rank_source']=='user_supplied_browser_capture'
    full_bodies=common.get('classification_scope') in ['all_139_browser_results_bodies','all_browser_result_bodies']
    if full_bodies:
        matching_note=f'제공된 {common["source_unique_posts"]}개 글의 본문을 모두 확보했습니다. 브랜드 연결 {common["coverage"]["matched"]}건 / 고유 글 {common["coverage"]["unique_matched_posts"]}개를 반영했습니다. 나머지 {common["coverage"]["unclassified"]}건은 일반 글·타 브랜드·브랜드 미확정으로 별도 보존했습니다. 브랜드 명시 글은 장비 미확정이어도 반영하며, 모델 후보는 AI 용어 판정을 연결했습니다. 브랜드 언급·추천 여부의 전문 의미 검토는 아닙니다.'
    else:
        matching_note=f'7개 검색어 × 첫 {common["depth"]}개 = {common["source_rows"]}건(고유 글 {common["source_unique_posts"]}개). 장비 분류 매칭 {common["coverage"]["matched"]}건 / 고유 글 {common["coverage"]["unique_matched_posts"]}개만 반영했습니다. 기존 후보 밖 {common["coverage"]["unmatched"]}건과 기존 미분류 {common["coverage"]["unclassified"]}건은 제외했습니다. —는 브랜드가 없거나 30위 밖이라는 확정이 아닙니다.'
    keywords=common['keywords'];rows=[]
    ceiling=max(b['observed_score'] for b in common['brand_scores'])
    for b in common['brand_scores']:
        cells=[]
        by_keyword={x['keyword']:x for x in b['keyword_ranks']}
        for keyword in keywords:
            x=by_keyword[keyword]
            cells.append('<a href="'+E(x['url'])+'" target="_blank" rel="noopener" title="기존 매칭 글 열기">'+rank(x['best_rank'])+'</a>' if x['best_rank'] else '<span class="matrix-none">—</span>')
        value=b['observed_score']
        display='—' if not value else '&lt;1' if value<1 else f'{value:.0f}'
        shade=.04+.96*(value/ceiling)**3 if ceiling else .04
        color='#fff' if shade>=.6 else '#172b3a'
        score_cell=f'<span class="matrix-value" style="--shade:{shade:.3f};color:{color}" title="원값 {value:.6f}">{display}</span>'
        rows.append([E(b['brand']),*cells,score_cell,b['matched_posts']])
    page('블로그 탭 · 제공 화면 순서','블로그 탭 검색 순서 · 브랜드별 기존 글 매칭',
         '제공된 블로그 탭·관련도순 첫 30개 일반 글의 순서입니다. 광고는 제외됐으며, 본문에서 브랜드를 연결한 글의 최고 위치를 표시합니다. 순위를 누르면 근거 글을 엽니다.',
         table(['브랜드',*[E(k)+'<small>분류 글 최고 위치</small>' for k in keywords],'관측 점수<small>0~100 · 제한 표본</small>','매칭 글 수<small>고유 URL · 개</small>'],rows,'compact common-brand-matrix',
             reading=matching_note)+
         '<p class="micro"><b>계산:</b> 관측 점수 = 100 × 수집된 검색어별 최고 순위 역수의 평균. 미관측 칸은 계산 기여만 0입니다. 여러 블로그 점수를 합산하거나 장비 수로 나누지 않습니다. 여러 브랜드를 담은 글은 각 브랜드에 포함될 수 있어 합계 100이 아닙니다.</p>'+
         '<p class="micro"><b>표시:</b> 진한 초록 1위 · 초록 2~3위 · 파랑 4~10위 · 회색 11위 이하. 점수 색은 관측 최고값 기준 3제곱 곡선입니다. 점수는 정수 반올림, 1점 미만은 &lt;1로 표시하며 원값은 마우스를 올려 확인합니다.</p>'+audit_note,
         '제공 화면 수집: '+E(' / '.join(common.get('captured_at',[])))+' · 블로그 탭 · PC/모바일·로그인 상태 미기록 · 통합검색 순위 아님 · API 순서와 별도 저장')
