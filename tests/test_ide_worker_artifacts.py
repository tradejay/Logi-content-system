import hashlib
import tempfile
from pathlib import Path
import unittest
from services.ide_worker_bridge import save,load,verify_report
from services.ide_worker_artifacts import finalize,review_packet
from services.ide_test_review import handoff
from services.ide_edit_task import prepare
from services.ide_review_status import sync


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.worker=Path(self.tmp.name)
        self.before=[{'id':'B1','markdown':'조건 A이면 대안 B를 사용합니다.','claim_ids':['C1']},
                     {'id':'B2','markdown':'유지 문단','claim_ids':[]}]
        save(self.worker/'inbox/T/blocks.json',{'blocks':self.before})
        save(self.worker/'inbox/T/claims.json',{'claims':[{'id':'C1','text':'조건 A이면 대안 B','fact_ids':['F1']}]})
        save(self.worker/'inbox/T/manifest.json',{'files':[]})
        self.task={'task_id':'T','worker_id':'W','stage':'naver_edit','execution_type':'ide',
            'content_id':'CONTENT','output_protocol':'content_only_v1','ai_output':'work/T/naver_edit/result.json',
            'system_inputs':{'blocks':'inbox/T/blocks.json','claims':'inbox/T/claims.json'},
            'input_manifest':'inbox/T/manifest.json','required_outputs':['work/T/naver_edit/edited.md']}
        save(self.worker/'inbox/T/task.json',self.task)

    def result(self,blocks):save(self.worker/'work/T/naver_edit/result.json',{'blocks':blocks})

    def test_system_assembles_claims_diff_and_valid_report(self):
        self.result([{'id':'B1','markdown':'조건 A이면\n대안 B를 사용합니다.'},{'id':'B2','markdown':'유지 문단'}])
        self.assertTrue(finalize(self.worker,'T',self.task))
        output=self.worker/'work/T/naver_edit'
        self.assertEqual(load(output/'claim-map.json')['claims'][0]['text'],'조건 A이면\n대안 B')
        self.assertEqual(len(load(output/'changes.json')['changes']),1)
        report=verify_report(self.worker,'T',self.task)
        self.assertEqual(report['generated_by'],'system')
        self.assertTrue(finalize(self.worker,'T',self.task))

    def test_missing_block_rejected_without_report(self):
        self.result([{'id':'B1','markdown':'조건 A이면 대안 B를 사용합니다.'}])
        with self.assertRaises(ValueError):finalize(self.worker,'T',self.task)
        self.assertFalse((self.worker/'outbox/T/report.json').exists())

    def test_semantic_claim_rewrite_is_not_inferred(self):
        self.result([{'id':'B1','markdown':'조건 A이어도 대안 B를 사용합니다.'},{'id':'B2','markdown':'유지 문단'}])
        with self.assertRaises(ValueError):finalize(self.worker,'T',self.task)

    def test_review_input_includes_unchanged_text_once(self):
        after=[{**self.before[0],'markdown':'조건 A이면\n대안 B를 사용합니다.'},self.before[1]]
        packet=review_packet(self.before,after)
        self.assertIn('before',packet['blocks'][0]);self.assertNotIn('before',packet['blocks'][1])
        self.assertEqual(packet['blocks'][1]['edited'],'유지 문단')

    def test_review_handoff_only_content_and_style_inputs(self):
        root=self.worker
        writer=root/'worker-workspaces/writer';reviewer=root/'worker-workspaces/review'
        save(writer/'inbox/T/task.json',{'test_only':True,'content_id':'C','policy_snapshot':'P',
            'output_protocol':'content_only_v1','system_inputs':{'blocks':'inbox/T/blocks.json'},
            'test_review_handoff':{'enabled':True,'worker_folder':'review','edited_artifacts':{'edited-blocks.json':'work/T/edited.json'}}})
        save(writer/'inbox/T/blocks.json',{'blocks':self.before})
        save(writer/'work/T/edited.json',{'blocks':self.before})
        (writer/'inbox/T/style-guide.md').write_text('가이드',encoding='utf-8')
        save(reviewer/'worker.json',{'worker_id':'R','owned_stages':['feedback']})
        rid=handoff('writer','T',{'status':'collected','result_status':'completed'},root)
        manifest=load(reviewer/'inbox'/rid/'input-manifest.json')
        self.assertEqual(len(manifest['files']),2)
        packet=load(reviewer/'inbox'/rid/'review-input.json')
        self.assertNotIn('before',packet['blocks'][0])
        self.assertEqual(load(reviewer/'inbox'/rid/'task.json')['output_protocol'],'content_only_v1')

    def test_new_task_asks_for_one_content_file_without_evidence_bundle(self):
        root=self.worker;cid='C';run=root/'run'
        draft='\n\n'.join(b['markdown'] for b in self.before)
        p=root/'content-system/02_writer_ai/drafts/C.draft.md';p.parent.mkdir(parents=True);p.write_text(draft,encoding='utf-8')
        save(root/'content-system/working/C/pipeline-latest.json',{'run_directory':str(run)})
        save(run/'revisions/r1.writer-metadata.json',{'blocks':self.before})
        save(run/'revisions/r1.claim-map.json',{'claims':[{'id':'C1','text':'조건 A이면 대안 B','fact_ids':['F1']}]})
        worker=root/'worker-workspaces/03_writing_editing'
        save(worker/'resources/latest.json',{'snapshot_id':'P'})
        tid=prepare(root,cid)
        task=load(worker/'inbox'/tid/'task.json')
        self.assertEqual(task['output_protocol'],'content_only_v1')
        packet=load(worker/'inbox'/tid/'editing-input.json')
        self.assertEqual(packet['blocks'][0]['protected_phrases'],['조건 A이면 대안 B'])
        self.assertFalse((worker/'inbox'/tid/'fact-bundle.json').exists())

    def test_collected_review_updates_preview_status(self):
        root=self.worker;reviewer=root/'worker-workspaces/review'
        save(reviewer/'inbox/T-REVIEW/task.json',{'stage':'feedback'})
        save(reviewer/'work/T-REVIEW/feedback/review.json',{'passed':True,'issues':[]})
        page=root/'static/experiments/naver-ide-full/T/index.html';page.parent.mkdir(parents=True)
        page.write_text('<span id="review-status">독립 리뷰 대기</span>',encoding='utf-8')
        sync('review','T-REVIEW',{'status':'collected','result_status':'completed'},root)
        self.assertIn('독립 리뷰 통과',page.read_text(encoding='utf-8'))
        self.assertTrue(load(page.parent/'review.json')['passed'])


if __name__=='__main__':unittest.main()
