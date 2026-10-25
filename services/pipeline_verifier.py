"""Offline execution-contract, provenance and end-to-end handoff verification."""
import hashlib
import json
import re
from pathlib import Path

from scripts.verify_policy_call_logs import verify_run as verify_calls
from services.pipeline_provider import parse_object
from services.web_planning import planning_input, finalize, RULE_ID
from services.web_source_policy import allowed_url, POLICY_ID

COMPLETED = {'COMPLETED_REVIEW_PENDING', 'COMPLETED_READY'}
META = {'schema_version', 'content_id', 'run_id', 'artifact_revision', 'created_at', 'input_refs'}


def strip_meta(value):
    return {k: v for k, v in value.items() if k not in META}


def sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def verify_pipeline(run_directory):
    root = Path(run_directory).resolve()
    checks, warnings = [], []

    def check(name, operation):
        try:
            detail = operation()
            checks.append({'check': name, 'status': 'PASS', 'detail': detail or 'ok'})
        except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
            checks.append({'check': name, 'status': 'FAIL', 'detail': str(exc)})

    def read(name):
        return json.loads((root / name).read_text(encoding='utf-8'))

    def require(ok, message):
        if not ok:
            raise ValueError(message)

    try:
        contract, result = read('execution-contract.json'), read('run-result.json')
        if not isinstance(contract, dict) or not isinstance(result, dict):
            raise ValueError('invalid_execution_contract_or_result')
    except (OSError, ValueError) as exc:
        return {'valid': False, 'status': 'UNSUPPORTED', 'pipeline_complete': False,
                'checks': [], 'findings': [{'check': 'execution_contract', 'detail': str(exc)}],
                'warnings': ['실행 계약 없는 구버전 로그는 전체 검증 완료로 판정하지 않습니다.'],
                'semantic_compliance': 'not_evaluated'}

    calls = contract.get('calls', [])
    if not isinstance(calls, list) or any(not isinstance(c, dict) for c in calls):
        return {'valid': False, 'status': 'FAIL', 'pipeline_complete': False,
                'findings': [{'check': 'call_inventory', 'detail': 'invalid_call_inventory'}]}
    records, responses, ledgers = {}, {}, {}
    start = contract.get('start_stage')
    outcome = result.get('outcome')
    complete = outcome in COMPLETED

    def artifacts():
        require(contract.get('version') == 1, 'unsupported_contract_version')
        require(outcome in COMPLETED | {'PREPARED', 'NEEDS_EVIDENCE', 'FAILED', 'REVISION_REQUIRED'}, 'invalid_terminal_outcome')
        require(contract.get('outcome') == outcome and start == result.get('start_stage'), 'execution_result_mismatch')
        hashes = contract.get('artifacts', {})
        require(hashes and 'run-result.json' in hashes, 'empty_artifact_manifest')
        for name, expected in hashes.items():
            path = (root / name).resolve()
            require(path.is_relative_to(root), 'artifact_path_outside_run')
            require(path.is_file(), 'missing_artifact: ' + name)
            require(hashlib.sha256(path.read_bytes()).hexdigest() == expected, 'artifact_hash_mismatch: ' + name)
        actual = {str(p.relative_to(root)).replace('\\', '/') for folder in ('prompts', 'responses', 'rule-audit', 'revisions')
                  for p in (root / folder).glob('*') if p.is_file()}
        require(actual <= set(hashes), 'unregistered_call_or_revision_artifact')
        require(contract.get('run_id') == result.get('run_id') == root.name, 'run_identity_mismatch')

    check('artifact_integrity', artifacts)

    def call_inventory():
        require([c['sequence'] for c in calls] == list(range(1, len(calls) + 1)), 'invalid_call_sequence')
        labels = [c['label'] for c in calls]
        require(len(labels) == len(set(labels)), 'duplicate_call_label')
        require(set(labels) == {p.stem for p in (root / 'prompts').glob('*.json')}, 'call_inventory_mismatch')
        for c in calls:
            label = c['label']
            require(re.fullmatch(r'[a-z0-9.-]+', label) is not None, 'invalid_call_label')
            prompt = read('prompts/' + label + '.json')['prompt']
            ledger = read('rule-audit/' + label + '.json')
            require(ledger.get('sequence') == c['sequence'] and ledger['stage'] == c['stage'], 'call_sequence_ledger_mismatch')
            records[label], ledgers[label] = prompt['context'], ledger
            if (root / ('responses/' + label + '.json')).exists():
                try:
                    responses[label] = parse_object(read('responses/' + label + '.json')['raw'])['result']
                except (ValueError, KeyError, TypeError):
                    pass  # Failed calls are judged by the saved failure contract below.
        if not calls:
            require(outcome in ('PREPARED', 'NEEDS_EVIDENCE', 'FAILED'), 'missing_all_calls')
            return 'intentional pre-dispatch stop'
        report = verify_calls(root)
        planning = read('web-planning-discovery.json') if (root / 'web-planning-discovery.json').exists() else {}
        for finding in report['findings']:
            match = re.fullmatch(r'r(\d+)\.write', finding.get('call', ''))
            repaired_block_error = False
            if match and finding.get('detail') == 'block_contract_failed':
                revision = int(match[1])
                qa_path = root / ('revisions/r' + str(revision) + '.feedback.json')
                if qa_path.exists():
                    blocked = read('revisions/r' + str(revision) + '.feedback.json')
                    repaired_block_error = (blocked.get('passed') is False and bool(blocked.get('contract_errors')) and
                                            any(c['stage'] == 'write' and int(c['label'].split('.')[0][1:]) > revision for c in calls))
            optional_failure = (finding.get('call') == 'planning-research' and planning.get('status') == 'failed'
                                and finding.get('detail') in ('missing_or_invalid_artifact', 'receipt_not_verified', 'token_budget_not_verified'))
            terminated_failure = (outcome in ('FAILED', 'REVISION_REQUIRED') and
                                  finding.get('detail') in ('missing_or_invalid_artifact', 'receipt_not_verified', 'token_budget_not_verified'))
            if optional_failure or terminated_failure or repaired_block_error:
                warnings.append({'check': 'call_integrity', **finding, 'status': 'recorded_call_failure'})
            else:
                raise ValueError('call_integrity: ' + str(finding))

    check('call_inventory_and_receipts', call_inventory)

    def lineage():
        previous = contract.get('resume_source_run_id')
        if not previous:
            require(start not in ('assets', 'write', 'feedback', 'official') or not complete, 'missing_resume_origin')
            return 'fresh run'
        require(Path(previous).name == previous and previous != root.name, 'invalid_resume_origin')
        prior = root.parent / previous
        require(prior.is_dir(), 'missing_resume_run')
        # These stages consume saved planning/strategy rather than silently recomputing them.
        for name in ('web-planning-discovery.json', 'strategy.json'):
            if (prior / name).exists() and (root / name).exists():
                old = json.loads((prior / name).read_text(encoding='utf-8'))
                prior_contract = json.loads((prior / 'execution-contract.json').read_text(encoding='utf-8'))
                require(prior_contract.get('artifacts', {}).get(name) == hashlib.sha256((prior / name).read_bytes()).hexdigest(), 'resume_origin_artifact_hash_mismatch: ' + name)
                require(strip_meta(old) == strip_meta(read(name)), 'inherited_artifact_mismatch: ' + name)
        if start in ('feedback', 'official') and complete:
            inherited = read('revision-input.json').get('previous_draft', {}).get('markdown')
            require(isinstance(inherited, str), 'missing_inherited_draft')
            maps = [json.loads(p.read_text(encoding='utf-8')) for p in (prior / 'revisions').glob('*.claim-map.json')]
            require(any(m.get('draft_sha256') == sha(inherited) for m in maps), 'inherited_draft_without_matching_claim_map')
        return previous

    check('resume_lineage', lineage)

    def web_planning():
        if outcome in ('PREPARED', 'NEEDS_EVIDENCE') and not (root / 'web-planning-discovery.json').exists():
            return 'stopped before planning'
        planning = strip_meta(read('web-planning-discovery.json'))
        brief = read('brief.json')['brief']
        research = read('web-research.json') if (root / 'web-research.json').exists() else {}
        request = brief.get('web_research', {})
        enabled = contract.get('web_research_enabled') and request is not False and not (isinstance(request, dict) and request.get('enabled') is False)
        if enabled and start in ('inputs', 'strategy') and not contract.get('prepare_only'):
            require(bool(research), 'missing_web_search_stage')
        if research.get('status') == 'trusted':
            request_log = research.get('request', {})
            require(all(isinstance(request_log.get(k), str) and request_log[k] for k in ('instruction', 'query', 'model')), 'missing_web_search_request')
            source_contract = contract
            if contract.get('resume_source_run_id'):
                source_contract = json.loads((root.parent / contract['resume_source_run_id'] / 'execution-contract.json').read_text(encoding='utf-8'))
            require(sha(request_log['instruction']) == source_contract.get('web_search_instruction_sha256'), 'web_search_instruction_mismatch')
            require(sha(request_log['model'] + request_log['instruction'] + request_log['query']) == research.get('request_sha256'), 'web_search_request_fingerprint_mismatch')
            require(research.get('finish_reason') == 'STOP' and research.get('search_queries'), 'missing_successful_grounded_search')
            require(research.get('source_policy', {}).get('id') == POLICY_ID, 'missing_source_trust_policy')
            sources = {s['document_id']: s for s in research['results']}
            for s in sources.values():
                require(allowed_url(s['source_location']) and s.get('trust_policy_id') == POLICY_ID and s.get('trust_score') == 1.0, 'untrusted_web_source')
            for segment in research.get('trusted_segments', []):
                require(segment.get('source_ids') and set(segment['source_ids']) <= set(sources), 'unsupported_grounding_segment')
                # Recheck saved Google's citation text and chunk indices without network access.
                supports = research.get('grounding_metadata', {}).get('groundingSupports', [])
                index_sources = {i: s['document_id'] for s in sources.values() for i in s.get('grounding_chunk_indices', [])}
                def support_text(support):
                    seg = support.get('segment', {})
                    if seg.get('text'):
                        return seg['text']
                    text = research.get('raw_summary', '')
                    begin, end = seg.get('startIndex', 0), seg.get('endIndex', 0)
                    if type(begin) is int and type(end) is int and 0 <= begin < end <= len(text):
                        return text[begin:end]
                    return None
                require(any(support_text(s) == segment['text'] and
                            s.get('groundingChunkIndices') and
                            all(i in index_sources for i in s['groundingChunkIndices']) and
                            list(dict.fromkeys(index_sources[i] for i in s['groundingChunkIndices'])) == segment['source_ids']
                            for s in supports), 'grounding_provenance_mismatch')
        payload = planning_input(brief, research)
        if 'planning-research' in responses and planning.get('status') != 'failed':
            sent = records['planning-research']
            require(all(sent.get(k) == payload[k] for k in ('topic', 'search', 'sources', 'segments')), 'planning_search_handoff_mismatch')
            require({RULE_ID, POLICY_ID} <= {e['id'] for e in ledgers['planning-research']['entries']}, 'missing_planning_rule_receipt')
            expected = finalize(responses['planning-research'], payload)
            normalized_planning = {**planning, 'excluded_article_source_ids': planning.get('excluded_article_source_ids', [])}
            require(expected == normalized_planning, 'planning_selection_output_mismatch')
        elif not contract.get('resume_source_run_id'):
            require(planning.get('mode') == 'product_facts_only' and not planning.get('points') and not planning.get('sources'), 'unsupported_planning_fallback')
            require(not payload['segments'] or planning.get('status') == 'failed', 'missing_planning_selection_call')
            if planning.get('status') == 'failed':
                require(any(c.get('kind') == 'web_planning_failed' for c in result.get('admin_checks', [])), 'unlogged_planning_failure')
                warnings.append({'check': 'planning_selection', 'status': 'recorded_failure', 'detail': '제품 Fact로 대체 진행'})
        for c in calls:
            if c['stage'] in ('strategy', 'write', 'feedback'):
                require(records[c['label']].get('planning_references') == planning, 'planning_context_not_delivered: ' + c['label'])
                require(RULE_ID in {e['id'] for e in ledgers[c['label']]['entries']}, 'missing_planning_context_rule')
        return planning['mode']

    check('avixa_psni_search_selection_delivery', web_planning)

    def flow_and_facts():
        stages = [c['stage'] for c in calls]
        require(all(s in ('planning_research', 'strategy', 'write', 'naver_edit', 'feedback', 'official', 'official_interpret') for s in stages), 'unknown_stage')
        if 'planning_research' in stages:
            require(stages.index('planning_research') == 0, 'planning_must_precede_strategy')
        narrative = [s for s in stages if s != 'planning_research']
        allowed_next = {'strategy': {'write'}, 'write': {'naver_edit','feedback'}, 'naver_edit':{'feedback'}, 'feedback': {'write', 'official'}, 'official': {'official_interpret'}, 'official_interpret': {'write'}}
        for before, after in zip(narrative, narrative[1:]):
            require(after in allowed_next[before], 'invalid_stage_transition: ' + before + ' -> ' + after)
        if complete:
            require(stages and stages[-1] in ('official', 'official_interpret'), 'missing_terminal_official_stage')
            if start in ('inputs', 'strategy'):
                require('strategy' in stages and stages.index('strategy') < stages.index('write'), 'missing_or_misordered_strategy')
            if start in ('inputs', 'strategy', 'assets', 'write'):
                require('write' in stages and 'feedback' in stages, 'missing_writer_or_feedback_stage')
            if start == 'feedback':
                require('feedback' in stages, 'missing_resumed_feedback')
        facts = {f['id']: f for f in read('fact-bundle.json')['facts']}
        if complete:
            require(facts and not read('fact-bundle.json').get('missing'), 'completed_with_missing_product_evidence')
            strategy = strip_meta(read('strategy.json'))
            writer_strategy = read('writer-context.json')['strategy']
            require({k: v for k, v in writer_strategy.items() if k != 'asset_needs'} ==
                    {k: v for k, v in strategy.items() if k != 'asset_needs'}, 'writer_strategy_changed')
            plan = read('asset-plan.json')['needs']
            require([n['id'] for n in plan] == [n['id'] for n in strategy['asset_needs']], 'asset_plan_strategy_mismatch')
            bindings = read('asset-bindings.json')['bindings']
            require({b['need']['id'] for b in bindings} == {n['id'] for n in plan}, 'asset_binding_coverage_mismatch')
        for c in calls:
            stage, label = c['stage'], c['label']
            if stage=='naver_edit' and label in responses:
                from services.naver_editor import apply_edit
                rev=label.split('.')[0]
                writer_label=rev+'.write'
                original=records[label].get('draft',{})
                if writer_label not in responses:
                    require(contract.get('naver_edit_existing') and start=='feedback','unexpected_standalone_naver_edit')
                    require(original.get('markdown')==read('revision-input.json').get('previous_draft',{}).get('markdown'),'naver_edit_wrong_inherited_draft')
                edited=apply_edit(original,responses[label],records[label].get('editable_block_ids'))
                require(edited['markdown']==(root/('revisions/'+rev+'.draft.md')).read_text(encoding='utf-8'),'naver_edit_output_not_saved')
                require(edited['claims']==read('revisions/'+rev+'.claim-map.json')['claims'],'naver_edit_claims_not_saved')
            if stage not in ('strategy', 'write', 'feedback', 'official'):
                continue
            from services.context_transport import expand_fact_scopes, restore_review_draft
            for f in expand_fact_scopes(records[label]):
                require(f.get('id') in facts, 'unknown_or_web_promoted_product_fact')
                for key in ('value', 'unit', 'property', 'scope', 'knowledge_id'):
                    if key in f:
                        require(f[key] == facts[f['id']].get(key), 'product_fact_changed: ' + f['id'] + '.' + key)
                require(('scope' in f) == ('scope' in facts[f['id']]), 'product_fact_scope_missing: ' + f['id'])
            if stage == 'feedback':
                rev = label.split('.')[0]
                require((root / ('revisions/' + rev + '.draft.md')).exists(), 'feedback_without_revision_draft')
                draft = (root / ('revisions/' + rev + '.draft.md')).read_text(encoding='utf-8')
                require(records[label].get('draft', {}).get('markdown') == draft, 'feedback_reviewed_wrong_draft')
                if ledgers[label].get('draft_transport') == 'body_spans_v1':
                    original = restore_review_draft(records[label])
                    require(original.get('blocks') == responses.get(rev + '.write', {}).get('blocks') or
                            original.get('blocks') == strip_meta(read('revisions/' + rev + '.writer-metadata.json')).get('blocks'),
                            'feedback_block_spans_changed')
                qa = read('revisions/' + rev + '.feedback.json')
                require(qa.get('draft_sha256') == sha(draft), 'feedback_revision_hash_mismatch')
                if label in responses:
                    require(all(qa.get('feedback', {}).get(k) == responses[label].get(k) for k in ('passed', 'issues', 'missing_claims')), 'feedback_response_not_used')
            if stage in ('write', 'feedback'):
                stored = read('writer-context.json')
                expected_strategy = stored['strategy']
                if ledgers[label].get('context_optimization'):
                    from services.context_optimization import apply_fact_policy, optimize_context
                    refreshed, _ = apply_fact_policy({**stored['context'], 'strategy': expected_strategy})
                    optimized, _ = optimize_context(stage, {**refreshed, 'asset_plan': stored['asset_plan']})
                    expected_strategy = optimized['strategy']
                actual_strategy = records[label].get('strategy', {})
                require({k: v for k, v in actual_strategy.items() if k != 'asset_needs'} ==
                        {k: v for k, v in expected_strategy.items() if k != 'asset_needs'}, 'strategy_not_delivered: ' + label)
                if 'asset_needs' in actual_strategy:
                    require(actual_strategy['asset_needs'] == stored['strategy'].get('asset_needs'), 'strategy_asset_needs_changed: ' + label)
            if stage == 'strategy' and label in responses:
                require(strip_meta(read('strategy.json')) == responses[label], 'strategy_output_not_used')
            if stage == 'write' and label in responses:
                call_index = calls.index(c)
                if call_index and calls[call_index - 1]['stage'] == 'official_interpret':
                    origin = calls[call_index - 1]['label']
                    interpreted = responses.get(origin, {})
                    from services.official_feedback import writer_feedback
                    require(interpreted.get('decision') == 'rewrite', 'writer_dispatched_without_official_repair')
                    sent_feedback = records[label].get('feedback', {})
                    require(sent_feedback == writer_feedback(interpreted), 'official_feedback_not_delivered_to_writer')
                    require(records[label].get('official_raw') == records[origin].get('official_raw'), 'manufacturer_text_not_delivered_to_writer')
                    require(records[label].get('previous_draft', {}).get('markdown') == records[origin].get('draft', {}).get('markdown'), 'official_repair_wrong_previous_draft')
                rev = label.split('.')[0]
                draft = (root / ('revisions/' + rev + '.draft.md')).read_text(encoding='utf-8')
                edit_label=label.replace('.write','.naver-edit')
                if edit_label in responses:
                    from services.naver_editor import apply_edit
                    require(records[edit_label].get('draft',{}).get('markdown')==responses[label].get('markdown'),'naver_edit_wrong_input')
                    edited=apply_edit(responses[label],responses[edit_label],records[edit_label].get('editable_block_ids'))
                    require(edited['markdown']==draft,'naver_edit_output_not_saved')
                    require(read('revisions/'+rev+'.claim-map.json')['claims']==edited['claims'],'naver_edit_claims_not_saved')
                else:
                    require(responses[label].get('markdown') == draft, 'writer_output_not_saved')
        return stages

    check('stage_order_and_product_fact_separation', flow_and_facts)

    def final_review():
        if not result.get('draft_revision'):
            require(not complete, 'completed_without_draft')
            return 'stopped before final draft'
        rev = 'r' + str(result['draft_revision'])
        draft = (root / ('revisions/' + rev + '.draft.md')).read_text(encoding='utf-8')
        claims = read('revisions/' + rev + '.claim-map.json')
        require(sha(draft) == result.get('draft_sha256') == claims.get('draft_sha256'), 'final_draft_hash_mismatch')
        metadata = read('writer-metadata.json')
        require(metadata.get('draft_sha256') == sha(draft), 'writer_metadata_revision_mismatch')
        facts = {f['id'] for f in read('fact-bundle.json')['facts']}
        require(len({c['id'] for c in claims['claims']}) == len(claims['claims']), 'duplicate_claim_id')
        for c in claims['claims']:
            require(c.get('fact_ids') and set(c['fact_ids']) <= facts, 'claim_has_unknown_fact')
        if complete:
            from services.content_pipeline import ContentPipeline
            plan = read('asset-plan.json')['needs']
            fact_items = read('fact-bundle.json')['facts']
            errors = ContentPipeline.validate_draft(draft, claims['claims'], fact_items, plan)
            errors += ContentPipeline.validate_writer_metadata({'markdown': draft, **strip_meta(metadata)}, plan)
            require(not errors, 'final_draft_contract_errors: ' + str(errors))
            require(result.get('qa', {}).get('passed') is True, 'completed_with_failed_qa')
            qa = read('revisions/' + rev + '.feedback.json')
            require(qa.get('passed') is True and qa.get('draft_sha256') == sha(draft), 'final_qa_revision_mismatch')
            official = read('reviews/' + rev + '.official.json')
            require(official.get('status') == 'REVIEWED' and official.get('draft_sha256') == sha(draft), 'completed_without_matching_official_review')
            reviewed = official['claims']
            require(len(reviewed) == len(claims['claims']) and {c['id'] for c in reviewed} == {c['id'] for c in claims['claims']}, 'official_claim_coverage_mismatch')
            require(all(c.get('verdict') == 'confirmed' and c.get('evidence') for c in reviewed), 'completed_with_unconfirmed_claim')
            label = rev + '.official'
            interpreted_label = label + '-interpret'
            natural = ledgers.get(label, {}).get('receipt_status') == 'external_response_preserved'
            require(label in records and (label in responses or natural), 'missing_official_call')
            sent = records[label]
            require(sent.get('draft', {}).get('markdown') == draft and sent.get('claims') == claims['claims'], 'official_reviewed_wrong_draft_or_claims')
            if natural or official.get('interpretation'):
                from services.official_feedback import validate_interpretation
                raw = read('responses/' + label + '.json')['raw']
                require(interpreted_label in responses, 'missing_official_interpretation')
                interpretation = responses[interpreted_label]
                validate_interpretation(interpretation, claims['claims'], raw)
                require(interpretation['decision'] == 'continue' and interpretation['claims'] == reviewed, 'official_interpretation_output_mismatch')
                require(records[interpreted_label].get('official_raw') == raw and records[interpreted_label].get('claims') == claims['claims'] and records[interpreted_label].get('draft', {}).get('markdown') == draft, 'official_interpretation_wrong_input')
            else:
                require(responses[label].get('claims') == reviewed, 'official_response_output_mismatch')
            required = {f for c in claims['claims'] for f in c['fact_ids']}
            require({f['id'] for f in sent.get('facts', [])} == required, 'official_missing_linked_facts')
            for f in sent.get('facts', []):
                sid = (f.get('source') or {}).get('id') or (f.get('source') or {}).get('source_id')
                require(sid in sent.get('sources', {}), 'official_missing_source_location')
        return 'matching draft / Claim / Fact / official review' if complete else '원고·Claim 연결만 확인. 전체 검토는 미완료.'

    check('final_draft_qa_and_logitech_review', final_review)
    if (root / 'publish-checks.json').exists():
        def publish_integrity():
            report = read('publish-checks.json')
            revision = result.get('draft_revision')
            if not revision:
                candidates = sorted((root / 'revisions').glob('r*.draft.md'), key=lambda p: int(p.name.split('.')[0][1:]))
                require(bool(candidates), 'publish_check_has_no_draft')
                path = candidates[-1]
            else:
                path = root / 'revisions' / f'r{revision}.draft.md'
            require(report.get('draft_sha256') == sha(path.read_text(encoding='utf-8')), 'publish_check_draft_mismatch')
            return '발행 전 검사와 원고 hash 일치'
        check('publish_check_revision_integrity', publish_integrity)
    if (root / 'image-production.json').exists():
        def image_integrity():
            report = read('image-production.json')
            project = root.parents[4]
            for item in report.get('items', []):
                if item.get('status') != 'generated_pending_review': continue
                asset = item.get('asset') or {}
                path = (project / asset.get('local_path', '')).resolve()
                require(path.is_relative_to((project / 'content-system/assets').resolve()), 'generated_image_outside_asset_directory')
                require(path.is_file(), 'generated_image_missing')
                require(hashlib.sha256(path.read_bytes()).hexdigest() == asset.get('sha256'), 'generated_image_hash_mismatch')
                require(asset.get('review_status') == 'candidate', 'generation_must_not_auto_approve')
            return '생성 이미지 파일·후보 등록 확인; 시각 검토는 별도'
        check('image_candidate_integrity', image_integrity)
    findings = [c for c in checks if c['status'] == 'FAIL']
    valid = not findings
    return {'verifier_id': 'SYS-PIPELINE-VERIFY-005', 'verifier_version': 1,
            'valid': valid, 'status': 'FAIL' if not valid else 'NOT_COMPLETE' if not complete else 'PASS_WITH_WARNINGS' if warnings else 'PASS',
            'pipeline_complete': complete and valid, 'outcome': outcome, 'start_stage': start,
            'checks': checks, 'findings': findings, 'warnings': warnings,
            'scope': 'execution_integrity_and_data_handoffs', 'semantic_compliance': 'not_evaluated'}
