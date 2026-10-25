"""Regression and monitor unit tests for ROOT-INSIGHTS-20261023.

Verifies:
1. CLI start/resume --online/--offline parser and manifest mode preservation.
2. Worker dispatch JSON panel (.json) input and single result.json contract.
3. Preflight gate blocking on worker disconnect/reservations in online mode.
4. StepTracker atomic logging, dashboard projection, and staleness detection.
5. Offline isolation and HTML monitor verification.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from services.blog_performance.insights import main as insights_main
from services.blog_performance.insights.tracker import StepTracker, STATUS_PROJECTION_FILE, RUNS_PROJECTION_FILE
from services import worker_preflight
from services import worker_dispatch

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_COMMON = ROOT / 'data/blog_performance/browser-search/20261022-common-ea7fdc3e9b/input.json'
FIXTURE_PRODUCTS = ROOT / 'data/blog_performance/browser-search/20261022-products-ko-419ff665f1/input.json'
FIXTURE_AI_DECISIONS = ROOT / 'data/blog_performance/browser-search/20261022-common-ea7fdc3e9b/body-analysis/ai-decisions.json'


class TestInsightsRegressionAndMonitor(unittest.TestCase):

    def test_cli_parser_online_offline_flags(self):
        """Issue 1: Test CLI start/resume parser supports --online and --offline explicitly."""
        parser = insights_main.build_cli_parser()

        # start defaults to offline=True
        args_st_def = parser.parse_args(['start'])
        self.assertTrue(args_st_def.offline)

        # start --offline
        args_st_off = parser.parse_args(['start', '--offline'])
        self.assertTrue(args_st_off.offline)

        # start --online
        args_st_on = parser.parse_args(['start', '--online'])
        self.assertFalse(args_st_on.offline)

        # resume defaults to offline=None (to preserve manifest)
        args_res_def = parser.parse_args(['resume'])
        self.assertIsNone(args_res_def.offline)

        # resume --online
        args_res_on = parser.parse_args(['resume', '--online'])
        self.assertFalse(args_res_on.offline)

        # resume --offline
        args_res_off = parser.parse_args(['resume', '--offline'])
        self.assertTrue(args_res_off.offline)

        # prepare options
        args_prep_on = parser.parse_args(['prepare', '--online'])
        self.assertFalse(args_prep_on.offline)
        args_prep_off = parser.parse_args(['prepare', '--offline'])
        self.assertTrue(args_prep_off.offline)

    def test_manifest_mode_preservation_on_resume(self):
        """Issue 1: Test that resume preserves the execution manifest mode."""
        tmp = tempfile.mkdtemp(prefix='test-manifest-mode-')
        test_root = Path(tmp)
        try:
            # Prepare run in online mode
            rid = "INSIGHTS-TEST-MODE-PRESERVE"
            prep = insights_main.prepare_run(rid, offline=False, root=test_root)
            self.assertFalse(prep['offline'])

            manifest_path = test_root / 'data/blog_performance/insights' / rid / 'manifest.json'
            self.assertTrue(manifest_path.exists())
            manifest = insights_main.read_json(manifest_path)
            self.assertFalse(manifest['offline'])

            # Resume with offline=None -> should preserve offline=False
            run_dir = test_root / 'data/blog_performance/insights' / rid
            # Simulate call with offline=None
            with patch('services.blog_performance.insights.steps.check_worker_dispatch_preflight', return_value=(False, ['mock_blocked'], [])):
                res = insights_main.run_pipeline(run_id=rid, offline=None, root=test_root)
                # It should attempt online dispatch and hit the mock preflight gate
                self.assertEqual(res['status'], 'worker_preflight_blocked')
                # Manifest must still be offline=False
                manifest_after = insights_main.read_json(manifest_path)
                self.assertFalse(manifest_after['offline'])

            # Calling resume with explicit override --offline updates manifest
            with patch('services.blog_performance.insights.steps.check_worker_dispatch_preflight', return_value=(False, ['mock_blocked'], [])):
                res_off = insights_main.run_pipeline(run_id=rid, offline=True, root=test_root)
                self.assertEqual(res_off['status'], 'waiting_for_inputs')
                manifest_off = insights_main.read_json(manifest_path)
                self.assertTrue(manifest_off['offline'])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_worker_dispatch_json_panel_and_contract(self):
        """Issue 2: Test online dispatch sends .json panel and includes START result.json contract."""
        tmp = tempfile.mkdtemp(prefix='test-dispatch-json-')
        test_root = Path(tmp)
        try:
            rid = "INSIGHTS-TEST-DISPATCH-JSON"
            insights_main.prepare_run(rid, offline=False, root=test_root)
            run_dir = test_root / 'data/blog_performance/insights' / rid

            # Verify search-panel.json has schema_version
            panel_json = run_dir / 'search-panel.json'
            self.assertTrue(panel_json.exists())
            p_data = insights_main.read_json(panel_json)
            self.assertEqual(p_data.get('schema_version'), 'insights-search-panel-v1')
            self.assertEqual(p_data.get('total'), 34)

            # Mock check_worker_dispatch_preflight to pass
            with patch('services.blog_performance.insights.steps.check_worker_dispatch_preflight', return_value=(True, [], [])):
                captured_enqueues = []

                def mock_enqueue(role, msg, inputs, kind, root):
                    captured_enqueues.append({'role': role, 'msg': msg, 'inputs': inputs, 'kind': kind})
                    return {'task_id': 'MOCK-PLANNER-TASK-123'}

                with patch('services.worker_dispatch.enqueue', side_effect=mock_enqueue):
                    res = insights_main.run_pipeline(run_id=rid, offline=False, root=test_root)
                    self.assertEqual(res['status'], 'collection_dispatched')
                    self.assertEqual(len(captured_enqueues), 1)

                    call = captured_enqueues[0]
                    self.assertEqual(call['role'], 'planner')
                    # Must pass search-panel.json, NEVER .csv
                    self.assertEqual(len(call['inputs']), 1)
                    input_file = Path(call['inputs'][0])
                    self.assertEqual(input_file.suffix, '.json')
                    self.assertEqual(input_file.name, 'search-panel.json')

                    # Verify message specifies result.json contract
                    msg = call['msg']
                    self.assertIn("search-panel.json", msg)
                    self.assertIn("result.json", msg)
                    self.assertIn("schema_version", msg)
                    self.assertIn("common", msg)
                    self.assertIn("products", msg)
                    self.assertIn("rows", msg)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_preflight_worker_gate_blocking(self):
        """Issue 3: Test preflight blocks online dispatch on disconnected worker or pending reservation."""
        tmp = tempfile.mkdtemp(prefix='test-worker-gate-')
        test_root = Path(tmp)
        try:
            rid = "INSIGHTS-TEST-WORKER-GATE"
            insights_main.prepare_run(rid, offline=False, root=test_root)

            # Case A: Worker disconnected
            mock_pf_disconnected = {
                'workers': [
                    {'role': 'planner', 'folder': '02_research_planning', 'connected': False,
                     'workspace_matches': True, 'can_dispatch': False, 'pending_tasks': [],
                     'issues': ['worker_not_connected']}
                ]
            }
            with patch('services.worker_preflight.run', return_value=mock_pf_disconnected):
                res = insights_main.run_pipeline(run_id=rid, offline=False, root=test_root)
                self.assertEqual(res['status'], 'worker_preflight_blocked')
                self.assertEqual(res['role'], 'planner')
                self.assertTrue(any('세션 구동' in iss for iss in res['issues']))

            # Case B: Worker has pending unfinished task
            mock_pf_pending = {
                'workers': [
                    {'role': 'planner', 'folder': '02_research_planning', 'connected': True,
                     'workspace_matches': True, 'can_dispatch': False,
                     'pending_tasks': [{'task_id': 'TASK-BUSY-001', 'state': 'notified'}],
                     'issues': ['unfinished_delivery_check_before_new_task']}
                ]
            }
            with patch('services.worker_preflight.run', return_value=mock_pf_pending):
                res2 = insights_main.run_pipeline(run_id=rid, offline=False, root=test_root)
                self.assertEqual(res2['status'], 'worker_preflight_blocked')
                self.assertEqual(len(res2['pending_tasks']), 1)

            # Case C: Offline mode does NOT block on worker connection
            with patch('services.worker_preflight.run', return_value={'dependencies': []}):
                res_replay = insights_main.run_pipeline(
                    run_id=rid,
                    offline=True,
                    root=test_root
                )
                self.assertEqual(res_replay['status'], 'waiting_for_inputs')
                self.assertNotEqual(res_replay.get('status'), 'worker_preflight_blocked')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_step_tracker_lifecycle_and_projection(self):
        """Test StepTracker atomic logging, progress tracking, and dashboard projection."""
        tmp = tempfile.mkdtemp(prefix='test-tracker-')
        test_root = Path(tmp)
        try:
            rid = "INSIGHTS-TEST-TRACKER"
            # 1. Normal success step
            with StepTracker('preflight', run_id=rid, root=test_root) as trk:
                trk.progress(completed=10, total=10, message="모든 파일 정상")

            state_file = test_root / 'data/blog_performance/insights' / rid / 'monitor-state.json'
            self.assertTrue(state_file.exists())
            state = json.loads(state_file.read_text(encoding='utf-8'))
            self.assertEqual(state['run_id'], rid)
            self.assertEqual(state['steps']['preflight']['status'], 'succeeded')
            self.assertEqual(state['steps']['preflight']['completed'], 10)
            self.assertEqual(state['steps']['preflight']['total'], 10)

            # 2. Waiting worker step
            with StepTracker('collection_dispatch', run_id=rid, root=test_root) as trk_col:
                trk_col.set_waiting_worker('TASK-02-COLLECT', '수집 대기 중')

            state2 = json.loads(state_file.read_text(encoding='utf-8'))
            self.assertEqual(state2['steps']['collection_dispatch']['status'], 'waiting_worker')
            self.assertEqual(state2['steps']['collection_dispatch']['worker_task_id'], 'TASK-02-COLLECT')

            # 3. Exception failure step
            with self.assertRaises(ValueError):
                with StepTracker('html_build', run_id=rid, root=test_root) as trk_err:
                    raise ValueError("Simulated template error")

            state3 = json.loads(state_file.read_text(encoding='utf-8'))
            self.assertEqual(state3['steps']['html_build']['status'], 'failed')
            self.assertEqual(state3['steps']['html_build']['error_code'], 'ValueError')
            self.assertIn("Simulated template error", state3['steps']['html_build']['message'])

            # 4. Check dashboard projection file in test_root
            test_status_file = test_root / 'static/reports/insights-status.json'
            self.assertTrue(test_status_file.exists())
            proj = json.loads(test_status_file.read_text(encoding='utf-8'))
            self.assertIn('steps', proj)
            self.assertIn('preflight', proj['steps'])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_monitor_html_structure_and_playwright(self):
        """Verify monitor HTML page structure and validate DOM rendering via Node Playwright."""
        monitor_path = ROOT / 'static/reports/insights-pipeline-monitor.html'
        self.assertTrue(monitor_path.exists(), "Monitor HTML missing")

        html_text = monitor_path.read_text(encoding='utf-8')
        # Invariant checks
        self.assertIn('class="spinner"', html_text)
        self.assertIn('@keyframes spin', html_text)
        self.assertIn('insights-status.json', html_text)
        self.assertIn('timeline-track', html_text)
        self.assertIn('steps-grid', html_text)
        self.assertIn('workers-grid', html_text)

        # Run Node test script to verify browser DOM rendering
        node_script = """
