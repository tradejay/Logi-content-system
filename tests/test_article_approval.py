from pathlib import Path
import sys

LOCAL_ROOT = Path(__file__).resolve().parent.parent
if str(LOCAL_ROOT) not in sys.path:
    sys.path.insert(0, str(LOCAL_ROOT))

import importlib.util
mod_path = LOCAL_ROOT / 'services' / 'article_approval.py'
spec = importlib.util.spec_from_file_location('local_article_approval', mod_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
ArticleApproval = mod.ArticleApproval

import contextlib
import hashlib
import json
import tempfile
import unittest
from unittest.mock import Mock, patch
import yaml

from services.content_pipeline import ContentPipeline, atomic
from services.pipeline_context import digest


class ApprovalTests(unittest.TestCase):
    def test_ide_current_draft_and_missing_review_job_are_connected_on_confirm(self):
        latest = self.pipeline.latest(self.cid)
        old_draft = self.pipeline.draft_path(self.cid)
        revised = self.pipeline.work(self.cid) / 'runs/run-1/revisions/current.draft.md'
        revised.parent.mkdir(parents=True)
        revised.write_text('수정 원고 {{asset:NEED-1}}', encoding='utf-8')
        atomic(revised.parents[1] / 'asset-bindings.json', {'bindings': [{'need': {'id': 'NEED-1'}, 'candidate': self.asset}]})
        new_sha = digest(revised.read_text(encoding='utf-8'))
        latest.update(execution_type='ide', draft_file=str(revised), draft_sha256=new_sha)
        atomic(self.pipeline.work(self.cid) / 'pipeline-latest.json', latest)
        state = self.service.snapshot(self.cid)
        self.assertEqual(self.pipeline.draft_path(self.cid), revised.resolve())
        self.assertTrue(state['images'][0]['job_id'].startswith('RUNIMG-'))
        self.assertEqual(state['images'][0]['job_draft_sha256'], new_sha)
        self.assertEqual(len(yaml.safe_load(self.queue.read_text())['jobs']), 1)
        result = self.service.images(self.cid, self.request())
        self.assertEqual(result['images'][0]['review_status'], 'approved')
        self.assertEqual(old_draft.read_text(encoding='utf-8'), '원고 {{asset:NEED-1}}')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.cid='CNT-TEST'
        self.pipeline=object.__new__(ContentPipeline)
        self.pipeline.root=self.root;self.pipeline.system=self.root/'content-system'
        draft=self.pipeline.draft_path(self.cid);draft.parent.mkdir(parents=True)
        draft.write_text('원고 {{asset:NEED-1}}',encoding='utf-8')
        self.sha=digest(draft.read_text(encoding='utf-8'))
        atomic(self.pipeline.work(self.cid)/'pipeline-latest.json',{'run_id':'run-1','draft_sha256':self.sha,
            'outcome':'COMPLETED_REVIEW_PENDING','qa':{'passed':True},
            'official_review':{'status':'REVIEWED','claims':[{'verdict':'confirmed'}]}})
        image=self.root/'image.jpg';image.write_bytes(b'test-image')
        self.registry=self.root/'content-system/assets'/self.cid/'assets.yaml';self.registry.parent.mkdir(parents=True)
        self.asset={'need_id':'NEED-1','asset_id':'AST-1','local_path':'image.jpg','url':'/image.jpg',
            'sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'origin_type':'generated',
            'source_ref':{'request':'REQ-1'},'caption':'이미지','review_status':'candidate'}
        self.registry.write_text(yaml.safe_dump({'assets':[self.asset]}),encoding='utf-8')
        self.queue=self.root/'content-system/queue/asset.queue.yaml';self.queue.parent.mkdir(parents=True)
        self.queue.write_text(yaml.safe_dump({'review':['IMG-1'],'jobs':{'IMG-1':{'content_id':self.cid,
            'need_id':'NEED-1','draft_sha256':self.sha,'status':'pending_review'}}}),encoding='utf-8')
        self.addCleanup(patch.stopall)
        patch.object(self.pipeline,'lock',side_effect=lambda _:contextlib.nullcontext()).start()
        patch('services.article_approval.article_details',return_value={'markdown':draft.read_text(encoding='utf-8'),
            'asset_bindings':[{'need':{'id':'NEED-1','purpose':'문제 설명'},'candidate':self.asset}]}).start()
        self.upload=Mock(return_value='https://example.com/image.jpg')
        self.service=ArticleApproval(self.root,self.pipeline,self.upload)

    def request(self,**kw):
        s=self.service.snapshot(self.cid)
        return {k:s[k] for k in ('snapshot_token','run_id','draft_sha256')}|{'reviewer':'관리자',
            'images':[{'need_id':'NEED-1','asset_id':'AST-1','decision':'approve','review_note':'직접 확인'}],
            'confirmed_images':True,'publish_to_drive':True}|kw

    def test_confirmation_and_upload_consent_required(self):
        for options in ({'confirmed_images':False},{'publish_to_drive':False}):
            with self.assertRaises(ValueError):self.service.images(self.cid,self.request(**options))
        self.upload.assert_not_called()
        self.assertEqual(yaml.safe_load(self.registry.read_text())['assets'][0]['review_status'],'candidate')

    def test_stale_snapshot_and_changed_image_block_upload(self):
        data=self.request();self.pipeline.draft_path(self.cid).write_text('변경 원고',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'변경'):self.service.images(self.cid,data)
        self.upload.assert_not_called()

    def test_approval_records_registry_queue_and_final_bindings(self):
        state=self.service.images(self.cid,self.request())
        self.upload.assert_called_once()
        self.assertEqual(state['images'][0]['review_status'],'approved')
        self.assertEqual(yaml.safe_load(self.queue.read_text(encoding='utf-8'))['jobs']['IMG-1']['status'],'completed')
        self.assertEqual(yaml.safe_load(self.registry.read_text(encoding='utf-8'))['assets'][0]['reviewer'],'관리자')
        with patch.object(self.pipeline,'approve') as approve:
            self.service.finalize(self.cid,self.request(confirmed_final=True,resolutions=['확인']))
        args=approve.call_args.args
        self.assertEqual(args[:4],(self.cid,'run-1',self.sha,'관리자'))
        self.assertEqual(args[4]['NEED-1']['url'],'https://example.com/image.jpg')
        self.assertEqual(args[4]['NEED-1']['origin'],'generated')

    def test_final_confirmation_and_image_approval_required(self):
        with self.assertRaises(ValueError):self.service.finalize(self.cid,self.request(confirmed_final=False))
        with self.assertRaisesRegex(ValueError,'이미지'):self.service.finalize(self.cid,self.request(confirmed_final=True))

    def test_public_asset_does_not_upload_and_failed_upload_does_not_approve(self):
        data=self.request();data['images'][0]['public_url']='https://example.com/already.jpg'
        self.service.images(self.cid,data);self.upload.assert_not_called()

    def test_failed_upload_preserves_candidate(self):
        self.upload.return_value=None
        with self.assertRaisesRegex(ValueError,'연동 실패'):self.service.images(self.cid,self.request())
        self.assertEqual(yaml.safe_load(self.registry.read_text())['assets'][0]['review_status'],'candidate')

    def test_empty_official_claims_are_not_a_completed_review(self):
        path = self.pipeline.work(self.cid) / 'pipeline-latest.json'
        result = json.loads(path.read_text(encoding='utf-8'))
        result['official_review'] = {'status': 'REVIEWED', 'claims': []}
        atomic(path, result)
        self.assertFalse(self.service.snapshot(self.cid)['official_confirmed'])
        with self.assertRaisesRegex(ValueError, 'Official claim review is incomplete'):
            self.pipeline.approve(self.cid, 'run-1', self.sha, '관리자', {}, [])

    def test_file_hash_checked_before_upload(self):
        (self.root/'image.jpg').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'hash'):self.service.images(self.cid,self.request())
        self.upload.assert_not_called()

    def test_publish_records_published_url_and_status(self):
        self.make_publish_ready()
        reg = self.root / 'content-system/registry/CONTENT_REGISTRY.csv'
        reg.parent.mkdir(parents=True, exist_ok=True)
        reg.write_text('content_id,status,published_url,published_date,title\nCNT-TEST,READY,,,테스트\n', encoding='utf-8')
        with patch('services.taiga_tracking.synchronize', return_value={}):
            state = self.service.publish(self.cid, {'published_url': 'https://blog.naver.com/test/12345', 'published_date': '2026-10-20', 'run_id': 'run-1', 'draft_sha256': self.sha})
        self.assertEqual(state['published_url'], 'https://blog.naver.com/test/12345')
        self.assertEqual(state['published_date'], '2026-10-20')
        self.assertEqual(state['stage']['number'], 8)

    def test_publish_record_rejects_pending_review_without_changing_registry(self):
        reg = self.root / 'content-system/registry/CONTENT_REGISTRY.csv'
        reg.parent.mkdir(parents=True, exist_ok=True)
        original = 'content_id,status,published_url,published_date,title\nCNT-TEST,READY,,,테스트\n'
        reg.write_text(original, encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Publishing blocked'):
            self.service.publish(self.cid, {'published_url': 'https://blog.naver.com/test/12345',
                                            'run_id': 'run-1', 'draft_sha256': self.sha})
        self.assertEqual(reg.read_text(encoding='utf-8'), original)

    def test_publish_rejects_invalid_or_non_naver_urls(self):
        reg = self.root / 'content-system/registry/CONTENT_REGISTRY.csv'
        reg.parent.mkdir(parents=True, exist_ok=True)
        reg.write_text('content_id,status,published_url,published_date,title\nCNT-TEST,READY,,,테스트\n', encoding='utf-8')
        for bad_url in ['http://evil.com/123', 'https://blog.daum.net/123', 'https://blog.naver.com/invalid_no_post_id', 'javascript:alert(1)']:
            with self.assertRaises(ValueError):
                self.service.publish(self.cid, {'published_url': bad_url, 'run_id': 'run-1', 'draft_sha256': self.sha})

    def test_publish_rejects_missing_or_past_run_or_mismatched_hash(self):
        reg = self.root / 'content-system/registry/CONTENT_REGISTRY.csv'
        reg.parent.mkdir(parents=True, exist_ok=True)
        reg.write_text('content_id,status,published_url,published_date,title\nCNT-TEST,READY,,,테스트\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '과거 실행|유효하지 않은'):
            self.service.publish(self.cid, {'published_url': 'https://blog.naver.com/test/12345', 'draft_sha256': self.sha})
        with self.assertRaisesRegex(ValueError, '원고 해시'):
            self.service.publish(self.cid, {'published_url': 'https://blog.naver.com/test/12345', 'run_id': 'run-1'})
        with self.assertRaisesRegex(ValueError, '과거 실행'):
            self.service.publish(self.cid, {'published_url': 'https://blog.naver.com/test/12345', 'run_id': 'old-run-id', 'draft_sha256': self.sha})
        with self.assertRaisesRegex(ValueError, '원고 해시'):
            self.service.publish(self.cid, {'published_url': 'https://blog.naver.com/test/12345', 'run_id': 'run-1', 'draft_sha256': 'wrong-hash'})

    def test_publish_preserves_previous_url_when_updated(self):
        self.make_publish_ready()
        reg = self.root / 'content-system/registry/CONTENT_REGISTRY.csv'
        reg.parent.mkdir(parents=True, exist_ok=True)
        reg.write_text('content_id,status,published_url,published_date,title\nCNT-TEST,READY,,,테스트\n', encoding='utf-8')
        with patch('services.taiga_tracking.synchronize', return_value={}):
            self.service.publish(self.cid, {'published_url': 'https://blog.naver.com/test/111', 'published_date': '2026-10-19', 'run_id': 'run-1', 'draft_sha256': self.sha})
            state = self.service.publish(self.cid, {'published_url': 'https://blog.naver.com/test/222', 'published_date': '2026-10-20', 'run_id': 'run-1', 'draft_sha256': self.sha})
        self.assertEqual(state['published_url'], 'https://blog.naver.com/test/222')
        self.assertEqual(state['previous_published_url'], 'https://blog.naver.com/test/111')

    def make_publish_ready(self):
        latest = self.pipeline.latest(self.cid)
        latest.update(outcome='COMPLETED_READY', publish_ready=True, admin_checks=[],
                      official_review={'status': 'REVIEWED', 'draft_sha256': self.sha,
                                       'claims': [{'verdict': 'confirmed'}]},
                      approval={'reviewer': 'test-reviewer', 'draft_sha256': self.sha, 'resolutions': []})
        atomic(self.pipeline.work(self.cid)/'pipeline-latest.json', latest)


if __name__=='__main__':
    unittest.main()
