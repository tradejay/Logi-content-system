"""Audit captured top-five results against the displayed brand-best matrix."""
import html,json,re
from collections import Counter
from pathlib import Path
from services.blog_performance.insights.collect_common_query_ranks import ROOT,read,save

# Human-readable content findings from the already saved body texts, not title-only labels.
FINDINGS={
 'dsideaee50/224439052905':('software','네이버 웨일온 사용법','하드웨어 장비 브랜드 비교 대상이 아닌 화상회의 앱 설정 글'),
 'dig_a_bit_deeper/224434829347':('language','화상회의 비즈니스 영어','장비 소개가 아닌 회의 영어 표현 학습 글'),
 'livingchanger/224444650951':('software','Microsoft Teams 설정','팀즈 장치 설정·회의 기능 안내. HP Poly 장비 글이 아님'),
 'iotspace/224391608984':('generic_av','회의실 장비 선택 일반 가이드','장비 이야기는 있지만 특정 모델 설명은 아님. 맥스허브·클릭쉐어는 회사소개 링크 문구에만 등장'),
 'aagg8989/224401781128':('generic_av','대회의실 AV 시스템 설계','카메라·마이크·음향 구성 설명. 수집 본문 텍스트에 비교 7개 브랜드 없음'),
 'dfinemedia/224380594650':('generic_av','대회의실 PTZ·마이크·화자 추적 설계','장비 구성 설명은 있으나 특정 제조사·모델을 명시하지 않은 본문'),
 'dpimediatech4904/224357461393':('generic_av','대회의실 화상회의 시스템 구성','PTZ 카메라·믹서·스피커 등의 구성 예시. 특정 제조사·모델 명시 없음'),
 'kang3ku/224432926665':('outside_brand','MAXHUB XBar U50','장비 글이 맞지만 현재 7개 비교 브랜드에 MAXHUB가 없어 미표시'),
 'kang3ku/224398383186':('outside_brand','MAXHUB Video Bar / XBar U50','장비 글이 맞지만 현재 7개 비교 브랜드에 MAXHUB가 없어 미표시'),
 'ajooav/224442188073':('outside_brand','Roland VR 시리즈·PTZ 카메라','장비 글이 맞지만 현재 7개 비교 브랜드에 Roland가 없어 미표시'),
}

def load_findings():
    findings_file = Path(__file__).resolve().parent / 'top5_findings.json'
    if findings_file.exists():
        data = read(findings_file)
        return {k: (v['category'], v['topic'], v['reason']) for k, v in data.items()}
    return FINDINGS


def generate_audit(folder, raw_path=None, out_dir=None, capture_date=None, review_date=None, findings=None):
    folder = Path(folder)
    raw_path = Path(raw_path) if raw_path else (folder.parent / 'input.json' if (folder.parent / 'input.json').exists() else folder / 'input.json')
    report = read(folder / 'report.json')
    raw = read(raw_path)
    classes = {r['post_key']: r for r in read(folder / 'final-classifications.json')['items']}
    bodies_path = folder / 'bodies.json'
    bodies = {r['post_key']: r for r in read(bodies_path)} if bodies_path.exists() else {}
    findings_dict = findings if findings is not None else load_findings()
    rows = []
    for q in raw['results']:
        keyword = q['keyword']
        best = {b['brand']: next(v['best_rank'] for v in b['keyword_ranks'] if v['keyword'] == keyword) for b in report['brand_scores']}
        for h in q['rows'][:5]:
            post = h['url'].split('blog.naver.com/')[1] if 'blog.naver.com/' in h['url'] else h['url']
            c = classes.get(post, {'brands': []})
            shown = [b for b, rank in best.items() if rank == h['rank']]
            if shown:
                category = 'displayed'
                topic = ' / '.join(c.get('brands', []))
                reason = '현재 브랜드 행의 최고 위치로 표시됨'
            elif c.get('brands'):
                category = 'same_brand_later'
                topic = ' / '.join(c.get('brands', []))
                reason = '브랜드별 최고 위치만 표시하므로 같은 브랜드의 더 뒤쪽 글은 별도 칸에 표시되지 않음'
            else:
                if post in findings_dict:
                    category, topic, reason = findings_dict[post]
                else:
                    category = 'unreviewed'
                    topic = '미검토 일반 글'
                    reason = '신규 순위 진입 글 - 04 독립 검토 미실시 (자체 단정 금지)'
            body_rec = bodies.get(post, {})
            rows.append({
                'keyword': keyword,
                'rank': h['rank'],
                'title': h['title'],
                'url': h['url'],
                'post_key': post,
                'displayed': bool(shown),
                'displayed_brands': shown,
                'classified_brands': c.get('brands', []),
                'category': category,
                'topic': topic,
                'reason': reason,
                'body_status': c.get('body_status', body_rec.get('status')),
                'body_sha256': body_rec.get('body_sha256')
            })
    counts = dict(Counter(r['category'] for r in rows))
    out_dir = Path(out_dir) if out_dir else folder / 'audits/20261023-top5'
    out_dir.mkdir(parents=True, exist_ok=True)
    audit_data = {
        'capture_date': capture_date or '2026-10-22',
        'review_date': review_date or '2026-10-23',
        'rows': rows,
        'counts': counts,
        'scope': 'Saved body text review; images/OCR not reviewed. Original captured order preserved.'
    }
    save(out_dir / 'audit.json', audit_data)
    save(folder / 'top5-audit.json', audit_data)
    return audit_data


