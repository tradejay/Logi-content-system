"""Local project work -> Taiga Kanban. Task completion never grants publication approval."""
import csv
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from urllib.parse import urlencode, urlparse
import yaml

ROOT = Path(__file__).resolve().parents[1]
STATES = ['대기', '진행 중', '검토 대기', '막힘', '완료', '변경 검토', '수정 요청', '반려', '검토 이력']
COLORS = ['#64748b', '#2563eb', '#a855f7', '#ea580c', '#16a34a', '#0891b2', '#d97706', '#dc2626', '#94a3b8']


def system_task(task):
    return task['category'] in {'Fact', '가이드', '개발'}


def settings(root=ROOT):
    path = Path(root) / 'config/taiga.json'
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}


def yaml_file(path):
    return yaml.safe_load(path.read_text(encoding='utf-8-sig')) or {} if path.exists() else {}


def content_state(result, registry_status):
    outcome = result.get('outcome')
    if (result.get('manual_edit') or {}).get('requires_review') and outcome == 'REVISION_REQUIRED':
        return '변경 검토'
    if registry_status == 'PUBLISHED':
        return '완료'
    if outcome == 'COMPLETED_READY':
        return '완료'
    if outcome in {'RUNNING', 'CHECKING'}:
        return '진행 중'
    if outcome in {'FAILED', 'REVISION_REQUIRED', 'NEEDS_EVIDENCE'}:
        return '막힘'
    if outcome in {'COMPLETED_REVIEW_PENDING', 'COMPLETED_READY'}:
        return '검토 대기'
    if registry_status == 'PUBLISHED':
        return '완료'
    return '대기'


def resolve_candidate_bindings(root, cid, result, details):
    import copy
    root = Path(root)
    bindings = copy.deepcopy(details.get('asset_bindings') or [])
    valid_hashes = set()
    if result.get('draft_sha256'):
        valid_hashes.add(result['draft_sha256'])
    draft_file = result.get('draft_file')
    if draft_file:
        df_path = Path(draft_file)
        if df_path.is_file():
            valid_hashes.add(hashlib.sha256(df_path.read_bytes()).hexdigest())
    markdown = details.get('markdown') or ''
    if markdown:
        valid_hashes.add(hashlib.sha256(markdown.encode('utf-8')).hexdigest())
        valid_hashes.add(hashlib.sha256(markdown.replace('\n', '\r\n').encode('utf-8')).hexdigest())
        valid_hashes.add(hashlib.sha256(markdown.replace('\r\n', '\n').encode('utf-8')).hexdigest())
    run_id = result.get('run_id')
    if run_id:
        revisions_dir = root / f"content-system/working/{cid}/runs/{run_id}/revisions"
        if revisions_dir.is_dir():
            for r_file in revisions_dir.glob("r*.draft.md"):
                valid_hashes.add(hashlib.sha256(r_file.read_bytes()).hexdigest())

    if not valid_hashes:
        return bindings

    eligible_needs = {}
    eligible_assets = {}
    queue_dir = root / 'content-system/queue'
    for qpath in (queue_dir.glob('*.queue.yaml') if queue_dir.is_dir() else []):
        qdata = yaml_file(qpath)
        jobs = qdata.get('jobs') or {}
        for jid, job in jobs.items():
            if not isinstance(job, dict) or job.get('content_id') != cid:
                continue
            j_sha = job.get('draft_sha256')
            if j_sha and j_sha in valid_hashes:
                nid = job.get('need_id')
                if nid:
                    eligible_needs[nid] = job
                out_aid = (job.get('output') or {}).get('asset_id')
                exist_aid = (job.get('existing_asset') or {}).get('asset_id')
                if out_aid:
                    eligible_assets[out_aid] = nid
                if exist_aid:
                    eligible_assets[exist_aid] = nid

    if not eligible_needs and not eligible_assets:
        return bindings

    assets_file = root / 'content-system/assets' / cid / 'assets.yaml'
    candidates_by_need = {}
    if assets_file.is_file():
        adata = yaml_file(assets_file)
        for item in adata.get('assets', []):
            if not isinstance(item, dict):
                continue
            if not (item.get('url') or item.get('public_url')):
                continue
            nid = item.get('need_id')
            aid = item.get('asset_id')
            target_nid = nid if (nid and nid in eligible_needs) else eligible_assets.get(aid)
            if target_nid:
                candidates_by_need[target_nid] = item

    if not candidates_by_need:
        return bindings

    existing_nids = set()
    for b in bindings:
        need = b.get('need') or {}
        nid = need.get('id')
        if nid:
            existing_nids.add(nid)
        cand = b.get('candidate')
        if nid in candidates_by_need:
            c_data = dict(candidates_by_need[nid])
            b['candidate'] = c_data
            b['status'] = c_data.get('review_status') or 'pending_review'

    for nid, cand_item in candidates_by_need.items():
        if nid not in existing_nids:
            bindings.append({
                'need': {'id': nid, 'purpose': cand_item.get('caption') or cand_item.get('alt') or nid},
                'candidate': dict(cand_item),
                'status': cand_item.get('review_status') or 'pending_review'
            })

    return bindings


