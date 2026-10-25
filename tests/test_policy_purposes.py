import unittest
from tests import test_policy_manager as fixtures
from services.policy_normalization import normalize
from services.policy_purposes import classify, partition


class PolicyPurposeTests(unittest.TestCase):
    setUp = fixtures.PolicyManagerTests.setUp
    tearDown = fixtures.PolicyManagerTests.tearDown

    def test_constraints_take_priority_over_editorial_design(self):
        atom={'domain':'editorial','kind':'require','text':'쉬운 말로 쓰되 지원 조건을 보존한다.', 'target':'GUIDE-03-STRUCTURE'}
        self.assertEqual(classify(atom)[0], 'runtime_guardrail')
        atom['text']='도입에서 문제를 소개하고 마감에서 다음 행동을 안내한다.'
        self.assertEqual(classify(atom)[0], 'template_design')

    def test_contract_and_reference_are_separate(self):
        atom={'domain':'response-contract','kind':'require','text':'JSON 객체만 반환한다.', 'target':'PROMPT-WRITE'}
        self.assertEqual(classify(atom)[0], 'runtime_contract')
        atom.update(entry_type='source',text='Version: 1.0.0')
        self.assertEqual(classify(atom)[0], 'reference')

    def test_partition_preserves_runtime_documents_and_is_versioned(self):
        normalize(self.manager, 1)
        before = self.manager.preview()['documents']
        state=partition(self.manager, 2)
        self.assertEqual(state['revision'], 3)
        self.assertEqual(before, self.manager.preview()['documents'])
        self.assertTrue((self.manager.directory/'collections/template_design.json').exists())
        self.assertTrue(self.manager.preview()['validation']['valid'])
        self.assertEqual(partition(self.manager,3)['revision'],3)
        atom=next(a for a in state['atoms'] if not a.get('retired_by') and a['kind']!='reference')
        self.manager.save(atom['id'],{'purpose':'template_design','review_note':'용도 검토'},3)
