import json
from pathlib import Path
import tempfile
import unittest
from services.web_research import normalize_response, collect, research_for_brief

DATA = {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': '검토 후보'}]},
                       'groundingMetadata': {'webSearchQueries': ['HFOV'], 'groundingChunks': [
                           {'web': {'uri': 'https://avixa.org/doc', 'title': 'Doc'}},
                           {'web': {'uri': 'https://avixa.org/doc', 'title': 'Doc'}},
                           {'web': {'uri': 'javascript:bad', 'title': 'Bad'}}],
                            'groundingSupports': [{'segment': {'text': '검토 후보'}, 'groundingChunkIndices': [0]}]}}]}

class WebResearchTests(unittest.TestCase):
    def test_candidates_never_approved_and_deduplicated(self):
        result = normalize_response(DATA, 'HFOV')
        self.assertEqual(len(result['results']), 1)
        self.assertFalse(result['approved_for_writing'])
        self.assertEqual(result['status'], 'needs_review')

    def test_missing_grounding_not_success(self):
        result = normalize_response({'candidates': [{'finishReason': 'STOP'}]}, 'x')
        self.assertEqual(result['status'], 'ungrounded')
        with self.assertRaises(RuntimeError):
            normalize_response({'candidates': [{'finishReason': 'MAX_TOKENS'}]}, 'x')

    def test_cache_tool_and_credentials_not_persisted(self):
        class Session:
            calls = 0
            def post(self, url, **kw):
                self.calls += 1
                self.body = kw['json']
                return type('Response', (), {'status_code': 200, 'json': lambda _: DATA})()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'config').mkdir()
            (root / 'config/config.json').write_text(json.dumps({'gemini_api_key': 'test-secret', 'gemini_model': 'test-model'}))
            session = Session()
            cache = root / 'cache.json'
            collect(root, 'HFOV', cache, session)
            self.assertTrue(collect(root, 'HFOV', cache, session)['cache_hit'])
            self.assertEqual(session.calls, 1)
            self.assertEqual(session.body['tools'], [{'google_search': {}}])
            self.assertNotIn('responseMimeType', session.body['generationConfig'])
            self.assertNotIn('test-secret', cache.read_text(encoding='utf-8'))

    def test_opt_out_has_no_call(self):
        self.assertEqual(research_for_brief('.', {'web_research': False}, None)['status'], 'disabled')

if __name__ == '__main__':
    unittest.main()
