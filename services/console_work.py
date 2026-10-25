"""Fixed IDE console actions and content-scoped artifact links."""
import hashlib
import re
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from datetime import datetime, timezone
from .ide_worker_bridge import ROOT, load, save
from .worker_flow import read

GATE = threading.Lock()
ACTIONS = {'manager', 'planner', 'writer', 'review', 'official'}


def current(cid, root=ROOT):
    from .worker_flow import monitor
    monitor(cid, root)  # registry membership and path checks
    latest = read(root / 'content-system/working' / cid / 'pipeline-latest.json')
    run = root / 'content-system/working' / cid / 'runs' / str(latest.get('run_id', '__missing__'))
    return latest, run


def artifacts(cid, run_id=None, root=ROOT):
    latest, active = current(cid, root)
    run_id = run_id or active.name
    if not re.fullmatch(r'[A-Za-z0-9_-]+', run_id):
        raise ValueError('Invalid run ID')
    run = active.parent / run_id
    if not run.resolve().is_relative_to(active.parent.resolve()) or not run.is_dir():
        raise ValueError('실행 기록이 없습니다.')
    batch = root / 'worker-control/article-reruns' / run.name
    rows = []
    def add(path, role, label=None):
        path = path.resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file() or path.suffix not in {'.json', '.md', '.txt'}:
            return
        allowed = [run.resolve(), (root / 'worker-control/console-actions').resolve(), (root / 'worker-control/asset-revisions').resolve()]
        allowed += [(root / 'worker-workspaces' / folder / area).resolve() for folder in ['01_management', '02_research_planning', '03_writing_editing', '04_review', '05_assets'] for area in ['inbox', 'work', 'outbox']]
        if not any(path.is_relative_to(base) for base in allowed):
            return
        rel = path.relative_to(root).as_posix()
        key = hashlib.sha256(rel.encode()).hexdigest()[:24]
        if any(r['id'] == key for r in rows):
            return
        rows.append({'id': key, 'role': role, 'label': label or path.name, 'path': rel,
                     'at': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                     'url': f'/api/content-system/contents/{cid}/work-artifacts/{key}?run_id={run_id}'})
    for p in run.rglob('*'):
        if not p.is_file() or p.suffix not in {'.json', '.md', '.txt'}:
            continue
        name = p.name
        role = 'official' if name.startswith(('official-', 'previous-official')) else 'writer' if 'draft' in name or 'writer-metadata' in name or 'candidate-blocks' in name else 'review' if name == 'review.json' or 'claim-map' in name else 'planner' if name in {'brief.json', 'strategy.json', 'fact-bundle.json', 'web-research.json'} else 'assets' if 'asset' in name or 'image' in name else 'manager'
        add(p, role, str(p.relative_to(run)))
    refs = []
    execution = read(batch / 'execution.json')
    if execution.get('planner_task'):
        refs.append(execution['planner_task'])
    for p in (run / 'official-corrections').glob('round-*/*-task.json'):
        refs.append(read(p))
    resumed = read(batch / 'official-resume.json').get('articles', {}).get(cid, {})
    if resumed.get('task'):
        refs.append(resumed['task'])
    for p in (root / 'worker-control/console-actions').glob('*/job.json'):
        job = read(p)
        if job.get('content_id') == cid and job.get('run_id') == run_id:
            add(p, job.get('action', 'manager'), '콘솔 요청 · ' + str(job.get('action')))
            if job.get('task'):
                refs.append(job['task'])
    for p in (root / 'worker-control/asset-revisions').glob('*/job.json'):
        job = read(p)
        if job.get('content_id') == cid and job.get('run_id') == run_id:
            add(p, 'assets', '이미지 요청 · ' + str(job.get('need_id')))
            if job.get('task'):
                refs.append(job['task'])
    # Earlier block calls carry content_id in the host-generated input packet.
    title = next((a.get('plan', {}).get('title') for a in execution.get('articles', []) if a.get('content_id') == cid), None)
    for p in (batch / 'dispatch').glob('*.json'):
        ref = read(p)
        worker = root / 'worker-workspaces' / str(ref.get('worker_folder', '__missing__'))
        packet = read(worker / 'inbox' / str(ref.get('task_id')) / 'input-1.json')
        blocks = packet.get('blocks') or []
        first_markdown = blocks[0].get('markdown', '') if blocks and isinstance(blocks[0], dict) else ''
        if packet.get('content_id') == cid or title and first_markdown.lstrip('# ').strip() == title:
            refs.append(ref)
    for ref in refs:
        folder, tid = ref.get('worker_folder', ''), ref.get('task_id', '')
        if folder not in {'01_management', '02_research_planning', '03_writing_editing', '04_review', '05_assets'} or not re.fullmatch(r'[A-Za-z0-9_-]+', tid):
            continue
        worker = root / 'worker-workspaces' / folder
        role = {'01_management': 'manager', '02_research_planning': 'planner', '03_writing_editing': 'writer', '04_review': 'review', '05_assets': 'assets'}[folder]
        task = read(worker / 'inbox' / tid / 'task.json')
        for name in ['task.json', 'START.md', 'input-manifest.json', 'input-1.json', 'input-2.md']:
            add(worker / 'inbox' / tid / name, role, tid + ' · 입력 ' + name)
        if task.get('ai_output'):
            add(worker / task['ai_output'], role, tid + ' · AI 결과')
        add(worker / 'outbox' / tid / 'report.json', role, tid + ' · 시스템 수집 기록')
    return sorted(rows, key=lambda r: r['at'], reverse=True)


