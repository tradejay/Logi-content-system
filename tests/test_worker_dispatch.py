import tempfile
from pathlib import Path
from unittest.mock import patch
import unittest
from services.ide_worker_bridge import save,load
from services.worker_dispatch import enqueue,status,naver_url


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        save(self.root/'worker-control/dispatch-presets.json',{'roles':{'review':{'folder':'reviewer','stage':'feedback'}}})
        save(self.root/'worker-workspaces/reviewer/worker.json',{'worker_id':'R'})
        self.source=self.root/'post.md';self.source.write_text('게시글 내용',encoding='utf-8')

    def test_fixed_route_and_content_only_contract(self):
        r=enqueue('review','문단 검토',[self.source],root=self.root)
        worker=self.root/'worker-workspaces/reviewer';task=load(worker/'inbox'/r['task_id']/'task.json')
        self.assertEqual(task['stage'],'feedback');self.assertEqual(task['output_protocol'],'content_only_v1')
        self.assertEqual((worker/'inbox'/r['task_id']/'input-1.md').read_text(encoding='utf-8'),'게시글 내용')

    def test_short_status_returns_only_first_three_issues(self):
        record=enqueue('review','문단 검토',[self.source],root=self.root)
        worker=self.root/'worker-workspaces/reviewer';task=load(worker/'inbox'/record['task_id']/'task.json')
        save(worker/task['ai_output'],{'passed':False,'issues':[{'reason':str(i)} for i in range(5)]})
        with patch('services.worker_dispatch.process',return_value={'status':'collected'}):result=status(root=self.root)
        self.assertEqual(result['issues_count'],5);self.assertEqual(len(result['issues']),3)

    def test_external_and_config_input_rejected(self):
        path=self.root/'config/config.json';save(path,{'key':'not-a-real-key'})
        with self.assertRaises(ValueError):enqueue('review','review',[path],root=self.root)

    def test_post_url_allowlist(self):
        self.assertEqual(naver_url('https://blog.naver.com/oceantech01/224440463862')[0],'https://blog.naver.com/oceantech01/224440463862')
        for url in ['http://127.0.0.1/a','https://example.com/a','https://blog.naver.com/profile']:
            with self.assertRaises(ValueError):naver_url(url)

    def test_no_tasks_is_short_status(self):self.assertEqual(status(root=self.root),{'status':'no_tasks'})


if __name__=='__main__':unittest.main()
