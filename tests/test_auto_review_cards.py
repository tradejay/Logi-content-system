"""Comprehensive Automated Offline Tests for Auto-Review, Shorts/Card News, and Connector Concurrency.

Adheres to ROOT-REVIEW-AUTO-CARDS-20261024 & CODE-REVIEW-GUIDE.md:
1. Card schema & validation (all valid card types, 2~4 points, alerts, details)
2. Markdown sections to structured cards parsing (alerts, code snippets, summaries)
3. Completed task packaging & secret redaction (no credentials, tokens, DB URLs)
4. Auto-review queue deduplication & idempotency
5. Single-session concurrency lock (blocking chat Q&A while auto-review in-flight and vice versa)
6. Late response recovery via transcript cursor and correlation tokens
7. Process restart recovery without duplicate prompts
8. Full end-to-end: completion event -> mock review -> parse cards -> publish API -> DB docs/cards/notif
9. Card-level question context prefill and doc_id association
10. Read-only site browsing invariant (GET does not mutate or enqueue)
11. Static UI structure verification for index.html
"""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from services.review_app import server as app_server
from services.review_app.auto_reviewer import (
    enqueue_auto_review,
    get_next_pending_job,
    get_queue,
    package_completed_task,
    save_queue,
    update_job_status,
)
from services.review_app.card_parser import (
    parse_markdown_to_cards,
    validate_card,
)
from services.review_app.connector import (
    ReviewAppConnector,
    clear_active_job,
    load_active_job,
    save_active_job,
)
from services.review_app.db import Database

ROOT = Path(__file__).resolve().parents[1]


