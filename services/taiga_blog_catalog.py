"""Native Taiga wiki index of content records, separate from activity timeline."""
import csv
from datetime import datetime, timedelta, timezone

from services.taiga_ticket_view import table
from services.article_stage import STAGE_NAMES


def render_catalog(root, tasks, report):
    with (root / 'content-system/registry/CONTENT_REGISTRY.csv').open(encoding='utf-8-sig', newline='') as stream:
        registry = {r['content_id']: r for r in csv.DictReader(stream)}
    tickets = {t['key']: t for t in report['tickets']}
    rows = []
    articles = [t for t in tasks if t['category'] == '글']
    published = sum(registry.get(t['refs']['content_id'], {}).get('status') == 'PUBLISHED' for t in articles)
    for task in articles:
        cid = task['refs']['content_id']
        record, details = registry.get(cid, {}), task.get('details', {})
        title = task['title'].replace('[', '').replace(']', '')
        ticket = tickets.get(task['key'], {})
        bindings = details.get('asset_bindings') or []
        available = sum(bool(b.get('candidate') and (b['candidate'].get('url') or b['candidate'].get('public_url')) and
                             b['candidate'].get('review_status') != 'rejected') for b in bindings)
        at = details.get('created_at')
        try:
            date = datetime.fromisoformat(at).astimezone(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M')
        except (TypeError, ValueError):
            date = record.get('created_date') or '미기록'
        state = ticket.get('state', task['state'])
        stage = task.get('current_stage') or {}
        stage_label = (str(stage['number']) + '단계 · ' + stage['name'] + ' (' + stage['reason'] + ')') if stage else '단계 확인 필요'
        if record.get('status') == 'PUBLISHED':
            state = '발행됨'
        url = record.get('published_url')
        published_link = '[발행 글](' + url + ')' if url and url.startswith('https://') else '미발행'
        approval_url = task['console_url'].split('/article-console.html',1)[0] + '/article-approval.html?content=' + cid
        actions = '[콘솔](' + task['console_url'] + ')'
        actions += ' · [승인·다음 단계](' + approval_url + ')'
        if stage.get('number') == 7:
            actions += ' · [네이버 복사](' + task['console_url'] + '#naver-copy)'
        rows.append(['[' + title + '](' + approval_url + ')',
                     stage_label, stage.get('actors', '담당 확인 필요'), stage.get('intervention', '확인 필요'),
                     state, date, details.get('keyword') or record.get('primary_keyword') or '미기록',
                     str(details.get('draft_chars', 0)) + '자', str(available) + '/' + str(len(bindings)),
                     published_link, actions])
    return '\n\n'.join(['# 블로그 글 목록',
        f'등록 글 **{len(articles)}개** · 발행 기록 **{published}개**',
        '작성·검토 중인 원고를 포함한 콘텐츠 목록입니다. 티켓 완료와 실제 블로그 발행은 구분합니다. '
        '사진 수는 확보된 후보/요구 자리이며 이미지 승인 완료를 뜻하지 않습니다. 실행 시각은 한국 시간입니다.',
        '단계는 AI와 관리자의 공통 작업 흐름입니다. 중간 관리자 개입은 별도 열에 표시합니다.\n\n단계: ' + ' → '.join(str(n) + '. ' + name for n, name in STAGE_NAMES.items()),
        table(['글 제목', '현재 단계', '작업 주체', '관리자 개입', '현재 상태', '최근 실행', '키워드', '원고 분량', '사진 확보', '발행', '바로가기'], rows),
        '이 목록은 원본 기록에서 자동 갱신합니다. 글은 원고 작성 콘솔 및 승인 페이지에서 확인하세요.']).strip()


def synchronize_catalog(root, client, project, tasks, report):
    content = render_catalog(root, tasks, report)
    links = client.request('GET', 'wiki-links', params={'project': project['id']})
    matching = [link for link in links if link['title'] == '블로그 글 목록']
    link = min(matching, key=lambda item: item['id']) if matching else None
    if not link:
        link = client.request('POST', 'wiki-links', {'project': project['id'], 'title': '블로그 글 목록', 'order': 0})
    # Current Taiga creates a wiki page and derives href from title on POST.
    # Always use the returned href rather than assuming the requested slug.
    slug = link['href']
    pages = client.request('GET', 'wiki', params={'project': project['id']})
    page = next((p for p in pages if p['slug'] == slug), None)
    if page:
        page = client.request('GET', 'wiki/' + str(page['id']))
        if page.get('content') != content:
            client.request('PATCH', 'wiki/' + str(page['id']), {'content': content, 'version': page['version']})
    else:
        client.request('POST', 'wiki', {'project': project['id'], 'slug': slug, 'content': content})
    url = client.base.removesuffix('/api/v1') + '/project/' + project['slug'] + '/wiki/' + slug
    home_content = '# 블로그 콘텐츠 운영\n\n## [블로그 글 목록 열기](' + url + ')\n\n'
    home_content += '작성된 글·사진·검토 상태는 위 목록에서 확인하세요. 원고 수정 링크도 각 글에 있습니다.\n\n'
    home_content += '[글 작업 보드](' + report['board_url'] + ')\n\n프로젝트 Timeline은 작업 활동 기록 화면입니다.'
    home = next((p for p in pages if p['slug'] == 'home'), None)
    if not home:
        client.request('POST', 'wiki', {'project': project['id'], 'slug': 'home', 'content': home_content})
    elif not (home.get('content') or '').strip():
        detail = client.request('GET', 'wiki/' + str(home['id']))
        if not (detail.get('content') or '').strip():
            client.request('PATCH', 'wiki/' + str(home['id']), {'content': home_content, 'version': detail['version']})
    current = client.request('GET', 'projects/' + str(project['id']))
    if url not in (current.get('description') or ''):
        client.request('PATCH', 'projects/' + str(project['id']), {'description':
            (current.get('description') or '') + '\n\n블로그 글 목록: ' + url})
    report['blog_catalog_url'] = url
