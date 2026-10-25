import json
from pathlib import Path
import tempfile
import unittest

from services.policy_manager import PolicyManager, PolicyError, PolicyConflict, write
from services.guide_repository import GuideRepository, IntegrityError

ROOT = Path(__file__).resolve().parents[1]


class PolicyManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.authoring = self.root / 'content-system/02_writer_ai/authoring'
        write(self.authoring / 'rules/registry.json', {'rules': [
            {'id': 'RULE-TEST', 'version': '1.0.0', 'path': 'test.md', 'stages': ['write', 'feedback']} ]})
        write(self.authoring / 'guide-registry.json', {'guides': [
            {'id': 'GUIDE-TEST', 'path': 'test-guide.md', 'kind': 'stage', 'description': 'test', 'stages': ['write']} ]})
        (self.authoring / 'rules/test.md').write_text('# Evidence\n\n근거를 확인한다.\n\n사례를 만들지 않는다.\n', encoding='utf-8')
        (self.authoring / 'test-guide.md').write_text('# Guide\n\n독자 질문에 답한다.\n', encoding='utf-8')
        (self.authoring / 'prompts').mkdir()
        for stage in ('strategy', 'write', 'feedback', 'official'):
            (self.authoring / f'prompts/{stage}.md').write_text(
                (ROOT / f'content-system/02_writer_ai/authoring/prompts/{stage}.md').read_text(encoding='utf-8-sig'), encoding='utf-8')
        self.manager = PolicyManager(self.root)
        self.state = self.manager.load()

    def tearDown(self):
        self.tmp.cleanup()

    def atom(self):
        return next(a for a in self.state['atoms'] if a['target'] == 'RULE-TEST' and a['kind'] != 'reference')

    def test_roundtrip_preserves_source_and_edit_compiles(self):
        source = (self.authoring / 'rules/test.md').read_text(encoding='utf-8')
        self.assertEqual(self.manager.assemble(self.state)['content-system/02_writer_ai/authoring/rules/test.md'], source)
        self.manager.save(self.atom()['id'], {'text': '공식 근거를 먼저 확인한다.', 'review_note': '문체 수정'}, 1)
        preview = self.manager.preview()
        self.assertTrue(preview['validation']['valid'])
        self.assertIn('공식 근거를 먼저', preview['documents']['content-system/02_writer_ai/authoring/rules/test.md'])
        self.assertEqual((self.authoring / 'rules/test.md').read_text(encoding='utf-8'), source)
        self.assertEqual(len(self.manager.load()['history']), 1)
        self.assertTrue((self.manager.directory / 'history/workspace-000002.json').exists())

    def test_concurrent_edits_and_unknown_fields_rejected(self):
        self.manager.save(self.atom()['id'], {'text': '수정', 'review_note': '검토'}, 1)
        with self.assertRaises(PolicyConflict):
            self.manager.save(self.atom()['id'], {'text': '오래된 수정', 'review_note': '검토'}, 1)
        with self.assertRaises(PolicyError):
            self.manager.save(self.atom()['id'], {'source': '/outside'}, 2)
        with self.assertRaises(PolicyError):
            self.manager.save(self.atom()['id'], {'stages': ['official'], 'review_note': '변경'}, 2)

    def test_new_policy_is_scoped_to_prompt(self):
        self.manager.create({'title': '짧은 문단', 'text': '문단을 짧게 쓴다.', 'stages': ['write'], 'review_note': '편집 지시'}, 1)
        files = self.manager.preview()['documents']
        self.assertIn('문단을 짧게 쓴다.', files['content-system/02_writer_ai/authoring/prompts/write.md'])
        self.assertNotIn('문단을 짧게 쓴다.', files['content-system/02_writer_ai/authoring/prompts/official.md'])

    def test_opposing_same_scope_blocks_build(self):
        base = {'title': '대상', 'text': '행위', 'subject': 'writer', 'action': 'render', 'object': 'image', 'review_note': '검토', 'stages': ['write']}
        self.manager.create({**base, 'kind': 'require'}, 1)
        self.manager.create({**base, 'kind': 'prohibit'}, 2)
        self.assertFalse(self.manager.preview()['validation']['valid'])
        with self.assertRaises(PolicyConflict):
            self.manager.build(3, 'owner', '검토')

    def test_stage_disjoint_is_not_conflict(self):
        base = {'title': '대상', 'text': '행위', 'subject': 'writer', 'action': 'render', 'object': 'image', 'review_note': '검토'}
        self.manager.create({**base, 'kind': 'require', 'stages': ['write']}, 1)
        self.manager.create({**base, 'kind': 'prohibit', 'stages': ['official']}, 2)
        self.assertTrue(self.manager.preview()['validation']['valid'])

    def test_split_keeps_old_revision_and_replaces_slot(self):
        old = self.atom()
        self.manager.split(old['id'], ['첫 번째 지시.', '두 번째 지시.'], 1, '독립 지시로 분리')
        state = self.manager.load()
        self.assertFalse(next(a for a in state['atoms'] if a['id'] == old['id'])['enabled'])
        body = self.manager.assemble(state)['content-system/02_writer_ai/authoring/rules/test.md']
        self.assertIn('첫 번째 지시.\n\n두 번째 지시.', body)
        self.assertNotIn(old['text'], body)

    def test_response_contract_change_and_unwired_evaluator_block(self):
        atom = next(a for a in self.state['atoms'] if a['target'] == 'PROMPT-WRITE' and 'JSON 객체만 반환한다:' in a['text'])
        self.manager.save(atom['id'], {'text': atom['text'].replace('claims(array)', 'new_field(array)'), 'review_note': '계약 변경'}, 1)
        self.assertFalse(self.manager.preview()['validation']['valid'])

    def test_source_drift_detected(self):
        (self.authoring / 'rules/test.md').write_text('외부 변경', encoding='utf-8')
        self.assertFalse(self.manager.preview()['validation']['valid'])

    def test_candidate_integrity_and_activation_guards(self):
        record = self.manager.build(1, 'owner', '관련 지시와 출력 계약 대조')
        repo = GuideRepository(self.root)
        self.assertIsNone(repo.get_active_release_id())
        manifest = repo.verify_release(record['release_id'])
        self.assertIn('policy-snapshot.json', manifest.prompts)
        with self.assertRaises(PolicyConflict):
            self.manager.activate(record['release_id'], 'stale')
        self.manager.activate(record['release_id'], None)
        self.assertEqual(repo.get_active_release_id(), record['release_id'])
        snapshot = repo.releases_dir / record['release_id'] / 'prompts/policy-snapshot.json'
        snapshot.write_text('{}', encoding='utf-8')
        with self.assertRaises(IntegrityError):
            repo.verify_release(record['release_id'])

    def test_candidate_becomes_stale_after_edit(self):
        record = self.manager.build(1, 'owner', '검토')
        self.manager.save(self.atom()['id'], {'text': '새 수정', 'review_note': '변경'}, 1)
        with self.assertRaises(PolicyConflict):
            self.manager.activate(record['release_id'], None)

    def test_assembled_policy_is_consumed_by_runtime_prompt_repository(self):
        from services.prompt_repository import LocalPromptRepository
        self.manager.create({'title': '문단 길이', 'text': '문단을 짧게 쓴다.',
                             'stages': ['write'], 'review_note': '집필 지시 추가'}, 1)
        candidate = self.manager.build(2, 'owner', '단계 범위와 응답 계약 확인')
        repo = GuideRepository(self.root)
        manifest = repo.verify_release(candidate['release_id'])
        prompts = LocalPromptRepository(repo.releases_dir / candidate['release_id'] / 'prompts', manifest)
        self.assertIn('문단을 짧게 쓴다.', prompts.get_prompt('write')[0])
        self.assertNotIn('문단을 짧게 쓴다.', prompts.get_prompt('official')[0])
        self.assertNotIn('문단을 짧게 쓴다.', (self.authoring / 'prompts/write.md').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
