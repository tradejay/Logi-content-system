from datetime import date
import unittest
import threading
import time
from unittest.mock import patch

import test_content_pipeline as fixtures
from services.content_pipeline import ContentPipeline, atomic
from services.pipeline_dispatcher import PipelineDispatcher


class DispatcherTests(unittest.TestCase):
    tearDown = fixtures.PipelineTests.tearDown
    run_pipeline = fixtures.PipelineTests.run_pipeline
    def setUp(self):
        fixtures.PipelineTests.setUp(self)
        atomic(self.root / 'content-system/registry/CONTENT_REGISTRY.csv',
               'content_id,status,title\nCNT-test,READY_FOR_WRITING,Test\n')
        atomic(self.root / 'content-system/03_sources/INDEX.yaml', {'sources': [{'id': 'S1', 'status': 'VALID',
            'path': 'docs/spec.md', 'last_verified': str(date.today()), 'freshness_limit_days': 90}]})
        self.dispatcher = PipelineDispatcher(self.root,
            factory=lambda root, progress=None: ContentPipeline(root, self.provider, progress=progress))

    def test_fresh_inspection_skips_review_pending(self):
        self.assertEqual(self.dispatcher.inspect()['items'][0]['action'], 'RUN')
        self.run_pipeline()
        item = self.dispatcher.inspect()['items'][0]
        self.assertEqual(item['action'], 'WAIT')
        self.assertEqual(item['stage'], 'human')

    def test_changed_draft_requires_work(self):
        self.run_pipeline()
        self.pipeline.save_edit('CNT-test', 'changed')
        self.assertEqual(self.dispatcher.inspect()['items'][0]['action'], 'RUN')

    def test_expired_source_blocks_execution(self):
        atomic(self.root / 'content-system/03_sources/INDEX.yaml', {'sources': [{'id': 'S1', 'status': 'VALID',
            'path': 'docs/spec.md', 'last_verified': '2000-01-01', 'freshness_limit_days': 90}]})
        item = self.dispatcher.inspect()['items'][0]
        self.assertEqual(item['action'], 'WAIT')
        self.assertEqual(item['stage'], 'evidence')

    def test_single_dispatch_lock_and_persisted_progress(self):
        with patch('services.pipeline_dispatcher.threading.Thread'):
            first, created = self.dispatcher.start()
            second, created_again = self.dispatcher.start()
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first['job_id'], second['job_id'])
        self.dispatcher._execute(first, None, self.dispatcher.directory / 'dispatch.lock')
        result = self.dispatcher.read_job()
        self.assertEqual(result['status'], 'FINISHED')
        self.assertIn('write', [e['stage'] for e in result['events']])
        self.assertEqual(result['items'][0]['outcome'], 'COMPLETED_REVIEW_PENDING')
        self.assertFalse((self.dispatcher.directory / 'dispatch.lock').exists())

    def test_api_returns_immediately_and_exposes_inflight_progress(self):
        from flask import Flask
        from services.content_ops_api import content_ops_bp
        app = Flask(__name__)
        app.register_blueprint(content_ops_bp)
        entered = threading.Event()
        release = threading.Event()
        original = self.provider.complete

        def slow_complete(stage, instruction, context):
            if stage == 'write':
                entered.set()
                if not release.wait(5):
                    raise RuntimeError('test release timeout')
            return original(stage, instruction, context)

        self.provider.complete = slow_complete
        with patch('services.pipeline_dispatcher.dispatcher', self.dispatcher):
            client = app.test_client()
            try:
                response = client.post('/api/content-system/pipeline/dispatch', json={})
                self.assertEqual(response.status_code, 202)
                self.assertTrue(entered.wait(5))
                status = client.get('/api/content-system/pipeline/operations').json
                self.assertEqual(status['job']['status'], 'RUNNING')
                self.assertEqual(status['job']['items'][0]['stage'], 'write')
                duplicate = client.post('/api/content-system/pipeline/dispatch', json={}).json
                self.assertFalse(duplicate['created'])
                self.assertEqual(duplicate['job']['job_id'], response.json['job']['job_id'])
            finally:
                release.set()
                deadline = time.monotonic() + 5
                while (self.dispatcher.directory / 'dispatch.lock').exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
            self.assertEqual(self.dispatcher.read_job()['status'], 'FINISHED')
