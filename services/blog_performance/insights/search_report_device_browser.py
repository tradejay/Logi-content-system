"""Device matrices from Korean-only browser captures; never mix English API ranks."""
from services.blog_performance.insights.search_report_metric_pages import E
from services.blog_performance.insights.search_report_blog_directory import blog_link
from services.blog_performance.insights.search_report_room_groups import GROUPS, grouped_report, medium_research


def build_device_browser_matrices(report,page,table):
    report = grouped_report(report)
    def pill(row,unconfirmed=False):
        if not row:return '<span class="matrix-none">—</span>'
        n=row['rank'];cls='top1' if n==1 else 'top3' if n<=3 else 'top10' if n<=10 else 'other'
        return '<a href="'+E(row['url'])+'" target="_blank" rel="noopener" title="'+E(row.get('title',''))+(' · 본문 장비명 미확인' if unconfirmed else '')+'"><span class="rank-pill '+cls+'">'+str(n)+'위'+('*' if unconfirmed else '')+'</span></a>'
    footer='사용자 제공 블로그 탭·관련도순·광고 제외 · 한글 검색만 수집 · 영어 순위는 미수집 · 원래 위치 유지'
    for g,label in GROUPS:
        products=[p for p in report['products'] if p['group']==g]
        if g == 'medium':
            products.sort(key=lambda p: (p['product_id'] != 'VC-009', p['product_id']))
            medium_research(report, page, table)
        rows=[]
        for p in products:
            own=p['own_raw_ranks'][0] if p['own_raw_ranks'] else None
            rows.append([E(p['brand']),E(p['product']),p['raw_results'],p['model_matched_results'],pill(own,own is not None and not own['model_name_matched'])])
        page('실제 블로그 탭 · 한글 장비명',label+' · 한글 장비명 검색의 오우션 위치',
             '각 장비의 한글 검색어 결과에서 오우션 글이 처음 나타난 원래 위치입니다. 다른 모델이 나왔더라도 실제 순서는 바꾸지 않습니다.',
             table(['브랜드','장비','제공 결과 수','장비명 매칭 건수','오우션 원래 최고 위치'],rows,'compact',reading='오우션 위치는 원래 검색 결과의 URL 기준입니다. *는 그 글 본문에서 해당 장비명이 아직 확인되지 않았다는 뜻입니다. 장비명 매칭은 기계 후보이며 전문 의미 검토 완료가 아닙니다.'),footer)
        blogs={}
        for p in products:
            for b in p['blog_ranks']:blogs.setdefault(b['blog_id'],[]).append(b['rank'])
        selected=sorted(blogs,key=lambda b:(min(blogs[b]),-sum(n<=10 for n in blogs[b]),b))[:8]
        if 'oceantech01' not in selected:selected.append('oceantech01')
        focus_ids={p['product_id'] for p in products if p['brand'] in ['Logitech','HP Poly']}
        focus_rows=[r for r in report['rank_rows'] if r['product_id'] in focus_ids and r['rank']<=10]
        if focus_rows:
            focus_blogs={r['blog_id'] for r in focus_rows}
            def focus_order(blog):
                ranks=[min((r['rank'] for r in focus_rows if r['blog_id']==blog and r['product_id']==pid),default=999) for pid in [p['product_id'] for p in products if p['product_id'] in focus_ids]]
                return min(ranks),*ranks,blog
            selected=sorted(focus_blogs,key=focus_order)+[b for b in selected if b not in focus_blogs]
        rows=[]
        for blog in selected:
            cells=[]
            for p in products:
                raw_top=[r for r in focus_rows if r['product_id']==p['product_id'] and r['blog_id']==blog]
                if raw_top:
                    cells.append('<span class="rank-stack">'+''.join(pill(r,r['status']!='catalog_model_name_matched') for r in sorted(raw_top,key=lambda r:r['rank']))+'</span>')
                elif blog=='oceantech01':
                    own=p['own_raw_ranks'][0] if p['own_raw_ranks'] else None
                    cells.append(pill(own,own is not None and not own['model_name_matched']))
                else:cells.append(pill(next((b for b in p['blog_ranks'] if b['blog_id']==blog),None)))
            blog_url='https://'+blog if blog.endswith('.tistory.com') else 'https://blog.naver.com/'+blog
            rows.append([blog_link(blog)+('<small>내 블로그</small>' if blog=='oceantech01' else ''),*cells])
        own_note='오우션 행은 원래 검색 결과에서의 위치입니다. *는 본문 장비명 미확인. 경쟁 블로그는 본문 장비명 매칭 후보 중 최고 순위가 앞선 8곳입니다. 각 칸을 누르면 실제 글을 엽니다.'
        if focus_rows:
            own_note='V는 사용자 지정 오우션 관련 업체입니다. 로지텍·Poly 장비는 1~10위의 모든 원래 결과를 표시합니다. 같은 블로그의 여러 글도 각 순위를 함께 표시합니다. *는 다른 모델이거나 본문 장비명 미확인입니다. 그 밖의 칼럼은 해당 블로그의 장비명 매칭 최고 위치입니다. 각 순위는 해당 글로 연결됩니다.'
        page('실제 블로그 탭 · 한글 검색 순서',label+' · 블로그별 한글 검색 화면 위치',
             '각 칸은 해당 장비의 한글 검색 화면에서 제공된 일반 글 순서입니다. 영문 API 순위는 혼합하지 않았습니다.',
             table(['업체명',*[E(p['brand'])+' '+E(p['product'])+'<small><i>('+E(p['keyword'])+')</i></small>' for p in products]],rows,'compact rank-matrix'+(' expanded-top10' if focus_rows else ''),reading=own_note)+
             '<p class="micro">검색어: '+ ' / '.join(E(p['keyword'])+f' ({p["raw_results"]}개)' for p in products)+'</p>',footer)
