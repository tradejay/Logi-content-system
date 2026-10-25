import contextlib
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from services.taiga_workflow import TaigaWorkflow, sha
from services.content_pipeline import ContentPipeline


class FakeClient:
    base = 'http://127.0.0.1:9000/api/v1'
    def __init__(self):
        self.stories = {}
    def request(self, method, path, payload=None, **kwargs):
        if method == 'POST':
            ident = len(self.stories) + 1
            item = {**payload, 'id': ident, 'ref': ident, 'version': 1}
            self.stories[ident] = item
        else:
            item = self.stories[int(path.split('/')[-1])]
            if method == 'PATCH':
                if payload['version'] != item['version']:
                    raise ValueError('Conflict')
                item.update(payload)
                item['version'] += 1
        return copy.deepcopy(item)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pipeline = object.__new__(ContentPipeline)
        self.pipeline.root = self.root
        self.pipeline.system = self.root / 'content-system'
        self.cid = 'CNT-TEST'
        p = self.pipeline.draft_path(self.cid)
        p.parent.mkdir(parents=True)
        p.write_text('원래 원고', encoding='utf-8')
        from services.content_pipeline import atomic
        atomic(self.pipeline.work(self.cid)/'pipeline-latest.json', {'run_id':'old', 'outcome':'COMPLETED_READY',
            'publish_ready':True, 'approval':{'reviewer':'old'}, 'draft_file':str(p), 'draft_sha256':sha('원래 원고')})
        self.client = FakeClient()
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        states = {name:index for index,name in enumerate(['대기','진행 중','검토 대기','막힘','완료','변경 검토'])}
        self.workflow = TaigaWorkflow(self.root, self.client, self.db, {'id':1,'slug':'test'}, states, [],
                                      pipeline_factory=lambda **kw:self.pipeline)
        self.task = {'key':'content:'+self.cid, 'category':'글','state':'검토 대기','refs':{'content_id':self.cid}}

    def test_editor_save_versions_invalidates_approval_and_is_idempotent(self):
        self.workflow.editor(self.task)
        editor = self.client.stories[1]
        editor['description'] = '수정 원고'
        editor['version'] += 1
        with patch.object(self.pipeline, 'lock', return_value=contextlib.nullcontext()):
            self.workflow.editor(self.task)
            self.workflow.editor(self.task)
        result = self.pipeline.latest(self.cid)
        self.assertEqual(self.pipeline.draft_path(self.cid).read_text(encoding='utf-8'), '수정 원고')
        self.assertFalse(result['publish_ready'])
        self.assertIsNone(result['approval'])
        self.assertEqual(self.task['state'], '변경 검토')
        self.assertEqual(len(list((self.pipeline.work(self.cid)/'edits').glob('*.json'))),1)

    def test_concurrent_source_edit_is_not_overwritten(self):
        self.workflow.editor(self.task)
        self.pipeline.draft_path(self.cid).write_text('다른 IDE 원고',encoding='utf-8')
        self.client.stories[1].update(description='Taiga 수정',version=2)
        self.workflow.editor(self.task)
        self.assertEqual(self.pipeline.draft_path(self.cid).read_text(encoding='utf-8'),'다른 IDE 원고')
        self.assertEqual(self.client.stories[1]['description'],'Taiga 수정')

    def test_complete_is_blocked_without_current_approval(self):
        self.workflow.editor(self.task)
        with patch.object(self.pipeline,'assert_publishable',side_effect=ValueError('승인 필요')):
            self.workflow.process(self.task,{'status':4,'version':1})
        self.assertNotEqual(self.task['state'],'완료')
        self.assertIn('완료 요청 보류',self.task['workflow_note'])

    def test_move_image_to_done_does_not_approve(self):
        task={'key':'image:1','category':'이미지','state':'검토 대기','refs':{'draft_sha256':'hash'},'summary':{}}
        self.workflow.image_review(task,{'status':4,'version':1,'description':''})
        self.assertEqual(task['state'],'검토 대기')
        self.assertIn('완료 이동만으로 승인할 수 없습니다',task['workflow_note'])

    def test_review_json_is_read_after_instructions(self):
        task={'key':'image:1','category':'이미지','state':'검토 대기','refs':{},'summary':{}}
        story={'status':2,'version':1,'description':'## 이미지 검토 입력\n설명\n```json\n'+json.dumps({'decision':'reject','review_note':'오류'})+'\n```'}
        with patch.object(self.workflow,'apply_image') as apply:
            self.workflow.image_review(task,story)
        self.assertEqual(apply.call_args.args[1]['decision'],'reject')
        self.assertEqual(task['state'],'반려')

    def test_image_rejection_updates_registry_and_queue_without_approval(self):
        import yaml
        registry=self.root/'content-system/assets'/self.cid/'assets.yaml'
        registry.parent.mkdir(parents=True)
        registry.write_text(yaml.safe_dump({'assets':[{'asset_id':'AST-1','need_id':'NEED-1','review_status':'candidate'}]}),encoding='utf-8')
        queue=self.root/'content-system/queue/asset.queue.yaml'
        queue.parent.mkdir(parents=True)
        queue.write_text(yaml.safe_dump({'ready':[],'review':['IMG-1'],'jobs':{'IMG-1':{
            'content_id':self.cid,'need_id':'NEED-1','draft_sha256':sha('원래 원고'),'status':'pending_review'}}}),encoding='utf-8')
        task={'refs':{'job_id':'IMG-1'}}
        self.workflow.apply_image(task,{'decision':'reject','asset_id':'AST-1',
            'draft_sha256':sha('원래 원고'),'review_note':'수치 표현 오류'})
        self.assertEqual(yaml.safe_load(registry.read_text(encoding='utf-8'))['assets'][0]['review_status'],'rejected')
        state=yaml.safe_load(queue.read_text(encoding='utf-8'))
        self.assertEqual(state['jobs']['IMG-1']['status'],'rejected')
        self.assertNotIn('IMG-1',state['review'])

    def test_stale_image_cannot_be_approved(self):
        import yaml
        queue=self.root/'content-system/queue/asset.queue.yaml'
        queue.parent.mkdir(parents=True)
        queue.write_text(yaml.safe_dump({'jobs':{'IMG-1':{'content_id':self.cid,'draft_sha256':sha('이전 원고')}}}),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'원고가 변경'):
            self.workflow.apply_image({'refs':{'job_id':'IMG-1'}},{'decision':'approve','draft_sha256':sha('이전 원고')})


if __name__ == '__main__':
    unittest.main()
