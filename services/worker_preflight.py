"""Read-only worker/dependency preflight. Never dispatches or collects a task."""
import json
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .ide_worker_bridge import AgentAPI, ROOT, file_activity, local, verify_workspace


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def outstanding(root, folder):
    """Unfinished delivery is a reservation, even if files have stopped changing."""
    worker = root / 'worker-workspaces' / folder
    superseded = root / 'worker-control/superseded-tasks.json'
    skipped = {(x.get('worker_folder'), x.get('task_id')) for x in read(superseded).get('tasks', [])} if superseded.exists() else set()
    pending = []
    for state_path in sorted((root / 'worker-control/notifications' / folder).glob('*.json')):
        state = read(state_path)
        tid = state_path.stem
        if (folder, tid) in skipped or state.get('status') not in {'pending', 'sending', 'notified', 'delivery_unknown'}:
            continue
        task_path = worker / 'inbox' / tid / 'task.json'
        if not task_path.exists():
            pending.append({'task_id': tid, 'state': 'task_file_missing'})
            continue
        task = read(task_path)
        output = local(worker, task['ai_output']) if task.get('ai_output') else None
        # A result may have arrived before the collector runs. Do not notify it again.
        if output and output.is_file():
            continue
        pending.append({'task_id': tid, 'state': state.get('status')})
    return pending


def inspect_worker(role, route, root, probe):
    worker = root / 'worker-workspaces' / route['folder']
    result = {'role': role, 'folder': route['folder'], 'connected': False, 'workspace_matches': False,
              'can_dispatch': False, 'runtime_busy': 'unknown', 'browser_capability': 'not_probed', 'issues': []}
    try:
        config = read(worker / 'worker.json')
        if not config.get('conversation_id'):
            raise ValueError('conversation_missing')
        if route['stage'] not in config.get('owned_stages', []):
            raise ValueError('stage_not_owned')
        result['pending_tasks'] = outstanding(root, route['folder'])
        # Only AI output directories count as activity; host inbox preparation is excluded.
        activities = [file_activity(worker / name) for name in ('work', 'outbox')]
        available = [x for x in activities if x['latest_modified_at'] is not None]
        result['activity'] = max(available, key=lambda x: x['latest_modified_at']) if available else {'signal': 'no_files'}
        if probe is None:
            result['issues'].append('local_agent_service_unavailable')
        else:
            metadata = probe(config['conversation_id'])
            result['connected'] = True
            expected = root if config.get('worker_id') == 'BLOG-SYSTEM' and config.get('workspace_scope') == 'project_system' else worker
            verify_workspace(metadata, expected)
            result['workspace_matches'] = True
        if result['pending_tasks']:
            result['issues'].append('unfinished_delivery_check_before_new_task')
        result['can_dispatch'] = result['connected'] and result['workspace_matches'] and not result['pending_tasks']
    except Exception as error:
        # Raw metadata/process/endpoint errors may contain credentials. Only class-safe labels leave this layer.
        result['issues'].append('workspace_or_config_invalid' if isinstance(error, (ValueError, KeyError)) else 'connection_check_failed')
    return result


def port_open(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=.5):
            return True
    except OSError:
        return False


def run(root=ROOT, pipeline='insights', probe=None, online=True):
    root = Path(root)
    routes = read(root / 'worker-control/dispatch-presets.json')['roles']
    required = ['planner', 'review'] if pipeline == 'insights' else list(routes)
    if probe is None and online:
        try:
            endpoints = AgentAPI().discover()
            class SharedDiscovery(AgentAPI):
                def discover(self):
                    return endpoints
            # Fresh per-session endpoint resolution; no credentials saved or printed.
            probe = lambda conversation: SharedDiscovery().metadata(conversation)
        except Exception:
            probe = None
    with ThreadPoolExecutor(max_workers=3) as pool:
        workers = list(pool.map(lambda item: inspect_worker(*item, root, probe), routes.items()))
    for row in workers:
        row['required'] = row['role'] in required
        if not online and probe is None:
            row.update(connected=None, workspace_matches=None, connection_check='skipped_offline')
            row['issues'] = [x for x in row['issues'] if x != 'local_agent_service_unavailable']
    dependencies = []
    if pipeline == 'insights':
        for name in ['services/blog_performance/product-search-catalog.json',
                     'services/blog_performance/insights/main.py',
                     'scripts/import_browser_search_ranks.py', 'scripts/import_product_browser_ranks.py',
                     'scripts/analyze_browser_search_bodies.py', 'scripts/merge_browser_body_classifications.py',
                     'scripts/merge_product_browser_ranks.py', 'scripts/build_search_insights_html.py',
                     'scripts/check_search_insights_html.cjs', 'data/blog_performance/blog-directory.json']:
            dependencies.append({'path': name, 'exists': (root / name).is_file()})
    required_workers_ready = all(w['can_dispatch'] for w in workers if w['required'])
    issues = []
    if not required_workers_ready:
        issues.append('필수 워커 연결·작업 예약 상태를 확인하세요.')
    if any(not d['exists'] for d in dependencies):
        issues.append('필수 파이프라인 파일이 누락됐습니다.')
    if pipeline == 'insights':
        issues += ['브라우저 도구와 네이버 검색 성공 여부는 연결 조회만으로 확인되지 않습니다. 최근 수집 테스트 또는 시작 단계 검증이 필요합니다.']
    servers = [{'port': p, 'listening': port_open(p) if online else None, 'required': False,
                'scope': '콘솔' if p == 5014 else '보고서 열람' if p == 5015 else '글 공식검토용 · 인사이트 분석에는 불필요'} for p in (5014, 5015, 5050)]
    return {'checked_at': time.time(), 'pipeline': pipeline, 'mode': 'read_only_no_dispatch',
            'required_workers_ready': required_workers_ready,
            'pipeline_ready': required_workers_ready and all(d['exists'] for d in dependencies),
            'workers': workers, 'dependencies': dependencies, 'servers': servers, 'issues': issues,
            'limits': '연결됨은 실행 중·브라우저 가능·모델 사용량 충분함을 뜻하지 않습니다. 최근 파일 변경 없음도 대기 또는 고장 확정이 아닙니다.'}
