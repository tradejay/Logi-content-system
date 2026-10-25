"""Read-only, run-scoped authoring console data; never trigger model calls."""
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def read(path, fallback=None):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return fallback if fallback is not None else {}


def seconds(start, end):
    try:
        return max(0, (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds())
    except (ValueError, TypeError):
        return None


def usage_object(value):
    """Error logs can contain provider text instead of usage metadata."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            pass
    return {}


def monitor_contents(root):
    root = Path(root)
    registry = root / 'content-system/registry/CONTENT_REGISTRY.csv'
    if not registry.exists():
        return []
    with registry.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    return [{'content_id': r['content_id'], 'title': r.get('title') or r.get('canonical_topic') or r['content_id'],
             'registered_status': r.get('status'),
             'has_brief': (root / 'content-system/01_keyword_ai/briefs' / (r['content_id'] + '.brief.yaml')).is_file()}
            for r in rows if re.fullmatch(r'CNT-[A-Za-z0-9-]+', r.get('content_id', ''))]


def read_monitor(root, cid, run_id=None):
    root = Path(root).resolve()
    if not re.fullmatch(r'CNT-[A-Za-z0-9-]+', cid):
        raise ValueError('Invalid content_id')
    work = root / 'content-system/working' / cid
    latest = read(work / 'pipeline-latest.json')
    runs_root = work / 'runs'
    directories = sorted((p for p in runs_root.iterdir() if p.is_dir() and re.fullmatch(r'[A-Za-z0-9_-]+', p.name)), reverse=True) if runs_root.exists() else []
    history = []
    for p in directories:
        data = read(p / 'run-result.json')
        if p.name == latest.get('run_id'):
            data = latest
        history.append({'run_id': p.name, 'outcome': data.get('outcome', 'UNKNOWN'), 'created_at': data.get('created_at')})
    chosen = run_id or latest.get('run_id') or (directories[0].name if directories else None)
    if chosen and not re.fullmatch(r'[A-Za-z0-9_-]+', chosen):
        raise ValueError('Invalid run_id')
    if not chosen:
        return {'content_id': cid, 'runs': history, 'run_id': None, 'markdown': '', 'calls': [], 'events': [], 'checks': {}}
    directory = (runs_root / chosen).resolve()
    if not directory.is_relative_to(runs_root.resolve()) or not directory.is_dir():
        raise FileNotFoundError('Run not found')
    result = latest if chosen == latest.get('run_id') else read(directory / 'run-result.json')
    brief = read(directory / 'brief.json')
    brief = brief.get('brief', brief)
    contract = read(directory / 'execution-contract.json')
    registry = root / 'content-system/registry/CONTENT_REGISTRY.csv'
    record = {}
    if registry.is_file():
        with registry.open(encoding='utf-8-sig', newline='') as stream:
            record = next((r for r in csv.DictReader(stream) if r['content_id'] == cid), {})
    metrics = []
    labels = [c['label'] for c in contract.get('calls', [])]
    paths = sorted((directory / 'context-metrics').glob('*.json'))
    paths.sort(key=lambda p: labels.index(p.stem) if p.stem in labels else len(labels))
    for p in paths:
        data = read(p)
        usage = usage_object(data.get('usage_metadata'))
        ledger = read(directory / 'rule-audit' / p.name)
        verification = ledger.get('verification') or ledger.get('receipt_verification') or {
            key: ledger[key] for key in ('receipt_status', 'received_ids', 'missing_ids', 'unknown_ids', 'errors') if key in ledger}
        metrics.append({'call': p.stem, 'stage': data.get('stage'),
                        'input_tokens': data.get('input_tokens'),
                        'estimated_input_tokens': (data.get('token_accounting') or {}).get('estimated_input_tokens'),
                        'input_budget': data.get('input_token_budget'), 'within_budget': data.get('within_token_budget'),
                        'output_tokens': usage.get('candidatesTokenCount'), 'thinking_tokens': usage.get('thoughtsTokenCount'),
                        'provider_total_tokens': usage.get('totalTokenCount'), 'provider_input_tokens': usage.get('promptTokenCount'),
                        'dispatch_status': ledger.get('dispatch_status'), 'receipt': verification,
                        'finish_reason': data.get('finish_reason'), 'model': data.get('model_version'),
                        'sent_chars': data.get('sent_chars'), 'token_accounting': data.get('token_accounting'),
                        'rules': ledger.get('entries', []), 'routing': data.get('provider_routing'), 'timestamp': data.get('timestamp')})
    web = read(directory / 'web-research.json')
    if web:
        usage = {} if web.get('cache_hit') else usage_object(web.get('usage_metadata'))
        metrics.insert(0, {'call': 'web_search', 'stage': 'web_search', 'input_tokens': usage.get('promptTokenCount'),
                          'provider_input_tokens': usage.get('promptTokenCount'), 'output_tokens': usage.get('candidatesTokenCount'),
                          'thinking_tokens': usage.get('thoughtsTokenCount'), 'provider_total_tokens': usage.get('totalTokenCount'),
                          'dispatch_status': 'CACHE_REUSED' if web.get('cache_hit') else 'PROVIDER_USAGE' if usage else 'UNMEASURED'})
    production = read(directory / 'image-production.json')
    for item in production.get('items', []):
        asset = item.get('asset') or {}
        usage = usage_object(asset.get('usage_metadata'))
        if item.get('status') != 'generated_pending_review':
            continue
        metrics.append({'call': 'image:' + str(item.get('need_id')), 'stage': 'image_generation',
                        'input_tokens': usage.get('input_tokens_measured'), 'input_budget': 50000,
                        'provider_input_tokens': usage.get('promptTokenCount'), 'output_tokens': usage.get('candidatesTokenCount'),
                        'thinking_tokens': usage.get('thoughtsTokenCount'), 'provider_total_tokens': usage.get('totalTokenCount'),
                        'dispatch_status': 'generated_pending_review', 'rules': usage.get('guide_delivery', []),
                        'receipt': {'status': usage.get('receipt_status')},
                        'routing': {key: usage.get(key) for key in ('key_slot', 'key_tier', 'routing_attempts')}})
    drafts = list((directory / 'revisions').glob('r*.draft.md'))
    drafts.sort(key=lambda p: int(re.search(r'r(\d+)', p.name).group(1)), reverse=True)
    recorded = Path(result.get('draft_file') or '__missing__').resolve()
    if recorded.is_relative_to(directory.resolve()) and recorded.is_file() and result.get('draft_sha256') == hashlib.sha256(recorded.read_bytes()).hexdigest():
        drafts = [recorded]
    markdown = drafts[0].read_text(encoding='utf-8') if drafts else ''
    # Never substitute a draft from another run when this run failed before writing.
    revision = drafts[0].name.split('.')[0] if drafts else None
    events = result.get('natural_logs', [])
    groups = []
    for event in events:
        if not groups or groups[-1]['stage'] != event.get('stage'):
            groups.append({'stage': event.get('stage'), 'at': event.get('at'), 'events': []})
        groups[-1]['events'].append(event)
    end = datetime.now(timezone.utc).isoformat() if result.get('outcome') == 'RUNNING' else result.get('updated_at')
    for i, group in enumerate(groups):
        group['seconds'] = seconds(group['at'], groups[i + 1]['at'] if i + 1 < len(groups) else end)
    totals = {name: sum(c[name] for c in metrics if type(c.get(name)) is int)
              for name in ('input_tokens', 'provider_input_tokens', 'output_tokens', 'thinking_tokens', 'provider_total_tokens')}
    totals['unmeasured_input_calls'] = sum(c.get('input_tokens') is None and c.get('dispatch_status') != 'CACHE_REUSED' for c in metrics)
    from services.asset_display import describe
    asset_bindings = read(directory / 'asset-bindings.json').get('bindings', [])
    for binding in asset_bindings:
        binding['display'] = describe(root, cid, binding)
    return {'content_id': cid, 'run_id': chosen, 'runs': history, 'outcome': result.get('outcome'),
            'stage': result.get('stage'), 'error': result.get('error'), 'created_at': result.get('created_at'),
            'updated_at': result.get('updated_at'), 'elapsed_seconds': seconds(result.get('created_at'), end),
            'release_id': result.get('guide_release_id'), 'publish_ready': bool(result.get('publish_ready')),
            'published_url': record.get('published_url') or '', 'published_date': record.get('published_date') or '',
            'registered_status': record.get('status') or '',
            'keyword': (brief.get('search') or {}).get('primary_keyword'), 'search': brief.get('search'),
            'topic': brief.get('topic'), 'markdown': markdown, 'draft_revision': revision, 'draft_chars': len(markdown),
            'draft_sha256': result.get('draft_sha256'),
            'calls': metrics, 'totals': totals, 'events': events, 'stage_groups': groups,
            'admin_checks': result.get('admin_checks', []),
            'checks': {'qa': result.get('qa'), 'official': result.get('official_review') or result.get('official'),
                       'mechanical': read(directory / 'pipeline-verification.json'),
                       'block_review': read(directory / 'block-review' / (revision + '.write.json')) if revision else None},
            'inputs': {'strategy': read(directory / 'strategy.json'), 'facts': read(directory / 'fact-bundle.json'),
                       'planning_references': read(directory / 'web-planning-discovery.json'),
                       'claims': read(Path(result['claim_map_file'])) if result.get('claim_map_file') and Path(result['claim_map_file']).resolve().is_relative_to(directory.resolve()) else read(directory / 'revisions' / (revision + '.claim-map.json')) if revision else None},
            'token_audit': read(directory / 'token-audit.json'),
            'image_production': read(directory / 'image-production.json'),
            'asset_bindings': asset_bindings,
            'publish_checks': read(directory / 'publish-checks.json') or read(work / 'inspections' / (chosen + '-publish-checks.json')),
            'notes': ['Input measurement includes countTokens-only or blocked calls; provider totals count only recorded generations.',
                      'Missing usage is unknown, not zero; cached search usage is excluded.',
                      'Draft and checks belong to the selected run; a generated draft is not an approved final article.']}
