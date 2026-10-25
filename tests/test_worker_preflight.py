import json
from pathlib import Path
import tempfile
import unittest
from services.worker_preflight import inspect_worker, outstanding


class WorkerPreflightTest(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[1] / 'scratch'
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = '02_research_planning'
        self.worker = self.root / 'worker-workspaces' / self.folder
        self.worker.mkdir(parents=True)
        (self.worker / 'worker.json').write_text(json.dumps({'worker_id':'TEST','conversation_id':'test-id','owned_stages':['strategy']}))
        self.route = {'folder':self.folder,'stage':'strategy'}

    def metadata(self, path):
        return {'response':{'conversationMetadata':{'metadata':{'workspaces':[{'workspaceFolderAbsoluteUri':path.as_uri()}]}}}}

    def test_connected_is_not_workspace_valid(self):
        row = inspect_worker('planner',self.route,self.root,lambda _:self.metadata(self.root))
        self.assertTrue(row['connected'])
        self.assertFalse(row['can_dispatch'])

    def test_no_activity_does_not_clear_unfinished_delivery(self):
        tid = 'TEST-1'
        inbox = self.worker / 'inbox' / tid
        inbox.mkdir(parents=True)
        (inbox/'task.json').write_text(json.dumps({'ai_output':f'work/{tid}/result.json'}))
        notifications = self.root / 'worker-control/notifications' / self.folder
        notifications.mkdir(parents=True)
        (notifications/f'{tid}.json').write_text(json.dumps({'status':'notified'}))
        row=inspect_worker('planner',self.route,self.root,lambda _:self.metadata(self.worker))
        self.assertFalse(row['can_dispatch'])
        self.assertEqual(row['runtime_busy'],'unknown')
        output=self.worker/'work'/tid/'result.json';output.parent.mkdir(parents=True);output.write_text('{}')
        self.assertEqual(outstanding(self.root,self.folder),[])
        self.assertTrue(inspect_worker('planner',self.route,self.root,lambda _:self.metadata(self.worker))['can_dispatch'])

    def test_failure_does_not_expose_error_or_send_message(self):
        def fail(_):
            raise RuntimeError('SECRET_CSRF_VALUE')
        row=inspect_worker('planner',self.route,self.root,fail)
        self.assertNotIn('SECRET_CSRF_VALUE',json.dumps(row))
        self.assertFalse(row['can_dispatch'])
        self.assertEqual(row['browser_capability'],'not_probed')


if __name__=='__main__':
    unittest.main()
