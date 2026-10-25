"""Generate persistent front overlay from the locally installed official image."""
import json
from pathlib import Path
import subprocess
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def prepare(root=ROOT):
    root = Path(root)
    report = json.loads((root/'content-system/operations/taiga-sync/latest-sync.json').read_text(encoding='utf-8'))
    slug = report['project_slug']
    path = urlparse(report['blog_catalog_url']).path
    if not path.startswith('/project/' + slug + '/wiki/') or any(c in slug + path for c in '\"\'<>'):
        raise ValueError('Invalid navigation paths')
    result = subprocess.run(['docker', 'run', '--rm', '--entrypoint', 'cat',
                             'taigaio/taiga-front:latest', '/usr/share/nginx/html/index.html'],
                            capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        raise RuntimeError('Cannot read installed official front image')
    original = result.stdout
    if '</head>' not in original or 'app-loader.js' not in original:
        raise ValueError('Unexpected Taiga index format')
    directory = root/'deployments/taiga/runtime/front-overlay'
    directory.mkdir(parents=True, exist_ok=True)
    from services.taiga_tracking import collect_tasks, settings, read_json, TaigaClient
    tasks={t['key']:t for t in collect_tasks(root)}
    refs={str(t['ref']):tasks[t['key']]['refs']['content_id'] for t in report['tickets']
          if t.get('project_slug')==slug and t['key'] in tasks and tasks[t['key']]['refs'].get('content_id')}
    import sqlite3
    with sqlite3.connect((root/'data/taiga-tracking.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
        editors=db.execute('SELECT source_key,story_id FROM editors').fetchall()
    client=TaigaClient(settings(root)['base_url'],credentials=read_json(root/'config/taiga.secrets.json'));client.login()
    for key,ident in editors:
        if key in tasks:
            story=client.request('GET','userstories/'+str(ident));refs[str(story['ref'])]=tasks[key]['refs']['content_id']
    config = json.dumps({'projectSlug': slug, 'catalogPath': path, 'articleRefs':refs,
                         'approvalBase':settings(root).get('console_url','http://127.0.0.1:5014').rstrip('/')+'/article-approval.html'}, ensure_ascii=False)
    scripts = '<script>window.CONTENT_OPS_NAVIGATION=' + config + ';</script>\n<script defer src="/content-ops-navigation.js"></script>\n'
    (directory/'index.html').write_text(original.replace('</head>', scripts + '</head>'), encoding='utf-8')
    (directory/'content-ops-navigation.js').write_text((root/'deployments/taiga/front/custom-navigation.js').read_text(encoding='utf-8'), encoding='utf-8')
    (directory/'Dockerfile').write_text('FROM taigaio/taiga-front:latest\nCOPY index.html /usr/share/nginx/html/index.html\nCOPY content-ops-navigation.js /usr/share/nginx/html/content-ops-navigation.js\n', encoding='utf-8')
    return {'overlay': str(directory), 'catalog_path': path}


if __name__ == '__main__':
    print(json.dumps(prepare(), ensure_ascii=False))
