import tempfile
import unittest
from pathlib import Path
from scripts.backup_pipeline_state import create_backup, verify_backup, restore_backup, compute_bytes_sha256


class PipelineBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        
        # Setup mock project directory structure
        cs = self.root / 'content-system'
        (cs / 'registry').mkdir(parents=True, exist_ok=True)
        (cs / '02_writer_ai/drafts').mkdir(parents=True, exist_ok=True)
        (cs / 'working/CNT-2026W39-001/runs/run-1').mkdir(parents=True, exist_ok=True)
        
        self.reg_csv = cs / 'registry/CONTENT_REGISTRY.csv'
        self.reg_csv.write_text('content_id,status\nCNT-2026W39-001,REVISION_REQUIRED\n', encoding='utf-8')
        
        self.draft = cs / '02_writer_ai/drafts/CNT-2026W39-001.draft.md'
        self.draft.write_text('# Test Draft Content\n', encoding='utf-8')
        
        self.latest = cs / 'working/CNT-2026W39-001/pipeline-latest.json'
        self.latest.write_text('{"run_id": "run-1", "outcome": "REVISION_REQUIRED"}', encoding='utf-8')
        
        self.run_artifact = cs / 'working/CNT-2026W39-001/runs/run-1/draft.json'
        self.run_artifact.write_text('{"text": "artifact"}', encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def test_backup_create_verify_and_restore(self):
        backup_root = self.root / 'audit/backups'
        bid, bpath, manifest = create_backup(
            root=self.root,
            target_cids=['CNT-2026W39-001'],
            backup_id='test-bk-1',
            backup_root=backup_root
        )

        self.assertEqual(bid, 'test-bk-1')
        self.assertTrue((bpath / 'manifest.json').exists())
        self.assertEqual(len(manifest['files']), 4)

        # 1. Verify backup
        ver = verify_backup(bpath, root=self.root)
        self.assertTrue(ver['valid'])
        self.assertEqual(ver['checked'], 4)

        # 2. Modify files
        original_draft_sha = compute_bytes_sha256(self.draft)
        self.draft.write_text('# Modified Externally\n', encoding='utf-8')
        modified_draft_sha = compute_bytes_sha256(self.draft)
        self.assertNotEqual(original_draft_sha, modified_draft_sha)

        # 3. Dry-run restore
        plan = restore_backup(bpath, root=self.root, dry_run=True)
        draft_item = next(p for p in plan if 'draft.md' in p['relative_path'])
        self.assertEqual(draft_item['status'], 'MODIFIED')
        self.assertEqual(compute_bytes_sha256(self.draft), modified_draft_sha)

        # 4. Actual restore (apply)
        restore_backup(bpath, root=self.root, dry_run=False)
        self.assertEqual(compute_bytes_sha256(self.draft), original_draft_sha)
        self.assertEqual(self.draft.read_text(encoding='utf-8'), '# Test Draft Content\n')


if __name__ == '__main__':
    unittest.main()
