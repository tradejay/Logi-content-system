import json
from pathlib import Path
import tempfile
import unittest
from scripts.prepare_worker_workspaces import LOCAL_TOOL, OWNED_STAGES


class WorkerIOTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);tool=self.root/'tools/worker_io.py';tool.parent.mkdir()
        tool.write_text(LOCAL_TOOL,encoding='utf-8')
        self.ns={'__file__':str(tool),'__name__':'test_local_tool'}
        exec(compile(LOCAL_TOOL,str(tool),'exec'),self.ns)
        (self.root/'worker.json').write_text(json.dumps({'worker_id':'TEST','owned_stages':['write']}),encoding='utf-8')

    def task(self,**overrides):
        inbox=self.root/'inbox/T1';inbox.mkdir(parents=True)
        data={'task_id':'T1','worker_id':'TEST','stage':'write','execution_type':'ide'}
        data.update(overrides)
        (inbox/'task.json').write_text(json.dumps(data),encoding='utf-8')

    def test_parent_absolute_and_other_worker_paths_rejected(self):
        for path in ['../other/work/result.md',str(self.root.parent/'outside'), 'work/../../outside']:
            with self.assertRaises(ValueError):self.ns['inside'](path)

    def test_local_report_and_hash_and_no_overwrite(self):
        self.task()
        work=self.root/'work/T1';work.mkdir(parents=True);(work/'result.md').write_text('result')
        r=self.ns['submit']('T1','completed','done',['work/T1/result.md'])
        self.assertEqual(r['artifacts'][0]['bytes'],6)
        self.assertFalse(r['publication_approved'])
        with self.assertRaises(ValueError):self.ns['submit']('T1','completed','again',[])

    def test_artifacts_outside_task_rejected(self):
        self.task()
        with self.assertRaises(ValueError):self.ns['submit']('T1','completed','bad',['worker.json'])

    def test_wrong_stage_rejected(self):
        self.task(stage='feedback')
        with self.assertRaises(ValueError):self.ns['submit']('T1','completed','bad',[])

    def test_api_task_rejected(self):
        self.task(execution_type='api')
        with self.assertRaises(ValueError):self.ns['submit']('T1','completed','bad',[])

    def test_execution_ownership_is_unique(self):
        stages=[s for owned in OWNED_STAGES.values() for s in owned]
        self.assertEqual(len(stages),len(set(stages)))


if __name__=='__main__':unittest.main()