def article_details(root, cid, result):
    from services.pipeline_monitor import read_monitor
    try:
        details = read_monitor(root, cid, result.get('run_id'))
    except FileNotFoundError:
        # Older runs have no console run folder. Only use a draft whose recorded
        # digest matches this result; never attach a newer article to an old run.
        markdown = ''
        path = Path(result.get('draft_file') or '__missing__').resolve()
        if path.is_relative_to(root.resolve()) and path.is_file():
            raw = path.read_bytes()
            if result.get('draft_sha256') == hashlib.sha256(raw).hexdigest():
                markdown = raw.decode('utf-8-sig')
        details = {'markdown': markdown, 'draft_chars': len(markdown),
                'checks': {'qa': result.get('qa'), 'official': result.get('official')},
                'admin_checks': result.get('admin_checks', []),
                'events': result.get('natural_logs', []), 'calls': [],
                'notes': ['역사 실행의 상세 모니터 기록이 없습니다. 누락된 시간·토큰은 미기록으로 표시합니다.']}
    details['asset_bindings'] = resolve_candidate_bindings(root, cid, result, details)
    edit = result.get('manual_edit') or {}
    if edit.get('requires_review'):
        draft = Path(result.get('draft_file') or '__missing__')
        if draft.is_relative_to(root.resolve()) and draft.is_file():
            current = draft.read_text(encoding='utf-8')
            if hashlib.sha256(current.encode()).hexdigest() == edit.get('draft_sha256'):
                details.update(markdown=current, draft_chars=len(current), checks={'qa': result.get('qa'),
                               'official': {'status': 'STALE'}}, publish_ready=False)
    return details


