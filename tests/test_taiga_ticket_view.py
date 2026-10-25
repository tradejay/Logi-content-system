import hashlib
from pathlib import Path
import tempfile
import unittest

from services.taiga_tracking import article_details
from services.taiga_ticket_view import render_ticket, article_with_images


class TicketViewTests(unittest.TestCase):
    def test_system_work_is_separate_from_content(self):
        from services.taiga_tracking import system_task
        for category in ['Fact', '가이드', '개발']:
            self.assertTrue(system_task({'category': category}))
        for category in ['글', '이미지']:
            self.assertFalse(system_task({'category': category}))

    def test_images_are_resolved_and_unavailable_candidates_remain_pending(self):
        bindings = [{'need': {'id': 'NEED-A'}, 'candidate': {'asset_id': 'AST-A',
                    'url': '/api/content-system/assets/CNT-TEST/photo.jpg'}, 'status': 'pending_review'}]
        rendered = article_with_images('{{asset:NEED-A}} {{asset:NEED-MISSING}}', bindings, 'http://127.0.0.1:5014/article-console.html')
        self.assertIn('http://127.0.0.1:5014/api/content-system/assets/CNT-TEST/photo.jpg', rendered)
        self.assertIn('승인 상태 확인 필요', rendered)
        self.assertIn('이미지 확보 대기 · NEED-MISSING', rendered)
        bindings[0]['candidate']['review_status'] = 'rejected'
        self.assertNotIn('photo.jpg', article_with_images('{{asset:AST-A}}', bindings, ''))

    def test_article_and_revision_feedback_visible_without_fake_usage(self):
        task = {'key': 'content:CNT-TEST', 'category': '글', 'state': '막힘',
                'refs': {'content_id': 'CNT-TEST'}, 'summary': {'outcome': 'REVISION_REQUIRED'},
                'details': {'markdown': '## 원고\n작성된 본문', 'draft_chars': 12,
                            'checks': {'qa': {'passed': False, 'feedback': {'issues': [
                                {'claim_id': 'CLM-1', 'category': 'DRAFT_ERROR', 'detail': '근거 보완'}]}}}}}
        rendered = render_ticket(task)
        for expected in ['작성된 본문', 'CLM-1', '근거 보완', '보완 필요', '입력 토큰 측정 합계 | 미기록']:
            self.assertIn(expected, rendered)

    def test_historical_draft_requires_matching_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            draft = root / 'draft.md'
            draft.write_bytes('해당 실행 원고'.encode('utf-8'))
            result = {'run_id': 'old-run', 'draft_file': str(draft), 'draft_sha256': 'wrong'}
            self.assertEqual(article_details(root, 'CNT-TEST', result)['markdown'], '')
            result['draft_sha256'] = hashlib.sha256(draft.read_bytes()).hexdigest()
            self.assertEqual(article_details(root, 'CNT-TEST', result)['markdown'], '해당 실행 원고')


    def test_assets_yaml_candidates_linked_when_queue_matches_manuscript(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            draft = root / 'draft.md'
            content = '원고 내용 {{asset:NEED-DIAGRAM}}'
            draft.write_text(content, encoding='utf-8')
            digest = hashlib.sha256(draft.read_bytes()).hexdigest()

            # Create queue with matching job
            queue_file = root / 'content-system/queue/asset.queue.yaml'
            queue_file.parent.mkdir(parents=True, exist_ok=True)
            queue_file.write_text(
                f"jobs:\n"
                f"  JOB-1:\n"
                f"    content_id: CNT-TEST\n"
                f"    need_id: NEED-DIAGRAM\n"
                f"    draft_sha256: {digest}\n"
                f"    status: pending_review\n"
                f"    output:\n"
                f"      asset_id: AST-GEN-1\n",
                encoding='utf-8'
            )

            # Create assets.yaml with candidate
            assets_file = root / 'content-system/assets/CNT-TEST/assets.yaml'
            assets_file.parent.mkdir(parents=True, exist_ok=True)
            assets_file.write_text(
                "assets:\n"
                "- asset_id: AST-GEN-1\n"
                "  need_id: NEED-DIAGRAM\n"
                "  url: /api/content-system/assets/CNT-TEST/AST-GEN-1.jpg\n"
                "  alt: 다이어그램 후보\n"
                "  review_status: candidate\n",
                encoding='utf-8'
            )

            result = {'run_id': 'old-run', 'draft_file': str(draft), 'draft_sha256': digest}
            details = article_details(root, 'CNT-TEST', result)
            task = {'key': 'content:CNT-TEST', 'category': '글', 'state': '검토 대기',
                    'refs': {'content_id': 'CNT-TEST'}, 'summary': {'outcome': 'COMPLETED_REVIEW_PENDING'},
                    'details': details, 'console_url': 'http://127.0.0.1:5014/article-console.html?content=CNT-TEST'}
            rendered = render_ticket(task)

            self.assertIn('http://127.0.0.1:5014/api/content-system/assets/CNT-TEST/AST-GEN-1.jpg', rendered)
            self.assertIn('다이어그램 후보 — 미리보기 · 승인 상태 확인 필요', rendered)
            self.assertNotIn('이미지 확보 대기', rendered)

    def test_assets_yaml_candidates_not_linked_when_draft_hash_mismatches(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            draft = root / 'draft.md'
            content = '새로 수정된 원고 {{asset:NEED-DIAGRAM}}'
            draft.write_text(content, encoding='utf-8')
            digest = hashlib.sha256(draft.read_bytes()).hexdigest()

            queue_file = root / 'content-system/queue/asset.queue.yaml'
            queue_file.parent.mkdir(parents=True, exist_ok=True)
            queue_file.write_text(
                "jobs:\n"
                "  JOB-1:\n"
                "    content_id: CNT-TEST\n"
                "    need_id: NEED-DIAGRAM\n"
                "    draft_sha256: old_mismatched_hash_12345\n"
                "    status: pending_review\n",
                encoding='utf-8'
            )

            assets_file = root / 'content-system/assets/CNT-TEST/assets.yaml'
            assets_file.parent.mkdir(parents=True, exist_ok=True)
            assets_file.write_text(
                "assets:\n"
                "- asset_id: AST-GEN-1\n"
                "  need_id: NEED-DIAGRAM\n"
                "  url: /api/content-system/assets/CNT-TEST/AST-GEN-1.jpg\n"
                "  alt: 다이어그램 후보\n"
                "  review_status: candidate\n",
                encoding='utf-8'
            )

            result = {'run_id': 'old-run', 'draft_file': str(draft), 'draft_sha256': digest}
            details = article_details(root, 'CNT-TEST', result)
            task = {'key': 'content:CNT-TEST', 'category': '글', 'state': '검토 대기',
                    'refs': {'content_id': 'CNT-TEST'}, 'summary': {'outcome': 'COMPLETED_REVIEW_PENDING'},
                    'details': details, 'console_url': 'http://127.0.0.1:5014/article-console.html?content=CNT-TEST'}
            rendered = render_ticket(task)

            self.assertNotIn('AST-GEN-1.jpg', rendered)
            self.assertIn('이미지 확보 대기 · NEED-DIAGRAM', rendered)

    def test_live_article_15_six_images_connected_with_unapproved_markers(self):
        import re
        from services.taiga_tracking import ROOT, collect_tasks
        tasks = collect_tasks(ROOT)
        task_15 = next((t for t in tasks if t['key'] == 'content:CNT-LIVE-20261008-VERIFY-001'), None)
        self.assertIsNotNone(task_15)
        rendered = render_ticket(task_15)

        imgs = re.findall(r'!\[([^\]]*)\]\(([^)]+)\)', rendered)
        self.assertEqual(len(imgs), 6)
        self.assertNotIn('이미지 확보 대기', rendered)
        unapproved = [l for l in rendered.splitlines() if '미리보기 · 승인 상태 확인 필요' in l]
        self.assertEqual(len(unapproved), 6)


if __name__ == '__main__':
    unittest.main()

