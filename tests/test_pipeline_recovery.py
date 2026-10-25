import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.recover_pipeline import inspect_recovery_target, recover_target
from services.content_pipeline import atomic


class TestPipelineRecovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cid = 'CNT-TEST-REC'
        self.work_dir = self.root / f'content-system/working/{self.cid}'
        self.work_dir.mkdir(parents=True, exist_ok=True)
        (self.work_dir / 'runs/run-test').mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_dry_run_identifies_interrupted_run(self):
        # 1. 죽은 프로세스(존재하지 않는 큰 PID)의 잠금 생성
        lock_file = self.work_dir / 'pipeline.lock'
        lock_payload = {
            'content_id': self.cid,
            'run_id': 'run-test',
            'pid': 9999999,
            'process_create_time': 1000.0,
            'status': 'RUNNING',
            'stage': 'write'
        }
        lock_file.write_text(json.dumps(lock_payload), encoding='utf-8')

        latest_path = self.work_dir / 'pipeline-latest.json'
        latest_path.write_text(json.dumps({'run_id': 'run-test', 'outcome': 'RUNNING'}), encoding='utf-8')

        # 검사
        info = inspect_recovery_target(self.root, self.cid)
        self.assertTrue(info['eligible'])
        self.assertEqual(info['status'], 'INTERRUPTED_DEAD_PROCESS')
        self.assertEqual(info['liveness'], 'DEAD')
        # 파일이 변경되지 않았는지 확인 (dry-run)
        self.assertTrue(lock_file.is_file())
        latest_after = json.loads(latest_path.read_text(encoding='utf-8'))
        self.assertEqual(latest_after['outcome'], 'RUNNING')

    def test_apply_recovers_interrupted_run(self):
        lock_file = self.work_dir / 'pipeline.lock'
        lock_payload = {
            'content_id': self.cid,
            'run_id': 'run-test',
            'pid': 9999999,
            'process_create_time': 1000.0,
            'status': 'RUNNING',
            'stage': 'write'
        }
        lock_file.write_text(json.dumps(lock_payload), encoding='utf-8')

        latest_path = self.work_dir / 'pipeline-latest.json'
        latest_path.write_text(json.dumps({'run_id': 'run-test', 'outcome': 'RUNNING'}), encoding='utf-8')

        run_res_path = self.work_dir / 'runs/run-test/run-result.json'
        run_res_path.write_text(json.dumps({'run_id': 'run-test', 'outcome': 'RUNNING'}), encoding='utf-8')

        info = inspect_recovery_target(self.root, self.cid)
        res = recover_target(self.root, info, reason="테스트 복구")

        self.assertTrue(res['recovered'])
        self.assertFalse(lock_file.is_file())  # 잠금 해제됨

        latest_after = json.loads(latest_path.read_text(encoding='utf-8'))
        self.assertEqual(latest_after['outcome'], 'FAILED')
        self.assertEqual(latest_after['stage'], 'finished')
        self.assertFalse(latest_after['publish_ready'])
        self.assertIn('테스트 복구', latest_after['error'])

        run_res_after = json.loads(run_res_path.read_text(encoding='utf-8'))
        self.assertEqual(run_res_after['outcome'], 'FAILED')
        self.assertEqual(run_res_after['stage'], 'finished')

    def test_active_running_process_protected(self):
        import psutil
        cur_proc = psutil.Process()
        lock_file = self.work_dir / 'pipeline.lock'
        lock_payload = {
            'content_id': self.cid,
            'run_id': 'run-active',
            'pid': os.getpid(),
            'process_create_time': cur_proc.create_time(),
            'status': 'RUNNING',
            'stage': 'feedback'
        }
        lock_file.write_text(json.dumps(lock_payload), encoding='utf-8')

        info = inspect_recovery_target(self.root, self.cid)
        self.assertFalse(info['eligible'])
        self.assertEqual(info['status'], 'ACTIVE_RUNNING')
        self.assertEqual(info['liveness'], 'ALIVE')

        # apply를 강제 시도해도 RuntimeError로 보호됨
        with self.assertRaises(RuntimeError):
            recover_target(self.root, info)

        self.assertTrue(lock_file.is_file())

    def test_recovery_aborts_if_new_run_started_race_condition(self):
        # 1. 이전 중단된 실행 검사
        lock_file = self.work_dir / 'pipeline.lock'
        lock_payload = {
            'content_id': self.cid,
            'run_id': 'run-old',
            'pid': 9999999,
            'process_create_time': 1000.0,
            'status': 'RUNNING',
            'stage': 'write'
        }
        lock_file.write_text(json.dumps(lock_payload), encoding='utf-8')
        latest_path = self.work_dir / 'pipeline-latest.json'
        latest_path.write_text(json.dumps({'run_id': 'run-old', 'outcome': 'RUNNING'}), encoding='utf-8')

        info = inspect_recovery_target(self.root, self.cid)
        self.assertTrue(info['eligible'])
        self.assertEqual(info['latest_run_id'], 'run-old')

        # 2. 복구 실행 직전에 새 실행(run-new)이 시작되어 latest 및 lock이 갱신된 상황 재현
        new_lock = {
            'content_id': self.cid,
            'run_id': 'run-new',
            'pid': os.getpid(),
            'process_create_time': 12345.0,
            'status': 'RUNNING',
            'stage': 'write'
        }
        lock_file.write_text(json.dumps(new_lock), encoding='utf-8')
        latest_path.write_text(json.dumps({'run_id': 'run-new', 'outcome': 'RUNNING'}), encoding='utf-8')

        # 3. recover_target 실행 시 run_id 변경을 감지하고 에러를 발생시켜 새 실행을 보호해야 함
        with self.assertRaises(RuntimeError) as ctx:
            recover_target(self.root, info)
        self.assertIn('새로운 run(run-new)이 감지되었습니다', str(ctx.exception))

        # 4. 새 실행의 latest가 훼손되지 않고 RUNNING으로 유지되어야 함
        latest_after = json.loads(latest_path.read_text(encoding='utf-8'))
        self.assertEqual(latest_after['run_id'], 'run-new')
        self.assertEqual(latest_after['outcome'], 'RUNNING')

    def test_unknown_process_liveness_blocked_unless_force(self):
        # UNKNOWN 상태의 잠금 생성
        lock_file = self.work_dir / 'pipeline.lock'
        lock_payload = {
            'content_id': self.cid,
            'run_id': 'run-unknown',
            'pid': 88888,
            'process_create_time': 1000.0,
            'status': 'RUNNING',
            'stage': 'write'
        }
        lock_file.write_text(json.dumps(lock_payload), encoding='utf-8')
        latest_path = self.work_dir / 'pipeline-latest.json'
        latest_path.write_text(json.dumps({'run_id': 'run-unknown', 'outcome': 'RUNNING'}), encoding='utf-8')

        with patch('scripts.recover_pipeline.check_process_liveness', return_value='UNKNOWN'):
            info = inspect_recovery_target(self.root, self.cid)
            self.assertEqual(info['liveness'], 'UNKNOWN')

            # 1. 기본(allow_unknown=False) 상태에서 복구 시도 시 RuntimeError 발생
            with self.assertRaises(RuntimeError) as ctx:
                recover_target(self.root, info, allow_unknown=False)
            self.assertIn('UNKNOWN', str(ctx.exception))
            self.assertTrue(lock_file.is_file())
            self.assertEqual(json.loads(latest_path.read_text(encoding='utf-8'))['outcome'], 'RUNNING')

            # 2. allow_unknown=True (--force 옵션) 지정 시에는 복구 성공
            res = recover_target(self.root, info, allow_unknown=True)
            self.assertTrue(res['recovered'])
            self.assertFalse(lock_file.is_file())
            self.assertEqual(json.loads(latest_path.read_text(encoding='utf-8'))['outcome'], 'FAILED')

    def test_recovery_exclusive_lock_blocks_concurrent_access(self):
        from scripts.recover_pipeline import recovery_exclusive_lock
        from services.pipeline_status import read_pipeline_lock, check_process_liveness
        # recovery_exclusive_lock 점유 중 lock 파일이 활성 상태(RECOVERING, ALIVE)로 유지되는지 확인
        with recovery_exclusive_lock(self.root, self.cid, expected_run_id='run-test'):
            cur_lock = read_pipeline_lock(self.root, self.cid)
            self.assertIsNotNone(cur_lock)
            self.assertEqual(cur_lock.get('status'), 'RECOVERING')
            self.assertEqual(check_process_liveness(cur_lock), 'ALIVE')

    def test_recovery_aborts_if_run_id_changes_just_before_save(self):
        # 1. 이전 중단된 실행 검사
        lock_file = self.work_dir / 'pipeline.lock'
        lock_payload = {
            'content_id': self.cid,
            'run_id': 'run-old',
            'pid': 9999999,
            'process_create_time': 1000.0,
            'status': 'RUNNING',
            'stage': 'write'
        }
        lock_file.write_text(json.dumps(lock_payload), encoding='utf-8')
        latest_path = self.work_dir / 'pipeline-latest.json'
        latest_path.write_text(json.dumps({'run_id': 'run-old', 'outcome': 'RUNNING'}), encoding='utf-8')

        info = inspect_recovery_target(self.root, self.cid)

        # 2. 복구 진행 중 저장 직전에 latest 파일의 run_id가 바뀐 상황 시뮬레이션
        import scripts.recover_pipeline
        orig_read_json = scripts.recover_pipeline.read_json_file
        call_count = [0]
        def simulated_read_json(path):
            call_count[0] += 1
            # 1회차: 초기 확인 -> run-old
            # 2회차 이후: 저장 직전 재확인 -> run-new로 변경됨
            if 'pipeline-latest.json' in str(path) and call_count[0] >= 2:
                return {'run_id': 'run-new', 'outcome': 'RUNNING'}
            return orig_read_json(path)

        with patch('scripts.recover_pipeline.read_json_file', side_effect=simulated_read_json):
            with self.assertRaises(RuntimeError) as ctx:
                recover_target(self.root, info)
            self.assertIn('새로운 run(run-new)이 감지되었습니다', str(ctx.exception))

        # 3. 새 실행이 덮어써지지 않았는지 확인
        latest_after = json.loads(latest_path.read_text(encoding='utf-8'))
        self.assertEqual(latest_after['outcome'], 'RUNNING')

    def test_cross_process_concurrent_acquisition_protection(self):
        import multiprocessing
        import time

        latest_path = self.work_dir / 'pipeline-latest.json'
        latest_path.write_text(json.dumps({'run_id': 'run-test', 'outcome': 'RUNNING'}), encoding='utf-8')

        # 1. 프로세스 1(실행)이 잠금을 쥔 상태에서 프로세스 2(복구)가 진입 시 차단되는지 검증
        q1 = multiprocessing.Queue()
        q2 = multiprocessing.Queue()
        p1 = multiprocessing.Process(target=_mp_worker_pipeline_run, args=(str(self.root), self.cid, q1))
        p2 = multiprocessing.Process(target=_mp_worker_recovery_lock, args=(str(self.root), self.cid, 'run-test', q2))

        p1.start()
        time.sleep(0.15)
        p2.start()

        r1 = q1.get(timeout=5)
        r2 = q2.get(timeout=5)
        p1.join()
        p2.join()

        self.assertEqual(r1[0], 'success')
        self.assertEqual(r2[0], 'error')
        self.assertIn('실행 중', r2[1])

        # 2. 고아 잠금 상태에서 프로세스 2(복구)가 먼저 점유했을 때 프로세스 1(실행)이 Pipeline busy로 차단되는지 검증
        lock_file = self.work_dir / 'pipeline.lock'
        dead_lock = {
            'content_id': self.cid,
            'run_id': 'run-test',
            'pid': 9999999,
            'process_create_time': 1000.0,
            'status': 'RUNNING',
            'stage': 'write'
        }
        lock_file.write_text(json.dumps(dead_lock), encoding='utf-8')

        q3 = multiprocessing.Queue()
        q4 = multiprocessing.Queue()
        p_rec = multiprocessing.Process(target=_mp_worker_recovery_lock, args=(str(self.root), self.cid, 'run-test', q3))
        p_run = multiprocessing.Process(target=_mp_worker_pipeline_run, args=(str(self.root), self.cid, q4))

        p_rec.start()
        time.sleep(0.15)
        p_run.start()

        r3 = q3.get(timeout=5)
        r4 = q4.get(timeout=5)
        p_rec.join()
        p_run.join()

        self.assertEqual(r3[0], 'recovered')
        self.assertEqual(r4[0], 'error')
        self.assertIn('Pipeline busy', r4[1])

    def test_lock_release_owner_token_protection(self):
        from services.pipeline_status import cross_process_gate, read_pipeline_lock
        lock_file = self.work_dir / 'pipeline.lock'
        token_a = 'token-process-a'
        token_b = 'token-process-b'

        foreign_lock = {
            'content_id': self.cid,
            'run_id': 'run-foreign',
            'lock_token': token_b,
            'pid': os.getpid(),
            'status': 'RUNNING'
        }
        lock_file.write_text(json.dumps(foreign_lock), encoding='utf-8')

        # Process A가 token_a로 해제를 시도할 때 token이 불일치하므로 삭제되지 않아야 함
        with cross_process_gate(self.root, self.cid):
            current = read_pipeline_lock(self.root, self.cid)
            if current and current.get('lock_token') == token_a:
                lock_file.unlink(missing_ok=True)

        self.assertTrue(lock_file.is_file())
        cur_after = read_pipeline_lock(self.root, self.cid)
        self.assertEqual(cur_after.get('lock_token'), token_b)


def _mp_worker_pipeline_run(root_str, cid, q):
    import time
    from services.content_pipeline import ContentPipeline
    cp = ContentPipeline(Path(root_str))
    try:
        with cp.lock(cid):
            q.put(('success', os.getpid()))
            time.sleep(0.4)
    except Exception as e:
        q.put(('error', str(e)))


def _mp_worker_recovery_lock(root_str, cid, expected_run_id, q):
    import time
    from scripts.recover_pipeline import recovery_exclusive_lock
    try:
        with recovery_exclusive_lock(Path(root_str), cid, expected_run_id=expected_run_id):
            q.put(('recovered', os.getpid()))
            time.sleep(0.4)
    except Exception as e:
        q.put(('error', str(e)))


if __name__ == '__main__':
    unittest.main()



