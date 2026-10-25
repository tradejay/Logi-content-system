"""Pipeline execution state tracking, atomic JSON logging, and dashboard projection.

Never logs secrets, tokens, or raw prompts.
"""
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

ROOT = Path(__file__).resolve().parents[3]
STATUS_PROJECTION_FILE = ROOT / 'static/reports/insights-status.json'
RUNS_PROJECTION_FILE = ROOT / 'static/reports/insights-runs.json'

STEPS_ORDER = [
    'preflight',
    'panel_preparation',
    'collection_dispatch',
    'common_import',
    'products_import',
    'body_collection',
    'term_review',
    'merge',
    'top5_audit',
    'html_build',
    'qa_verification',
    'activation'
]

STEP_LABELS = {
    'preflight': '사전 점검 (의존성·워커)',
    'panel_preparation': '검색어 패널 준비 (34개 쿼리)',
    'collection_dispatch': '02 검색 순위 수집 배정',
    'common_import': '공통 검색 순위 검증 및 수집',
    'products_import': '제품 검색 순위 검증 및 수집',
    'body_collection': '블로그 본문 수집 및 모델 매칭',
    'term_review': '04 미확정 용어 독립 검토',
    'merge': '본문 분류 및 순위 병합',
    'top5_audit': '상위 1~5위 신규 글 독립 감사',
    'html_build': '13페이지 인사이트 보고서 생성',
    'qa_verification': '기계·브라우저 DOM QA 검증',
    'activation': '최신 인사이트 본 활성화'
}


def get_step_label(step: str, test_only: bool = False, query_count: Optional[int] = None) -> str:
    """Format step label dynamically, adjusting query count and page descriptions for test runs."""
    if step == 'panel_preparation':
        if test_only:
            count_str = f"{query_count}개 쿼리" if query_count else "1~2개 쿼리"
            return f"검색어 패널 준비 ({count_str})"
        return "검색어 패널 준비 (34개 쿼리)"
    elif step == 'html_build':
        if test_only:
            return "테스트 인사이트 보고서 생성"
        return "13페이지 인사이트 보고서 생성"
    return STEP_LABELS.get(step, step)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def save_atomic_json(target_path, data):
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(f'.tmp.{os.getpid()}.{time.time_ns()}')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    for attempt in range(5):
        try:
            os.replace(tmp, target)
            return
        except PermissionError:
            if attempt == 4:
                try:
                    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
                    tmp.unlink(missing_ok=True)
                except Exception:
                    pass
                return
            time.sleep(0.05 * (attempt + 1))


