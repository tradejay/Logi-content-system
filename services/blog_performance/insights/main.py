"""Main insights pipeline runner: prepare, start, status, resume, and build.

Configuration-driven architecture:
- Schema validation via config.py (insights-pipeline-config-v1)
- Presets catalog (operational-full, test-single-common, test-mini-two-query, test-depth-10, replay-saved-data)
- ExecutionContext and StepResult contracts
- Dynamic step evaluation (no hardcoded query counts, depths, or QA thresholds)
- Operational pointer immutability under test_only mode
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from services.blog_performance.insights.tracker import StepTracker, save_atomic_json, STEPS_ORDER
from services.blog_performance.insights.config import (
    SCHEMA_VERSION,
    validate_config,
    compute_config_hash,
    load_preset,
    list_presets,
    build_config_from_args,
    ConfigValidationError,
    COMMON_KEYWORDS
)
from services.blog_performance.insights.context import ExecutionContext, StepResult
from services.blog_performance.insights.steps import (
    step_preflight,
    step_panel_preparation,
    step_collection_dispatch,
    step_common_import,
    step_products_import,
    step_body_collection,
    step_term_review,
    step_merge,
    step_top5_audit,
    step_html_build,
    step_qa_verification,
    step_activation,
    check_worker_dispatch_preflight,
    verify_standard_html
)

ROOT = Path(__file__).resolve().parents[3]
INSIGHTS_DATA = ROOT / 'data/blog_performance/insights'
ACTIVITY_SAMPLE_ID = '20261021T054347Z'
verify_html = verify_standard_html


def build_search_panel() -> List[Dict[str, Any]]:
    """Build full 34-query catalog search panel (7 common + 27 product queries)."""
    import urllib.parse
    from services.blog_performance.insights.config import COMMON_KEYWORDS, get_registered_catalog_keywords
    cat_map = get_registered_catalog_keywords(ROOT)
    panel = []
    base_url = "https://search.naver.com/search.naver?ssc=tab.blog.all&sm=tab_jum&query="
    for kw in COMMON_KEYWORDS:
        panel.append({
            'panel': 'common',
            'keyword': kw,
            'search_url': base_url + urllib.parse.quote_plus(kw),
            'product_id': None,
            'brand': None,
            'product': None,
            'report_group': 'common',
            'catalog_group': None
        })
    for kw, info in cat_map.items():
        item = dict(info)
        item['search_url'] = base_url + urllib.parse.quote_plus(kw)
        panel.append(item)
    return panel


STEP_DISPATCH_MAP = {
    'preflight': step_preflight,
    'panel_preparation': step_panel_preparation,
    'collection_dispatch': step_collection_dispatch,
    'common_import': step_common_import,
    'products_import': step_products_import,
    'body_collection': step_body_collection,
    'term_review': step_term_review,
    'merge': step_merge,
    'top5_audit': step_top5_audit,
    'html_build': step_html_build,
    'qa_verification': step_qa_verification,
    'activation': step_activation
}


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save_json(path: Path, data: Any) -> None:
    save_atomic_json(path, data)


def acquire_execution_lock(run_dir: Path, rid: str) -> Optional[Dict[str, Any]]:
    """Atomically acquire .execution.lock via O_CREAT | O_EXCL.
    Verifies owner process liveness before clearing stale crashes;
    never overwrites live executions solely based on elapsed time.
    """
    lock_file = run_dir / '.execution.lock'
    lock_payload = {
        'pid': os.getpid(),
        'locked_at': datetime.now(timezone.utc).isoformat(),
        'run_id': rid
    }

    for attempt in range(3):
        try:
            fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(lock_payload, f, ensure_ascii=False, indent=2)
            return None  # Lock acquired successfully
        except FileExistsError:
            pass

        # File exists. Read lock data carefully (handle brief race while other process writes)
        lock_data = None
        for read_attempt in range(3):
            try:
                content = lock_file.read_text(encoding='utf-8')
                if content.strip():
                    lock_data = json.loads(content)
                    break
            except Exception:
                pass
            time.sleep(0.05)

        if lock_data is None:
            # Cannot read valid lock data yet (file being written or unreadable).
            # Do NOT delete! Treat as actively locked.
            return {
                'run_id': rid,
                'status': 'locked',
                'message': "Run is actively locked (lock file is currently being created or written)."
            }

        owner_pid = lock_data.get('pid')
        locked_at_str = lock_data.get('locked_at')
        lock_time = None
        if locked_at_str:
            try:
                lock_time = datetime.fromisoformat(locked_at_str)
            except Exception:
                lock_time = None

        now = datetime.now(timezone.utc)

        # Check liveness
        is_alive = False
        if owner_pid and isinstance(owner_pid, int):
            try:
                import psutil
                is_alive = psutil.pid_exists(owner_pid)
            except Exception:
                is_alive = False

        # If process is alive, or if lock timestamp is in the future (simulated active lock in tests), it is actively locked.
        if is_alive or (lock_time and lock_time > now):
            return {
                'run_id': rid,
                'status': 'locked',
                'message': f"Run is actively locked by PID {owner_pid}."
            }

        # Age calculation
        age = (now - lock_time).total_seconds() if lock_time else 0

        # Stale lock cleanup: only if dead owner and aged over 300s, and re-verify ownership before unlink
        if owner_pid is not None and not is_alive and age >= 300:
            try:
                current_content = lock_file.read_text(encoding='utf-8')
                if json.loads(current_content).get('pid') == owner_pid:
                    lock_file.unlink(missing_ok=True)
            except Exception:
                pass
            continue

        return {
            'run_id': rid,
            'status': 'locked',
            'message': f"Run is actively locked by PID {owner_pid}."
        }

    return {
        'run_id': rid,
        'status': 'locked',
        'message': "Run is locked and acquisition could not be completed."
    }


def release_execution_lock(run_dir: Path) -> None:
    """Safely release execution lock only if owned by current process."""
    lock_file = run_dir / '.execution.lock'
    try:
        if lock_file.exists():
            content = lock_file.read_text(encoding='utf-8')
            lock_data = json.loads(content)
            if lock_data.get('pid') == os.getpid():
                lock_file.unlink(missing_ok=True)
    except Exception:
        pass


def validate_run_id(rid: str, root: Path = ROOT, test_only: bool = False) -> Tuple[str, Path]:
    if not rid or not isinstance(rid, str):
        raise ValueError("run_id must be a non-empty string")
    if not (rid.startswith('INSIGHTS-') or rid.startswith('INSIGHTS_')):
        raise ValueError(f"Invalid run_id prefix: '{rid}'. Must start with INSIGHTS-")
    pattern = r'^[a-zA-Z0-9_\-\.]+$'
    if not re.match(pattern, rid):
        raise ValueError(f"Invalid run_id format: '{rid}'. Only alphanumeric, -, _, . allowed.")

    base_dir = root / 'data/blog_performance/insights'
    if test_only:
        run_dir = base_dir / 'tests' / rid
    else:
        run_dir = base_dir / rid
    return rid, run_dir


def get_latest_run_id(root: Path = ROOT, test_only: bool = False) -> Optional[str]:
    if test_only:
        pointer = root / 'data/blog_performance/insights/tests/latest-test-run.json'
        if pointer.exists():
            data = read_json(pointer)
            if data.get('run_id'):
                return data['run_id']
        runs = sorted((root / 'data/blog_performance/insights/tests').glob('INSIGHTS-*'))
        return runs[-1].name if runs else None
    else:
        pointer = root / 'data/blog_performance/insights/latest-run.json'
        if pointer.exists():
            data = read_json(pointer)
            if data.get('run_id'):
                return data['run_id']
        runs = sorted((root / 'data/blog_performance/insights').glob('INSIGHTS-*'))
        return runs[-1].name if runs else None


def get_status(run_id: Optional[str] = None, root: Path = ROOT, test_only: bool = False) -> Dict[str, Any]:
    rid = run_id or get_latest_run_id(root, test_only=test_only)
    if not rid:
        return {'status': 'no_runs_found'}
    rid, run_dir = validate_run_id(rid, root, test_only=test_only)
    state_file = run_dir / 'state.json'
    if not state_file.exists():
        # Check alternative location if test_only flag was omitted
        alt_rid, alt_run_dir = validate_run_id(rid, root, test_only=not test_only)
        if (alt_run_dir / 'state.json').exists():
            run_dir = alt_run_dir
            state_file = alt_run_dir / 'state.json'
        else:
            return {'run_id': rid, 'status': 'state_missing'}

    state = read_json(state_file)
    return {
        'run_id': rid,
        'test_only': state.get('test_only', test_only),
        'stage': state.get('stage'),
        'updated_at': state.get('updated_at'),
        'steps': state.get('steps'),
        'task_ids': state.get('task_ids'),
        'artifacts': state.get('artifacts'),
        'errors': state.get('errors')
    }


def prepare_run(
    run_id: Optional[str] = None,
    offline: Optional[bool] = None,
    root: Path = ROOT,
    test_only: bool = False,
    queries: Optional[List[str]] = None,
    query_limit: Optional[int] = None,
    preset: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    depth: Optional[int] = None
) -> Dict[str, Any]:
    """Initialize a new insights run driven by validated schema configuration."""
    now_dt = datetime.now(timezone.utc)

    # 1. Resolve canonical configuration
    if config:
        valid, canonical_cfg, issues = validate_config(config, root=root)
        if not valid:
            raise ConfigValidationError(issues)
    elif preset:
        canonical_cfg = load_preset(preset, root=root)
        if offline is not None:
            canonical_cfg['execution']['mode'] = 'offline' if offline else 'online'
        if depth:
            canonical_cfg['execution']['depth'] = depth
    else:
        # Construct config from arguments
        class MockArgs:
            pass
        m = MockArgs()
        m.test = test_only
        m.test_only = test_only
        m.offline = offline if offline is not None else True
        m.depth = depth or 30
        m.query = None
        m.queries = queries
        m.query_limit = query_limit
        m.preset = None
        m.config = None
        m.common_json = None
        m.products_json = None
        m.ai_decisions = None
        canonical_cfg = build_config_from_args(m, root=root)

    cfg_hash = compute_config_hash(canonical_cfg)
    is_test = canonical_cfg.get('test_only', False)

    # 2. Assign and validate run ID and target directory
    if run_id:
        rid, run_dir = validate_run_id(run_id, root, test_only=is_test)
        if run_dir.exists() and (run_dir / 'state.json').exists():
            existing_state = read_json(run_dir / 'state.json')
            existing_manifest = read_json(run_dir / 'manifest.json') if (run_dir / 'manifest.json').exists() else {}
            panel_count = len(read_json(run_dir / 'search-panel.json').get('queries', [])) if (run_dir / 'search-panel.json').exists() else 0
            return {
                'run_id': rid,
                'test_only': is_test,
                'run_dir': str(run_dir.relative_to(root)),
                'status': existing_state.get('stage', 'already_prepared'),
                'panel_queries': panel_count,
                'offline': existing_manifest.get('offline', canonical_cfg['execution']['mode'] == 'offline'),
                'config_hash': cfg_hash,
                'resumed': True
            }
    else:
        prefix = "INSIGHTS-TEST" if is_test else "INSIGHTS"
        rid = f"{prefix}-{now_dt.strftime('%Y%m%dT%H%M%SZ')}"
        _, run_dir = validate_run_id(rid, root, test_only=is_test)

    run_dir.mkdir(parents=True, exist_ok=True)

    # 3. Persist config and its tamper-evident hash
    cfg_file = run_dir / 'config.json'
    cfg_file.write_text(json.dumps(canonical_cfg, ensure_ascii=False, indent=2), encoding='utf-8')
    (run_dir / 'config.json.sha256').write_text(cfg_hash, encoding='utf-8')

    # 4. Initialize state
    initial_state = {
        'run_id': rid,
        'test_only': is_test,
        'stage': 'prepared',
        'updated_at': now_dt.isoformat(),
        'config_hash': cfg_hash,
        'steps': {
            'preflight': {'status': 'pending'},
            'query_panel_ready': False,
            'common_imported': False,
            'products_imported': False,
            'common_bodies_analyzed': False,
            'products_bodies_analyzed': False,
            'terms_reviewed': False,
            'common_merged': False,
            'products_merged': False,
            'top5_audited': False,
            'html_built': False,
            'qa_verified': False,
            'activated': False
        },
        'task_ids': {},
        'artifacts': {
            'run_dir': str(run_dir.relative_to(root)),
            'config': str(cfg_file.relative_to(root))
        },
        'errors': []
    }
    save_json(run_dir / 'state.json', initial_state)

    ctx = ExecutionContext(
        run_id=rid,
        config=canonical_cfg,
        config_hash=cfg_hash,
        run_dir=run_dir,
        root=root,
        state=initial_state,
        manifest={},
        tracker=None
    )

    # 5. Execute Preflight check
    with StepTracker('preflight', run_id=rid, root=root, test_only=is_test) as trk_pf:
        pf_res = step_preflight(ctx)
        if pf_res.status == 'blocked':
            trk_pf.set_blocked(pf_res.error)
            raise RuntimeError(f"Preflight check failed for new run {rid}: {pf_res.error}")
        trk_pf.set_succeeded(pf_res.message)

    # 6. Execute Panel Preparation
    with StepTracker('panel_preparation', run_id=rid, root=root, test_only=is_test) as trk_prep:
        prep_res = step_panel_preparation(ctx)
        trk_prep.progress(completed=prep_res.metrics.get('panel_queries', 0), total=prep_res.metrics.get('panel_queries', 0))
        trk_prep.set_succeeded(prep_res.message, artifacts=prep_res.artifacts)

    return {
        'run_id': rid,
        'test_only': is_test,
        'run_dir': str(run_dir.relative_to(root)),
        'status': 'prepared',
        'panel_queries': len(ctx.panel_queries),
        'offline': ctx.is_offline,
        'config_hash': cfg_hash
    }


def run_pipeline(
    run_id: Optional[str] = None,
    common_json: Optional[Path] = None,
    products_json: Optional[Path] = None,
    ai_decisions: Optional[Path] = None,
    offline: Optional[bool] = None,
    root: Path = ROOT,
    test_only: bool = False,
    preset: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    depth: Optional[int] = None,
    query: Optional[Any] = None,
    queries: Optional[List[str]] = None,
    query_limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Execute or resume insights pipeline with strict idempotency, configuration integrity,
    and safe worker/file boundaries.
    """
    # 1. Resolve run_id and run_dir
    is_test_requested = bool(test_only or (run_id and run_id.startswith('INSIGHTS-TEST')) or query or queries or (preset and 'test' in preset))

    rid = run_id or get_latest_run_id(root, test_only=is_test_requested)
    target_dir = None
    if rid:
        # Check operational or test folder
        _, normal_dir = validate_run_id(rid, root, test_only=False)
        _, test_dir = validate_run_id(rid, root, test_only=True)
        if normal_dir.exists():
            target_dir = normal_dir
            is_test_requested = False
        elif test_dir.exists():
            target_dir = test_dir
            is_test_requested = True

    if not rid or not target_dir or not target_dir.exists():
        prep = prepare_run(
            run_id=rid,
            offline=True if offline is None else offline,
            root=root,
            test_only=is_test_requested,
            queries=queries,
            query_limit=query_limit,
            preset=preset,
            config=config,
            depth=depth
        )
        rid = prep['run_id']
        is_test_requested = prep['test_only']
        _, target_dir = validate_run_id(rid, root, test_only=is_test_requested)

    run_dir = target_dir

    # 2. Atomic execution lock check (idempotency & concurrent worker protection)
    lock_err = acquire_execution_lock(run_dir, rid)
    if lock_err:
        return lock_err

    try:
        # 3. Load & verify configuration
        cfg_file = run_dir / 'config.json'
        if not cfg_file.exists():
            # Migrate legacy or synthesize config
            class MockArgs:
                pass
            m = MockArgs()
            m.test = is_test_requested
            m.test_only = is_test_requested
            m.offline = offline if offline is not None else True
            m.depth = depth or 30
            m.query = query
            m.queries = queries
            m.query_limit = query_limit
            m.preset = preset
            m.config = None
            m.common_json = str(common_json) if common_json else None
            m.products_json = str(products_json) if products_json else None
            m.ai_decisions = str(ai_decisions) if ai_decisions else None
            canonical_cfg = build_config_from_args(m, root=root)
            cfg_file.write_text(json.dumps(canonical_cfg, ensure_ascii=False, indent=2), encoding='utf-8')
        else:
            canonical_cfg = read_json(cfg_file)

        # Check resume hash integrity if explicit config provided
        current_hash = compute_config_hash(canonical_cfg)
        saved_hash_file = run_dir / 'config.json.sha256'
        if saved_hash_file.exists():
            saved_hash = saved_hash_file.read_text(encoding='utf-8').strip()
            if config and current_hash != saved_hash:
                return {
                    'run_id': rid,
                    'status': 'config_hash_mismatch',
                    'error': f"Cannot resume run with modified configuration (saved SHA: {saved_hash[:8]}, current: {current_hash[:8]})."
                }

        # Apply runtime CLI overrides
        if offline is not None:
            canonical_cfg['execution']['mode'] = 'offline' if offline else 'online'
        if common_json:
            canonical_cfg['inputs']['common_json'] = str(common_json)
        if products_json:
            canonical_cfg['inputs']['products_json'] = str(products_json)
        if ai_decisions:
            canonical_cfg['inputs']['ai_decisions_json'] = str(ai_decisions)

        save_json(cfg_file, canonical_cfg)

        # Update manifest offline mode if changed
        manifest_file = run_dir / 'manifest.json'
        manifest = read_json(manifest_file) if manifest_file.exists() else {}
        if offline is not None and manifest:
            manifest['offline'] = offline
            save_json(manifest_file, manifest)

        state = read_json(run_dir / 'state.json')

        ctx = ExecutionContext(
            run_id=rid,
            config=canonical_cfg,
            config_hash=current_hash,
            run_dir=run_dir,
            root=root,
            state=state,
            manifest=manifest
        )

        # 4. Determine execution step sequence
        start_idx = STEPS_ORDER.index(ctx.start_step)
        stop_idx = STEPS_ORDER.index(ctx.stop_step)
        steps_to_run = STEPS_ORDER[start_idx:stop_idx + 1]

        # 5. Execute steps in order
        m_state_file = run_dir / 'monitor-state.json'
        existing_steps = {}
        if m_state_file.exists():
            try:
                existing_steps = read_json(m_state_file).get('steps', {})
            except Exception:
                existing_steps = {}

        for step_name in steps_to_run:
            step_fn = STEP_DISPATCH_MAP.get(step_name)
            if not step_fn:
                continue

            # On resume: if step already succeeded in monitor-state and artifacts exist, preserve it!
            if existing_steps.get(step_name, {}).get('status') == 'succeeded' and ctx.is_step_completed(step_name):
                continue

            with StepTracker(step_name, run_id=rid, root=root, test_only=ctx.test_only) as trk:
                ctx.tracker = trk
                result: StepResult = step_fn(ctx)

                if result.status == 'succeeded':
                    trk.set_succeeded(result.message, artifacts=result.artifacts)
                elif result.status == 'skipped':
                    trk.set_skipped(result.message)
                elif result.status == 'waiting':
                    if result.worker_task_id:
                        trk.set_waiting_worker(result.worker_task_id, result.message)
                    else:
                        trk.set_waiting_input(result.required_inputs, result.message)
                    ret = {
                        'run_id': rid,
                        'status': result.artifacts.get('status', 'waiting_for_inputs' if not result.worker_task_id else 'collection_dispatched'),
                        'step': step_name,
                        'message': result.message
                    }
                    if result.worker_task_id:
                        ret['task_id'] = result.worker_task_id
                    if result.required_inputs:
                        ret['required_inputs'] = result.required_inputs
                    ret.update(result.artifacts)
                    return ret
                elif result.status == 'blocked':
                    trk.set_blocked(result.error or result.message)
                    ret = {
                        'run_id': rid,
                        'status': result.artifacts.get('status', f'{step_name}_blocked'),
                        'step': step_name,
                        'error': result.error
                    }
                    ret.update(result.artifacts)
                    return ret
                elif result.status == 'failed':
                    trk.set_failed("STEP_FAILED", result.error or result.message)
                    return {
                        'run_id': rid,
                        'status': 'failed',
                        'step': step_name,
                        'error': result.error
                    }

        out_html = run_dir / 'report.html'
        return {
            'run_id': rid,
            'test_only': ctx.test_only,
            'status': 'completed',
            'report_html': str(out_html.relative_to(root)) if out_html.exists() else None,
            'activated': ctx.state['steps'].get('activated', False),
            'steps': ctx.state['steps']
        }

    finally:
        release_execution_lock(run_dir)


