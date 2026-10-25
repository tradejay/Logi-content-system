"""Observe existing IDE assignments and files without sending messages."""
import re
from pathlib import Path
from .ide_worker_bridge import ROOT, load, local, file_activity, verify_report


def read(path):
    try:
        return load(path)
    except (OSError, ValueError):
        return {}


def task_view(tid, root=ROOT):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', tid):
        raise ValueError('Invalid task ID')
    record = load(root / 'worker-control/dispatch/tasks' / (tid + '.json'))
    worker = local(root / 'worker-workspaces', record['worker_folder'])
    task = load(worker / 'inbox' / tid / 'task.json')
    if task.get('task_id') != tid:
        raise ValueError('Task identity mismatch')
    state = read(root / 'worker-control/notifications' / record['worker_folder'] / (tid + '.json'))
    start = worker / 'inbox' / tid / 'START.md'
    instruction = start.read_text(encoding='utf-8') if start.exists() else ''
    instruction = instruction.split('\n\n', 1)[-1].split('\n\n필수 입력만 읽기:', 1)[0]
    files = []
    def add(path, kind):
        resolved = path.resolve()
        if not resolved.is_file() or not any(resolved.is_relative_to((worker / area / tid).resolve()) for area in ['inbox', 'work', 'outbox']):
            return
        if any(part in {'.git', '__pycache__'} for part in path.parts):
            return
        if resolved.suffix.lower() not in {'.json', '.md', '.txt', '.py', '.patch', '.diff', '.html', '.png', '.jpg', '.jpeg', '.webp'}:
            return
        rel = resolved.relative_to(worker.resolve()).as_posix()
        files.append({'path': rel, 'kind': kind, 'bytes': resolved.stat().st_size, 'modified_at': resolved.stat().st_mtime,
                      'url': f'/api/content-system/ide-tasks/{tid}/file?path={rel}'})
    for item in read(worker / 'inbox' / tid / 'input-manifest.json').get('files', []):
        add(local(worker, item['path']), 'input')
    for path in (worker / 'work' / tid).rglob('*'):
        add(path, 'output')
    for path in (worker / 'outbox' / tid).rglob('*.json'):
        add(path, 'record')
    activity = file_activity(worker / 'work' / tid)
    output = local(worker, task['ai_output']) if task.get('ai_output') else None
    output_received = bool(output and output.is_file())
    verified, error = False, None
    if (worker / 'outbox' / tid / 'report.json').exists():
        try:
            verify_report(worker, tid, task)
            verified = True
        except (OSError, ValueError, KeyError) as exc:
            error = str(exc)[:240]
    status = 'collected' if verified else 'verification_failed' if error else 'output_received' if output_received else state.get('status', 'pending')
    return {'task_id': tid, 'worker': record['worker'], 'worker_folder': record['worker_folder'],
            'created_at': record.get('created_at'), 'status': status, 'instruction': instruction,
            'sent_at': state.get('sent_at'), 'collected_at': state.get('collected_at'),
            'activity': activity, 'files': sorted(files, key=lambda f: f['modified_at'], reverse=True),
            'result': read(output) if output_received and output.suffix == '.json' else None,
            'error': error or state.get('error'), 'test_only': task.get('test_only', True),
            'output_received': output_received, 'verified': verified}


def snapshot(tid=None, root=ROOT):
    paths = sorted((root / 'worker-control/dispatch/tasks').glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:100]
    tasks = []
    for path in paths:
        record = read(path)
        if not record.get('task_id'):
            continue
        state = read(root / 'worker-control/notifications' / record.get('worker_folder', '') / (record['task_id'] + '.json'))
        tasks.append({**{k: record.get(k) for k in ['task_id', 'worker', 'created_at']}, 'status': state.get('status', 'pending')})
    selected = tid or (tasks[0]['task_id'] if tasks else None)
    return {'tasks': tasks, 'selected': task_view(selected, root) if selected else None}
