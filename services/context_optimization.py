"""Deterministic input optimization; never summarize normative text or Facts."""
from copy import deepcopy
import hashlib
import json

# Reviewed implementation-only documents in the approved release. Unknown/new
# revisions stay in the AI input until their audience is reviewed again.
SERVER_GUIDES = {
    'GUIDE-07-CONTRACTS': '95bccc5bbb353cbf2b32a5314cbfdc69673ab7e6f271040d17ed7a4965cb2bd3',
    'GUIDE-08-RUNTIME': 'c25bfcd565f8954a465c54bb624ecd78423c999d4575fe27d331cacbcd0c83e2',
}


def field_sizes(payload):
    """Characters, not tokens. Exact token count remains the dispatch gate."""
    return {key: len(json.dumps(value, ensure_ascii=False, default=str, separators=(',', ':')))
            for key, value in payload.items()}


def validate_fact_policy(policy, facts, block_ids):
    policy = policy or {}
    if not isinstance(policy, dict) or set(policy) - {'excluded_fact_ids', 'block_fact_ids'}:
        raise ValueError('Invalid fact_policy fields')
    known = {f['id'] for f in facts}
    excluded = policy.get('excluded_fact_ids', [])
    overrides = policy.get('block_fact_ids', {})
    def valid_ids(ids):
        return isinstance(ids, list) and all(isinstance(i, str) for i in ids) and len(ids) == len(set(ids)) and set(ids) <= known
    if not valid_ids(excluded) or not isinstance(overrides, dict):
        raise ValueError('Unknown/duplicate Fact in fact_policy')
    for bid, ids in overrides.items():
        if bid not in block_ids or not valid_ids(ids) or set(ids) & set(excluded):
            raise ValueError('Invalid block Fact override: ' + str(bid))
    return deepcopy(policy)


def apply_fact_policy(snapshot):
    value = deepcopy(snapshot)
    policy = value.get('fact_policy') or value.get('brief', {}).get('fact_policy') or {}
    blocks = (value.get('strategy') or {}).get('content_blocks') or value.get('brief', {}).get('content_blocks') or []
    # Strategy may not exist yet. Validate override names when a plan is available.
    ids = {b['id'] for b in blocks} if blocks else set(policy.get('block_fact_ids', {})) if isinstance(policy, dict) else set()
    policy = validate_fact_policy(policy, value.get('facts', []), ids)
    if not policy:
        return value, {}
    excluded = set(policy.get('excluded_fact_ids', []))
    value['fact_policy'] = policy
    value['facts'] = [f for f in value.get('facts', []) if f['id'] not in excluded]
    if blocks:
        for block in blocks:
            if block['id'] in policy.get('block_fact_ids', {}):
                block['fact_ids'] = policy['block_fact_ids'][block['id']]
            elif 'fact_ids' in block:
                block['fact_ids'] = [fid for fid in block['fact_ids'] if fid not in excluded]
    return value, {'excluded_fact_ids': sorted(excluded), 'block_fact_ids': policy.get('block_fact_ids', {})}


def optimize_context(stage, payload):
    value = deepcopy(payload)
    before = field_sizes(value)
    server = []
    for gid, body in list(value.get('guides', {}).items()):
        if isinstance(body, str) and SERVER_GUIDES.get(gid) == hashlib.sha256(body.encode('utf-8')).hexdigest():
            server.append({'id': gid, 'source_sha256': SERVER_GUIDES[gid], 'reason': 'implementation_contract_server_only'})
            del value['guides'][gid]
    if stage == 'strategy':
        # Planning selects a playbook from descriptive metadata. Full playbooks
        # remain in the server snapshot and are supplied after selection below.
        for book in value.get('playbooks', {}).values():
            if isinstance(book, dict):
                book.pop('body', None)
    if stage in ('write', 'feedback') and value.get('asset_plan') and isinstance(value.get('strategy'), dict):
        if value['strategy'].get('asset_needs') == value['asset_plan']:
            del value['strategy']['asset_needs']
    if stage in ('write', 'feedback') and value.get('brief', {}).get('content_blocks') == value.get('strategy', {}).get('content_blocks'):
        value.get('brief', {}).pop('content_blocks', None)
    if value.get('cautions') == value.get('rules'):
        value.pop('cautions', None)
    return value, {'version': 1, 'before_fields_chars': before, 'after_fields_chars': field_sizes(value),
                   'server_guides': server, 'facts_and_rule_bodies': 'preserved', 'unit': 'characters_not_tokens'}