def start(cid, data, root=ROOT):
    action = data.get('action')
    if action not in ACTIONS:
        raise ValueError('지원하지 않는 작업입니다.')
    identity = str(uuid.UUID(data['request_id']))
    with GATE:
        directory = root / 'worker-control/console-actions' / identity
        if (directory / 'job.json').exists():
            old = load(directory / 'job.json')
            if (old['content_id'], old['action']) != (cid, action):
                raise ValueError('이미 사용한 요청 ID입니다.')
            return old
        latest, run = current(cid, root)
        if not latest.get('draft_file'):
            raise ValueError('현재 실행의 원고·자료가 필요합니다.')
        if data.get('run_id') != latest.get('run_id') or data.get('draft_sha256') != latest.get('draft_sha256'):
            raise ValueError('원고가 변경됐습니다. 새로고침 후 실행하세요.')
        for p in (root / 'worker-control/console-actions').glob('*/job.json'):
            job = read(p)
            if job.get('status') in {'queued', 'running'}:
                raise ValueError('콘솔 작업이 진행 중입니다. 완료 후 실행하세요.')
        batch = root / 'worker-control/article-reruns' / run.name
        if any((batch / name).exists() for name in ['controller.lock', 'official-resume.lock', 'official-corrections.lock']):
            raise ValueError('기존 파이프라인이 실행 중입니다. 완료 후 실행하세요.')
        if action in {'writer', 'official'} and run.name != 'RERUN-20261016T050248':
            raise ValueError('이 실행은 현재 IDE 재개 컨트롤러의 대상이 아닙니다.')
        job = {'id': identity, 'content_id': cid, 'run_id': run.name, 'draft_sha256': latest['draft_sha256'],
               'action': action, 'instruction': str(data.get('instruction', ''))[:3000], 'status': 'queued',
               'created_at': datetime.now(timezone.utc).isoformat(), 'execution_type': 'ide'}
        save(directory / 'job.json', job)
        with (directory / 'stdout.log').open('w') as stdout, (directory / 'stderr.log').open('w') as stderr:
            process = subprocess.Popen([sys.executable, '-u', '-m', 'scripts.run_console_action', '--job', identity], cwd=root,
                stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        job = read(directory / 'job.json') or job
        job['pid'] = process.pid
        save(directory / 'job.json', job)
        return job