def run_and_manage(
    run_id: Optional[str] = None,
    watch: bool = False,
    max_wait_seconds: float = 300.0,
    poll_interval: float = 2.0,
    root: Path = ROOT,
    **kwargs
) -> Dict[str, Any]:
    """Single execution manager: executes pipeline and, if watch is True,
    monitors worker dispatch completion and seamlessly resumes until completion or block."""
    res = run_pipeline(run_id=run_id, root=root, **kwargs)
    if not watch:
        return res

    rid = res.get('run_id')
    start_time = time.time()

    while res.get('status') in ['collection_dispatched', 'term_review_dispatched']:
        task_id = res.get('task_id')
        if not task_id:
            break

        if time.time() - start_time > max_wait_seconds:
            res['manage_note'] = f"Single execution manager timed out after {max_wait_seconds}s"
            break

        time.sleep(poll_interval)

        from services.worker_dispatch import status as get_worker_status
        w_stat = get_worker_status(task_id, root=root)
        current_w_status = w_stat.get('status')

        if current_w_status == 'collected':
            # Worker task output collected, seamlessly resume!
            res = run_pipeline(
                run_id=rid,
                root=root,
                offline=kwargs.get('offline'),
                test_only=kwargs.get('test_only', False)
            )
        elif current_w_status in ['failed', 'delivery_unknown', 'superseded']:
            res['worker_terminal_status'] = current_w_status
            break

    return res


