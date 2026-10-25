"""Load versioned inputs without embedding product or writing policy in code."""
import hashlib
import json
import sqlite3
from pathlib import Path
import yaml


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def read_yaml(path):
    return yaml.safe_load(path.read_text(encoding='utf-8-sig')) or {}


def contained(base, relative):
    path = (base / relative).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError('Input path escapes its root')
    return path


def load_context(root, cid):
    root = Path(root).resolve()
    system = root / 'content-system'
    authoring = system / '02_writer_ai/authoring'
    refs = []
    def text(path):
        resolved_path = Path(path).resolve()
        value = resolved_path.read_text(encoding='utf-8-sig')
        refs.append({'path': str(resolved_path.relative_to(root)), 'sha256': digest(value)})
        return value
    brief = yaml.safe_load(text(system / f'01_keyword_ai/briefs/{cid}.brief.yaml'))
    if not brief.get('topic') or not brief.get('search', {}).get('primary_keyword'):
        raise ValueError('Brief requires topic and search.primary_keyword')
    packs, facts, missing = [], [], []
    available = {p.stem: p for p in (system / '03_sources/knowledge').rglob('*.yaml')}
    for kid in brief.get('knowledge_packs', []):
        if kid not in available:
            missing.append({'kind': 'missing_knowledge', 'id': kid})
            continue
        pack = yaml.safe_load(text(available[kid]))
        packs.append(pack)
        for fact in pack.get('facts', []):
            facts.append({**fact, 'knowledge_id': kid, 'scope': fact.get('scope', pack.get('scope', {}))})
    if len({f['id'] for f in facts}) != len(facts):
        raise ValueError('Duplicate fact IDs')
    required = {f for s in brief.get('sections', []) for f in s.get('required_facts', [])}
    for fid in sorted(required - {f['id'] for f in facts}):
        missing.append({'kind': 'missing_fact', 'id': fid})
    index = yaml.safe_load(text(system / '03_sources/INDEX.yaml'))
    sources = {s['id']: s for s in index.get('sources', [])}
    selected_sources = {}
    for fact in facts:
        source = fact.get('source', {})
        sid = (source.get('id') or source.get('source_id')) if isinstance(source, dict) else source
        if sid in selected_sources:
            continue
        entry = sources.get(sid)
        if not entry or not entry.get('path'):
            missing.append({'kind': 'missing_source', 'fact_id': fact['id'], 'id': sid})
            continue
        path = contained(system / '03_sources', entry['path'])
        if not path.is_file():
            missing.append({'kind': 'missing_source_file', 'id': sid})
            continue
        selected_sources[sid] = {**entry, 'body': text(path)}
        if entry.get('status') != 'VALID':
            missing.append({'kind': 'source_status', 'id': sid})
    guides = {p.name: text(p) for p in sorted(authoring.glob('0[1-6]-*.md'))}
    for path in sorted((system / '02_writer_ai/core').glob('*.md')):
        guides[path.name] = text(path)
    playbooks = {}
    playbook_registry = system / '02_writer_ai/strategy/playbook-registry.yaml'
    if playbook_registry.exists():
        for book in yaml.safe_load(text(playbook_registry)).get('playbooks', []):
            playbooks[book['id']] = {**book, 'body': text(contained(system / '02_writer_ai', book['path']))}
    registry_path = authoring / 'rules/registry.json'
    registry = json.loads(text(registry_path))
    # Legacy facts lack typed claim metadata. Conservative matching loads all rule
    # kinds until a pack has explicit claim_kinds; never infer cautions from prose.
    fields = {k: set() for k in ['product_ids', 'feature_ids', 'property_ids', 'claim_kinds', 'intents']}
    fields['intents'].update(brief.get('intent', []))
    fields['property_ids'].update(f.get('canonical_property', f.get('property', '')) for f in facts)
    explicit = set()
    legacy = False
    for pack in packs:
        fields['product_ids'].update(pack.get('scope', {}).get('applies_to', []))
        fields['feature_ids'].update(pack.get('feature_ids', []))
        explicit.update(pack.get('caution_rule_ids', []))
    for fact in facts:
        explicit.update(fact.get('caution_rule_ids', []))
        fields['claim_kinds'].update(fact.get('claim_kinds', []))
        legacy |= not bool(fact.get('claim_kinds'))
    rules = registry['rules']
    if legacy:
        for rule in rules:
            for cond in rule.get('match', {}).get('any', []) + rule.get('match', {}).get('all', []):
                if cond['field'] == 'claim_kinds':
                    fields['claim_kinds'].update(cond['values'])
    if explicit - {r['id'] for r in rules if r.get('status', 'active') == 'active'}:
        raise ValueError('Unknown/inactive caution_rule_ids')
    def condition(c):
        if c['op'] != 'intersects' or c['field'] not in fields:
            raise ValueError('Unsupported caution matching contract')
        return bool(fields[c['field']] & set(c['values']))
    matched = []
    for rule in sorted(rules, key=lambda r: r.get('priority', 50)):
        if rule.get('status', 'active') != 'active':
            continue
        match = rule.get('match', {})
        matches = all(condition(c) for c in match.get('all', [])) and (
            not match.get('any') or any(condition(c) for c in match['any']))
        if matches or rule['id'] in explicit:
            body = text(contained(registry_path.parent, rule['path']))
            matched.append({**rule, 'body': body, 'sha256': digest(body)})
    assets = []
    COMMON_ASSET_IDS = {'AST-COMPANY-OCEAN-001'}
    for path in [system / '03_sources/assets/INDEX.yaml', system / f'assets/{cid}/assets.yaml']:
        if path.exists():
            for asset in yaml.safe_load(text(path)).get('assets', []):
                aid = asset.get('asset_id')
                if (asset.get('content_id') == cid or
                    asset.get('product') in fields['product_ids'] or
                    aid in COMMON_ASSET_IDS or
                    asset.get('asset_type') == 'company_intro_card'):
                    assets.append(asset)
    product_links = {}
    product_link_errors = []
    try:
        from services.device_blog_registry import load_realtime_device_blog_registry, resolve_device_id_strictly
        dev_reg = load_realtime_device_blog_registry()
        for pid in fields['product_ids']:
            # 1. Strict canonical resolution first (e.g. tap-ip vs tap, meetup 2 vs meetup)
            canonical_id = resolve_device_id_strictly(pid)
            matched_entry = None
            if canonical_id and canonical_id in dev_reg and dev_reg[canonical_id].get('blog_url'):
                matched_entry = {
                    'product_id': pid,
                    'canonical_id': canonical_id,
                    'label': dev_reg[canonical_id].get('label', canonical_id),
                    'blog_url': dev_reg[canonical_id]['blog_url'],
                    'source': 'device_blog_registry'
                }
            else:
                # 2. Exact key match without ambiguous substring guessing
                pid_clean = pid.lower().replace('_', '-').replace(' ', '')
                candidates = []
                for k, v in dev_reg.items():
                    if v.get('blog_url'):
                        k_clean = k.lower().replace('_', '-').replace(' ', '')
                        if pid_clean == k_clean or f"logi-{pid_clean}" == k_clean or pid_clean == k_clean.replace('logi-', ''):
                            candidates.append((k, v))
                if len(candidates) == 1:
                    k, v = candidates[0]
                    matched_entry = {
                        'product_id': pid,
                        'canonical_id': k,
                        'label': v.get('label', k),
                        'blog_url': v['blog_url'],
                        'source': 'device_blog_registry'
                    }
                elif len(candidates) > 1:
                    product_link_errors.append({
                        'kind': 'ambiguous_product_link',
                        'product_id': pid,
                        'candidates': [c[0] for c in candidates],
                        'detail': f'제품 링크 후보가 복수 개 감지되어 특정 불가: {[c[0] for c in candidates]}'
                    })
            if matched_entry:
                product_links[pid] = matched_entry
    except Exception as e:
        product_link_errors.append({
            'kind': 'product_link_load_failed',
            'detail': f'제품 블로그 레지스트리 로딩 실패: {type(e).__name__} {e}'
        })

    if product_link_errors:
        missing.extend(product_link_errors)

    # Track only relevant product links for this specific post
    if product_links:
        links_serialized = json.dumps(product_links, sort_keys=True, ensure_ascii=False)
        refs.append({
            'path': f'virtual:product_links:{cid}',
            'sha256': digest(links_serialized),
            'virtual': True
        })

    prompts = {p.stem: text(p) for p in (authoring / 'prompts').glob('*.md')}
    return {'brief': brief, 'facts': facts, 'knowledge': packs, 'sources': selected_sources,
            'guides': guides, 'playbooks': playbooks, 'cautions': matched, 'assets': assets, 'missing': missing,
            'input_refs': refs, 'prompts': prompts, 'legacy_claim_metadata': legacy,
            'product_links': product_links,
            'entities': {k: sorted(v) for k, v in fields.items()}}


def gap_snapshot(root, cid):
    result = {'selection': 'existing_brief', 'collection_status': 'NOT_COLLECTED',
              'rank_history': [], 'keyword_candidates': []}
    for filename, query, params, key in [
        ('performance_history.db', 'SELECT * FROM keyword_rank_history WHERE content_id=? ORDER BY date DESC LIMIT 100', (cid,), 'rank_history'),
        ('keyword_graph.db', 'SELECT query, opportunity_score, monthly_total, updated_at FROM query_nodes ORDER BY opportunity_score DESC LIMIT 30', (), 'keyword_candidates')]:
        path = root / 'data' / filename
        if not path.exists():
            continue
        try:
            with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as conn:
                conn.row_factory = sqlite3.Row
                result[key] = [dict(r) for r in conn.execute(query, params)]
        except sqlite3.Error as error:
            result.setdefault('errors', []).append(str(error))
    if result['rank_history'] or result['keyword_candidates']:
        result['collection_status'] = 'STORED_OBSERVATIONS'
    return result
