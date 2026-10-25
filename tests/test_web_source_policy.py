import unittest
from services.web_source_policy import apply_policy, allowed_url, original_url, POLICY_ID
from services.web_evidence import finalize_assessment

class WebSourcePolicyTests(unittest.TestCase):
    def test_exact_domains_and_subdomains_only(self):
        self.assertTrue(allowed_url('https://www.avixa.org/resource'))
        self.assertTrue(allowed_url('https://psni.org/blog'))
        for url in ['https://avixa.org.evil.com/x', 'https://reddit.com/x', 'https://avixa.org@evil.com', 'file:///avixa.org']:
            self.assertFalse(allowed_url(url))

    def test_third_party_citations_do_not_leak_into_context(self):
        research = {'summary': 'valid and invalid', 'results': [
            {'document_id': 'A', 'source_location': 'https://avixa.org/a', 'grounding_chunk_indices': [0]},
            {'document_id': 'R', 'source_location': 'https://reddit.com/a', 'grounding_chunk_indices': [1]}],
            'grounding_metadata': {'groundingSupports': [
                {'segment': {'text': 'valid'}, 'groundingChunkIndices': [0]},
                {'segment': {'text': 'invalid'}, 'groundingChunkIndices': [1]},
                {'segment': {'text': 'mixed'}, 'groundingChunkIndices': [0, 1]}]}}
        result = apply_policy(research, None)
        self.assertEqual([s['document_id'] for s in result['results']], ['A'])
        self.assertEqual(result['summary'], '[A] valid')
        self.assertEqual(result['status'], 'trusted')
        self.assertEqual(result['results'][0]['trust_score'], 1.0)

    def test_redirect_identity_checked_not_title(self):
        class Response:
            status_code = 302
            headers = {'Location': 'https://www.psni.org/blog'}
            def close(self): pass
        class Session:
            def get(self, url, **kwargs): return Response()
        self.assertEqual(original_url('https://vertexaisearch.cloud.google.com/grounding-api-redirect/test', Session()), 'https://www.psni.org/blog')
        self.assertIsNone(original_url('https://example.com/avixa', Session()))

    def test_trusted_institution_bypasses_manual_investigation_gate(self):
        evidence = {'id': 'E1', 'statement': 'Institution guidance', 'source_url': 'https://psni.org/blog',
                    'source_type': 'institution', 'trust_policy_id': POLICY_ID}
        item = {'id': 'D1', 'source_ids': ['S1'], 'verified_evidence_ids': ['E1'], 'statement': 'guidance',
                'decision_impact': 'selection', 'limitations': [], 'mitigations': [], 'alternatives': [], 'missing_context': [],
                'importance': 'material', 'inclusion_decision': 'investigate', 'reason': 'review pending', 'target_roles': ['body.conditions']}
        result = finalize_assessment({'items': [item]}, {'candidate_sources': [{'document_id': 'S1'}], 'verified_evidence': [evidence], 'available_roles': ['body.conditions']})
        self.assertEqual(result['status'], 'assessed')
        self.assertEqual(result['items'][0]['inclusion_decision'], 'include')
        self.assertEqual(len(result['usable_evidence']), 1)

if __name__ == '__main__': unittest.main()
