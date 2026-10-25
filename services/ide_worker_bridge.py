"""Host-only Antigravity notifications and verified outbox collection."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(tmp, path)


def local(root, relative):
    p = Path(relative)
    if p.is_absolute() or p.drive or '..' in p.parts:
        raise ValueError('Invalid worker-relative path')
    p = (root / p).resolve()
    if not p.is_relative_to(root.resolve()):
        raise ValueError('Path leaves worker root')
    return p


def file_activity(worker, recent_seconds=120, now=None):
    """Infer file activity using metadata only; do not read worker conversations."""
    now = time.time() if now is None else now
    latest = None
    for directory, subdirs, names in os.walk(worker, followlinks=False):
        subdirs[:] = [s for s in subdirs if s not in ['.git','__pycache__']
                      and not (Path(directory)/s).is_symlink()]
        for name in names:
            path = Path(directory)/name
            if path.is_symlink():
                continue
            try:
                stamp = path.stat().st_mtime
                if latest is None or stamp > latest[0]:
                    latest = (stamp, path.relative_to(worker).as_posix())
            except OSError:
                continue
    age = max(0, now-latest[0]) if latest else None
    return {'signal':'recent_file_changes' if age is not None and age <= recent_seconds else 'no_recent_file_changes',
            'latest_path':latest[1] if latest else None,'latest_modified_at':latest[0] if latest else None,
            'seconds_since_change':round(age,1) if age is not None else None,
            'recent_window_seconds':recent_seconds}


class AgentAPI:
    def __init__(self):
        self.exe = Path(os.environ['LOCALAPPDATA']) / 'Programs/Antigravity/resources/bin/language_server.exe'
        self.env = None

    def discover(self):
        import psutil
        endpoints = []
        for process in psutil.process_iter(['name', 'exe', 'cmdline']):
            try:
                if 'language_server' not in (process.info['name'] or '').lower():
                    continue
                match = __import__('re').search(r'--csrf_token\s+(\S+)', ' '.join(process.info['cmdline'] or []))
                if not match:
                    continue
                for connection in process.net_connections(kind='tcp'):
                    if connection.status == 'LISTEN':
                        endpoints.append((connection.laddr.port, match.group(1), process.info['exe']))
            except (psutil.Error, OSError):
                continue
        if endpoints:
            return endpoints
        # Capture credentials in memory only. Never log the process command line.
        ps = """$items=@(); Get-CimInstance Win32_Process -Filter \"name='language_server.exe'\" | ForEach-Object {
        $m=[regex]::Match($_.CommandLine,'--csrf_token\\s+(\\S+)');
        if($m.Success){$ports=@(Get-NetTCPConnection -State Listen -OwningProcess $_.ProcessId | Select-Object -ExpandProperty LocalPort);
        $items+=@{token=$m.Groups[1].Value;ports=$ports}} }; ConvertTo-Json -InputObject $items -Compress"""
        proc = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True, timeout=30)
        if proc.returncode or not proc.stdout.strip():
            raise RuntimeError('Cannot discover Antigravity local server')
        endpoints = json.loads(proc.stdout)
        return [(port, item['token']) for item in endpoints for port in item['ports']]

    def call(self, args, env):
        proc = subprocess.run([str(self.exe), 'agentapi', *args], env=env,
                              capture_output=True, text=True, encoding='utf-8', timeout=45)
        try:
            data = json.loads(proc.stdout)
        except ValueError:
            raise RuntimeError('agentapi returned an invalid response') from None
        if proc.returncode or data.get('error'):
            raise RuntimeError('agentapi request failed')
        return data

    def metadata(self, conversation):
        if self.env:
            return self.call(['get-conversation-metadata', conversation], self.env)
        for endpoint in self.discover():
            port, token = endpoint[:2]
            if len(endpoint) > 2:
                self.exe = Path(endpoint[2])
            env = {k: v for k, v in os.environ.items() if not k.startswith('ANTIGRAVITY_')}
            env['ANTIGRAVITY_LS_ADDRESS'] = f'https://127.0.0.1:{port}'
            env['ANTIGRAVITY_CSRF_TOKEN'] = token
            try:
                result = self.call(['get-conversation-metadata', conversation], env)
                self.env = env
                return result
            except RuntimeError:
                continue
        raise RuntimeError('No reachable Antigravity agentapi endpoint')

    def send(self, conversation, message):
        return self.call(['send-message', conversation, message], self.env)


def verify_workspace(metadata, worker):
    m = metadata['response']['conversationMetadata']['metadata']
    uris = [w['workspaceFolderAbsoluteUri'] for w in m.get('workspaces', [])]
    paths = [Path(unquote(urlparse(uri).path).lstrip('/')).resolve() for uri in uris]
    if paths != [worker.resolve()]:
        raise ValueError('Conversation workspace does not match assigned worker root')


def verify_report(worker, task_id, task):
    source = worker / 'inbox' / task_id / 'task.json'
    report_path = worker / 'outbox' / task_id / 'report.json'
    pointer = worker / 'outbox' / task_id / 'current-report.json'
    if pointer.exists():
        selected = local(worker, load(pointer)['path'])
        if not selected.is_relative_to(worker / 'outbox' / task_id / 'resubmissions'):
            raise ValueError('Resubmission report outside task history')
        report_path = selected
    report = load(report_path)
    if (report.get('task_id'), report.get('worker_id'), report.get('stage'), report.get('execution_type')) != (
            task_id, task['worker_id'], task['stage'], 'ide'):
        raise ValueError('Report identity mismatch')
    if report.get('status') not in ['completed', 'needs_input', 'blocked']:
        raise ValueError('Invalid result status')
    if report.get('publication_approved') is not False:
        raise ValueError('Worker cannot approve publication')
    if report.get('input_sha256') != hashlib.sha256(source.read_bytes()).hexdigest():
        raise ValueError('Task changed since submission')
    paths = set()
    for item in report.get('artifacts', []):
        p = local(worker, item['path'])
        if not p.is_relative_to(local(worker, 'work/' + task_id)):
            raise ValueError('Artifact outside task folder')
        raw = p.read_bytes()
        if hashlib.sha256(raw).hexdigest() != item['sha256'] or len(raw) != item['bytes']:
            raise ValueError('Artifact hash mismatch')
        paths.add(item['path'])
    if report['status'] == 'completed' and not set(task['required_outputs']).issubset(paths):
        raise ValueError('Required output missing')
    manifest = load(local(worker, task['input_manifest']))
    for item in manifest['files']:
        if hashlib.sha256(local(worker, item['path']).read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Input snapshot changed')
    return report


def process(worker_folder, task_id, api=None, root=ROOT):
    # Prevent simultaneous collectors from notifying the same task twice.
    lock_dir = root / 'worker-control/notification-locks'
    lock_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256((worker_folder + '/' + task_id).encode()).hexdigest()
    lock = lock_dir / (key + '.lock')
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return {'status':'locked'}
    try:
        os.close(fd)
        return _process(worker_folder, task_id, api, root)
    finally:
        lock.unlink(missing_ok=True)


def _process(worker_folder, task_id, api=None, root=ROOT):
    superseded_path=root/'worker-control/superseded-tasks.json'
    if superseded_path.exists():
        entries=load(superseded_path).get('tasks',[])
        if any(item.get('worker_folder')==worker_folder and item.get('task_id')==task_id for item in entries):
            return {'task_id':task_id,'worker':worker_folder,'status':'superseded'}
    workers = root / 'worker-workspaces'
    worker = local(workers, worker_folder)
    task_path = local(worker, 'inbox/' + task_id + '/task.json')
    task = load(task_path)
    config = load(worker / 'worker.json')
    if task.get('task_id') != task_id or task.get('worker_id') != config['worker_id']:
        raise ValueError('Task identity mismatch')
    if task.get('execution_type') != 'ide' or task.get('stage') not in config['owned_stages']:
        raise ValueError('Task execution ownership mismatch')
    if not task.get('notification', {}).get('enabled'):
        raise ValueError('Task notification not authorized')
    state_path = root / 'worker-control/notifications' / worker_folder / (task_id + '.json')
    state = load(state_path) if state_path.exists() else {'task_id': task_id, 'worker': worker_folder, 'status': 'pending'}
    if task.get('output_protocol')=='content_only_v1':
        from .ide_worker_artifacts import finalize
        finalize(worker,task_id,task)
    if (worker / 'outbox' / task_id / 'report.json').exists():
        report = verify_report(worker, task_id, task)
        collected_at=state.get('collected_at',time.time())
        state.update(status='collected', result_status=report['status'], collected_at=collected_at, report=report)
        if state.get('sent_at') is not None:state['dispatch_to_collection_seconds']=round(collected_at-state['sent_at'],2)
        save(state_path, state)
        return state
    if state['status'] != 'pending':
        return state  # Includes sending/unknown: never blindly duplicate a message.
    if not config.get('conversation_id'):
        raise ValueError('Worker conversation ID not registered')
    api = api or AgentAPI()
    system_scope = (config.get('worker_id') == 'BLOG-SYSTEM' and task.get('stage') == 'system_change'
                    and config.get('workspace_scope') == 'project_system')
    verify_workspace(api.metadata(config['conversation_id']), root if system_scope else worker)
    state.update(status='sending', conversation_id=config['conversation_id'], sent_at=time.time())
    save(state_path, state)
    completion=('편집 또는 리뷰 결과 파일 하나만 저장하세요. 기록·비교표·전문 조립·보고서·검증 코드는 작성하지 마세요.'
                if task.get('output_protocol')=='content_only_v1' else '완료 후 START.md의 worker_io.py submit 명령으로 outbox 보고서를 반드시 제출하세요.')
    message = ('원시인 모드: 지정된 필수 파일만 읽고, 계획·중간 해설·결과 부연설명 없이 산출물만 만드세요. 전문 작업의 본문·조건은 생략하지 마세요. '
               f'새 {"테스트 " if task.get("test_only", True) else ""}작업: inbox/{task_id}/START.md를 읽고 수행하세요. '
               '지정된 자기 루트 내 파일만 사용하고 실제 원고·승인·본 파이프라인은 변경하지 마세요. '
               +completion+' '
               '이 메시지는 기존 inbox 작업의 실행 알림이며 중복 작업을 만들지 마세요.')
    if system_scope:
        message = (f'사용자가 배정한 시스템 변경 작업입니다. worker-workspaces/{worker_folder}/AGENTS.md와 '
                   f'worker-workspaces/{worker_folder}/inbox/{task_id}/START.md를 읽으세요. '
                   f'작업 경로는 worker-workspaces/{worker_folder}/를 기준으로 해석하세요. '
                   '입력 복사본만 읽고 지정 work 폴더에 수정 코드·필요한 테스트·결과 JSON만 저장하세요. '
                   '프로젝트 원본 코드·실제 원고·승인·Fact·운영 설정은 직접 변경하지 마세요. 로그·보고서·해시는 시스템이 기록합니다. 완료 답변은 한 줄입니다.')
    try:
        api.send(config['conversation_id'], message)
        state['status'] = 'notified'
    except Exception:
        state['status'] = 'delivery_unknown'
        save(state_path, state)
        raise
    save(state_path, state)
    return state