class TestAutoReviewCards(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix='test-auto-cards-')
        self.test_root = Path(self.tmp_dir)
        self.db_path = self.test_root / 'test_app.db'
        self.db = Database(str(self.db_path))
        self.db.init_schema()
        app_server._seed_initial_user(self.db)

        # Create worker-control config mock
        wc_dir = self.test_root / 'worker-control'
        wc_dir.mkdir(parents=True, exist_ok=True)
        (wc_dir / 'code-review-worker.json').write_text(json.dumps({
            'worker_id': 'BLOG-SYSTEM-CODE-REVIEW',
            'conversation_id': 'c90739e7-27e4-4775-ba42-0c959cb6ef04',
            'enabled': True
        }), encoding='utf-8')

        # Patch server db instance
        self.orig_db = app_server._db_instance
        app_server._db_instance = self.db

        self.app = app_server.create_app({'TESTING': True})
        self.client = self.app.test_client()

        # Connector instance targeting test app
        self.connector = ReviewAppConnector(server_url="http://localhost:5080", root=self.test_root)
        # Point connector _post to test_client for offline execution
        self.orig_post = self.connector._post

        def mock_post(path, payload):
            res = self.client.post(path, json=payload, headers={'X-Connector-Secret': self.connector.secret})
            if res.status_code >= 400:
                raise RuntimeError(f"Server error {res.status_code}: {res.get_data(as_text=True)}")
            return res.get_json()

        self.connector._post = mock_post

    def tearDown(self):
        self.db.close()
        app_server._db_instance = self.orig_db
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def login_admin(self):
        return self.client.post('/api/auth/login', json={'username': 'admin', 'password': 'admin1234'})

    def test_card_schema_and_validation(self):
        """Test 1: Validate all card types, points count, and required fields."""
        # 1. Valid concept card
        c1 = validate_card({
            'card_id': 'CARD-001-1',
            'title': '원자적 트랜잭션 갱신',
            'summary': 'SQLite 및 PostgreSQL에서 원자적 블록 단위 트랜잭션을 보장합니다.',
            'card_type': 'implementation',
            'points': ['with db.transaction() 컨텍스트 사용', '중간 예외 발생 시 자동 rollback', '자동 커밋 비활성화'],
            'critical_note': '트랜잭션 내부에서 db.execute 호출 시 자동 commit하지 않아야 함'
        })
        self.assertEqual(c1['card_type'], 'implementation')
        self.assertEqual(len(c1['points']), 3)
        self.assertIn("SQLite 및 PostgreSQL", c1['summary'])

        # 2. Type fallback & points clamping
        c2 = validate_card({
            'card_id': 'CARD-001-2',
            'title': '임의의 카드',
            'summary': '요약문',
            'card_type': 'unknown_type',
            'points': ['1', '2', '3', '4', '5', '6', '7']
        })
        self.assertEqual(c2['card_type'], 'concept')
        self.assertEqual(len(c2['points']), 5)

        # 3. Missing required fields raise ValueError
        with self.assertRaises(ValueError):
            validate_card({'card_id': '', 'title': 'T', 'summary': 'S'})
        with self.assertRaises(ValueError):
            validate_card({'card_id': 'C', 'title': '', 'summary': 'S'})
        with self.assertRaises(ValueError):
            validate_card({'card_id': 'C', 'title': 'T', 'summary': ''})

    def test_markdown_section_to_cards_parsing(self):
        """Test 2: Parse markdown with alert notes, code snippets, and points into cards."""
        doc_md = """# 기술 코드 리뷰
## 1. 개요 및 요약
본 작업은 세션 단일 큐와 늦은 응답 복구를 완성합니다.
- 동시성 충돌 방지 락 도입
- 프로세스 재시작 시 상태 복구
- 카드 뉴스 형식 변환

## 2. 문제 배경 및 결함
> [!WARNING]
> 기존 연결기는 타임아웃 발생 시 뒤늦게 도착한 워커 응답을 유실하는 결함이 있었습니다.
기존 구조는 다음과 같은 결함이 확인되었습니다.
- 단일 세션에 두 요청이 동시 전달되어 race condition 발생
- 커넥터 재시작 시 cursor가 초기화됨

## 3. 구현 설계 및 핵심 변경
`active-jobs.json`을 통해 세션 상태를 추적합니다.
```python
def check_late_response():
    pass
```
- cursor 기반 뒤늦은 회신 수집
- 원자적 파일 교체

## 4. 실무 면접 대비 Q&A
- Q: 분산 환경에서 단일 워커 세션을 어떻게 보호하나요?
- A: 파일 기반 세션 락과 조건부 토큰을 통해 순차 처리를 강제합니다.
"""
        cards = parse_markdown_to_cards('DOC-REV-01', 'TASK-01', doc_md)
        self.assertEqual(len(cards), 4)

        # Card 1: summary
        self.assertEqual(cards[0]['card_type'], 'summary')
        self.assertIn("개요 및 요약", cards[0]['title'])
        self.assertEqual(len(cards[0]['points']), 3)

        # Card 2: problem with critical note
        self.assertEqual(cards[1]['card_type'], 'problem')
        self.assertIsNotNone(cards[1]['critical_note'])
        self.assertIn("결함이 있었습니다", cards[1]['critical_note'])

        # Card 3: implementation with code snippet
        self.assertEqual(cards[2]['card_type'], 'implementation')
        self.assertIsNotNone(cards[2]['code_snippet'])
        self.assertIn("def check_late_response():", cards[2]['code_snippet'])

        # Card 4: interview_qa
        self.assertEqual(cards[3]['card_type'], 'interview_qa')

    def test_completed_task_packaging_and_secret_redaction(self):
        """Test 3: Verify packaging of completed tasks and strict secret redaction."""
        pkg = package_completed_task('TASK-SYSTEM-TEST-001', root=ROOT)
        self.assertEqual(pkg['task_id'], 'TASK-SYSTEM-TEST-001')
        self.assertIn('diff', pkg)
        self.assertIn('head_commit', pkg)
        self.assertIn('package_hash', pkg)

        # Secret redaction check
        diff_text = pkg['diff']
        self.assertNotIn("DATABASE_URL = 'postgres://", diff_text)
        self.assertNotIn("CONNECTOR_SECRET = '", diff_text)
        if "REDACTED" in diff_text:
            self.assertIn("[REDACTED SENSITIVE LINE]", diff_text)

    def test_auto_review_queue_deduplication(self):
        """Test 4: Verify auto-review queue enqueuing and deduplication."""
        task_id = "TASK-AUTO-DEDUP-001"
        job1, is_new1 = enqueue_auto_review(task_id, root=self.test_root)
        self.assertTrue(is_new1)
        self.assertEqual(job1['status'], 'pending')

        # Duplicate call without force returns existing
        job2, is_new2 = enqueue_auto_review(task_id, root=self.test_root)
        self.assertFalse(is_new2)
        self.assertEqual(job2['job_id'], job1['job_id'])

        # Next pending job retrieves job1
        next_job = get_next_pending_job(root=self.test_root)
        self.assertIsNotNone(next_job)
        self.assertEqual(next_job['job_id'], job1['job_id'])

        # Update status to completed
        update_job_status(job1['job_id'], 'completed', root=self.test_root)
        self.assertIsNone(get_next_pending_job(root=self.test_root))

    def test_session_concurrency_lock(self):
        """Test 5: Verify connector in-flight session lock blocks concurrent dispatches."""
        # Save active in-flight job
        save_active_job({
            'job_type': 'auto_review',
            'job_id': 'AUTOREV-INFLIGHT-001',
            'task_id': 'TASK-INFLIGHT-001',
            'req_token': '[REV-REQ-AUTOREV-INFLIGHT-001]',
            'started_at': 9999999999.0,  # far future to avoid timeout
            'status': 'running'
        }, root=self.test_root)

        # Enqueue a user question into DB
        self.login_admin()
        # Seed task
        self.db.execute("INSERT INTO review_tasks (task_id, title, status, created_at, updated_at) VALUES ('TASK-INFLIGHT-001', 'Title', 'active', '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z')")
        self.client.post('/api/tasks/TASK-INFLIGHT-001/messages', json={'content': '동시성 락 질문'})

        # Connector poll should report in_flight_busy and NOT claim or dispatch
        res = self.connector.process_one()
        self.assertEqual(res, 'in_flight_busy')

        # Question in DB should still be queued
        msg = self.db.fetchone("SELECT status FROM chat_messages WHERE content = '동시성 락 질문'")
        self.assertEqual(msg['status'], 'queued')

        # Clear lock
        clear_active_job(root=self.test_root)

    def test_late_response_recovery_from_transcript_cursor(self):
        """Test 6: Verify recovery of late arriving responses using transcript cursor."""
        transcript_file = self.test_root / 'mock_transcript.jsonl'
        transcript_file.write_text('{"step_index": 1, "source": "USER", "content": "초기 로그"}\n', encoding='utf-8')
        initial_cursor = transcript_file.stat().st_size

        msg_id = "MSG-LATE-001"
        req_token = f"[REV-REQ-{msg_id}]"

        # Save active chat_qa job
        save_active_job({
            'job_type': 'chat_qa',
            'job_id': msg_id,
            'task_id': 'TASK-LATE-001',
            'req_token': req_token,
            'transcript_path': str(transcript_file),
            'initial_cursor': initial_cursor,
            'started_at': 9999999999.0,
            'status': 'running'
        }, root=self.test_root)

        # Seed question in DB
        self.db.execute("INSERT INTO review_tasks (task_id, title, status, created_at, updated_at) VALUES ('TASK-LATE-001', 'Late Task', 'active', '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z')")
        self.db.execute(
            """
            INSERT INTO chat_messages (message_id, task_id, thread_id, sender_type, content, status, read_by_user, created_at, updated_at)
            VALUES (?, 'TASK-LATE-001', 'TH-1', 'user', '지연 응답 질문', 'running', 1, '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z')
            """,
            (msg_id,)
        )

        # Append late response to transcript
        late_json = json.dumps({
            "step_index": 2,
            "source": "MODEL",
            "type": "PLANNER_RESPONSE",
            "status": "DONE",
            "content": f"{req_token} 검토 완료: 지연 응답이 성공적으로 복구되었습니다."
        })
        with open(transcript_file, 'a', encoding='utf-8') as f:
            f.write(late_json + '\n')

        # Poll connector
        res = self.connector.process_one()
        self.assertEqual(res, 'late_reply_recovered')

        # Verify active job was cleared
        self.assertIsNone(load_active_job(root=self.test_root))

        # Verify reply message in DB
        reply = self.db.fetchone("SELECT * FROM chat_messages WHERE reply_to = ?", (msg_id,))
        self.assertIsNotNone(reply)
        self.assertIn("지연 응답이 성공적으로 복구되었습니다", reply['content'])

    def test_restart_recovery_across_connector_reboot(self):
        """Test 7: Verify connector recovers pending in-flight state after process restart."""
        task_id = "TASK-REBOOT-001"
        job_id = f"AUTOREV-{task_id}"
        req_token = f"[REV-REQ-{job_id}]"

        transcript_file = self.test_root / 'reboot_transcript.jsonl'
        transcript_file.write_text('{"step": 0}\n', encoding='utf-8')
        initial_cursor = transcript_file.stat().st_size

        # Save auto-review job in queue
        save_queue([{
            'job_id': job_id,
            'task_id': task_id,
            'title': '재시작 복구 작업',
            'target_scope': 'system',
            'status': 'running'
        }], root=self.test_root)

        # Simulate state saved before connector process crashed
        save_active_job({
            'job_type': 'auto_review',
            'job_id': job_id,
            'task_id': task_id,
            'title': '재시작 복구 작업',
            'target_scope': 'system',
            'req_token': req_token,
            'transcript_path': str(transcript_file),
            'initial_cursor': initial_cursor,
            'started_at': 9999999999.0,
            'status': 'running'
        }, root=self.test_root)

        # Append review result to transcript
        sample_review = f"""{req_token}
# 기술 코드 리뷰
## 1. 개요 및 요약
재시작 복구 검토 완료.
- 프로세스 재부팅 후에도 큐 복구
- 트랜스크립트 커서 보존

## 2. 구현 설계 및 핵심 변경
active-jobs.json을 기반으로 상태를 복원합니다.
"""
        with open(transcript_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                "step_index": 5,
                "source": "MODEL",
                "type": "PLANNER_RESPONSE",
                "status": "DONE",
                "content": sample_review
            }) + '\n')

        # NEW Connector instance after reboot
        new_connector = ReviewAppConnector(server_url="http://localhost:5080", root=self.test_root)
        new_connector._post = self.connector._post

        res = new_connector.process_one()
        self.assertEqual(res, 'late_auto_review_published')

        # Verify published in DB
        task_row = self.db.fetchone("SELECT * FROM review_tasks WHERE task_id = ?", (task_id,))
        self.assertIsNotNone(task_row)
        self.assertEqual(task_row['title'], '재시작 복구 작업')

        # Active job cleared
        self.assertIsNone(load_active_job(root=self.test_root))

    def test_end_to_end_completion_to_publish_and_cards(self):
        """Test 8: Full end-to-end: completion event -> mock review -> parse cards -> publish API -> DB docs/cards/notif."""
        task_id = "TASK-E2E-AUTO-CARDS-001"
        job, is_new = enqueue_auto_review(task_id, title="E2E 자동 리뷰 테스트", root=self.test_root)
        self.assertTrue(is_new)

        mock_review_output = f"""[REV-REQ-{job['job_id']}]
# 기술 코드 리뷰: {task_id}
## 1. 개요 및 요약
E2E 자동 검토 완료.
- 카드 뉴스 파서 검증
- 숏츠 캐러셀 UI 연동
- 알림 생성 확인

## 2. 문제 배경 및 결함
> [!WARNING]
> 기존에는 자동화 파이프라인에서 리뷰 워커 결과가 웹 포털에 직접 게시되지 않았습니다.

## 3. 구현 설계 및 핵심 변경
원자적 upsert 및 카드 데이터베이스 스키마를 구성했습니다.
```python
def publish_review():
    pass
```

---
# 회차별 가상 교재: {task_id}
## 1. 회차 개요 및 학습 목표
자동 리뷰와 카드뉴스 시스템 아키텍처를 학습합니다.

## 2. 실무 면접 대비 Q&A
- Q: 카드 뉴스로 기술 문서를 변환할 때 핵심 고려사항은?
- A: 한 카드당 하나의 명확한 개념을 담고 결함/제약사항을 눈에 띄게 배치합니다.
"""

        def mock_bridge(prompt, cfg):
            return {'status': 'completed', 'reply': mock_review_output}

        res = self.connector.process_one(mock_bridge=mock_bridge)
        self.assertEqual(res, 'auto_review_published')

        # Verify DB review_tasks
        task_row = self.db.fetchone("SELECT * FROM review_tasks WHERE task_id = ?", (task_id,))
        self.assertIsNotNone(task_row)
        self.assertEqual(task_row['title'], 'E2E 자동 리뷰 테스트')

        # Verify DB review_documents (2 documents: review & learn)
        docs = self.db.fetchall("SELECT * FROM review_documents WHERE task_id = ?", (task_id,))
        self.assertEqual(len(docs), 2)

        # Verify DB review_cards
        cards = self.db.fetchall("SELECT * FROM review_cards WHERE task_id = ?", (task_id,))
        self.assertGreaterEqual(len(cards), 4)

        # Verify API /api/documents/<id>/cards
        self.login_admin()
        doc_id = docs[0]['doc_id']
        res_cards = self.client.get(f'/api/documents/{doc_id}/cards')
        self.assertEqual(res_cards.status_code, 200)
        api_cards = res_cards.get_json()['cards']
        self.assertGreaterEqual(len(api_cards), 2)
        self.assertIn('title', api_cards[0])
        self.assertIn('summary', api_cards[0])
        self.assertIsInstance(api_cards[0]['points'], list)

        # Verify notification generated
        notif = self.db.fetchone("SELECT * FROM notifications WHERE task_id = ?", (task_id,))
        self.assertIsNotNone(notif)
        self.assertIn("새로운 코드 리뷰", notif['title'])
        self.assertIn("카드가 게시되었습니다", notif['title'])

    def test_card_question_context_prefill(self):
        """Test 9: Verify question pre-filled with card context and doc_id association."""
        self.login_admin()
        task_id = "TASK-CARD-QA-001"
        doc_id = "DOC-CARD-QA-001"

        self.db.execute("INSERT INTO review_tasks (task_id, title, status, created_at, updated_at) VALUES (?, 'QA Task', 'active', '2026-10-24T00:00:00Z', '2026-10-24T00:00:00Z')", (task_id,))
        self.db.execute(
            "INSERT INTO review_documents (doc_id, task_id, doc_type, version, title, content_markdown, created_at) VALUES (?, ?, 'technical_review', 1, 'Doc Title', 'Doc Markdown', '2026-10-24T00:00:00Z')",
            (doc_id, task_id)
        )

        card_context = "[참조 카드: 원자적 갱신 (ID: CARD-01, 문서: Doc Title)]\n이 카드의 락 메커니즘을 설명해주세요."
        res = self.client.post(f'/api/tasks/{task_id}/messages', json={
            'content': card_context,
            'doc_id': doc_id
        })
        self.assertEqual(res.status_code, 201)
        created = res.get_json()['message']
        self.assertEqual(created['doc_id'], doc_id)
        self.assertIn("CARD-01", created['content'])

        # Claim question from connector
        claim = self.connector.claim_question()
        self.assertIsNotNone(claim)
        self.assertEqual(claim['message_id'], created['message_id'])
        self.assertEqual(claim['doc_id'], doc_id)
        self.assertEqual(claim['doc_context'], 'Doc Markdown')

    def test_site_browsing_readonly(self):
        """Test 10: Invariant check: GET endpoints do not mutate database or create tasks."""
        self.login_admin()
        task_count_before = self.db.fetchone("SELECT COUNT(*) as cnt FROM review_tasks")['cnt']
        msg_count_before = self.db.fetchone("SELECT COUNT(*) as cnt FROM chat_messages")['cnt']
        job_count_before = len(get_queue(root=self.test_root))

        # Perform multiple GETs
        self.client.get('/api/tasks')
        self.client.get('/api/notifications')
        self.client.get('/deployment-check')
        self.client.get('/legacy')

        task_count_after = self.db.fetchone("SELECT COUNT(*) as cnt FROM review_tasks")['cnt']
        msg_count_after = self.db.fetchone("SELECT COUNT(*) as cnt FROM chat_messages")['cnt']
        job_count_after = len(get_queue(root=self.test_root))

        self.assertEqual(task_count_before, task_count_after)
        self.assertEqual(msg_count_before, msg_count_after)
        self.assertEqual(job_count_before, job_count_after)

    def test_index_html_static_ui_structure(self):
        """Test 11: Verify index.html contains Card News toggle, carousel, and question buttons."""
        index_file = ROOT / 'services/review_app/static/index.html'
        self.assertTrue(index_file.exists())
        html_text = index_file.read_text(encoding='utf-8')

        # Check UI structural elements
        self.assertIn('btnModeCardsReview', html_text)
        self.assertIn('btnModeFullReview', html_text)
        self.assertIn('cardSlideReview', html_text)
        self.assertIn('btnModeCardsLearning', html_text)
        self.assertIn('btnModeFullLearning', html_text)
        self.assertIn('cardSlideLearning', html_text)

        # Check JS functions
        self.assertIn('function renderDoc(', html_text)
        self.assertIn('function switchDocMode(', html_text)
        self.assertIn('function navigateCard(', html_text)
        self.assertIn('function askCardQuestion(', html_text)
        self.assertIn('function toggleCardAccordion(', html_text)
        self.assertIn('ArrowLeft', html_text)
        self.assertIn('ArrowRight', html_text)


if __name__ == '__main__':
    unittest.main()
