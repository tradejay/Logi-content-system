"""Report-only room grouping. Captures, identities and observed ranks stay intact."""
from copy import deepcopy

GROUPS = [('bar', '대형 비디오바'), ('medium', '중형 비디오바'), ('small', '소형 비디오바'), ('modular', '모듈형·분리형')]
# Product ID, intended room range, operating type, official source.
MEDIUM = [
    ('VC-009', '소형~중형', '독립 구동형 / USB', 'https://www.logitech.com/en-us/products/video-conferencing/room-solutions/rallybarmini.960-001563.html'),
    ('VC-002', '중형 (제조사 표기 6~9인)', '독립 구동형 / USB', 'https://support.hp.com/emea_middle_east-en/product/product-specs/studio-x52-series/2101842931'),
    ('VC-011', '소형~중형 (제조사 표기 5~12인)', '독립 구동형 / USB', 'https://www.yealink.com/en/onepage/simplify-medium-room-video-conferencing-with-the-right-meetingbar'),
    ('VC-014', '소형~중형', '독립 구동형 / USB', 'https://neat.no/bar/'),
    ('VC-005', '중형 · 확장 구성 가능', '독립 구동형 / USB', 'https://www.cisco.com/c/en/us/products/collateral/collaboration-endpoints/webex-room-series/room-bar-pro-ds.html'),
]
MEDIUM_IDS = {row[0] for row in MEDIUM}


def grouped_report(report):
    result = deepcopy(report)
    for product in result['products']:
        if product['product_id'] in {'VC-016', 'VC-017'}:
            product['group'] = 'small'
        elif product['product_id'] in MEDIUM_IDS:
            product['group'] = 'medium'
    return result


def medium_research(report, page, table):
    from services.blog_performance.insights.search_report_metric_pages import E
    products = {p['product_id']: p for p in report['products']}
    rows = []
    for pid, size, mode, url in MEDIUM:
        if pid not in products:
            continue
        p = products[pid]
        rows.append([E(p['brand']) + ' ' + E(p['product']), E(size), E(mode), '<a href="' + E(url) + '" target="_blank" rel="noopener">제조사 자료 ↗</a>'])
    page('제조사 자료 조사 · 2026-10-23', '중형 비디오바 · Rally Bar Mini 비교군과 분류 근거',
         f'이번 표본에 포함된 중형 장비 {len(rows)}종을 묶었습니다. 권장 공간의 범위가 겹치는 제품은 이 보고서에서 중형으로 한 번만 배치합니다.',
         table(['장비', '공식 권장 공간', '운영 방식', '분류 근거'], rows, 'compact',
               reading='중형은 보고서의 비교용 분류이며 동일 성능·가격 등급을 뜻하지 않습니다. Rally Bar Mini·A40·Neat는 소형~중형 범위가 겹칩니다.') +
         '<p class="micro">대형에는 Rally Bar·A50·Neat Bar Pro·VB350을 유지합니다. 이들은 중형까지 포함하는 확장 범위가 있지만 대형 대응 비교군으로 배치했습니다. Cisco Room Bar는 공식 소형 용도를 따라 소형에 유지했습니다. PanaCast 50과 Video Bar System은 사용자 지정에 따라 소형으로 분류했습니다. 제조사 분류는 통일된 인원 기준이 아니며, 이 조사는 기존 27종의 재분류입니다. 검색 순위 신규 수집이나 점수 재산정은 하지 않았습니다.</p>',
         '공식 제품·설계 자료 기준 · 보고서 분류만 변경 · 원본 검색 자료와 순위 보존')
