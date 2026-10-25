import unittest
from services.pipeline_provider import parse_object, ModelProvider
from unittest.mock import patch, Mock


class PipelineProviderTests(unittest.TestCase):
    def test_http_failure_records_only_status_and_stage(self):
        provider = ModelProvider.__new__(ModelProvider)
        provider.config = {}
        provider.credentials = lambda: ('test-key', 'test-model')
        response = Mock(status_code=402)
        with patch('requests.post', return_value=response):
            with self.assertRaisesRegex(RuntimeError, 'HTTP 402'):
                provider.complete('feedback', 'test instruction', {})
        self.assertEqual(provider.last_metadata['http_status'], 402)
        self.assertEqual(provider.last_metadata['error_stage'], 'feedback')
        self.assertNotIn('test-key', str(provider.last_metadata))
        response.json.assert_not_called()

    def test_single_direct_json(self):
        self.assertEqual(parse_object('{"key": "value"}'), {"key": "value"})

    def test_single_json_in_markdown_code_block(self):
        text = '```json\n{"claims": [{"id": "c1", "verdict": "confirmed"}]}\n```'
        res = parse_object(text)
        self.assertEqual(res['claims'][0]['id'], 'c1')

    def test_single_json_surrounded_by_explanation(self):
        text = (
            "아래는 공식 RAG 검토 결과입니다.\n\n"
            "{\n  \"claims\": [{\"id\": \"A\", \"detail\": \"괄호 { } 포함\"}]\n}\n\n"
            "감사합니다. 이상 검토 완료."
        )
        res = parse_object(text)
        self.assertEqual(res['claims'][0]['detail'], "괄호 { } 포함")

    def test_multiple_json_objects_rejected(self):
        text = '```json\n{"a": 1}\n```\n{"b": 2}'
        with self.assertRaises(ValueError) as cm:
            parse_object(text)
        self.assertIn('Multiple JSON objects found', str(cm.exception))

    def test_multiple_code_blocks_rejected(self):
        text = '```json\n{"a": 1}\n```\n```json\n{"b": 2}\n```'
        with self.assertRaises(ValueError) as cm:
            parse_object(text)
        self.assertIn('Multiple JSON objects found', str(cm.exception))

    def test_nested_objects_not_counted_twice(self):
        text = '{"outer": {"nested": {"value": 123}}, "list": [{"k": "v"}]}'
        res = parse_object(text)
        self.assertEqual(res['outer']['nested']['value'], 123)

    def test_escaped_strings_and_braces_in_strings(self):
        text = '{"message": "Hello \\"world\\" with {braces} and \\\\ slashes"}'
        res = parse_object(text)
        self.assertEqual(res['message'], 'Hello "world" with {braces} and \\ slashes')

    def test_truncated_json_rejected(self):
        with self.assertRaises(ValueError):
            parse_object('{"a": 1, "b":')

    def test_truncated_inner_json_rejected(self):
        # 외부 객체가 닫히지 않고 내부에 온전한 객체 파편만 있는 경우
        with self.assertRaises(ValueError) as cm:
            parse_object('{"claims":[{"id":"A"}')
        self.assertTrue('No valid JSON' in str(cm.exception) or 'malformed' in str(cm.exception))

    def test_json_array_rejected(self):
        # 배열 내부 객체를 정상 응답으로 추출하지 않고 거부해야 함
        with self.assertRaises(ValueError) as cm:
            parse_object('[{"id":"A"}]')
        self.assertTrue('JSON array' in str(cm.exception) or 'No valid JSON' in str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            parse_object('[{"id":"A"}, {"id":"B"}]')
        self.assertTrue('JSON array' in str(cm.exception) or 'No valid JSON' in str(cm.exception))

    def test_json_array_in_markdown_rejected(self):
        text = '```json\n[{"id":"A"}]\n```'
        with self.assertRaises(ValueError) as cm:
            parse_object(text)
        self.assertTrue('JSON array' in str(cm.exception) or 'No valid JSON' in str(cm.exception))

    def test_no_json_rejected(self):
        with self.assertRaises(ValueError):
            parse_object('이 텍스트에는 JSON이 전혀 없습니다.')


if __name__ == '__main__':
    unittest.main()
