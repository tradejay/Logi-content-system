"""Read-only periodic integrity check: python -m scripts.verify_policy_call_logs RUN_DIRECTORY."""
import argparse
import json
from pathlib import Path
from services.policy_call_audit import encoded, sha, verify_receipt
from services.pipeline_provider import parse_object
from services.block_authoring import validate_blocks


def verify_run(run_directory):
    root = Path(run_directory)
    findings = []
    prompts = list((root / 'prompts').glob('*.json'))
    if not prompts:
        return {'valid': False, 'calls_checked': 0, 'findings': ['no_call_logs']}
    for path in prompts:
        label = path.stem
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
            prompt = record['prompt']
            ledger = json.loads((root / 'rule-audit' / path.name).read_text(encoding='utf-8'))
            if sha(prompt['instruction']) != ledger['instruction_sha256'] or sha(encoded(prompt['context'])) != ledger['context_sha256']:
                raise ValueError('sent_input_hash_mismatch')
            if prompt['release_id'] != ledger['release_id'] or prompt['context']['policy_receipt']['bundle'] != ledger['bundle']:
                raise ValueError('bundle_or_release_mismatch')
            if prompt['context']['policy_receipt']['ids'] != [e['alias'] for e in ledger['entries']]:
                raise ValueError('sent_id_mapping_mismatch')
            from services.context_transport import expand_fact_scopes, restore_review_draft
            if ledger.get('fact_scope_transport') == 'shared_scopes_v1':
                originals = {f['id']: f for f in json.loads((root / 'fact-bundle.json').read_text(encoding='utf-8'))['facts']}
                for fact in expand_fact_scopes(prompt['context']):
                    if fact['id'] not in originals or fact.get('scope') != originals[fact['id']].get('scope'):
                        raise ValueError('shared_fact_scope_changed')
            if ledger.get('draft_transport') == 'body_spans_v1':
                restored = restore_review_draft(prompt['context'])
                rev = label.split('.')[0]
                stored = json.loads((root / 'revisions' / (rev + '.writer-metadata.json')).read_text(encoding='utf-8'))
                if restored.get('blocks') != stored.get('blocks'):
                    raise ValueError('review_block_span_mismatch')
            for entry in ledger['entries']:
                if entry['kind'] == 'prompt':
                    if entry['body_sha256'] != prompt['prompt_sha256'] or entry['id'] != prompt['prompt_version']:
                        raise ValueError('prompt_mapping_mismatch')
                    continue
                if entry['kind'] == 'guide':
                    body = prompt['context']['guides'][entry['alias']]
                else:
                    field = 'rules' if entry['kind'] == 'rule' else 'cautions'
                    body = next(r['body'] for r in prompt['context'][field] if r['id'] == entry['alias'])
                if sha(body) != entry['body_sha256']:
                    raise ValueError('policy_body_hash_mismatch')
            selection = root / 'context-selection' / path.name
            if selection.exists():
                selected = json.loads(selection.read_text(encoding='utf-8'))
                expected = {r['id'] for r in selected['selected_rules']} | set(ledger.get('runtime_rule_ids', []))
                if expected != {r['id'] for r in ledger['entries'] if r['kind'] == 'rule'}:
                    raise ValueError('selection_delivery_mismatch')
                if 'selected_guides' in selected:
                    if {g['id'] for g in selected['selected_guides']} != {g['id'] for g in ledger['entries'] if g['kind'] == 'guide'}:
                        raise ValueError('guide_selection_delivery_mismatch')
                    from services.context_optimization import SERVER_GUIDES
                    manifest = json.loads((root / 'guide-manifest.json').read_text(encoding='utf-8'))
                    for guide in selected.get('server_guides', []):
                        approved = manifest['guides'][guide['id']]
                        if guide['source_sha256'] != SERVER_GUIDES.get(guide['id']) or guide['source_sha256'] != approved['sha256']:
                            raise ValueError('server_guide_revision_mismatch')
                    if ledger.get('context_optimization') != selected.get('optimization'):
                        raise ValueError('optimization_audit_mismatch')
                    expected_policy = selected.get('fact_policy') or {}
                    if expected_policy:
                        sent_policy = prompt['context'].get('fact_policy') or {}
                        if set(expected_policy.get('excluded_fact_ids', [])) != set(sent_policy.get('excluded_fact_ids', [])) or expected_policy.get('block_fact_ids') != sent_policy.get('block_fact_ids', {}):
                            raise ValueError('fact_policy_delivery_mismatch')
                        if set(sent_policy.get('excluded_fact_ids', [])) & {f['id'] for f in prompt['context'].get('facts', [])}:
                            raise ValueError('excluded_fact_delivered')
            metrics = json.loads((root / 'context-metrics' / path.name).read_text(encoding='utf-8'))
            if ledger['stage'] != 'official':
                if metrics.get('token_count_status') != 'measured' or metrics.get('within_token_budget') is not True:
                    raise ValueError('token_budget_not_verified')
            raw = json.loads((root / 'responses' / path.name).read_text(encoding='utf-8'))['raw']
            if ledger['stage'] == 'official' and ledger.get('receipt_status') == 'external_response_preserved':
                if not isinstance(raw, str) or not raw.strip():
                    raise ValueError('empty_external_review')
                # External manufacturer text has no receipt; its internal interpreter must have one.
                interpreter_label = label + '-interpret'
                interpreter_ledger = json.loads((root / 'rule-audit' / (interpreter_label + '.json')).read_text(encoding='utf-8'))
                interpreter_prompt = json.loads((root / 'prompts' / (interpreter_label + '.json')).read_text(encoding='utf-8'))['prompt']
                if interpreter_ledger.get('receipt_status') != 'verified' or interpreter_prompt['context'].get('official_raw') != raw:
                    raise ValueError('external_review_interpreter_missing')
                continue
            checked = verify_receipt(parse_object(raw), ledger)
            if checked['receipt_status'] != 'verified' or ledger['receipt_status'] != 'verified':
                raise ValueError('receipt_not_verified')
            block_plan = prompt['context'].get('block_plan')
            if block_plan:
                aliases = {e['id']: e['alias'] for e in ledger['entries'] if e['kind'] == 'rule'}
                sent_blocks = []
                for block in ledger.get('block_assignments', []):
                    guides = [{key: value for key, value in guide.items() if key != 'source_policy_refs'} for guide in block.get('guide', [])]
                    sent_blocks.append({**block, 'guide': guides, 'rule_ids': [aliases[rid] for rid in block['rule_ids']]})
                if ledger.get('block_guide_transport') == 'deduplicated_roles_v1':
                    from services.policy_call_audit import pack_block_guides
                    sent_blocks, catalog = pack_block_guides(sent_blocks)
                    if catalog != prompt['context'].get('block_guides'):
                        raise ValueError('block_guide_catalog_mismatch')
                if sent_blocks != block_plan:
                    raise ValueError('block_rule_assignment_mismatch')
                if validate_blocks(parse_object(raw)['result'], block_plan):
                    raise ValueError('block_contract_failed')
        except (OSError, ValueError, KeyError, TypeError, StopIteration) as error:
            findings.append({'call': label, 'error': type(error).__name__, 'detail': str(error) if isinstance(error, ValueError) else 'missing_or_invalid_artifact'})
    return {'valid': not findings, 'calls_checked': len(prompts), 'findings': findings,
            'scope': 'delivery_and_receipt_integrity_only', 'compliance_status': 'not_evaluated'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_directory')
    args = parser.parse_args()
    report = verify_run(args.run_directory)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report['valid'] else 1)


if __name__ == '__main__':
    main()