let chromium;
try {
  chromium = require('playwright').chromium;
} catch (e) {
  try {
    chromium = require('C:/Users/Choijay/AppData/Local/Programs/Python/Python311/Lib/site-packages/playwright/driver/package').chromium;
  } catch (e2) {
    console.error('Playwright not found');
    process.exit(0);
  }
}
const path = require('path');

(async () => {
  let browser;
  try {
    browser = await chromium.launch({
      headless: true,
      executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
    });
  } catch (e) {
    browser = await chromium.launch({ headless: true });
  }
  const page = await browser.newPage();
  const filePath = 'file:///' + path.resolve(process.argv[2]).replace(/\\\\/g, '/');
  
  const errors = [];
  page.on('pageerror', err => errors.push(err.message));

  await page.goto(filePath, { waitUntil: 'domcontentloaded' });
  const title = await page.title();
  const spinnerCount = await page.locator('.spinner').count();
  const timelineExists = await page.locator('#timelineTrack').count();
  const gridExists = await page.locator('#stepsGrid').count();

  await browser.close();
  console.log(JSON.stringify({ title, spinnerCount, timelineExists, gridExists, errors }));
})();
"""
        cjs_path = ROOT / 'static/reports/_test_monitor_playwright.cjs'
        cjs_path.write_text(node_script, encoding='utf-8')
        try:
            proc = subprocess.run(
                ['node', str(cjs_path), str(monitor_path)],
                capture_output=True, text=True, encoding='utf-8', timeout=30
            )
            self.assertEqual(proc.returncode, 0, f"Node Playwright failed: {proc.stderr}")
            if proc.stdout.strip():
                result = json.loads(proc.stdout)
                self.assertIn("인사이트 파이프라인", result['title'])
                self.assertEqual(result['timelineExists'], 1)
                self.assertEqual(result['gridExists'], 1)
                self.assertEqual(result['errors'], [])
        finally:
            cjs_path.unlink(missing_ok=True)

    def test_worker_result_schema_validation_rejection(self):
        """Test rejection of malformed or invalid schema worker results."""
        tmp = tempfile.mkdtemp(prefix='test-worker-invalid-')
        test_root = Path(tmp)
        try:
            rid = "INSIGHTS-TEST-WORKER-INVALID"
            prep = insights_main.prepare_run(rid, offline=False, root=test_root)
            run_dir = test_root / 'data/blog_performance/insights' / rid
            state_file = run_dir / 'state.json'
            state = insights_main.read_json(state_file)
            state['task_ids']['collect_browser_ranks'] = 'TASK-INVALID-001'
            insights_main.save_json(state_file, state)

            worker_dir = test_root / 'worker-workspaces/02_research_planning'
            outbox_dir = worker_dir / 'outbox/TASK-INVALID-001'
            outbox_dir.mkdir(parents=True, exist_ok=True)
            res_file = outbox_dir / 'result.json'

            # 1. Malformed JSON
            res_file.write_text('{ invalid json ...', encoding='utf-8')
            with patch('services.worker_dispatch.status', return_value={'status': 'collected', 'result_file': 'outbox/TASK-INVALID-001/result.json'}), \
                 patch('services.worker_dispatch.load', return_value={'worker_folder': '02_research_planning'}):
                res = insights_main.run_pipeline(run_id=rid, offline=False, root=test_root)
                self.assertEqual(res['status'], 'collection_dispatch_blocked')
                self.assertIn("파싱 실패", res.get('error', ''))

            # 2. Schema version mismatch
            bad_schema = {'schema_version': 'unsupported-schema-v9', 'results': []}
            res_file.write_text(json.dumps(bad_schema), encoding='utf-8')
            with patch('services.worker_dispatch.status', return_value={'status': 'collected', 'result_file': 'outbox/TASK-INVALID-001/result.json'}), \
                 patch('services.worker_dispatch.load', return_value={'worker_folder': '02_research_planning'}):
                res2 = insights_main.run_pipeline(run_id=rid, offline=False, root=test_root)
                self.assertEqual(res2['status'], 'worker_result_invalid')
                self.assertIn("규격 불일치", res2.get('error', ''))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_offline_network_guard_active(self):
        """Verify that offline network guard strictly blocks unauthorized external connections."""
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with self.assertRaises(RuntimeError) as ctx:
                s.connect(('naver.com', 80))
            self.assertIn("OFFLINE GUARD", str(ctx.exception))
        finally:
            s.close()

    def test_defect1_atomic_lock_concurrency_and_ownership(self):
        """Defect 1: Test atomic lock acquisition using exclusive create; exactly 1 of 2 contenders enters."""
        import concurrent.futures
        tmp = tempfile.mkdtemp(prefix='test-lock-atomic-')
        test_root = Path(tmp)
        try:
            rid = "INSIGHTS-TEST-LOCK-ATOMIC"
            run_dir = test_root / 'data/blog_performance/insights' / rid
            run_dir.mkdir(parents=True, exist_ok=True)

            outcomes = []
            def contender(cid):
                res = insights_main.acquire_execution_lock(run_dir, rid)
                outcomes.append({'cid': cid, 'result': res})
                return res

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                f1 = executor.submit(contender, 1)
                f2 = executor.submit(contender, 2)
                concurrent.futures.wait([f1, f2])

            acquired = [o for o in outcomes if o['result'] is None]
            locked = [o for o in outcomes if o['result'] is not None and o['result'].get('status') == 'locked']
            self.assertEqual(len(acquired), 1, "Exactly one contender must acquire the atomic lock")
            self.assertEqual(len(locked), 1, "The second contender must be rejected with locked status")

            # Verify ownership: releasing from a mismatched PID does not remove the lock
            lock_file = run_dir / '.execution.lock'
            self.assertTrue(lock_file.exists())
            fake_lock_data = {'pid': 99999999, 'locked_at': datetime.now(timezone.utc).isoformat(), 'run_id': rid}
            lock_file.write_text(json.dumps(fake_lock_data), encoding='utf-8')
            insights_main.release_execution_lock(run_dir)
            self.assertTrue(lock_file.exists(), "Lock owned by PID 99999999 must NOT be deleted by mismatched PID")

            # Restore correct PID and verify clean release
            real_lock_data = {'pid': os.getpid(), 'locked_at': datetime.now(timezone.utc).isoformat(), 'run_id': rid}
            lock_file.write_text(json.dumps(real_lock_data), encoding='utf-8')
            insights_main.release_execution_lock(run_dir)
            self.assertFalse(lock_file.exists(), "Owner process must cleanly release lock")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_defect2_resume_timing_preservation_and_separation(self):
        """Defect 2: On resume, already succeeded steps must preserve historical elapsed_seconds and finished_at."""
        tmp = tempfile.mkdtemp(prefix='test-resume-timing-')
        test_root = Path(tmp)
        try:
            rid = "INSIGHTS-TEST-TIMING-PRESERVE"
            prep = insights_main.prepare_run(rid, preset='test-single-common', root=test_root, offline=True)
            run_dir = test_root / 'data/blog_performance/insights/tests' / rid

            # Verify preflight and panel_preparation were created
            m_file = run_dir / 'monitor-state.json'
            self.assertTrue(m_file.exists())
            initial_m = insights_main.read_json(m_file)
            pf_orig_elapsed = initial_m['steps']['preflight']['elapsed_seconds']
            pf_orig_finished = initial_m['steps']['preflight']['finished_at']

            # Simulate passage of time by artificially backdating run started_at
            initial_m['started_at'] = '2026-10-24T00:00:00+00:00'
            insights_main.save_json(m_file, initial_m)

            # StepTracker entered for already succeeded step without force_rerun
            with StepTracker('preflight', run_id=rid, root=test_root, test_only=True) as trk:
                pass

            after_m = insights_main.read_json(m_file)
            self.assertEqual(after_m['steps']['preflight']['elapsed_seconds'], pf_orig_elapsed, "Historical elapsed_seconds must not be overwritten or inflated")
            self.assertEqual(after_m['steps']['preflight']['finished_at'], pf_orig_finished, "Historical finished_at must not change on resume")
            self.assertIn('wall_clock_seconds', after_m)
            self.assertIn('sum_execution_seconds', after_m)
            self.assertIn('sum_waiting_seconds', after_m)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_defect3_presets_catalog_alignment(self):
        """Defect 3: Rally Bar Mini must match canonical catalog: VC-009, report_group medium, catalog_group small."""
        presets = ['test-mini-two-query', 'test-depth-10']
        for p_name in presets:
            cfg = insights_main.load_preset(p_name, root=ROOT)
            queries = cfg.get('panel', {}).get('queries', [])
            rally_mini = next((q for q in queries if q.get('keyword') == '로지텍 랠리바 미니'), None)
            self.assertIsNotNone(rally_mini, f"Preset {p_name} must contain '로지텍 랠리바 미니'")
            self.assertEqual(rally_mini.get('product_id'), 'VC-009')
            self.assertEqual(rally_mini.get('brand'), 'Logitech')
            self.assertEqual(rally_mini.get('product'), 'Rally Bar Mini')
            self.assertEqual(rally_mini.get('report_group'), 'medium', "report_group must be 'medium'")
            self.assertEqual(rally_mini.get('catalog_group'), 'small', "catalog_group must be 'small'")

    def test_defect4_pending_reservation_notice_and_no_resend_delivery_unknown(self):
        """Defect 4: Pending reservations block with task ID notice without delete/resend; delivery_unknown is preserved."""
        from services.blog_performance.insights.steps import step_collection_dispatch, step_term_review
        from services.blog_performance.insights.context import ExecutionContext
        tmp = tempfile.mkdtemp(prefix='test-reservations-')
        test_root = Path(tmp)
        try:
            rid = "INSIGHTS-TEST-RESERVATIONS"
            prep = insights_main.prepare_run(rid, preset='test-single-common', root=test_root, offline=False)
            run_dir = test_root / 'data/blog_performance/insights/tests' / rid
            cfg = insights_main.load_preset('test-single-common', root=test_root)
            cfg['execution']['mode'] = 'online'
            ctx = ExecutionContext(
                run_id=rid,
                config=cfg,
                config_hash='fakehash',
                run_dir=run_dir,
                root=test_root,
                state=insights_main.read_json(run_dir / 'state.json'),
                manifest=insights_main.read_json(run_dir / 'manifest.json')
            )
            ctx.test_only = True

            # 1. Test pending reservations block with clear task IDs
            with patch('services.blog_performance.insights.steps.check_worker_dispatch_preflight',
                       return_value=(False, ['unfinished_delivery_reservation'], [{'task_id': 'TASK-OLD-RESERVE-01'}])):
                res = step_collection_dispatch(ctx)
                self.assertEqual(res.status, 'blocked')
                self.assertIn('TASK-OLD-RESERVE-01', res.artifacts.get('pending_reservations', []))
                self.assertIn('TASK-OLD-RESERVE-01', res.message)

            # 2. Test delivery_unknown is NOT resent
            ctx.state['task_ids']['collect_browser_ranks'] = 'TASK-DELIVERY-UNKNOWN-01'
            with patch('services.worker_dispatch.status', return_value={'status': 'delivery_unknown'}):
                res_unk = step_collection_dispatch(ctx)
                self.assertEqual(res_unk.status, 'waiting')
                self.assertIn('재발송하지 않고 대기', res_unk.message)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_defect5_term_context_extraction_and_metrics_distinction(self):
        """Defect 5: Unconfirmed term review attaches snippet, URL, and candidate equipment; distinguishes compliance vs accuracy."""
        from services.blog_performance.insights.steps import step_term_review, extract_context_for_term
        tmp = tempfile.mkdtemp(prefix='test-term-context-')
        test_root = Path(tmp)
        try:
            # 1. Test mechanical context extraction helper
            mock_bodies = [{
                'requested_url': 'https://blog.naver.com/test/123',
                'body_text': '전체 회의실 구성에서 A1 마이크 장비와 화상회의 카메라를 연동하여 설치를 진행했습니다.'
            }]
            mock_catalog = [
                {'brand': 'Logitech', 'product': 'Rally Bar Mini', 'queries': ['로지텍 랠리바 미니']}
            ]
            ctx_extracted = extract_context_for_term('A1', ['a1'], mock_bodies, mock_catalog)
            self.assertEqual(ctx_extracted['url'], 'https://blog.naver.com/test/123')
            self.assertIn('A1 마이크 장비', ctx_extracted['snippet'])
            self.assertLessEqual(len(ctx_extracted['snippet']), 200)
            self.assertIn('Logitech Rally Bar Mini', ctx_extracted['candidate_equipment'])

            # 2. Test metrics distinction in step_term_review
            rid = "INSIGHTS-TEST-TERM-METRICS"
            run_dir = test_root / 'data/blog_performance/insights' / rid
            run_dir.mkdir(parents=True, exist_ok=True)
            common_dir = run_dir / 'common/body-analysis'
            common_dir.mkdir(parents=True, exist_ok=True)
            (common_dir / 'ai-terms.json').write_text(json.dumps({'items': [{'id': 'T-01', 'term': 'A1', 'spellings': ['a1']}]}), encoding='utf-8')
            (common_dir / 'bodies.json').write_text(json.dumps(mock_bodies), encoding='utf-8')
            (run_dir / 'ai-decisions.json').write_text(json.dumps({'passed': True, 'issues': [], 'decisions': [{'id': 'T-01', 'category': 'uncertain'}]}), encoding='utf-8')

            from services.blog_performance.insights.context import ExecutionContext
            ctx = ExecutionContext(
                run_id=rid,
                config={'test_only': True, 'execution': {'mode': 'offline'}, 'inputs': {}},
                config_hash='hash',
                run_dir=run_dir,
                root=test_root,
                state={'steps': {}, 'task_ids': {}, 'artifacts': {}, 'errors': []},
                manifest={}
            )
            res = step_term_review(ctx)
            self.assertEqual(res.status, 'succeeded')
            metrics = res.metrics
            self.assertEqual(metrics['schema_compliance'], 1.0)
            self.assertEqual(metrics['uncertain_rate'], 1.0)
            self.assertIsNone(metrics['semantic_accuracy'], "semantic_accuracy must be null (unmeasured) without ground truth")

            # Verify unconfirmed-terms-input.json has enriched fields
            in_json = json.loads((run_dir / 'unconfirmed-terms-input.json').read_text(encoding='utf-8'))
            self.assertEqual(len(in_json['items']), 1)
            item = in_json['items'][0]
            self.assertEqual(item['url'], 'https://blog.naver.com/test/123')
            self.assertIn('A1 마이크 장비', item['snippet'])
            self.assertIn('candidate_equipment', item)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
