"""Offline editorial checks, not a Naver ranking/index predictor."""
import hashlib
import re
from collections import Counter

SOURCES = ['https://searchadvisor.naver.com/guide/content-basic',
           'https://searchadvisor.naver.com/guide/content-abusing']


def inspect_article(markdown, brief, bindings=None, other_drafts=None):
    title_match = re.search(r'^#\s+(.+)$', markdown, re.M)
    title = title_match.group(1) if title_match else ''
    body = re.sub(r'\{\{asset:[^}]+\}\}', '', markdown)
    keyword = brief.get('search', {}).get('primary_keyword', '')
    normalize = lambda text: re.sub(r'\s+', '', text).lower()
    issues = []
    def issue(rule_id, severity, detail, location):
        issues.append({'rule_id': rule_id, 'severity': severity, 'detail': detail, 'location': location})
    if not title:
        issue('PUB-TITLE', 'review', '제목이 없습니다. 기획 주제를 정확히 표현하는 제목을 확인하세요.', 'title')
    if keyword and normalize(keyword) not in normalize(title):
        issue('PUB-KEYWORD-TITLE', 'review', '주요 검색어가 제목에 직접 드러나지 않습니다. 동의어·검색 의도와의 일치 여부를 검토하세요. 삽입을 강제하지 않습니다.', 'title')
    if keyword and normalize(title).count(normalize(keyword)) > 1:
        issue('PUB-KEYWORD-REPEAT', 'review', '제목에서 같은 검색어가 반복됩니다. 의미 없는 반복인지 검토하세요.', 'title')
    paragraphs = [p.strip() for p in body.split('\n\n') if len(p.strip()) > 60 and not p.strip().startswith(('#', '|'))]
    counts = Counter(paragraphs)
    for paragraph, count in counts.items():
        if count > 1:
            issue('PUB-DUPLICATE-PARAGRAPH', 'review', f'같은 긴 문단 {count}회 반복: {paragraph[:90]}', 'body')
    if not re.search(r'^#{2,3}\s+', markdown, re.M):
        issue('PUB-HEADINGS', 'review', '본문 소제목이 없습니다. 글 흐름에 맞는 구분을 확인하세요.', 'body')
    if any(len(p) > 800 for p in paragraphs):
        issue('PUB-READABILITY', 'review', '800자를 넘는 문단이 있습니다. 이는 내부 검토 기준이며 네이버 순위 기준이 아닙니다.', 'body')
    if re.search(r'FACT-[A-Z0-9-]+|ASSET_REQUIRED|\[CLAIM', body):
        issue('PUB-INTERNAL-LABEL', 'blocking', '독자용 원고에 내부 ID 또는 작업용 라벨이 남았습니다.', 'body')
    used = set(re.findall(r'\{\{asset:([^}]+)\}\}', markdown))
    binding_map = {b.get('need', {}).get('id'): b for b in bindings or []}
    pending = [nid for nid in used if binding_map.get(nid, {}).get('status') != 'approved']
    if pending:
        issue('PUB-ASSET-REVIEW', 'blocking', f'미확보·미승인 이미지 {len(pending)}개. 발행 전 승인된 binding이 필요합니다.', 'media')
    duplicate_articles = []
    for item in other_drafts or []:
        candidate = normalize(item['markdown'])
        if candidate and candidate == normalize(markdown):
            duplicate_articles.append(item['content_id'])
    if duplicate_articles:
        issue('PUB-EXACT-DUPLICATE', 'review', '동일 원고가 다른 글에 저장돼 있습니다: ' + ', '.join(duplicate_articles), 'all_content')
    return {'checker_id': 'PUB-CONTENT-001', 'version': 1, 'draft_sha256': hashlib.sha256(markdown.encode()).hexdigest(),
            'status': 'needs_attention' if issues else 'checks_clear', 'issues': issues,
            'stats': {'chars': len(markdown), 'title': title, 'keyword': keyword,
                      'keyword_mentions': normalize(body).count(normalize(keyword)) if keyword else None,
                      'paragraphs': len(paragraphs), 'image_needs': len(used), 'pending_images': len(pending)},
            'sources': SOURCES, 'scope': '원고의 발행 전 콘텐츠 품질 점검. 네이버 블로그 지수·노출·순위를 측정하거나 보장하지 않는다. 원문 표절·사실성·링크 접속·이미지 시각 검토는 별도.',
            'automatically_rewrites': False}
