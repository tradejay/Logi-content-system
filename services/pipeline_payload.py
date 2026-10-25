"""Stage-specific model inputs.  Audit snapshots live in the run directory."""
import json
import re


def pick(value, fields):
    return {key: value[key] for key in fields if key in value and value[key] not in (None, '', [], {})}


# ── Fact reduction ──────────────────────────────────────────────────────
_BOOKKEEPING = frozenset({
    'sha256', 'input_refs', 'created_at', 'updated_at',
    'artifact_revision', 'schema_version',
})


def _slim_fact(fact, level):
    """Return a copy of *fact* trimmed to the detail *level*.

    Levels
    ------
    summary  – strategy: plan coverage (no scope/source detail)
    full     – write: complete for accurate drafting
    verify   – feedback/official: scope for checking, minimal source
    """
    base = {k: v for k, v in fact.items() if k not in _BOOKKEEPING}
    if level == 'summary':
        return pick(base, ['id', 'knowledge_id', 'property', 'canonical_property',
                           'subject', 'value', 'unit', 'notes'])
    if level == 'verify':
        source = base.get('source')
        if isinstance(source, dict):
            base = {**base, 'source': pick(source, ['id', 'source_id', 'locator'])}
        return base
    return base            # 'full'


# ── Source excerpt extraction ───────────────────────────────────────────
_HEADING_RE = re.compile(r'^(#{1,6})\s+(.+?)(?:\s*#*\s*)?$')


def _extract_sections(body, headings):
    """Pull only the markdown sections whose title overlaps *headings*."""
    lines = body.split('\n')
    entries = []                       # (line_idx, level, title)
    for i, line in enumerate(lines):
        m = _HEADING_RE.match(line.strip())
        if m:
            entries.append((i, len(m.group(1)), m.group(2).strip()))
    if not entries:
        return body

    ranges = []
    for idx, (li, level, title) in enumerate(entries):
        if any(h in title or title in h for h in headings):
            end = len(lines)
            for ni in range(idx + 1, len(entries)):
                if entries[ni][1] <= level:
                    end = entries[ni][0]
                    break
            ranges.append((li, end))
    if not ranges:
        # Locator headings did not match any section in source body
        limit = 1000
        truncated = body[:limit] + '\n…(근거 위치 매칭 실패: 확인 필요)' if len(body) > limit else body
        return f"[근거 위치 검색 불일치: {headings}]\n" + truncated

    ranges.sort()
    merged = [ranges[0]]
    for s, e in ranges[1:]:
        if s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return '\n\n---\n\n'.join('\n'.join(lines[s:e]).strip() for s, e in merged)


def _scoped_sources(sources, facts):
    """Replace full source bodies with fact-locator-scoped excerpts."""
    if not sources:
        return {}
    locators_by_source = {}
    for fact in facts:
        src = fact.get('source', {})
        if not isinstance(src, dict):
            continue
        sid = src.get('id') or src.get('source_id')
        loc = src.get('locator')
        if sid and loc and sid in sources:
            locators_by_source.setdefault(sid, []).append(loc)

    meta_keys = ['id', 'title', 'type', 'vendor', 'evidence_level', 'status', 'url', 'source_url', 'path', 'last_verified']
    cited = {f.get('source', {}).get('id') or f.get('source', {}).get('source_id')
             for f in facts if isinstance(f.get('source'), dict)}
    result = {}
    for sid, source in sources.items():
        if sid not in cited and sid not in locators_by_source:
            continue
        body = source.get('body', '')
        headings = set()
        for loc in locators_by_source.get(sid, []):
            for key in ('heading', 'section'):
                if loc.get(key):
                    headings.add(loc[key])
        entry = pick(source, meta_keys)
        if body:
            entry['body'] = _extract_sections(body, headings) if headings else body
        result[sid] = entry
    return result


# ── Core guide names ────────────────────────────────────────────────────
_CORE_GUIDE_NAMES = frozenset({'SAFETY_CORE.md', 'STYLE_CORE.md', 'WRITING_CORE.md'})