def build_cli_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)

    # 1. prepare
    prep = sub.add_parser('prepare', help='Prepare a new insights run')
    prep.add_argument('--run-id', help='Explicit run identifier')
    prep.add_argument('--preset', help='Preset name (e.g. test-single-common, test-mini-two-query, operational-full)')
    prep.add_argument('--config', type=Path, help='Direct configuration JSON file')
    prep.add_argument('--test', dest='test_only', action='store_true', help='Enable isolated test mode')
    prep.add_argument('--query', action='append', help='Repeatable single query')
    prep.add_argument('--queries', nargs='+', help='Space-separated queries list')
    prep.add_argument('--query-limit', type=int, help='Maximum queries limit')
    prep.add_argument('--depth', type=int, default=30, help='Collection depth (default: 30)')
    prep_mode = prep.add_mutually_exclusive_group()
    prep_mode.add_argument('--online', dest='offline', action='store_false', help='Prepare run in online mode')
    prep_mode.add_argument('--offline', dest='offline', action='store_true', help='Prepare run in offline mode')
    prep.set_defaults(offline=True)

    # 2. start
    st = sub.add_parser('start', help='Start or initialize-and-run the insights pipeline')
    st.add_argument('--run-id', help='Explicit run identifier')
    st.add_argument('--preset', help='Preset name (e.g. test-single-common, test-mini-two-query, operational-full)')
    st.add_argument('--config', type=Path, help='Direct configuration JSON file')
    st.add_argument('--test', dest='test_only', action='store_true', help='Enable isolated test mode')
    st.add_argument('--query', action='append', help='Repeatable single query')
    st.add_argument('--queries', nargs='+', help='Space-separated queries list')
    st.add_argument('--query-limit', type=int, help='Maximum queries limit')
    st.add_argument('--depth', type=int, help='Collection depth')
    st.add_argument('--common-json', type=Path, help='Path to local common input.json')
    st.add_argument('--products-json', type=Path, help='Path to local products input.json')
    st.add_argument('--ai-decisions', type=Path, help='Path to verified ai-decisions.json')
    st.add_argument('--watch', action='store_true', help='Watch worker dispatch and seamlessly resume upon completion')
    st_mode = st.add_mutually_exclusive_group()
    st_mode.add_argument('--online', dest='offline', action='store_false', help='Run in online mode (dispatch to workers)')
    st_mode.add_argument('--offline', dest='offline', action='store_true', help='Run in offline mode (use local files)')
    st.set_defaults(offline=True)

    # 3. resume
    res = sub.add_parser('resume', help='Resume an existing insights run')
    res.add_argument('--run-id', help='Run identifier to resume')
    res.add_argument('--test', dest='test_only', action='store_true', help='Resume in test directory')
    res.add_argument('--watch', action='store_true', help='Watch worker dispatch and seamlessly resume upon completion')
    res_mode = res.add_mutually_exclusive_group()
    res_mode.add_argument('--online', dest='offline', action='store_false', help='Resume in online mode')
    res_mode.add_argument('--offline', dest='offline', action='store_true', help='Resume in offline mode')
    res.set_defaults(offline=None)

    # 4. status
    stat = sub.add_parser('status', help='Check status of a run')
    stat.add_argument('--run-id', help='Run identifier')
    stat.add_argument('--test', dest='test_only', action='store_true', help='Check test run')

    # 5. presets
    sub.add_parser('presets', help='List all available configuration presets')

    # 6. build
    bld = sub.add_parser('build', help='Build HTML report directly')
    bld.add_argument('--run-id', help='Run identifier')
    bld.add_argument('--out', type=Path, help='Output HTML destination')

    # 7. preflight
    sub.add_parser('preflight', help='Execute worker preflight checks')

    # 8. test
    tst = sub.add_parser('test', help='Run insights test suite with Pytest and Allure reporting')
    tst.add_argument('subaction', nargs='?', default='all', choices=['all', 'rerun', 'report', 'open'], help='Test subaction')
    tst.add_argument('pytest_args', nargs=argparse.REMAINDER, help='Additional arguments passed to pytest')

    return p


