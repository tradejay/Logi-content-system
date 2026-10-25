"""Transport only. Editorial instructions live in authoring/prompts/*.md."""
import json
import os
from pathlib import Path


def configuration(root):
    path = Path(root) / 'config/config.json'
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}


def parse_object(text):
    text = text.strip()
    decoder = json.JSONDecoder()
    candidates = []
    has_malformed_outer = False
    has_outer_array = False

    i = 0
    n = len(text)

    in_string = False
    escape = False
    brace_depth = 0
    bracket_depth = 0

    while i < n:
        char = text[i]

        if in_string:
            if escape:
                escape = False
            elif char == '\\':
                escape = True
            elif char == '"':
                in_string = False
            i += 1
            continue

        if char == '"':
            in_string = True
            i += 1
            continue

        if char == '[':
            if brace_depth == 0 and bracket_depth == 0:
                try:
                    obj, end = decoder.raw_decode(text, i)
                    if isinstance(obj, list):
                        has_outer_array = True
                        i = end
                        continue
                except json.JSONDecodeError:
                    pass
            bracket_depth += 1
        elif char == ']':
            if bracket_depth > 0:
                bracket_depth -= 1
        elif char == '{':
            if brace_depth == 0 and bracket_depth == 0:
                # Top-level object candidate
                try:
                    obj, end = decoder.raw_decode(text, i)
                    if isinstance(obj, dict):
                        candidates.append(obj)
                        i = end
                        continue
                except json.JSONDecodeError:
                    has_malformed_outer = True
            brace_depth += 1
        elif char == '}':
            if brace_depth > 0:
                brace_depth -= 1
        i += 1

    if brace_depth > 0 or bracket_depth > 0 or in_string:
        has_malformed_outer = True

    if has_malformed_outer:
        raise ValueError('AI response contains truncated or malformed JSON object')

    if has_outer_array and len(candidates) > 0:
        raise ValueError('AI response contains mixed JSON objects and arrays')

    if has_outer_array:
        raise ValueError('AI response contains JSON array, expected object')

    if len(candidates) == 1:
        return candidates[0]
    elif len(candidates) > 1:
        raise ValueError(f'Multiple JSON objects found ({len(candidates)})')
    raise ValueError('AI response does not contain a single valid JSON object')