def main():
    pointer = read(ROOT / 'data/blog_performance/browser-search/latest-common.json')
    folder = (ROOT / pointer['report']).parent
    audit_data = generate_audit(folder)
    counts = audit_data['counts']
    rows = audit_data['rows']
    raw = read(folder.parent / 'input.json')
    E = lambda v: html.escape(str(v))
    sections = []
    for q in raw['results']:
        items = [r for r in rows if r['keyword'] == q['keyword']]
        sections.append('<h2>' + E(q['keyword']) + '</h2><table><thead><tr><th>원래 위치</th><th>글</th><th>내용</th><th>표시·제외 이유</th></tr></thead><tbody>' + ''.join('<tr class="' + ('shown' if r['displayed'] else '') + '"><td>' + str(r['rank']) + '</td><td><a href="' + E(r['url']) + '" target="_blank" rel="noopener">' + E(r['title']) + '</a><small>' + E(r['post_key']) + '</small></td><td>' + E(r['topic']) + '</td><td>' + E(r['reason']) + '</td></tr>' for r in items) + '</tbody></table>')
    text = '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>1~5위 미표시 결과 확인</title><style>body{font:15px/1.7 "Malgun Gothic",sans-serif;max-width:1180px;margin:30px auto;padding:0 20px;color:#17303b}table{border-collapse:collapse;width:100%;margin-bottom:35px}th,td{border-bottom:1px solid #d6e0e4;padding:12px;text-align:left;vertical-align:top}th{background:#edf4f5}td:first-child{width:70px}td:nth-child(2){width:40%}.shown{background:#eef8f0}small{display:block;font-size:11px;color:#657780}a{color:#087e86}.notice{padding:16px;background:#fff7dc}h2{margin-top:35px}@media(max-width:700px){table{font-size:11px}td,th{padding:7px}}</style><h1>공통 검색어 1~5위 · 표에 안 보이는 이유</h1><p>수집 2026-10-22 · 검토 2026-10-23 · 제공된 블로그 탭 관련도순. 새로 검색한 결과가 아닙니다.</p><div class="notice">35개 결과 중 표시 12건, 같은 브랜드의 뒤쪽 글 7건, 비교 대상 밖 장비 브랜드 6건, 브랜드 특정 없는 AV 일반 글 7건, 앱 사용법·영어 학습 3건입니다. 녹색 행은 현재 표에 표시된 위치입니다. 이미지는 OCR로 판독하지 않았습니다.</div><p>주의: Cisco로 표시된 화상회의 솔루션 2위는 Webex 등 소프트웨어 소개입니다. 현재 점수는 브랜드 언급 글 기준이며 하드웨어 장비 글만의 순위가 아닙니다.</p>' + ''.join(sections) + '</html>'
    dest = ROOT / 'static/reports/blog-search-top5-review-20261023.html'
    dest.write_text(text, encoding='utf-8')
    print(json.dumps({'counts': counts, 'html': str(dest), 'rows': len(rows)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
