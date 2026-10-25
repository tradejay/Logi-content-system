"""Lossless policy transport aliases and receipt checks (not compliance checks)."""
from copy import deepcopy
import hashlib
import json


def encoded(value):
    return json.dumps(value, ensure_ascii=False, default=str, separators=(',', ':'))


def sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def pack_block_guides(blocks):
    """Send each exact role guide once; preserve original assignments in ledger."""
    packed, catalog = deepcopy(blocks), {}
    for block in packed:
        roles = []
        for guide in block.pop('guide', []):
            value = {k: v for k, v in guide.items() if k != 'source_policy_refs'}
            role = value['role']
            if role in catalog and catalog[role] != value:
                raise ValueError('Conflicting role guide: ' + role)
            catalog[role] = value
            roles.append(role)
        block['guide_roles'] = roles
    return packed, catalog


TRANSPORT_INSTRUCTION = '''
[전송 계약]
기존 출력 계약의 JSON 객체를 result에 그대로 넣는다. 응답의 첫 필드는 receipt이다.
{"receipt":{"bundle":"입력 policy_receipt.bundle","ids":["P01","R01","G01"]},"result":{}}
ids에는 입력 policy_receipt.ids를 빠짐없이, 중복 없이 돌려준다(예시 ID를 복사하지 않는다).
이는 수신 확인이며 준수 판정이 아니다. rules는 cautions도 포함한다. 짧은 ID는 이번 호출에만 유효하다.
'''.strip()


def prepare_call(stage, instruction, context, call_id, release_id, prompt_id,
                 prompt_sha, manifest=None):
    payload = deepcopy(context)
    entries = [{'alias': 'P01', 'kind': 'prompt', 'id': prompt_id,
                'version': release_id, 'body_sha256': prompt_sha}]
    manifest = manifest or {}
    rules = payload.get('rules', [])
    duplicate_cautions = 'cautions' in payload and payload['cautions'] == rules
    if duplicate_cautions:
        del payload['cautions']
    for index, rule in enumerate(rules, 1):
        original = rule['id']
        alias = f'R{index:02d}'
        info = manifest.get('rules', {}).get(original, {})
        entries.append({'alias': alias, 'kind': 'rule', 'id': original,
                        'version': info.get('version'), 'body_sha256': sha(rule.get('body', ''))})
        rule['id'] = alias
    guides = {}
    for index, (original, body) in enumerate(payload.get('guides', {}).items(), 1):
        alias = f'G{index:02d}'
        info = manifest.get('guides', {}).get(original, {})
        entries.append({'alias': alias, 'kind': 'guide', 'id': original,
                        'version': info.get('version'), 'body_sha256': sha(body)})
        guides[alias] = body
    if 'guides' in payload:
        payload['guides'] = guides
    # Nonduplicate caution constraints must also be acknowledged, not dropped.
    if not duplicate_cautions:
        for index, rule in enumerate(payload.get('cautions', []), 1):
            original = rule['id']
            alias = f'C{index:02d}'
            info = manifest.get('rules', {}).get(original, {})
            entries.append({'alias': alias, 'kind': 'caution', 'id': original,
                            'version': info.get('version'), 'body_sha256': sha(rule.get('body', ''))})
            rule['id'] = alias
    actual_instruction = instruction + '\n\n' + TRANSPORT_INSTRUCTION
    actual_instruction += '\n이번 receipt.ids는 아래 배열을 순서·개수까지 그대로 복사한다(' + str(len(entries)) + '개): ' + encoded([e['alias'] for e in entries])
    block_assignments = deepcopy(payload.get('block_plan', []))
    aliases = {e['id']: e['alias'] for e in entries if e['kind'] == 'rule'}
    for block in payload.get('block_plan', []):
        block['rule_ids'] = [aliases[rid] for rid in block['rule_ids']]
        for guide in block.get('guide', []):
            guide.pop('source_policy_refs', None)  # Source provenance stays in server logs.
    if payload.get('block_plan'):
        payload['block_plan'], payload['block_guides'] = pack_block_guides(payload['block_plan'])
    from services.context_transport import pack_fact_scopes, pack_review_draft
    scoped = pack_fact_scopes(payload) if stage in ('strategy', 'write', 'feedback') and payload.get('facts') else False
    draft_transport = pack_review_draft(payload) if stage == 'feedback' else 'not_applicable'
    if scoped:
        actual_instruction += '\nFact의 scope_ref는 fact_scopes의 동일 ID에 있는 적용 범위 전체를 뜻한다. 그 안의 조건·예외·제약을 각 참조 Fact에 그대로 적용한다.'
    if draft_transport == 'body_spans_v1':
        actual_instruction += '\n검토 본문은 draft.markdown에 한 번만 전달된다. 각 blocks.body_span=[시작,끝]은 본문의 문자 위치(끝 제외)다. block ID와 claim_ids로 위치를 연결해 검토한다.'
    bundle = sha(encoded([call_id, release_id, entries, actual_instruction, payload]))[:16]
    payload['policy_receipt'] = {'bundle': bundle, 'ids': [e['alias'] for e in entries]}
    ledger = {'schema_version': 1, 'call_id': call_id, 'stage': stage,
              'release_id': release_id, 'bundle': bundle, 'entries': entries,
              'instruction_sha256': sha(actual_instruction), 'context_sha256': sha(encoded(payload)),
              'duplicate_cautions_removed': duplicate_cautions,
              'receipt_status': 'pending', 'compliance_status': 'not_evaluated'}
    ledger['fact_scope_transport'] = 'shared_scopes_v1' if scoped else 'inline'
    ledger['draft_transport'] = draft_transport
    if block_assignments:
        ledger['block_assignments'] = block_assignments
        ledger['block_guide_transport'] = 'deduplicated_roles_v1'
    return actual_instruction, payload, ledger


def verify_receipt(response, ledger):
    receipt = response.get('receipt') if isinstance(response, dict) else None
    expected = [e['alias'] for e in ledger['entries']]
    ids = receipt.get('ids') if isinstance(receipt, dict) else None
    valid_ids = isinstance(ids, list) and all(isinstance(i, str) for i in ids)
    received = ids if valid_ids else []
    errors = []
    if not isinstance(receipt, dict) or receipt.get('bundle') != ledger['bundle']:
        errors.append('bundle_mismatch_or_missing')
    if not valid_ids:
        errors.append('invalid_ids')
    if len(received) != len(set(received)):
        errors.append('duplicate_ids')
    missing = sorted(set(expected) - set(received))
    unknown = sorted(set(received) - set(expected))
    if missing or unknown:
        errors.append('id_set_mismatch')
    if not isinstance(response, dict) or not isinstance(response.get('result'), dict):
        errors.append('invalid_result')
    return {'receipt_status': 'failed' if errors else 'verified', 'received_ids': received,
            'missing_ids': missing, 'unknown_ids': unknown, 'errors': errors,
            'compliance_status': 'not_evaluated'}
