from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from services.web_evidence import finalize_assessment, validate_usage, load_verified


class WebEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.evidence = {'id': 'E1', 'statement': '특정 조건에서 발생하는 제약', 'conditions': ['small room'], 'source_type': 'forum', 'importance': 'material'}
        self.payload = {'candidate_sources': [{'document_id': 'S1'}], 'verified_evidence': [self.evidence], 'available_roles': ['body.conditions']}
        self.item = {'id': 'D1', 'source_ids': ['S1'], 'verified_evidence_ids': ['E1'], 'statement': 'limitation',
                     'conditions': [], 'decision_impact': 'purchase suitability', 'limitations': ['edge distortion'],
                     'mitigations': [], 'alternatives': [], 'missing_context': [], 'importance': 'material',
                     'inclusion_decision': 'include', 'reason': 'Reader decision affected', 'target_roles': ['body.conditions']}

    def test_material_disadvantage_included_without_mitigation(self):
        result = finalize_assessment({'items': [self.item]}, self.payload)
        self.assertEqual(result['usable_evidence'][0]['statement'], self.evidence['statement'])
        self.assertEqual(result['usable_evidence'][0]['source_type'], 'forum')
        self.assertEqual(result['status'], 'assessed')

    def test_material_cannot_exclude_or_include_unverified(self):
        item = deepcopy(self.item)
        item['inclusion_decision'] = 'exclude'
        with self.assertRaises(ValueError): finalize_assessment({'items': [item]}, self.payload)
        item['inclusion_decision'] = 'include'
        item['verified_evidence_ids'] = []
        with self.assertRaises(ValueError): finalize_assessment({'items': [item]}, self.payload)
        item['inclusion_decision'] = 'investigate'
        result = finalize_assessment({'items': [item]}, {**self.payload, 'verified_evidence': []})
        self.assertEqual(result['status'], 'needs_evidence')

    def test_reviewed_evidence_cannot_disappear_or_change_roles(self):
        with self.assertRaises(ValueError): finalize_assessment({'items': []}, self.payload)
        item = deepcopy(self.item)
        item['target_roles'] = ['unknown']
        with self.assertRaises(ValueError): finalize_assessment({'items': [item]}, self.payload)
        item = deepcopy(self.item)
        item.update(importance='contextual', inclusion_decision='exclude')
        with self.assertRaises(ValueError): finalize_assessment({'items': [item]}, self.payload)

    def test_usage_requires_material_evidence_at_correct_block(self):
        evidence = finalize_assessment({'items': [self.item]}, self.payload)['usable_evidence']
        plan = [{'id': 'conditions', 'roles': ['body.conditions']}]
        draft = {'blocks': [{'id': 'conditions', 'markdown': '환경에 따른 제약이 있습니다.'}]}
        self.assertTrue(validate_usage(draft, evidence, plan))
        draft['evidence_usage'] = [{'evidence_id': 'E1', 'block_id': 'conditions', 'quote': '환경에 따른 제약이 있습니다.'}]
        self.assertEqual(validate_usage(draft, evidence, plan), [])
        draft['evidence_usage'][0]['quote'] = '없는 문장'
        self.assertTrue(validate_usage(draft, evidence, plan))

    def test_original_review_hash_quote_and_path_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = '원문에는 제약 조건이 명시되어 있다.'.encode()
            (root / 'source.txt').write_bytes(raw)
            item = {**self.evidence, 'source_url': 'https://example.com/thread', 'source_path': 'source.txt',
                    'source_sha256': hashlib.sha256(raw).hexdigest(), 'locator': 'comment 123',
                    'quote': '제약 조건', 'reviewed_by': 'editor', 'reviewed_at': '2026-10-08', 'verification_status': 'verified'}
            path = root / 'review.json'
            path.write_text(json.dumps({'items': [item]}), encoding='utf-8')
            self.assertEqual(len(load_verified(root, path)), 1)
            (root / 'source.txt').write_text('changed', encoding='utf-8')
            with self.assertRaises(ValueError): load_verified(root, path)

if __name__ == '__main__':
    unittest.main()