class ModelProvider:
    def __init__(self, root):
        self.config = configuration(root)
        self.last_metadata = {}
        self._key_index = 0
        self._route_attempts = []
        self._measured_input = None

    def generation_config(self, stage, model):
        limits = self.config.get('pipeline_output_token_budgets', {})
        limit = limits.get(stage, 16384 if stage=='naver_edit' else 8192 if stage in ('write', 'evidence_review', 'official_interpret') else 4096)
        if type(limit) is not int or limit <= 0:
            raise ValueError('Pipeline output token budget must be a positive integer')
        result={'responseMimeType': 'application/json', 'maxOutputTokens': limit}
        if stage=='naver_edit':
            from services.naver_editor import RESPONSE_SCHEMA
            result['responseSchema']=RESPONSE_SCHEMA
        return result

    def credentials(self):
        raise RuntimeError('Gemini API is quarantined by user request. Use IDE workers; restoring API transport requires an explicit user request.')

    def configured_keys(self):
        return [entry[0] for entry in self.key_entries()]

    def key_entries(self):
        # Explicit environment overrides remain authoritative; configured keys are tried once each.
        override = os.getenv('GEMINI_API_KEY')
        if override:
            if self.config.get('gemini_key_policy') == 'free_only':
                raise ValueError('Free-only mode requires registered keys with declared free tiers; environment override is unclassified')
            return [(override, 'unknown', 1)]
        keys = [self.config.get('gemini_api_key')] + list(self.config.get('gemini_api_keys') or [])
        keys = list(dict.fromkeys(k.strip() for k in keys if isinstance(k, str) and k.strip()))
        tiers = self.config.get('gemini_api_key_tiers', [])
        entries = [(key, tiers[i] if i < len(tiers) else 'unknown', i + 1) for i, key in enumerate(keys)]
        if self.config.get('gemini_key_policy') == 'free_only':
            entries = [entry for entry in entries if entry[1] == 'free']
        return entries

    def key_slot(self, slot):
        entries = self.key_entries()
        return entries[slot - 1][2] if 0 < slot <= len(entries) else slot

    def key_tier(self, slot):
        """User-declared project tier; never expose the credential itself."""
        entries = self.key_entries()
        return entries[slot - 1][1] if 0 < slot <= len(entries) else 'unknown'

    def _with_key_failover(self, method, stage, instruction, context, reset=False):
        if reset or not hasattr(self, '_key_index'):
            self._key_index = 0
            self._route_attempts = []
            self._measured_input = None
        while True:
            try:
                value = method(stage, instruction, context)
                if method.__name__ == '_count_tokens_once':
                    self._measured_input = value
                self.last_metadata.update(key_slot=self.key_slot(self._key_index + 1), key_tier=self.key_tier(self._key_index + 1), routing_attempts=list(self._route_attempts))
                if self._measured_input is not None:
                    self.last_metadata['actual_input_tokens'] = self._measured_input
                return value
            except RuntimeError as error:
                # Only transport/account failures cause failover. Output truncation, safety and validation do not.
                import re
                match = re.search(r'HTTP (\d{3})', str(error))
                status = int(match.group(1)) if match else None
                self._route_attempts.append({'key_slot': self.key_slot(self._key_index + 1), 'key_tier': self.key_tier(self._key_index + 1), 'stage': stage,
                                             'operation': method.__name__, 'http_status': status})
                if status not in (401, 402, 403, 429, 500, 502, 503, 504) or self._key_index + 1 >= len(self.configured_keys()):
                    self.last_metadata.update(key_slot=self.key_slot(self._key_index + 1), key_tier=self.key_tier(self._key_index + 1), routing_attempts=list(self._route_attempts))
                    raise
                self._key_index += 1
                if method.__name__ == '_complete_once':
                    # Count again with the selected key before generating; never bypass the input gate.
                    self.count_tokens(stage, instruction, context, reset=False)
                    budget = self.config.get('pipeline_input_token_budget', 50000)
                    if self._measured_input > budget:
                        raise ValueError('Fallback input token budget exceeded')

    def count_tokens(self, stage, instruction, context, reset=True):
        raise RuntimeError('Gemini API is quarantined by user request. Use IDE workers; restoring API transport requires an explicit user request.')

    def complete(self, stage, instruction, context):
        raise RuntimeError('Gemini API is quarantined by user request. Use IDE workers; restoring API transport requires an explicit user request.')

    def request_body(self, stage, instruction, context, model):
        return {'systemInstruction': {'parts': [{'text': instruction}]},
                'contents': [{'role': 'user', 'parts': [{'text': json.dumps(context, ensure_ascii=False, default=str, separators=(',', ':'))}]}],
                'generationConfig': self.generation_config(stage, model)}

    def _count_tokens_once(self, stage, instruction, context):
        raise RuntimeError('Gemini API is quarantined by user request. Use IDE workers; restoring API transport requires an explicit user request.')

    def _complete_once(self, stage, instruction, context):
        raise RuntimeError('Gemini API is quarantined by user request. Use IDE workers; restoring API transport requires an explicit user request.')

    def official(self, instruction, context):
        import requests
        self.last_metadata = {}
        endpoint = self.config.get('logitech_ai_url', 'http://127.0.0.1:5050/ask')
        response = requests.post(endpoint, json={'question': instruction + '\n' +
            json.dumps(context, ensure_ascii=False, default=str)}, timeout=180)
        if response.status_code != 200:
            raise RuntimeError(f'Logitech review: HTTP {response.status_code}')
        data = response.json()
        if data.get('reason') == 'captcha_required':
            raise RuntimeError('Logitech review requires human CAPTCHA verification')
        if data.get('status') != 'success' or not isinstance(data.get('response'), str):
            raise ValueError('Logitech review did not return a successful response')
        self.last_metadata = {
            'usage_metadata': 'unavailable',
            'finish_reason': 'STOP',
            'model_version': 'logitech-rag-endpoint',
        }
        return data['response']