def main(argv: Optional[List[str]] = None) -> None:
    p = build_cli_parser()
    args = p.parse_args(argv)

    if args.command == 'presets':
        items = list_presets(ROOT)
        print(json.dumps({'schema_version': SCHEMA_VERSION, 'presets': items}, ensure_ascii=False, indent=2))
        return

    if args.command == 'prepare':
        res_data = prepare_run(
            run_id=args.run_id,
            offline=args.offline,
            root=ROOT,
            test_only=getattr(args, 'test_only', False),
            queries=getattr(args, 'queries', None) or (args.query if getattr(args, 'query', None) else None),
            query_limit=getattr(args, 'query_limit', None),
            preset=getattr(args, 'preset', None),
            config=read_json(args.config) if getattr(args, 'config', None) else None,
            depth=getattr(args, 'depth', 30)
        )
    elif args.command == 'status':
        res_data = get_status(args.run_id, root=ROOT, test_only=getattr(args, 'test_only', False))
    elif args.command in ['start', 'resume']:
        res_data = run_and_manage(
            run_id=args.run_id,
            watch=getattr(args, 'watch', False),
            common_json=getattr(args, 'common_json', None),
            products_json=getattr(args, 'products_json', None),
            ai_decisions=getattr(args, 'ai_decisions', None),
            offline=args.offline,
            root=ROOT,
            test_only=getattr(args, 'test_only', False),
            preset=getattr(args, 'preset', None),
            config=read_json(args.config) if getattr(args, 'config', None) else None,
            depth=getattr(args, 'depth', None),
            query=getattr(args, 'query', None),
            queries=getattr(args, 'queries', None),
            query_limit=getattr(args, 'query_limit', None)
        )
    elif args.command == 'build':
        rid = args.run_id or get_latest_run_id()
        _, run_dir = validate_run_id(rid, ROOT)
        out = args.out or run_dir / 'report.html'
        from services.blog_performance.insights import build_search_insights_html
        common_rep = run_dir / 'common/body-analysis/report.json'
        prod_rep = run_dir / 'products/body-analysis/product-report.json'
        activity_src = ROOT / f'data/blog_performance/product-search/20261021T054347Z/name-matched-diagnostic/report.json'
        build_search_insights_html.build(activity_src, out, common_rep, prod_rep)
        valid, issues = verify_standard_html(out, ROOT)
        res_data = {'html': str(out), 'valid': valid, 'issues': issues}
    elif args.command == 'preflight':
        from services.worker_preflight import run as run_pf
        res_data = run_pf(root=ROOT, pipeline='insights', online=False)
    elif args.command == 'test':
        from services.blog_performance.insights import test_runner
        subact = getattr(args, 'subaction', 'all')
        p_args = getattr(args, 'pytest_args', [])
        if subact == 'rerun':
            sys.exit(test_runner.run_tests(rerun=True, extra_args=p_args))
        elif subact == 'report':
            sys.exit(test_runner.generate_report())
        elif subact == 'open':
            sys.exit(test_runner.open_report())
        else:
            code = test_runner.run_tests(rerun=False, extra_args=p_args)
            test_runner.generate_report()
            sys.exit(code)

    print(json.dumps(res_data, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
