import tempfile
import unittest
from pathlib import Path
from services.ide_worker_bridge import save
from services.ide_task_monitor import task_view, snapshot


class IDEMonitorTests(unittest.TestCase):
    def test_existing_assignment_and_file_activity_do_not_imply_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            worker = root / 'worker-workspaces/06_system'
            save(root / 'worker-control/dispatch/tasks/TASK-1.json', {'task_id': 'TASK-1', 'worker': 'system', 'worker_folder': '06_system'})
            save(root / 'worker-control/notifications/06_system/TASK-1.json', {'status': 'notified', 'sent_at': 1})
            inbox = worker / 'inbox/TASK-1'
            save(inbox / 'task.json', {'task_id': 'TASK-1', 'ai_output': 'work/TASK-1/result.json'})
            save(inbox / 'input-manifest.json', {'files': []})
            (inbox / 'START.md').write_text('# 작업\n\n코드 수정\n\n필수 입력만 읽기:\n없음', encoding='utf-8')
            view = task_view('TASK-1', root)
            self.assertEqual(view['instruction'], '코드 수정')
            self.assertEqual(view['status'], 'notified')
            self.assertFalse(view['verified'])
            save(worker / 'work/TASK-1/result.json', {'status': 'done'})
            view = snapshot('TASK-1', root)['selected']
            self.assertEqual(view['status'], 'output_received')
            self.assertFalse(view['verified'])
            self.assertTrue(view['output_received'])
            with self.assertRaises(ValueError):
                task_view('../secret', root)
