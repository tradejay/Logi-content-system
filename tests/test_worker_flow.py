import tempfile
import unittest
from pathlib import Path
from services.ide_worker_bridge import save
from services.worker_flow import monitor


class WorkerFlowTests(unittest.TestCase):
    def test_returns_are_counted_from_dispatched_work_not_claimed_rounds(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            registry = root / 'content-system/registry/CONTENT_REGISTRY.csv'
            registry.parent.mkdir(parents=True)
            registry.write_text('content_id,title\nCNT-TEST,테스트\n', encoding='utf-8')
            work = root / 'content-system/working/CNT-TEST'
            save(work / 'pipeline-latest.json', {'run_id': 'R1', 'draft_file': 'draft.md', 'draft_sha256': 'new', 'official_review': {'status': 'PENDING'}})
            run = work / 'runs/R1'
            save(run / 'official-corrections/round-1/writer-task.json', {'task_id': 'T1'})
            save(run / 'official-call.json', {'status': 'response_received', 'draft_sha256': 'old'})
            batch = root / 'worker-control/article-reruns/R1'
            save(batch / 'official-corrections.json', {'articles': {'CNT-TEST': {'round': 7, 'status': 'rewriting'}}})
            result = monitor('CNT-TEST', root)
            writer = next(n for n in result['nodes'] if n['id'] == 'writer')
            official = next(n for n in result['nodes'] if n['id'] == 'official')
            self.assertEqual(writer['returns'], 1)
            self.assertEqual(writer['state'], 'active')
            self.assertFalse(official['tasks'][0]['done'])
            self.assertEqual(result['edges'][-1]['count'], 1)
            with self.assertRaises(ValueError):
                monitor('../invalid', root)


if __name__ == '__main__':
    unittest.main()
