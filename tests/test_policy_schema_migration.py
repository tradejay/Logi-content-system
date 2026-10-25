import unittest
from pathlib import Path
import tempfile
import json

from services.policy_manager import PolicyManager, write
from services.policy_schema_migration import migrate_to_v2

ROOT = Path(__file__).resolve().parents[1]

class TestSchemaMigration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.authoring = self.root / 'content-system/02_writer_ai/authoring'
        write(self.authoring / 'rules/registry.json', {'rules': [
            {'id': 'RULE-TEST', 'version': '1.0.0', 'path': 'test.md', 'stages': ['write', 'feedback']} ]})
        write(self.authoring / 'guide-registry.json', {'guides': [
            {'id': 'GUIDE-TEST', 'path': 'test-guide.md', 'kind': 'stage', 'description': 'test', 'stages': ['write']} ]})
        (self.authoring / 'rules/test.md').write_text('# Evidence\n\n근거를 확인한다.\n', encoding='utf-8')
        (self.authoring / 'test-guide.md').write_text('# Guide\n\n독자 질문에 답한다.\n', encoding='utf-8')
        (self.authoring / 'prompts').mkdir()
        for stage in ('strategy', 'write', 'feedback', 'official'):
            (self.authoring / f'prompts/{stage}.md').write_text(
                (ROOT / f'content-system/02_writer_ai/authoring/prompts/{stage}.md').read_text(encoding='utf-8-sig'), encoding='utf-8')
        self.manager = PolicyManager(self.root)
        self.manager.ensure()

    def tearDown(self):
        self.tmp.cleanup()

    def test_migrate_to_v2_preserves_content_and_adds_fields(self):
        state_before = self.manager.load()
        self.assertEqual(state_before.get('schema_version'), 1)
        before_assembled = self.manager.assemble(state_before)

        state_after = migrate_to_v2(self.manager, 1)
        self.assertEqual(state_after.get('schema_version'), 2)
        self.assertEqual(state_after['revision'], 2)
        after_assembled = self.manager.assemble(state_after)
        self.assertEqual(before_assembled, after_assembled)

        for a in state_after['atoms']:
            self.assertIn('condition', a)
            self.assertIn('exception', a)
            self.assertIn('relations', a)
            self.assertIn('sub_aspects', a)
            self.assertIn('semantic_review_status', a)

        # Idempotent
        state_idempotent = migrate_to_v2(self.manager, 2)
        self.assertEqual(state_idempotent['revision'], 2)

if __name__ == '__main__':
    unittest.main()
