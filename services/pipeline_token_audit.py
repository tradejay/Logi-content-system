"""Offline input accounting. Estimates never replace provider countTokens."""
from collections import defaultdict
from pathlib import Path
import json
import math
import statistics

FIXED_FIELDS = {'guides', 'rules', 'cautions', 'block_guides', 'policy_receipt', 'playbooks'}
PROFILES = {
    'short': dict(article_chars=3500, blocks=14, claims=20, facts=14, reference_items=6,
                  reference_chars=250, source_chars=1800, strategy_chars=1400, brief_chars=700),
    'standard': dict(article_chars=5000, blocks=20, claims=30, facts=20, reference_items=8,
                     reference_chars=350, source_chars=3000, strategy_chars=2000, brief_chars=1000),
    'long': dict(article_chars=8000, blocks=26, claims=45, facts=30, reference_items=8,
                 reference_chars=500, source_chars=5000, strategy_chars=3000, brief_chars=1400),
}


def text_chars(instruction, context):
    return len(instruction) + len(json.dumps(context, ensure_ascii=False, default=str, separators=(',', ':')))


def calibration_from_runs(run_dirs):
    samples = defaultdict(list)
    for root in run_dirs:
        root = Path(root)
        for path in (root / 'context-metrics').glob('*.json'):
            try:
                metrics = json.loads(path.read_text(encoding='utf-8'))
                count = metrics.get('input_tokens')
                if metrics.get('token_count_status') != 'measured' or type(count) is not int or count <= 0:
                    continue
                prompt = json.loads((root / 'prompts' / path.name).read_text(encoding='utf-8'))['prompt']
                chars = text_chars(prompt['instruction'], prompt['context'])
                if chars:
                    samples[metrics['stage']].append({'run_id': root.name, 'call': path.stem,
                        'chars': chars, 'tokens': count, 'tokens_per_char': count / chars})
            except (OSError, ValueError, KeyError, TypeError):
                continue
        web = root / 'web-research.json'
        if web.exists():
            try:
                data = json.loads(web.read_text(encoding='utf-8'))
                usage, request = data.get('usage_metadata') or {}, data.get('request') or {}
                count = usage.get('promptTokenCount') if isinstance(usage, dict) else None
                if not data.get('cache_hit') and type(count) is int and count > 0 and request.get('instruction'):
                    chars = text_chars(request['instruction'], {'query': '(site:avixa.org OR site:psni.org) ' + request['query']})
                    samples['web_search'].append({'run_id': root.name, 'call': 'web_search', 'chars': chars,
                                                  'tokens': count, 'tokens_per_char': count / chars})
            except (OSError, ValueError, KeyError, TypeError):
                pass
    return dict(samples)


def estimate_input(stage, instruction, context, calibration=None, budget=50000, measured=None):
    calibration = calibration or {}
    samples = calibration.get(stage, [])
    ratios = [s['tokens_per_char'] for s in samples]
    ratio = statistics.median(ratios) if ratios else 0.5
    low = min(ratios) * 0.8 if ratios else 0.35
    high = max(ratios) * 1.2 if ratios else 0.65
    parts = {'instruction': len(instruction)}
    parts.update({k: len(json.dumps(v, ensure_ascii=False, default=str, separators=(',', ':'))) for k, v in context.items()})
    total_chars = text_chars(instruction, context)
    fixed_chars = len(instruction) + sum(parts.get(k, 0) for k in FIXED_FIELDS)
    center, lower, upper = (math.ceil(total_chars * r) for r in (ratio, low, high))
    if type(measured) is int and measured >= 0:
        status = 'MEASURED_WITHIN_BUDGET' if measured <= budget else 'MEASURED_OVER_BUDGET'
    else:
        status = 'ESTIMATED_WITHIN_RANGE' if upper <= budget else 'ESTIMATED_OVER_BUDGET' if lower > budget else 'ESTIMATED_BORDERLINE'
    findings = []
    if fixed_chars > total_chars / 2:
        findings.append('Fixed instructions/policies dominate: review overlap before splitting article work.')
    draft = context.get('draft') or {}
    if isinstance(draft, dict) and isinstance(draft.get('markdown'), str) and any('markdown' in b for b in draft.get('blocks', []) if isinstance(b, dict)):
        findings.append('Draft text is present both in markdown and block markdown.')
    return {'stage': stage, 'status': status, 'actual_input_tokens': measured,
            'estimated_input_tokens': center, 'estimated_range': [lower, upper], 'budget': budget,
            'total_chars': total_chars, 'fixed_chars': fixed_chars, 'variable_chars': total_chars - fixed_chars,
            'fixed_share_percent': round(100 * fixed_chars / max(1, total_chars), 1),
            'fields': [{'name': k, 'chars': n, 'estimated_tokens': math.ceil(n * ratio)}
                       for k, n in sorted(parts.items(), key=lambda item: -item[1])],
            'calibration_samples': len(samples), 'tokens_per_char': round(ratio, 4),
            'estimate_method': 'stage median observed tokens/serialized characters; range is sensitivity, not a confidence interval',
            'findings': findings, 'quality_compliance': 'not_evaluated'}


def audit_saved_run(run_directory):
    root = Path(run_directory)
    rows = []
    for path in sorted((root / 'prompts').glob('*.json')):
        try:
            prompt = json.loads(path.read_text(encoding='utf-8'))['prompt']
            metrics = json.loads((root / 'context-metrics' / path.name).read_text(encoding='utf-8'))
            row = estimate_input(metrics['stage'], prompt['instruction'], prompt['context'],
                                 budget=metrics.get('input_token_budget', 50000), measured=metrics.get('input_tokens'))
            row['call'] = path.stem
            ledger_path = root / 'rule-audit' / path.name
            if ledger_path.exists():
                ledger = json.loads(ledger_path.read_text(encoding='utf-8'))
                row['sequence'] = ledger.get('sequence', 0)
                row['dispatch_status'] = ledger.get('dispatch_status', 'unknown')
            rows.append(row)
        except (OSError, ValueError, KeyError, TypeError) as error:
            rows.append({'call': path.stem, 'status': 'INVALID_LOG', 'error': type(error).__name__})
    rows.sort(key=lambda row: row.get('sequence', 0))
    web_path = root / 'web-research.json'
    if web_path.exists():
        try:
            data = json.loads(web_path.read_text(encoding='utf-8'))
            usage = data.get('usage_metadata') or {}
            count = usage.get('promptTokenCount') if isinstance(usage, dict) else None
            rows.insert(0, {'call': 'web_search', 'stage': 'web_search',
                           'status': 'CACHE_REUSED' if data.get('cache_hit') else 'MEASURED_PROVIDER_USAGE' if type(count) is int else 'UNMEASURED',
                           'actual_input_tokens': 0 if data.get('cache_hit') else count,
                           'note': 'Cache hits do not cause a new search-model generation.'})
        except (OSError, ValueError, TypeError, AttributeError):
            rows.insert(0, {'call': 'web_search', 'status': 'INVALID_LOG'})
    return {'version': 1, 'run_id': root.name, 'calls': rows,
            'actual_input_tokens_total': sum(r['actual_input_tokens'] for r in rows if type(r.get('actual_input_tokens')) is int),
            'unmeasured_calls': [r['call'] for r in rows if r.get('actual_input_tokens') is None],
            'scope': 'Prepared input counts, not billing. Budget-blocked calls may have countTokens but no generation. Output, thinking, grounding fees and images excluded.'}
