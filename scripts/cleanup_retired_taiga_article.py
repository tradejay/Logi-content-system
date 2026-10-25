"""Archive only the retired duplicate and editor task, preserving history."""
import json
from datetime import datetime
from services.taiga_tracking import ROOT, TaigaClient, settings, read_json, synchronize


def main():
    cfg = settings()
    client = TaigaClient(cfg['base_url'], credentials=read_json(ROOT / 'config/taiga.secrets.json'))
    client.login()
    project = next(p for p in client.request('GET', 'projects') if p['name'] == cfg['project_name'])
    statuses = client.request('GET', 'userstory-statuses', params={'project': project['id']})
    retired = next((s for s in statuses if s['name'] == '정리된 테스트'), None)
    if retired is None:
        retired = client.request('POST', 'userstory-statuses', {'project': project['id'], 'name': '정리된 테스트', 'order': 100, 'color': '#94a3b8', 'is_closed': True, 'is_archived': True})
    removed = []
    archive = ROOT / 'archive/topic-tests' / ('taiga-' + datetime.now().strftime('%Y%m%dT%H%M%S'))
    for story in client.request('GET', 'userstories', params={'project': project['id']}):
        detail = client.request('GET', f"userstories/{story['id']}")
        description = detail.get('description') or ''
        duplicate = '<!-- content-ops:content:CNT-2026W39-999 -->' in description
        editor = detail['subject'] == '[원고 편집] CNT-2026W39-999'
        if not (duplicate or editor):
            continue
        archive.mkdir(parents=True, exist_ok=True)
        (archive / f"story-{story['id']}.json").write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding='utf-8')
        client.request('PATCH', f"userstories/{story['id']}", {'status': retired['id'], 'version': detail['version']})
        removed.append(story['id'])
    report = synchronize(client=client)
    articles = [t for t in report['tickets'] if t['category'] == '글']
    assert len(articles) == 6, len(articles)
    print(json.dumps({'archived_story_ids': removed, 'article_count': len(articles), 'board_url': report['board_url']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
