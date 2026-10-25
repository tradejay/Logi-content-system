"""Remove only empty duplicate wiki placeholders created by our link setup bug."""
import json
import re
from datetime import datetime, timezone
from services.taiga_tracking import ROOT, read_json, settings, TaigaClient


def main():
    client = TaigaClient(settings()['base_url'], credentials=read_json(ROOT/'config/taiga.secrets.json'))
    client.login()
    report = read_json(ROOT/'content-system/operations/taiga-sync/latest-sync.json')
    links = client.request('GET', 'wiki-links', params={'project': report['project_id']})
    duplicates = sorted([link for link in links if link['title'] == '블로그 글 목록'], key=lambda link: link['id'])
    removed, preserved = [], []
    backup = ROOT/'content-system/operations/taiga-sync/wiki-link-repair'
    backup.mkdir(parents=True, exist_ok=True)
    for link in duplicates[1:]:
        if not re.fullmatch(r'beulrogeu-geul-mogrog-\d+', link['href']):
            preserved.append(link['id']); continue
        page = client.request('GET', 'wiki/by_slug', params={'project': report['project_id'], 'slug': link['href']})
        attachments = client.request('GET', 'wiki/attachments', params={'project': report['project_id'], 'object_id': page['id']})
        history = client.request('GET', 'history/wiki/' + str(page['id']))
        # Human content, attachments, comments or edits are retained.
        if (page.get('content') or '').strip() or attachments or len(history) > 1:
            preserved.append(link['id']); continue
        (backup / (str(link['id']) + '.json')).write_text(json.dumps({'link': link, 'page': page,
            'history': history, 'at': datetime.now(timezone.utc).isoformat()}, ensure_ascii=False, indent=2), encoding='utf-8')
        client.request('DELETE', 'wiki-links/' + str(link['id']))
        removed.append(link['id'])
    print(json.dumps({'empty_duplicate_links_removed': len(removed), 'nonempty_or_edited_preserved': preserved,
                      'backup_path': str(backup)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
