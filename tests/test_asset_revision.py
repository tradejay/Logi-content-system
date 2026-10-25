import hashlib
import tempfile
import unittest
import uuid
from unittest.mock import patch
from pathlib import Path
from services.ide_worker_bridge import save, load
from services.asset_revision import submit, snapshot, step, add_slot
from services.taiga_ticket_view import article_with_images


class AssetRevisionTests(unittest.TestCase):
    def test_add_slot_preserves_text_bindings_and_is_idempotent(self):
        view = snapshot('CNT-TEST', self.root)
        data = {**self.data, 'mode': 'add_slot', 'anchor': view['paragraphs'][0]['anchor'], 'feedback': '회의 장면 제작'}
        before = load(self.run / 'asset-bindings.json')['bindings'][0]
        job = add_slot('CNT-TEST', data, self.root)
        latest = load(self.work / 'pipeline-latest.json')
        text = Path(latest['draft_file']).read_text(encoding='utf-8')
        self.assertIn('{{asset:' + job['need_id'] + '}}', text)
        self.assertEqual(text.replace('\n\n{{asset:' + job['need_id'] + '}}', ''), '본문\n\n{{asset:N1}}')
        self.assertEqual(load(self.run / 'asset-bindings.json')['bindings'][0], before)
        self.assertFalse(latest['publish_ready'])
        self.assertEqual(latest['official_review']['status'], 'STALE')
        self.assertEqual(add_slot('CNT-TEST', data, self.root)['request_id'], job['request_id'])
        self.assertEqual(len(load(self.run / 'asset-bindings.json')['bindings']), 2)

    def test_add_slot_rejects_stale_or_invalid_anchor_without_change(self):
        old = load(self.work / 'pipeline-latest.json')
        for changes in [{'draft_sha256': 'wrong'}, {'anchor': '-1'}]:
            with self.assertRaises(ValueError):
                add_slot('CNT-TEST', {**self.data, 'anchor': '0', **changes}, self.root)
        self.assertEqual(load(self.work / 'pipeline-latest.json'), old)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / 'content-system/working/CNT-TEST'
        self.run = self.work / 'runs/r1'
        draft = self.run / 'revisions/r1.draft.md'
        draft.parent.mkdir(parents=True)
        draft.write_text('본문\n\n{{asset:N1}}', encoding='utf-8')
        self.digest = hashlib.sha256(draft.read_bytes()).hexdigest()
        save(self.work / 'pipeline-latest.json', {'run_id': 'r1', 'draft_file': str(draft), 'draft_sha256': self.digest})
        save(self.run / 'asset-bindings.json', {'bindings': [{'need': {'id': 'N1', 'purpose': '회의실'}, 'candidate': None}]})
        self.data = {'request_id': str(uuid.uuid4()), 'run_id': 'r1', 'draft_sha256': self.digest, 'need_id': 'N1', 'feedback': '참석자 4명으로 변경'}

    def test_request_is_queued_and_retry_is_idempotent(self):
        first = submit('CNT-TEST', self.data, self.root)
        second = submit('CNT-TEST', self.data, self.root)
        self.assertEqual(first, second)
        self.assertEqual(first['status'], 'queued')
        self.assertIsNone(load(self.run / 'asset-bindings.json')['bindings'][0]['candidate'])

    def test_stale_or_foreign_slot_cannot_be_dispatched(self):
        for changed in [{'draft_sha256': 'old'}, {'need_id': 'other'}]:
            with self.assertRaises(ValueError):
                submit('CNT-TEST', {**self.data, **changed}, self.root)

    def test_second_active_request_for_same_slot_is_rejected(self):
        submit('CNT-TEST', self.data, self.root)
        with self.assertRaises(ValueError):
            submit('CNT-TEST', {**self.data, 'request_id': str(uuid.uuid4())}, self.root)

    def test_existing_and_missing_images_have_request_links(self):
        rendered = article_with_images('{{asset:N1}}', [{'need': {'id': 'N1'}, 'candidate': None}], 'http://127.0.0.1:5014/article-console.html?content=CNT-TEST')
        self.assertIn('asset-revision.html?content=CNT-TEST&need=N1', rendered)

    def test_completed_image_only_replaces_requested_slot_and_keeps_history(self):
        from PIL import Image
        job = submit('CNT-TEST', self.data, self.root)
        job.update(status='running', task={'task_id': 'T1'})
        job_path = self.root / 'worker-control/asset-revisions' / job['request_id'] / 'job.json'
        save(job_path, job)
        old = {'asset_id': 'OLD', 'url': 'https://example.com/old.png'}
        other = {'need': {'id': 'N2'}, 'candidate': {'asset_id': 'KEEP'}, 'status': 'approved'}
        save(self.run / 'asset-bindings.json', {'bindings': [{'need': {'id': 'N1'}, 'candidate': old}, other]})
        worker = self.root / 'worker-workspaces/05_assets'
        image = worker / 'work/T1/image.png'
        image.parent.mkdir(parents=True)
        Image.new('RGB', (8, 8)).save(image)
        save(worker / 'inbox/T1/task.json', {'ai_output': 'work/T1/result.json'})
        save(worker / 'work/T1/result.json', {'candidates': [{'need_id': 'N1', 'path': 'work/T1/image.png', 'caption': '새 이미지'}]})
        before = (self.run / 'revisions/r1.draft.md').read_bytes()
        with patch('services.asset_revision.status', return_value={'status': 'collected'}):
            step(self.root)
        self.assertEqual(load(job_path)['status'], 'completed')
        bindings = load(self.run / 'asset-bindings.json')['bindings']
        self.assertEqual(bindings[0]['status'], 'pending_review')
        self.assertEqual(bindings[1], other)
        self.assertEqual(load(job_path.parent / 'previous-binding.json')['candidate'], old)
        self.assertEqual((self.run / 'revisions/r1.draft.md').read_bytes(), before)

    def test_failed_quota_request_accepts_changed_result_without_new_ai_call(self):
        from PIL import Image
        from services.ide_worker_bridge import verify_report
        job = submit('CNT-TEST', self.data, self.root)
        job.update(status='failed', error='quota exceeded', task={'task_id': 'T2', 'created_at': '2026-10-16T01:00:00Z'})
        job_path = self.root / 'worker-control/asset-revisions' / job['request_id'] / 'job.json'
        save(job_path, job)
        worker = self.root / 'worker-workspaces/05_assets'
        image = worker / 'work/T2/image.png'
        image.parent.mkdir(parents=True)
        Image.new('RGB', (8, 8)).save(image)
        task = {'task_id': 'T2', 'worker_id': 'W', 'stage': 'asset_fulfillment', 'execution_type': 'ide',
                'ai_output': 'work/T2/result.json', 'required_outputs': ['work/T2/result.json'], 'input_manifest': 'inbox/T2/input-manifest.json'}
        task_path = worker / 'inbox/T2/task.json'
        save(task_path, task)
        save(worker / task['input_manifest'], {'files': []})
        result_path = worker / task['ai_output']
        save(result_path, {'candidates': [], 'unresolved_items': ['quota']})
        old = {'task_id': 'T2', 'worker_id': 'W', 'stage': 'asset_fulfillment', 'execution_type': 'ide', 'status': 'completed',
               'publication_approved': False, 'input_sha256': hashlib.sha256(task_path.read_bytes()).hexdigest(),
               'artifacts': [{'path': task['ai_output'], 'sha256': hashlib.sha256(result_path.read_bytes()).hexdigest(), 'bytes': result_path.stat().st_size}]}
        save(worker / 'outbox/T2/report.json', old)
        save(result_path, {'candidates': [{'need_id': 'N1', 'path': 'work/T2/image.png', 'caption': '재작업'}]})
        with patch('services.asset_revision.status', return_value={'status': 'collected'}), patch('services.asset_revision.enqueue') as enqueue:
            step(self.root)
            enqueue.assert_not_called()
        self.assertEqual(load(job_path)['status'], 'completed')
        self.assertEqual(load(worker / 'outbox/T2/report.json'), old)
        self.assertEqual(verify_report(worker, 'T2', task)['resubmission_of'], old['artifacts'][0]['sha256'])

    def test_watch_cycle_detects_image_only_change_and_retries_remote_sync(self):
        from PIL import Image
        from scripts.watch_asset_revisions import cycle
        job = submit('CNT-TEST', self.data, self.root)
        job.update(status='running', task={'task_id': 'T3', 'created_at': '2026-10-16T01:00:00Z'})
        job_path = self.root / 'worker-control/asset-revisions' / job['request_id'] / 'job.json'
        save(job_path, job)
        worker = self.root / 'worker-workspaces/05_assets'
        image = worker / 'work/T3/image.png'
        image.parent.mkdir(parents=True)
        Image.new('RGB', (8, 8), 'red').save(image)
        task = {'task_id': 'T3', 'worker_id': 'W', 'stage': 'asset_fulfillment', 'execution_type': 'ide',
                'ai_output': 'work/T3/result.json', 'required_outputs': ['work/T3/result.json'], 'input_manifest': 'inbox/T3/input-manifest.json'}
        task_path = worker / 'inbox/T3/task.json'
        save(task_path, task)
        save(worker / task['input_manifest'], {'files': []})
        result_path = worker / task['ai_output']
        save(result_path, {'candidates': [{'need_id': 'N1', 'path': 'work/T3/image.png', 'caption': '도식'}]})
        original_json = result_path.read_bytes()
        report = {'task_id': 'T3', 'worker_id': 'W', 'stage': 'asset_fulfillment', 'execution_type': 'ide', 'status': 'completed',
                  'publication_approved': False, 'input_sha256': hashlib.sha256(task_path.read_bytes()).hexdigest(),
                  'artifacts': [{'path': task['ai_output'], 'sha256': hashlib.sha256(original_json).hexdigest(), 'bytes': len(original_json)}]}
        save(worker / 'outbox/T3/report.json', report)
        with patch('services.asset_revision.status', return_value={'status': 'collected'}), patch('services.asset_revision.enqueue') as enqueue:
            cycle(self.root, synchronize=lambda: (_ for _ in ()).throw(RuntimeError('Taiga offline')))
            first = load(job_path)
            self.assertEqual(first['phase'], 'taiga_sync_pending')
            self.assertFalse(first['taiga_synced'])
            first_asset = load(self.run / 'asset-bindings.json')['bindings'][0]['candidate']
            preserved = self.root / first_asset['local_path']
            original_image = preserved.read_bytes()
            Image.new('RGB', (8, 8), 'blue').save(image)
            cycle(self.root, synchronize=lambda: None)
            enqueue.assert_not_called()
        final = load(job_path)
        self.assertEqual(final['phase'], 'synced')
        self.assertTrue(final['taiga_synced'])
        self.assertNotEqual(first['asset_id'], final['asset_id'])
        self.assertEqual(preserved.read_bytes(), original_image)
        self.assertEqual(result_path.read_bytes(), original_json)
        self.assertTrue(load(self.root / 'worker-control/asset-revisions/health.json')['heartbeat'])

    def test_snapshot_restores_latest_request_for_the_input_screen(self):
        job = submit('CNT-TEST', self.data, self.root)
        self.assertEqual(snapshot('CNT-TEST', self.root)['images'][0]['last_request']['request_id'], job['request_id'])


if __name__ == '__main__':
    unittest.main()