def collect_tasks(root=ROOT):
    root = Path(root)
    cfg = settings(root)
    tasks = []
    registry = root / 'content-system/registry/CONTENT_REGISTRY.csv'
    if registry.exists():
        with registry.open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                cid = row.get('content_id', '')
                if not cid.startswith('CNT-') or any(x in cid for x in ('/', '\\', '..')):
                    continue
                work = root / 'content-system/working' / cid
                result = read_json(work / 'pipeline-latest.json')
                ref = {'content_id': cid, 'run_id': result.get('run_id'), 'draft_sha256': result.get('draft_sha256')}
                summary = {'outcome': result.get('outcome', row.get('status')), 'qa_passed': result.get('qa', {}).get('passed'),
                           'admin_checks': len(result.get('admin_checks', [])), 'error': result.get('error')}
                details = article_details(root, cid, result)
                from services.article_stage import current_stage
                tasks.append({'key': 'content:' + cid, 'category': '글', 'state': content_state(result, row.get('status')),
                              'title': row.get('title') or row.get('canonical_topic') or cid, 'refs': ref, 'summary': summary,
                              'details': details, 'current_stage': current_stage(result, details, row.get('status')),
                              'source_path': (work / 'pipeline-latest.json').relative_to(root).as_posix(),
                              'console_url': cfg.get('console_url', 'http://127.0.0.1:5014').rstrip('/') + '/article-console.html?' + urlencode({'content': cid})})
                for index, issue in enumerate(result.get('knowledge_queue', [])):
                    identity = hashlib.sha256(json.dumps(issue, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
                    tasks.append({'key': f'fact:{cid}:{identity}', 'category': 'Fact', 'state': '검토 이력',
                                  'tracking_note': '과거 실행에서 기록된 Fact 보완 제안입니다. 현재 미해결 또는 해결 완료로 판정한 항목이 아닙니다.',
                                  'source_path': (work / 'pipeline-latest.json').relative_to(root).as_posix(),
                                  'title': f"{cid} · 근거 정정 검토 {index + 1}", 'refs': ref, 'summary': issue})
    # Existing independent worker queues remain the source of truth.
    directory = root / 'content-system/queue'
    for path in directory.glob('*.queue.yaml'):
        queue = yaml_file(path)
        if not isinstance(queue.get('jobs'), dict):
            continue
        for identity, job in queue['jobs'].items():
            status = job.get('status', 'pending')
            state = '반려' if status == 'rejected' else '수정 요청' if status == 'revision_required' else '완료' if status in {'completed', 'done'} else '진행 중' if status in {'running', 'in_progress'} else '막힘' if status in {'blocked', 'failed', 'stale'} else '검토 대기' if status in {'pending_review', 'candidate'} else '대기'
            category = '이미지' if path.name == 'asset.queue.yaml' else '가이드' if path.name.startswith('policy') else '개발'
            tasks.append({'key': f'queue:{path.name}:{identity}', 'category': category, 'state': state,
                          'title': job.get('purpose') or job.get('title') or identity,
                          'refs': {'job_id': identity, **{k: job.get(k) for k in ('content_id', 'run_id', 'need_id', 'rule_id', 'draft_sha256')}},
                          'summary': {'status': status, 'task_type': job.get('task_type'), 'output': job.get('output')},
                          'source_path': path.relative_to(root).as_posix()})
    # Explicitly recorded project follow-ups; no conversion of every log into a ticket.
    manual = read_json(root / 'content-system/operations/tracking-tasks.json')
    for task in manual.get('tasks', []):
        if task.get('state') not in STATES or task.get('category') not in {'Fact', '가이드', '개발'}:
            raise ValueError('Invalid tracking task')
        tasks.append(task)
    if len({t['key'] for t in tasks}) != len(tasks):
        raise ValueError('Duplicate tracking key')
    return tasks


def description(task):
    from services.taiga_ticket_view import render_ticket
    return render_ticket(task)


class TaigaClient:
    def __init__(self, base_url, token=None, session=None, credentials=None):
        parsed = urlparse(base_url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Invalid Taiga URL')
        if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in {'127.0.0.1', 'localhost', '::1'}):
            raise ValueError('Remote Taiga requires HTTPS')
        if session is None:
            import requests
            session = requests.Session()
        self.base = base_url.rstrip('/') + '/api/v1'
        self.token = token
        self.session = session
        self.credentials = credentials or {}

    def request(self, method, path, payload=None, params=None):
        headers = {'Content-Type': 'application/json', 'x-disable-pagination': 'true'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        try:
            response = self.session.request(method, self.base + '/' + path.lstrip('/'), headers=headers,
                                            json=payload, params=params, timeout=30, allow_redirects=False)
        except Exception:
            raise RuntimeError('Taiga connection failed') from None
        if response.status_code not in {200, 201, 204}:
            raise RuntimeError(f'Taiga HTTP {response.status_code}')
        return response.json() if response.status_code != 204 else None

    def login(self):
        if self.token:
            self.request('GET', 'users/me')
            return
        username = os.getenv('TAIGA_USERNAME') or self.credentials.get('username')
        password = os.getenv('TAIGA_PASSWORD') or self.credentials.get('password')
        if not username or not password:
            raise ValueError('Set TAIGA_AUTH_TOKEN or TAIGA_USERNAME/TAIGA_PASSWORD locally')
        result = self.request('POST', 'auth', {'type': 'normal', 'username': username, 'password': password})
        self.token = result.get('auth_token')
        if not self.token:
            raise ValueError('Taiga authentication failed')


def synchronize(root=ROOT, client=None):
    root = Path(root)
    cfg = settings(root)
    if not cfg.get('enabled'):
        raise ValueError('Taiga connection is not enabled; installation and account setup required')
    tasks = collect_tasks(root)
    credentials = read_json(root / 'config/taiga.secrets.json')
    client = client or TaigaClient(cfg['base_url'], os.getenv('TAIGA_AUTH_TOKEN') or credentials.get('auth_token'), credentials=credentials)
    client.login()
    directory = root / 'content-system/operations/taiga-sync'
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / 'sync.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError('Another Taiga sync is active; inspect sync.lock before retrying')
    os.close(fd)
    try:
        projects = client.request('GET', 'projects')
        project = next((p for p in projects if (cfg.get('project_slug') and p['slug'] == cfg['project_slug']) or
                        (not cfg.get('project_slug') and p['name'] == cfg['project_name'])), None)
        created_project = project is None
        if created_project:
            project = client.request('POST', 'projects', {'name': cfg['project_name'], 'slug': cfg.get('project_slug') or 'content-ops', 'description': '글·이미지·Fact·가이드·개발 작업 추적',
                'is_private': True, 'is_kanban_activated': True, 'is_backlog_activated': False})
        if not project.get('is_kanban_activated'):
            project = client.request('PATCH', f"projects/{project['id']}",
                {'is_kanban_activated': True, 'is_backlog_activated': False})
        statuses = client.request('GET', 'userstory-statuses', params={'project': project['id']})
        status_map = {}
        for index, name in enumerate(STATES):
            match = next((s for s in statuses if s['name'] == name), None)
            payload = {'project': project['id'], 'name': name, 'order': index, 'color': COLORS[index], 'is_closed': name == '완료'}
            if not match and created_project and index < len(statuses):
                match = client.request('PATCH', f"userstory-statuses/{statuses[index]['id']}", payload)
            elif not match:
                match = client.request('POST', 'userstory-statuses', payload)
            status_map[name] = match['id']
        stories = client.request('GET', 'userstories', params={'project': project['id']})
        # Taiga's list serializer omits descriptions. Load details before matching
        # source markers or comparing text, including when local mappings are lost.
        stories = [client.request('GET', f"userstories/{s['id']}")
                   if 'description' not in s else s for s in stories]
        main_project, main_stories = project, stories
        archive = next((s for s in statuses if s['name'] == '시스템 이력 이관'), None)
        if not archive:
            archive = client.request('POST', 'userstory-statuses', {'project': project['id'],
                'name': '시스템 이력 이관', 'order': 99, 'color': '#94a3b8', 'is_closed': True, 'is_archived': True})
        contexts = {'content': (project, status_map, stories)}
        if any(system_task(t) for t in tasks):
            name = cfg.get('system_project_name') or '시스템 개선·검토 이력'
            system_project = next((p for p in projects if p['name'] == name), None)
            if not system_project:
                system_project = client.request('POST', 'projects', {'name': name, 'description': 'Fact·가이드·개발 개선 및 과거 검토 이력. 글 작업과 분리.',
                    'is_private': True, 'is_kanban_activated': True, 'is_backlog_activated': False})
            if not system_project.get('is_kanban_activated'):
                system_project = client.request('PATCH', f"projects/{system_project['id']}",
                    {'is_kanban_activated': True, 'is_backlog_activated': False})
            system_statuses = client.request('GET', 'userstory-statuses', params={'project': system_project['id']})
            system_map = {}
            for index, name in enumerate(STATES):
                match = next((s for s in system_statuses if s['name'] == name), None)
                if not match:
                    match = client.request('POST', 'userstory-statuses', {'project': system_project['id'], 'name': name,
                        'order': index, 'color': COLORS[index], 'is_closed': name == '완료'})
                system_map[name] = match['id']
            system_stories = client.request('GET', 'userstories', params={'project': system_project['id']})
            system_stories = [client.request('GET', f"userstories/{s['id']}") for s in system_stories]
            contexts['system'] = (system_project, system_map, system_stories)
        report = {'project_id': project['id'], 'project_slug': project['slug'], 'created': 0, 'updated': 0, 'unchanged': 0, 'tickets': []}
        database = root / 'data/taiga-tracking.sqlite3'
        database.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database) as db:
            db.execute('CREATE TABLE IF NOT EXISTS mappings (source_key TEXT PRIMARY KEY, project_id INTEGER, story_id INTEGER, story_ref INTEGER, payload_hash TEXT)')
            from services.taiga_workflow import TaigaWorkflow
            workflows = {name: TaigaWorkflow(root, client, db, context[0], context[1], context[2])
                         for name, context in contexts.items()}
            for task in tasks:
                target = 'system' if system_task(task) else 'content'
                project, status_map, stories = contexts[target]
                workflow = workflows[target]
                marker = '<!-- content-ops:' + task['key'] + ' -->'
                story = next((s for s in stories if marker in (s.get('description') or '')), None)
                if story is None:
                    saved = db.execute('SELECT story_id FROM mappings WHERE source_key=? AND project_id=?', (task['key'], project['id'])).fetchone()
                    if saved:
                        story = next((s for s in stories if s['id'] == saved[0]), None)
                if story is not None:
                    workflow.preserve_manual_description(task, story)
                    workflow.process(task, story)
                    # Inbound edits may have changed the source. Refresh its
                    # display without overwriting action controls or messages.
                    if task['category'] in {'글', '이미지'}:
                        fresh = next((t for t in collect_tasks(root) if t['key'] == task['key']), None)
                        if fresh:
                            task.update({k: v for k, v in fresh.items() if k != 'state'})
                elif task['category'] == '글':
                    workflow.editor(task)
                payload = {'project': project['id'], 'subject': task['title'][:500], 'description': description(task),
                           'status': status_map[task['state']], 'tags': [task['category'].lower(), 'content-ops'] +
                           (['시스템개선'] if target == 'system' else [])}
                fingerprint = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                if story is None:
                    story = client.request('POST', 'userstories', payload)
                    stories.append(story)
                    report['created'] += 1
                else:
                    changes = {k: v for k, v in payload.items() if story.get(k) != v and k not in {'project', 'tags'}}
                    # Keep human assignees, comments and extra labels; local states remain authoritative.
                    old_tags = story.get('tags') or []
                    normalized_tags = [t[0] if isinstance(t, list) else t for t in old_tags]
                    if not set(payload['tags']) <= set(normalized_tags):
                        changes['tags'] = list(dict.fromkeys(normalized_tags + payload['tags']))
                    if changes:
                        story = client.request('PATCH', f"userstories/{story['id']}", {**changes, 'version': story['version']})
                        report['updated'] += 1
                    else:
                        report['unchanged'] += 1
                db.execute('INSERT OR REPLACE INTO mappings VALUES (?,?,?,?,?)', (task['key'], project['id'], story['id'], story['ref'], fingerprint))
                db.execute('INSERT OR REPLACE INTO remote_snapshots VALUES (?,?)', (task['key'], story.get('description') or payload['description']))
                db.commit()
                report['tickets'].append({'key': task['key'], 'id': story['id'], 'ref': story['ref'], 'state': task['state'],
                    'project_slug': project['slug'], 'category': task['category'],
                    'url': cfg['base_url'].rstrip('/') + '/project/' + project['slug'] + '/us/' + str(story['ref'])})
                if target == 'system':
                    old = next((s for s in main_stories if marker in (s.get('description') or '')), None)
                    if old and old['status'] != archive['id']:
                        url = report['tickets'][-1]['url']
                        client.request('PATCH', f"userstories/{old['id']}", {'status': archive['id'], 'version': old['version'],
                            'description': (old.get('description') or '') + '\n\n## 분류 이관\n[시스템 개선·검토 이력에서 보기](' + url + ')\n'
                            '글 작업 보드에서 분리했습니다. 해결 완료 판정이 아닙니다. 원래 기록·댓글은 이 티켓에 보존합니다.'})
        report['board_url'] = cfg['base_url'].rstrip('/') + '/project/' + main_project['slug'] + '/kanban'
        if 'system' in contexts:
            report['system_board_url'] = cfg['base_url'].rstrip('/') + '/project/' + contexts['system'][0]['slug'] + '/kanban'
        from services.taiga_blog_catalog import synchronize_catalog
        synchronize_catalog(root, client, main_project, tasks, report)
        (directory / 'latest-sync.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        return report
    finally:
        lock.unlink(missing_ok=True)


def tracking_snapshot(root=ROOT):
    root = Path(root)
    cfg = settings(root)
    tasks = collect_tasks(root)
    return {'enabled': bool(cfg.get('enabled')), 'base_url': cfg.get('base_url'), 'tasks': tasks,
            'counts': {state: sum(t['state'] == state for t in tasks) for state in STATES},
            'last_sync': read_json(root / 'content-system/operations/taiga-sync/latest-sync.json'),
            'note': '원고 편집 카드 저장은 새 원고·변경 검토로 반영됩니다. 이미지 검토 입력과 완료 요청은 검증 후 처리하며 자동 발행하지 않습니다.'}