# ── Public API ──────────────────────────────────────────────────────────
def compact_payload(stage, payload):
    """Build the stage-specific dict actually sent to the model.

    Management-only fields (sha256, input_refs, created_at, artifact_revision,
    schema_version, legacy_claim_metadata, entities, knowledge, missing) are
    preserved in run-directory snapshots but *never* forwarded to the model.
    """
    if stage not in {'strategy', 'write', 'feedback', 'official'}:
        raise ValueError('Unknown model stage')

    facts = payload.get('facts', [])

    # ── official: complete draft + claims + referenced Facts/source locations ──
    if stage == 'official':
        needed = {fid for c in payload.get('claims', []) for fid in c.get('fact_ids', [])}
        selected = [f for f in facts if f.get('id') in needed]
        return {
            'claims': payload.get('claims', []),
            'facts': [_slim_fact(f, 'verify') for f in selected],
            'draft': pick(payload.get('draft', {}), ['markdown']),
            'sources': _scoped_sources(payload.get('sources', {}), selected),
        }

    # ── brief: topic-relevant fields only ──
    brief = pick(payload.get('brief', {}), [
        'topic', 'one_line_purpose', 'audience', 'search', 'intent',
        'funnel_stage', 'questions', 'questions3', 'product_bridge', 'cta', 'sections',
    ])

    # ── cautions: rule id + body only (no sha256, match conditions, priority) ──
    cautions = [pick(r, ['id', 'body']) for r in payload.get('cautions', [])]

    # ── guides: stage-relevant authoring steps + core rules ──
    prefixes = {
        'strategy': ('01-', '02-', '03-'),        # topic, facts/cautions, structure
        'write':    ('02-', '03-', '04-'),         # facts/cautions, structure, images
        'feedback': ('02-', '05-'),                # facts/cautions (verify), review rules
    }[stage]
    include_core = stage in ('write', 'feedback')
    guides = {
        name: body for name, body in payload.get('guides', {}).items()
        if name.startswith(prefixes) or (include_core and name in _CORE_GUIDE_NAMES)
    }

    # ── strategy ──
    if stage == 'strategy':
        strat_res = {
            'brief': brief,
            'facts': [_slim_fact(f, 'summary') for f in facts],
            'cautions': cautions,
            'guides': guides,
            'playbooks': {
                k: pick(b, ['id', 'name', 'intents', 'suitable_for', 'reader_state',
                             'compatible_secondary', 'recommended_assets'])
                for k, b in payload.get('playbooks', {}).items()
            },
            'assets': [
                pick(a, ['asset_id', 'product', 'feature', 'purpose', 'caption',
                          'asset_type', 'review_status', 'origin_type'])
                for a in payload.get('assets', [])
            ],
            'gap': payload.get('gap', {}),
        }
        if payload.get('user_feedback'):
            strat_res['user_feedback'] = payload['user_feedback']
        return strat_res

    # ── write / feedback common ──
    sources = _scoped_sources(payload.get('sources', {}), facts)
    strategy = {k: v for k, v in payload.get('strategy', {}).items() if k != 'asset_needs'}

    if stage == 'write':
        result = {
            'brief': brief,
            'facts': [_slim_fact(f, 'full') for f in facts],
            'cautions': cautions,
            'guides': guides,
            'sources': sources,
            'strategy': strategy,
            'asset_plan': payload.get('asset_plan',
                                     payload.get('strategy', {}).get('asset_needs', [])),
            'playbooks': {k: pick(b, ['id', 'body'])
                          for k, b in payload.get('playbooks', {}).items()},
        }
        if payload.get('product_links'):
            result['product_links'] = payload['product_links']
        prev = payload.get('previous_draft')
        if prev:
            result['previous_draft'] = pick(prev, ['markdown'])
        for key in ('feedback', 'user_feedback'):
            if payload.get(key):
                result[key] = payload[key]
        return result

    # ── feedback ──
    fb_res = {
        'brief': brief,
        'facts': [_slim_fact(f, 'verify') for f in facts],
        'cautions': cautions,
        'guides': guides,
        'sources': sources,
        'strategy': strategy,
        'draft': pick(payload.get('draft', {}), ['markdown', 'claims', 'used_asset_need_ids', 'unresolved_items']),
    }
    if payload.get('product_links'):
        fb_res['product_links'] = payload['product_links']
    if payload.get('user_feedback'):
        fb_res['user_feedback'] = payload['user_feedback']
    return fb_res


def payload_size(value):
    return len(json.dumps(value, ensure_ascii=False, default=str, separators=(',', ':')))
