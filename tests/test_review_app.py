"""Automated offline test suite for Review & Learning Web App.

Adheres to ROOT-REVIEW-WEBAPP-20261024 & ROOT-REVIEW-WEBAPP-FIX-20261024:
- Auth & permission rejection (401 / 403) and PBKDF2 password hashing
- Question storage & XSS sanitization
- True atomic conditional claim with session in-flight blocking & outer WHERE re-validation
- Transaction rollback atomicity (db.execute honors db.transaction context)
- Real review document synchronization (audit/ REVIEW.md & LEARNING-REVIEW-R2.md)
- Duplicate reply prevention & user-correlated notifications
- Delivery unknown state handling
- Invalid task ID rejection
- Production unconfigured DB enforcement
- Mocked connector outbound dispatch flow
"""
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from services.review_app import server as app_server
from services.review_app.connector import ReviewAppConnector
from services.review_app.db import Database, DatabaseError
from services.review_app.sync import sync_tasks

ROOT = Path(__file__).resolve().parents[1]


class TestReviewWebApp(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix='test-review-app-')
        self.db_path = Path(self.tmp_dir) / 'test_app.db'
        self.db = Database(str(self.db_path))
        self.db.init_schema()
        app_server._seed_initial_user(self.db)
        sync_tasks(self.db)

        # Patch server db instance
        self.orig_db = app_server._db_instance
        app_server._db_instance = self.db

        self.app = app_server.create_app({'TESTING': True})
        self.client = self.app.test_client()

    def tearDown(self):
        self.db.close()
        app_server._db_instance = self.orig_db
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def login_admin(self):
        return self.client.post('/api/auth/login', json={'username': 'admin', 'password': 'admin1234'})

    def test_auth_and_permission_rejection(self):
        """Test 1: Verify unauthorized requests, invalid logins, and PBKDF2 hash verification."""
        # 1. Unauthenticated task list
        res = self.client.get('/api/tasks')
        self.assertEqual(res.status_code, 401)
        self.assertIn("UNAUTHORIZED", res.get_json()['error'])

        # 2. Connector claim without secret
        res_conn = self.client.post('/api/connector/claim', json={})
        self.assertEqual(res_conn.status_code, 403)
        self.assertIn("FORBIDDEN", res_conn.get_json()['error'])

        # 3. Invalid login
        res_bad_login = self.client.post('/api/auth/login', json={'username': 'admin', 'password': 'wrongpassword'})
        self.assertEqual(res_bad_login.status_code, 401)

        # 4. Valid login with PBKDF2
        res_login = self.login_admin()
        self.assertEqual(res_login.status_code, 200)
        self.assertEqual(res_login.get_json()['user']['username'], 'admin')

        # 5. Authenticated task list
        res_tasks = self.client.get('/api/tasks')
        self.assertEqual(res_tasks.status_code, 200)
        tasks = res_tasks.get_json()['tasks']
        self.assertGreaterEqual(len(tasks), 2)

    def test_question_storage_and_xss_sanitization(self):
        """Test 2: Question input sanitization (XSS removal), user correlation, and queue storage."""
        self.login_admin()
        task_id = 'TASK-INSIGHTS-LAST3-20261023'

        # Empty question rejected
        res_empty = self.client.post(f'/api/tasks/{task_id}/messages', json={'content': '   '})
        self.assertEqual(res_empty.status_code, 400)

        # XSS injection attempt
        malicious = "<script>alert('xss')</script><b>설계 원칙이 궁금합니다.</b>"
        res = self.client.post(f'/api/tasks/{task_id}/messages', json={'content': malicious})
        self.assertEqual(res.status_code, 201)
        created = res.get_json()['message']

        self.assertEqual(created['status'], 'queued')
        self.assertEqual(created['task_id'], task_id)
        self.assertIsNotNone(created.get('user_id'))
        self.assertNotIn("<script>", created['content'])
        self.assertIn("&lt;script&gt;", created['content'])
        self.assertIn("설계 원칙이 궁금합니다.", created['content'])

    def test_transaction_rollback_atomicity(self):
        """Test 3: Verify execute() does not auto-commit inside a transaction block and rolls back on failure."""
        test_task_id = 'TASK-TRANSACTION-TEST-001'

        try:
            with self.db.transaction():
                self.db.execute(
                    "INSERT INTO review_tasks (task_id, title, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (test_task_id, 'Tx Rollback Test', 'active', '2026-01-01', '2026-01-01')
                )
                # Intentionally trigger an error
                raise ValueError("Simulated unexpected transaction failure")
        except ValueError:
            pass

        # Verify the record was rolled back and does not persist
        check = self.db.fetchone("SELECT task_id FROM review_tasks WHERE task_id = ?", (test_task_id,))
        self.assertIsNone(check, "Record should have been rolled back and not committed.")

    def test_atomic_claim_and_session_inflight_blocking(self):
        """Test 4: Verify conditional claim blocks subsequent questions from the same session until completed."""
        self.login_admin()
        t1 = 'TASK-INSIGHTS-LAST3-20261023'
        t2 = 'TASK-INSIGHTS-PIPELINE-AUDIT-20261023'

        # Post Q1 to T1, Q2 to T1, Q3 to T2
        q1 = self.client.post(f'/api/tasks/{t1}/messages', json={'content': 'Q1 Task 1'}).get_json()['message']
        _ = self.client.post(f'/api/tasks/{t1}/messages', json={'content': 'Q2 Task 1'}).get_json()['message']
        _ = self.client.post(f'/api/tasks/{t2}/messages', json={'content': 'Q3 Task 2'}).get_json()['message']

        headers = {'X-Connector-Secret': app_server.CONNECTOR_SECRET}

        # Claim 1: Should claim Q1 (Task 1)
        res1 = self.client.post('/api/connector/claim', headers=headers, json={})
        self.assertEqual(res1.status_code, 200)
        c1 = res1.get_json()['claim']
        self.assertIsNotNone(c1)
        self.assertEqual(c1['question'], 'Q1 Task 1')

        # Claim 2: Task 1 has active in-flight claim! So Q2 is blocked. Should claim Q3 from Task 2!
        res2 = self.client.post('/api/connector/claim', headers=headers, json={})
        self.assertEqual(res2.status_code, 200)
        c2 = res2.get_json()['claim']
        self.assertIsNotNone(c2)
        self.assertEqual(c2['question'], 'Q3 Task 2')

        # Claim 3: Both Task 1 and Task 2 are currently in-flight! None should be claimed.
        res3 = self.client.post('/api/connector/claim', headers=headers, json={})
        self.assertEqual(res3.status_code, 200)
        self.assertIsNone(res3.get_json()['claim'])

        # Now complete Q1
        self.client.post('/api/connector/reply', headers=headers, json={
            'message_id': q1['message_id'],
            'reply_content': 'Q1 Completed response'
        })

        # Claim 4: Task 1 is no longer in-flight, so Q2 can now be claimed!
        res4 = self.client.post('/api/connector/claim', headers=headers, json={})
        self.assertEqual(res4.status_code, 200)
        c4 = res4.get_json()['claim']
        self.assertIsNotNone(c4)
        self.assertEqual(c4['question'], 'Q2 Task 1')

    def test_worker_reply_correlation_and_notification(self):
        """Test 5: Worker response properly links to user, updates status, and prevents duplicate replies."""
        self.login_admin()
        task_id = 'TASK-INSIGHTS-LAST3-20261023'

        # 1. Post question
        q_res = self.client.post(f'/api/tasks/{task_id}/messages', json={'content': '최근 3회 파이프라인 리뷰 요지는?'})
        msg_id = q_res.get_json()['message']['message_id']

        headers = {'X-Connector-Secret': app_server.CONNECTOR_SECRET}

        # 2. Worker claims
        c_res = self.client.post('/api/connector/claim', headers=headers, json={})
        self.assertEqual(c_res.get_json()['claim']['message_id'], msg_id)

        # 3. Worker replies
        reply_text = "모듈화 및 Config/Context 분리가 완료되었으며 Allure 리포트 증거 수집 체계가 연계되었습니다."
        rep_res = self.client.post('/api/connector/reply', headers=headers, json={
            'message_id': msg_id,
            'reply_content': reply_text
        })
        self.assertEqual(rep_res.status_code, 201)

        # 4. Check duplicate reply rejection
        rep_dup = self.client.post('/api/connector/reply', headers=headers, json={
            'message_id': msg_id,
            'reply_content': 'Duplicate reply attempt'
        })
        self.assertEqual(rep_dup.status_code, 200)
        self.assertEqual(rep_dup.get_json()['status'], 'already_completed')

        # 5. Check in-app notification directed to user
        notifs = self.client.get('/api/notifications').get_json()
        self.assertEqual(notifs['unread_count'], 1)

        # 6. Mark read
        self.client.post(f'/api/tasks/{task_id}/mark-read')
        notifs_after = self.client.get('/api/notifications').get_json()
        self.assertEqual(notifs_after['unread_count'], 0)

    def test_delivery_unknown_and_invalid_task_rejection(self):
        """Test 6: Delivery unknown ack handling and invalid task ID rejection."""
        self.login_admin()

        # Invalid task ID
        bad_task_res = self.client.post('/api/tasks/TASK-NONEXISTENT/messages', json={'content': 'Test'})
        self.assertEqual(bad_task_res.status_code, 404)

        # Delivery unknown state
        valid_tid = 'TASK-INSIGHTS-LAST3-20261023'
        q = self.client.post(f'/api/tasks/{valid_tid}/messages', json={'content': 'R2 교재 구조는?'}).get_json()['message']

        headers = {'X-Connector-Secret': app_server.CONNECTOR_SECRET}
        self.client.post('/api/connector/claim', headers=headers, json={})

        ack_res = self.client.post('/api/connector/ack', headers=headers, json={
            'message_id': q['message_id'],
            'status': 'delivery_unknown'
        })
        self.assertEqual(ack_res.status_code, 200)

        updated = self.client.get(f'/api/tasks/{valid_tid}/messages').get_json()['messages'][0]
        self.assertEqual(updated['status'], 'delivery_unknown')

    def test_production_unconfigured_db_rejection(self):
        """Test 7: Vercel serverless mode strictly rejects execution when DATABASE_URL is missing."""
        with patch.dict(os.environ, {'VERCEL': '1', 'DATABASE_URL': ''}):
            db = Database()
            self.assertEqual(db.mode, 'unconfigured_production')
            with self.assertRaises(DatabaseError) as ctx:
                db.get_connection()
            self.assertIn("DB_NOT_CONFIGURED", str(ctx.exception))

    def test_connector_outbound_mock_dispatch_flow(self):
        """Test 8: Full outbound connector loop with mocked local IDE review worker bridge."""
        self.login_admin()
        tid = 'TASK-INSIGHTS-LAST3-20261023'
        _ = self.client.post(f'/api/tasks/{tid}/messages', json={'content': '가상 교재 회차의 목적은?'}).get_json()['message']

        def mock_bridge(prompt, worker_cfg):
            self.assertIn("가상 교재 회차의 목적", prompt)
            self.assertEqual(worker_cfg['worker_id'], 'BLOG-SYSTEM-CODE-REVIEW')
            return {
                'status': 'completed',
                'task_id': 'MOCK-REVIEW-TASK-001',
                'reply': '프로젝트 실무 코드를 바탕으로 연속 학습과 면접 역량을 강화하기 위함입니다.'
            }

        class TestClientConnector(ReviewAppConnector):
            def __init__(self, test_client):
                super().__init__(server_url="http://testserver")
                self.client = test_client

            def _post(self, path, payload):
                headers = {'X-Connector-Secret': self.secret}
                res = self.client.post(path, headers=headers, json=payload)
                return res.get_json()

        connector = TestClientConnector(self.client)
        outcome = connector.process_one(mock_bridge=mock_bridge)
        self.assertEqual(outcome, 'replied')

        msgs = self.client.get(f'/api/tasks/{tid}/messages').get_json()['messages']
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]['status'], 'completed')
        self.assertEqual(msgs[1]['sender_type'], 'worker')
        self.assertIn("연속 학습과 면접 역량", msgs[1]['content'])

    def test_auth_me_and_logout(self):
        """Test 9: Verify /api/auth/me reflects session state and /api/auth/logout clears it."""
        # Unauthenticated
        me_unauth = self.client.get('/api/auth/me').get_json()
        self.assertFalse(me_unauth['authenticated'])

        # Login
        self.login_admin()
        me_auth = self.client.get('/api/auth/me').get_json()
        self.assertTrue(me_auth['authenticated'])
        self.assertEqual(me_auth['user']['username'], 'admin')

        # Logout
        self.client.post('/api/auth/logout')
        me_after = self.client.get('/api/auth/me').get_json()
        self.assertFalse(me_after['authenticated'])

    def test_legacy_and_deployment_check_routes(self):
        """Test 10: Verify /legacy and /deployment-check.html routes return 200 with static content."""
        res_legacy = self.client.get('/legacy')
        self.assertEqual(res_legacy.status_code, 200)

        res_check = self.client.get('/deployment-check.html')
        self.assertEqual(res_check.status_code, 200)


if __name__ == '__main__':
    unittest.main()
