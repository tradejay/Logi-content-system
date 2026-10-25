import unittest
from tests import test_policy_manager as fixtures
from services.policy_normalization import normalize, pieces


class PolicyNormalizationTests(unittest.TestCase):
    setUp = fixtures.PolicyManagerTests.setUp
    tearDown = fixtures.PolicyManagerTests.tearDown
    def test_normalization_preserves_documents_and_history(self):
        before = self.manager.preview()['documents']
        state = normalize(self.manager, 1)
        self.assertEqual(before, self.manager.assemble(state))
        self.assertEqual(state['revision'], 2)
        self.assertTrue(all(a['stages'] == [] for a in state['atoms'] if a.get('entry_type') == 'source'))
        self.assertTrue(self.manager.preview()['validation']['valid'])
        self.assertTrue(any(a.get('entry_type') == 'policy' and a['target'] == 'PROMPT-WRITE' for a in state['atoms']))
        self.assertTrue(any(a.get('retired_by') for a in state['atoms']))
        self.assertEqual(normalize(self.manager, 2)['revision'], 2)

    def test_normalization_keeps_user_added_policy_once(self):
        self.manager.create({'title': '추가 지시', 'text': '문단을 짧게 쓴다.',
                             'stages': ['write'], 'review_note': '추가'}, 1)
        before = self.manager.preview()['documents']
        normalize(self.manager, 2)
        self.assertEqual(before, self.manager.preview()['documents'])

    def test_fences_are_not_split_into_directives(self):
        body = '# 문서\n\n```python\n# 설명\n\nprint("한다.")\n```\n\n사실을 확인한다. 추정하지 않는다.\n'
        parts = list(pieces(body))
        self.assertEqual(''.join(p for p, _ in parts), body)
        self.assertEqual([p for p, role in parts if role == 'directive'], ['사실을 확인한다.', '추정하지 않는다.'])
