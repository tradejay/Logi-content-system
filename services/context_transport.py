"""Lossless wire formats; full originals remain in input/revision snapshots."""
from collections import Counter
from copy import deepcopy
import json


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def pack_fact_scopes(context):
    facts = deepcopy(context.get('facts', []))
    if context.get('fact_scopes') or any('scope_ref' in f for f in facts):
        raise ValueError('Fact scope transport is already packed or ambiguous')
    counts = Counter(encoded(f['scope']) for f in facts if 'scope' in f)
    catalog, refs = {}, {}
    for fact in facts:
        if 'scope' not in fact:
            continue
        key = encoded(fact['scope'])
        # Group repeated scope objects only when references are smaller.
        if counts[key] < 2 or (counts[key] - 1) * len(key) <= counts[key] * 30:
            continue
        if key not in refs:
            ref = 'SC' + str(len(refs) + 1).zfill(2)
            refs[key] = ref
            catalog[ref] = deepcopy(fact['scope'])
        fact['scope_ref'] = refs[key]
        del fact['scope']
    context['facts'] = facts
    if catalog:
        context['fact_scopes'] = catalog
    return bool(catalog)


def expand_fact_scopes(context):
    catalog = context.get('fact_scopes', {})
    if not isinstance(catalog, dict):
        raise ValueError('Invalid Fact scope catalog')
    facts = deepcopy(context.get('facts', []))
    for fact in facts:
        if 'scope_ref' in fact:
            ref = fact.pop('scope_ref')
            if not isinstance(ref, str) or ref not in catalog or 'scope' in fact:
                raise ValueError('Missing/ambiguous Fact scope reference')
            fact['scope'] = deepcopy(catalog[ref])
    return facts


def pack_review_draft(context):
    draft = context.get('draft')
    if not isinstance(draft, dict) or not draft.get('blocks'):
        return 'not_applicable'
    blocks = draft['blocks']
    if not isinstance(blocks, list) or any(not isinstance(b, dict) or not isinstance(b.get('markdown'), str) for b in blocks):
        return 'kept_invalid_blocks_for_review'
    if draft.get('markdown') != '\n\n'.join(b['markdown'] for b in blocks):
        return 'kept_assembly_mismatch_for_review'
    position = 0
    for block in blocks:
        if 'body_span' in block:
            raise ValueError('Reserved review body_span already present')
        body = block.pop('markdown')
        block['body_span'] = [position, position + len(body)]
        position += len(body) + 2
    return 'body_spans_v1'


def restore_review_draft(context):
    draft = deepcopy(context.get('draft', {}))
    body = draft.get('markdown')
    for block in draft.get('blocks') or []:
        if 'body_span' not in block:
            continue
        span = block.pop('body_span')
        if (not isinstance(body, str) or 'markdown' in block or not isinstance(span, list) or len(span) != 2
                or any(type(n) is not int for n in span) or not 0 <= span[0] <= span[1] <= len(body)):
            raise ValueError('Invalid review block span')
        block['markdown'] = body[span[0]:span[1]]
    if context.get('draft', {}).get('blocks') and any('body_span' in b for b in context['draft']['blocks']):
        if body != '\n\n'.join(b['markdown'] for b in draft['blocks']):
            raise ValueError('Review block spans do not reconstruct entire draft')
    return draft