class StepTracker:
    """Context manager and tracker for individual pipeline execution modules/steps."""

    def __init__(self, step, module_id=None, run_id=None, root=ROOT, attempt=1, test_only=False, force_rerun=False):
        self.step = step
        self.module_id = module_id or step
        self.root = Path(root)
        self.attempt = attempt
        self.run_id = run_id or os.environ.get('INSIGHTS_RUN_ID') or f"INSIGHTS-STANDALONE-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        self.test_only = bool(test_only)
        self.force_rerun = bool(force_rerun)
        self.start_perf = time.perf_counter()
        self.wait_start_perf = None

        base_insights = self.root / 'data/blog_performance/insights'
        if self.test_only:
            self.run_dir = base_insights / 'tests' / self.run_id
            self.status_file = self.root / 'static/reports/insights-test-status.json'
        else:
            self.run_dir = base_insights / self.run_id
            self.status_file = (self.root / 'static/reports/insights-status.json') if self.root != ROOT else STATUS_PROJECTION_FILE

        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.run_dir / 'monitor-state.json'
        self.runs_file = (self.root / 'static/reports/insights-runs.json') if self.root != ROOT else RUNS_PROJECTION_FILE
        self.started_at = now_iso()
        self.status = 'queued'
        self.message = '대기 중'
        self.completed = None
        self.total = None
        self.error_code = None
        self.worker_task_id = None
        self.artifacts = {}
        self._is_nested = False

    def __enter__(self):
        # Check if already tracking this step in the current run (avoid duplicate counts)
        current = self._read_state()
        existing_step = current.get('steps', {}).get(self.step, {})
        if existing_step.get('status') == 'running' and existing_step.get('pid') == os.getpid():
            self._is_nested = True
            return self

        # If already succeeded in previous run and not forced to rerun, preserve timing and skip re-executing
        if existing_step.get('status') == 'succeeded' and not self.force_rerun:
            self._is_nested = True
            self.status = 'succeeded'
            self.message = existing_step.get('message', '')
            self.artifacts = existing_step.get('artifacts', {})
            return self

        self.status = 'running'
        self.message = f"{get_step_label(self.step, test_only=self.test_only)} 실행 중"
        self._update()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._is_nested:
            return False

        if exc_type is not None:
            self.status = 'failed'
            self.error_code = exc_type.__name__
            self.message = str(exc_val)[:300]
            self._update(finished=True)
            return False  # Do not suppress exception
        elif self.status == 'running':
            self.status = 'succeeded'
            self.message = f"{get_step_label(self.step, test_only=self.test_only)} 완료"
            self._update(finished=True)
        else:
            self._update(finished=(self.status in ['succeeded', 'skipped', 'failed', 'blocked', 'cancelled']))
        return False

    def progress(self, completed, total=None, message=None):
        """Update confirmed progress counters without AI extrapolation."""
        self.completed = completed
        if total is not None:
            self.total = total
        if message:
            self.message = message
        self._update()

    def heartbeat(self, message=None):
        """Process liveness heartbeat."""
        if message:
            self.message = message
        self._update()

    def set_waiting_worker(self, task_id, message="워커 결과 수집 대기 중"):
        self.status = 'waiting_worker'
        self.worker_task_id = task_id
        self.message = message
        self.wait_start_perf = time.perf_counter()
        self._update()

    def set_waiting_input(self, required_inputs, message="입력 파일 준비 대기 중"):
        self.status = 'waiting_input'
        self.message = message
        self.artifacts['required_inputs'] = [str(p) for p in required_inputs]
        self.wait_start_perf = time.perf_counter()
        self._update()

    def set_blocked(self, reason, issues=None):
        self.status = 'blocked'
        self.error_code = 'BLOCKED'
        self.message = str(reason)[:300]
        if issues:
            self.artifacts['issues'] = issues
        self._update(finished=True)

    def set_succeeded(self, message=None, artifacts=None):
        self.status = 'succeeded'
        if message:
            self.message = message
        if artifacts:
            self.artifacts.update(artifacts)
        self._update(finished=True)

    def set_skipped(self, reason="스킵됨"):
        self.status = 'skipped'
        self.message = str(reason)[:300]
        self._update(finished=True)

    def set_failed(self, error_code, message):
        self.status = 'failed'
        self.error_code = str(error_code)
        self.message = str(message)[:300]
        self._update(finished=True)

    def _read_state(self):
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding='utf-8'))
            except Exception:
                pass
        return {
            'run_id': self.run_id,
            'started_at': self.started_at,
            'updated_at': now_iso(),
            'current_module': self.module_id,
            'current_step': self.step,
            'overall_status': 'running',
            'steps': {}
        }

    def _update(self, finished=False):
        state = self._read_state()
        state['updated_at'] = now_iso()
        state['current_module'] = self.module_id
        state['current_step'] = self.step

        existing = state['steps'].get(self.step)
        if existing and existing.get('status') == 'succeeded' and not self.force_rerun:
            # Preserve existing historical timing & outcome completely!
            step_info = existing
        else:
            step_info = existing or {
                'module_id': self.module_id,
                'step': self.step,
                'label': get_step_label(self.step, test_only=self.test_only),
                'attempt': self.attempt,
                'started_at': self.started_at,
                'pid': os.getpid()
            }

            step_info['status'] = self.status
            step_info['updated_at'] = now_iso()
            step_info['message'] = self.message
            step_info['error_code'] = self.error_code
            step_info['completed'] = self.completed
            step_info['total'] = self.total
            step_info['worker_task_id'] = self.worker_task_id
            step_info['artifacts'] = self.artifacts
            step_info['label'] = get_step_label(self.step, test_only=self.test_only, query_count=self.total or self.completed)

            exec_sec = round(time.perf_counter() - self.start_perf, 2)
            step_info['execution_seconds'] = exec_sec

            prev_waiting = float(step_info.get('waiting_seconds', 0.0) or 0.0)
            if self.status in ['waiting_worker', 'waiting_input'] and self.wait_start_perf:
                cur_wait = time.perf_counter() - self.wait_start_perf
                step_info['waiting_seconds'] = round(prev_waiting + cur_wait, 2)
            else:
                step_info['waiting_seconds'] = prev_waiting

            step_info['elapsed_seconds'] = round(exec_sec + step_info['waiting_seconds'], 2)

            if finished:
                step_info['finished_at'] = now_iso()

        state['steps'][self.step] = step_info

        # Track pipeline-level wall clock and separated sum metrics
        start_run_dt = datetime.fromisoformat(state['started_at'])
        state['wall_clock_seconds'] = round((datetime.now(timezone.utc) - start_run_dt).total_seconds(), 2)
        state['sum_execution_seconds'] = round(sum(float(v.get('execution_seconds', v.get('elapsed_seconds', 0.0)) or 0.0) for v in state['steps'].values()), 2)
        state['sum_waiting_seconds'] = round(sum(float(v.get('waiting_seconds', 0.0) or 0.0) for v in state['steps'].values()), 2)
        state['sum_elapsed_seconds'] = round(sum(float(v.get('elapsed_seconds', 0.0) or 0.0) for v in state['steps'].values()), 2)

        # Determine overall status
        all_statuses = [v.get('status') for v in state['steps'].values()]
        if 'failed' in all_statuses:
            state['overall_status'] = 'failed'
        elif 'blocked' in all_statuses:
            state['overall_status'] = 'blocked'
        elif 'waiting_worker' in all_statuses:
            state['overall_status'] = 'waiting_worker'
        elif 'waiting_input' in all_statuses:
            state['overall_status'] = 'waiting_input'
        elif all(state['steps'].get(s, {}).get('status') == 'succeeded' for s in STEPS_ORDER):
            state['overall_status'] = 'succeeded'
        else:
            state['overall_status'] = 'running'

        # Write state to run directory
        save_atomic_json(self.state_file, state)

        # Project sanitized public dashboard JSON
        self._project_dashboard(state)

    def _project_dashboard(self, state):
        """Project sanitized, safe status to static/reports for web dashboard access."""
        dashboard_data = {
            'run_id': state['run_id'],
            'test_only': self.test_only,
            'scope': 'test (1~2 queries)' if self.test_only else 'operational (34 queries)',
            'overall_status': state['overall_status'],
            'current_module': state['current_module'],
            'current_step': state['current_step'],
            'started_at': state['started_at'],
            'updated_at': state['updated_at'],
            'wall_clock_seconds': state.get('wall_clock_seconds'),
            'sum_execution_seconds': state.get('sum_execution_seconds'),
            'sum_waiting_seconds': state.get('sum_waiting_seconds'),
            'sum_elapsed_seconds': state.get('sum_elapsed_seconds'),
            'steps_order': STEPS_ORDER,
            'steps': {}
        }

        # Check worker activity from worker-workspaces (work / outbox only)
        worker_activity = {}
        presets_path = self.root / 'worker-control/dispatch-presets.json'
        if presets_path.exists():
            try:
                presets = json.loads(presets_path.read_text(encoding='utf-8'))
                for role, route in presets.get('roles', {}).items():
                    folder = route.get('folder')
                    worker_dir = self.root / 'worker-workspaces' / folder
                    if worker_dir.exists():
                        latest_mtime = 0
                        for sub in ('work', 'outbox'):
                            p = worker_dir / sub
                            if p.exists():
                                for f in p.rglob('*'):
                                    if f.is_file():
                                        latest_mtime = max(latest_mtime, f.stat().st_mtime)
                        worker_activity[role] = {
                            'folder': folder,
                            'latest_modified_at': datetime.fromtimestamp(latest_mtime, timezone.utc).isoformat() if latest_mtime > 0 else None,
                            'seconds_since_change': round(time.time() - latest_mtime, 1) if latest_mtime > 0 else None
                        }
            except Exception:
                pass
        dashboard_data['worker_activity'] = worker_activity

        for s_name in STEPS_ORDER:
            s_data = state['steps'].get(s_name)
            if s_data:
                # Sanitized artifacts (only allowlisted relative web paths)
                safe_artifacts = {}
                for k, v in s_data.get('artifacts', {}).items():
                    if isinstance(v, str) and not any(sec in v for sec in ['.git', 'config', 'token', 'key']):
                        safe_artifacts[k] = v
                dashboard_data['steps'][s_name] = {
                    'step': s_name,
                    'label': STEP_LABELS.get(s_name, s_name),
                    'module_id': s_data.get('module_id'),
                    'status': s_data.get('status'),
                    'attempt': s_data.get('attempt', 1),
                    'started_at': s_data.get('started_at'),
                    'updated_at': s_data.get('updated_at'),
                    'finished_at': s_data.get('finished_at'),
                    'elapsed_seconds': s_data.get('elapsed_seconds', 0),
                    'error_code': s_data.get('error_code'),
                    'message': s_data.get('message'),
                    'completed': s_data.get('completed'),
                    'total': s_data.get('total'),
                    'worker_task_id': s_data.get('worker_task_id'),
                    'artifacts': safe_artifacts
                }
            else:
                dashboard_data['steps'][s_name] = {
                    'step': s_name,
                    'label': STEP_LABELS.get(s_name, s_name),
                    'status': 'queued',
                    'message': '대기 중'
                }

        # Atomic write to status projection file
        save_atomic_json(self.status_file, dashboard_data)
        # Keep each execution selectable without exposing raw internal state.
        save_atomic_json(self.root / 'static/reports/insights-run-status' / f'{self.run_dir.name}.json', dashboard_data)

        # Update run list projection
        runs_dir = self.root / 'data/blog_performance/insights'
        all_runs = []
        # 1. Operational runs
        for r_dir in sorted(runs_dir.glob('INSIGHTS-*'), reverse=True):
            if r_dir.is_dir() and (r_dir / 'monitor-state.json').exists():
                try:
                    r_st = json.loads((r_dir / 'monitor-state.json').read_text(encoding='utf-8'))
                    all_runs.append({
                        'run_id': r_st.get('run_id'),
                        'test_only': False,
                        'scope': 'operational (34 queries)',
                        'started_at': r_st.get('started_at'),
                        'updated_at': r_st.get('updated_at'),
                        'overall_status': r_st.get('overall_status')
                    })
                except Exception:
                    continue

        # 2. Test runs
        tests_dir = runs_dir / 'tests'
        if tests_dir.exists():
            for r_dir in sorted(tests_dir.glob('INSIGHTS-*'), reverse=True):
                if r_dir.is_dir() and (r_dir / 'monitor-state.json').exists():
                    try:
                        r_st = json.loads((r_dir / 'monitor-state.json').read_text(encoding='utf-8'))
                        all_runs.append({
                            'run_id': r_st.get('run_id'),
                            'test_only': True,
                            'scope': 'test (1~2 queries)',
                            'started_at': r_st.get('started_at'),
                            'updated_at': r_st.get('updated_at'),
                            'overall_status': r_st.get('overall_status')
                        })
                    except Exception:
                        continue

        all_runs.sort(key=lambda x: x.get('started_at') or '', reverse=True)
        save_atomic_json(self.runs_file, {'runs': all_runs, 'updated_at': now_iso()})

        # If test run, also record into insights-tests-index.json
        if self.test_only:
            test_index_file = self.root / 'static/reports/insights-tests-index.json'
            test_runs = [r for r in all_runs if r.get('test_only')]
            save_atomic_json(test_index_file, {'test_runs': test_runs, 'updated_at': now_iso()})
