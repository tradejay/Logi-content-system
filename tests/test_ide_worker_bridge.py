import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from services.ide_worker_bridge import process, save, file_activity


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.worker = self.root / 'worker-workspaces/writer'
        save(self.worker / 'worker.json', {'worker_id':'W','owned_stages':['naver_edit'],'conversation_id':'C'})
        self.task = {'task_id':'T','worker_id':'W','stage':'naver_edit','execution_type':'ide',
                     'notification':{'enabled':True},'input_manifest':'inbox/T/manifest.json',
                     'required_outputs':['work/T/result.md']}
        save(self.worker / 'inbox/T/task.json', self.task)
        save(self.worker / 'inbox/T/manifest.json', {'files':[]})
        worker = self.worker
        class FakeAPI:
            sends = 0
            def metadata(self, cid):
                return {'response':{'conversationMetadata':{'metadata':{
                    'workspaces':[{'workspaceFolderAbsoluteUri':worker.as_uri()}]}}}}
            def send(self, cid, message): self.sends += 1
        self.api = FakeAPI()

    def test_no_duplicate_notification(self):
        self.assertEqual(process('writer','T',self.api,self.root)['status'],'notified')
        process('writer','T',self.api,self.root)
        self.assertEqual(self.api.sends,1)

    def test_non_opt_in_task_not_sent(self):
        self.task['notification']['enabled'] = False
        save(self.worker / 'inbox/T/task.json',self.task)
        with self.assertRaises(ValueError): process('writer','T',self.api,self.root)
        self.assertEqual(self.api.sends,0)

    def test_superseded_task_not_sent(self):
        save(self.root/'worker-control/superseded-tasks.json',{'tasks':[{'worker_folder':'writer','task_id':'T'}]})
        self.assertEqual(process('writer','T',self.api,self.root)['status'],'superseded')
        self.assertEqual(self.api.sends,0)

    def report(self):
        p = self.worker / 'work/T/result.md'; p.parent.mkdir(parents=True); p.write_text('result')
        raw = p.read_bytes()
        data = {'task_id':'T','worker_id':'W','stage':'naver_edit','execution_type':'ide',
                'status':'completed','publication_approved':False,
                'input_sha256':hashlib.sha256((self.worker/'inbox/T/task.json').read_bytes()).hexdigest(),
                'artifacts':[{'path':'work/T/result.md','sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}]}
        save(self.worker / 'outbox/T/report.json',data)
        return p

    def test_collect_valid_report_without_sending(self):
        self.report()
        self.assertEqual(process('writer','T',self.api,self.root)['status'],'collected')
        self.assertEqual(self.api.sends,0)

    def test_modified_output_rejected(self):
        self.report().write_text('changed')
        with self.assertRaises(ValueError): process('writer','T',self.api,self.root)

    def test_activity_uses_file_timestamp_and_has_quiet_state(self):
        latest=file_activity(self.worker)
        self.assertEqual(latest['signal'],'recent_file_changes')
        quiet=file_activity(self.worker,now=latest['latest_modified_at']+121)
        self.assertEqual(quiet['signal'],'no_recent_file_changes')


if __name__ == '__main__': unittest.main()
