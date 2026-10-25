import contextlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch

from services.content_pipeline import ContentPipeline, ROOT, atomic

def block_response(value, context):
    if 'block_plan' in context:
        value['blocks'] = [{'id': b['id'], 'markdown': value['markdown'] if i == 0 else '설명 ' + str(i),
                            'claim_ids': [c['id'] for c in value['claims']] if i == 0 else []}
                           for i, b in enumerate(context['block_plan'])]
        value['markdown'] = '\n\n'.join(b['markdown'] for b in value['blocks'])
    return value


class FakeProvider:
    bad_qa = False
    bad_official = False
    image = False
    def __init__(self):
        self.calls = []
    def count_tokens(self, stage, instruction, context):
        return 1200
    def complete(self, stage, instruction, context):
        self.calls.append((stage, instruction, context))
        if stage == 'planning_research':
            value = {'mode': 'product_facts_only', 'reason': 'No related reference', 'article_source_ids': [], 'points': []}
        elif stage == 'naver_edit':
            value = {**context['draft'],'changes':['네이버 문단 편집']}
        elif stage == 'strategy':
            value = dict(article_goal='goal', reader={'questions': ['why']}, primary_playbook='test',
                         must_cover=[], can_omit=[], avoid=[], technical_depth={}, opening='a', body=['b'], closing='c',
                         asset_needs=[{'id': 'image1', 'required': True, 'mode': 'generation_request'}] if self.image else [])
        elif stage == 'write':
            value = {'markdown': '# 장비\n\n화각은 120도입니다.' + ('\n\n{{asset:image1}}' if self.image else ''),
                     'claims': [{'id': 'c1', 'text': '화각은 120도입니다.', 'fact_ids': ['F1']}], 'changes': [], 'used_asset_need_ids': ['image1'] if self.image else [], 'unresolved_items': []}
        elif stage == 'official_interpret':
            value = {'decision': 'continue', 'reason': '원문 대조 완료', 'corrections': [],
                     'claims': [{'id': 'c1', 'verdict': 'confirmed', 'evidence': 'https://example.com/spec',
                                 'detail': 'ok', 'review_quote': 'confirmed'}]}
        else:
            value = {'passed': not self.bad_qa, 'issues': [{'category': 'DRAFT_ERROR'}] if self.bad_qa else [], 'missing_claims': []}
        return json.dumps({'receipt': context['policy_receipt'], 'result': block_response(value, context)}, ensure_ascii=False)
    def official(self, instruction, context):
        if self.bad_official:
            return '불일치 항목입니다'
        return json.dumps({'receipt': context['policy_receipt'], 'result': {'claims': [{'id': 'c1', 'verdict': 'confirmed', 'evidence': 'https://example.com/spec', 'detail': 'ok'}]}})


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        system = self.root / 'content-system'
        # Build an isolated release from source; never copy production release ACLs/pointers.
        shutil.copytree(ROOT / 'content-system/02_writer_ai/authoring', system / '02_writer_ai/authoring', ignore=shutil.ignore_patterns('archive', 'releases'))
        shutil.copytree(ROOT / 'content-system/02_writer_ai/core', system / '02_writer_ai/core')
        target = system / '00_system/templates/articles'
        target.mkdir(parents=True)
        shutil.copyfile(ROOT / 'content-system/00_system/templates/articles/content-block-guides.json', target / 'content-block-guides.json')
        atomic(system / '01_keyword_ai/briefs/CNT-test.brief.yaml', {'topic': '장비', 'search': {'primary_keyword': '장비'}, 'knowledge_packs': ['P1']})
        atomic(system / '03_sources/knowledge/products/P1.yaml', {'knowledge_id': 'P1', 'scope': {'applies_to': ['DEVICE']},
            'facts': [{'id': 'F1', 'value': 120, 'property': 'field_of_view', 'source': {'id': 'S1'}}]})
        atomic(system / '03_sources/INDEX.yaml', {'sources': [{'id': 'S1', 'status': 'VALID', 'path': 'docs/spec.md'}]})
        atomic(system / '03_sources/docs/spec.md', '공식 화각 120도')
        self.provider = FakeProvider()
        self.pipeline = ContentPipeline(self.root, self.provider)
        self.silence = contextlib.redirect_stdout(io.StringIO())
        self.silence.__enter__()
    def tearDown(self):
        self.silence.__exit__(None, None, None)
        for attempt in range(5):
            try:self.tmp.cleanup();break
            except PermissionError:
                if attempt==4:raise
                time.sleep(.1)

    def test_naver_edit_precedes_qa_and_saved_draft(self):
        original=self.provider.complete
        def edit(stage,instruction,context):
            value=json.loads(original(stage,instruction,context))
            if stage=='naver_edit':
                value['result']['markdown']=value['result']['markdown'].replace('설명','안내')
                for block in value['result'].get('blocks',[]):
                    block['markdown']=block['markdown'].replace('설명','안내')
            return json.dumps(value)
        self.provider.complete=edit
        result=self.run_pipeline();run=Path(result['run_directory'])
        self.assertEqual(result['outcome'],'COMPLETED_REVIEW_PENDING',result.get('error'))
        stages=[c[0] for c in self.provider.calls]
        self.assertLess(stages.index('write'),stages.index('naver_edit'))
        self.assertLess(stages.index('naver_edit'),stages.index('feedback'))
        draft=(run/'revisions/r1.draft.md').read_text(encoding='utf-8')
        self.assertIn('안내',draft)
        review=next(c[2] for c in self.provider.calls if c[0]=='feedback')
        self.assertEqual(review['draft']['markdown'],draft)
        self.assertTrue((run/'naver-edit/r1.naver-edit.json').is_file())

    def test_existing_naver_edit_resumes_without_new_writer(self):
        self.run_pipeline();self.provider.calls.clear()
        result=self.pipeline.run('CNT-test',start_stage='feedback',naver_edit_existing=True)
        self.assertEqual(result['outcome'],'COMPLETED_REVIEW_PENDING',result.get('error'))
        stages=[c[0] for c in self.provider.calls]
        self.assertNotIn('write',stages);self.assertEqual(stages[:2],['naver_edit','feedback'])
        from services.pipeline_verifier import verify_pipeline
        self.assertTrue(verify_pipeline(Path(result['run_directory']))['valid'])
    def run_pipeline(self):
        return self.pipeline.run('CNT-test', max_revisions=2)

    def natural_review_provider(self, first_decision):
        original = self.provider.complete
        reviews = []
        def official(instruction, context):
            reviews.append(context)
            return '형식은 지원하지 않습니다. 공식 화각 120도 확인. 명칭 수정이 필요합니다.'
        def complete(stage, instruction, context):
            if stage != 'official_interpret':
                return original(stage, instruction, context)
            decision = first_decision if len(reviews) == 1 else 'continue'
            value = {'decision': decision, 'reason': '제조사 피드백 판단',
                     'claims': [{'id': 'c1', 'verdict': 'confirmed' if decision == 'continue' else 'contradicted',
                                 'evidence': 'https://example.com/spec', 'detail': '정정' if decision == 'rewrite' else '확인',
                                 'review_quote': '공식 화각 120도 확인.'}],
                     'corrections': [{'claim_id': 'c1', 'category': 'naming', 'requested_change': '명칭을 수정한다.',
                                      'review_quote': '명칭 수정이 필요합니다.'}] if decision == 'rewrite' else []}
            return json.dumps({'receipt': context['policy_receipt'], 'result': value}, ensure_ascii=False)
        self.provider.official = official
        self.provider.complete = complete
        return reviews

    def test_natural_official_feedback_repairs_writer_and_rechecks(self):
        reviews = self.natural_review_provider('rewrite')
        original = self.provider.complete
        def complete(stage, instruction, context):
            raw = original(stage, instruction, context)
            if stage == 'write' and context.get('official_feedback'):
                response = json.loads(raw)
                value = response['result']
                value['markdown'] = value['markdown'].replace('화각은 120도입니다.', '공식 화각은 120도입니다.')
                for block in value.get('blocks', []):
                    block['markdown'] = block['markdown'].replace('화각은 120도입니다.', '공식 화각은 120도입니다.')
                value['claims'][0]['text'] = '공식 화각은 120도입니다.'
                value['changes'] = ['공식 피드백의 명칭 정정 적용']
                return json.dumps(response, ensure_ascii=False)
            return raw
        self.provider.complete = complete
        result = self.run_pipeline()
        self.assertEqual(result['outcome'], 'COMPLETED_REVIEW_PENDING')
        self.assertEqual(result['draft_revision'], 2)
        self.assertEqual(len(reviews), 2)
        writers = [c[2] for c in self.provider.calls if c[0] == 'write']
        self.assertEqual(len(writers), 2)
        self.assertEqual(writers[-1]['feedback']['issues'][0]['claim_id'], 'c1')
        run = Path(result['run_directory'])
        self.assertTrue((run / 'reviews/r1.writer-handoff.json').exists())
        self.assertNotEqual((run / 'revisions/r1.draft.md').read_text(encoding='utf-8'), (run / 'revisions/r2.draft.md').read_text(encoding='utf-8'))
        from services.pipeline_verifier import verify_pipeline
        report = verify_pipeline(run)
        self.assertTrue(report['valid'], report)

    def test_natural_official_continue_skips_extra_writer(self):
        reviews = self.natural_review_provider('continue')
        result = self.run_pipeline()
        self.assertEqual(result['outcome'], 'COMPLETED_REVIEW_PENDING')
        self.assertEqual(len(reviews), 1)
        self.assertEqual(result['draft_revision'], 1)
        self.assertEqual(len([c for c in self.provider.calls if c[0] == 'write']), 1)

    def test_natural_official_hold_does_not_rewrite_or_approve(self):
        self.natural_review_provider('hold')
        result = self.run_pipeline()
        self.assertEqual(result['outcome'], 'REVISION_REQUIRED')
        self.assertEqual(len([c for c in self.provider.calls if c[0] == 'write']), 1)

    def test_repeated_official_correction_stops_at_repair_limit(self):
        self.natural_review_provider('rewrite')
        original = self.provider.complete
        def complete(stage, instruction, context):
            raw = original(stage, instruction, context)
            if stage == 'official_interpret':
                response = json.loads(raw)
                value = response['result']
                value['decision'] = 'rewrite'
                value['claims'][0]['verdict'] = 'contradicted'
                value['corrections'] = [{'claim_id': 'c1', 'category': 'naming', 'requested_change': '명칭 수정', 'review_quote': '명칭 수정이 필요합니다.'}]
                return json.dumps(response, ensure_ascii=False)
            return raw
        self.provider.complete = complete
        result = self.run_pipeline()
        self.assertEqual(result['outcome'], 'REVISION_REQUIRED')
        self.assertEqual(result['draft_revision'], 2)
        self.assertTrue(result['official_review']['repair_limit_exhausted'])

    def test_resume_refreshes_new_external_asset_candidate(self):
        self.provider.image = True
        first = self.run_pipeline()
        self.assertIsNone(json.loads((Path(first['run_directory']) / 'asset-bindings.json').read_text(encoding='utf-8'))['bindings'][0]['candidate'])
        candidate = {'asset_id': 'AST-EXTERNAL-1', 'content_id': 'CNT-test', 'need_id': 'image1',
                     'review_status': 'candidate', 'url': '/api/content-system/assets/CNT-test/test.png'}
        atomic(self.root / 'content-system/assets/CNT-test/assets.yaml', {'assets': [candidate]})
        second = self.pipeline.run('CNT-test', start_stage='official')
        binding = json.loads((Path(second['run_directory']) / 'asset-bindings.json').read_text(encoding='utf-8'))['bindings'][0]
        self.assertEqual(binding['candidate']['asset_id'], 'AST-EXTERNAL-1')
        self.assertEqual(binding['status'], 'pending_review')
    def approve(self, result, bindings=None):
        return self.pipeline.approve('CNT-test', result['run_id'], result['draft_sha256'], 'tester', bindings or {},
                                     ['확인함'] * len(result['admin_checks']))
    def test_web_research_logged_but_not_sent_to_writer(self):
        atomic(self.root / 'config/config.json', {'pipeline_web_research_enabled': True})
        candidate = {'status': 'needs_review', 'results': [{'document_id': 'WEB-CANDIDATE'}],
                     'observed_query_count': 1, 'cache_hit': False, 'approved_for_writing': False}
        with patch('services.web_research.research_for_brief', return_value=candidate) as search:
            result = self.run_pipeline()
        search.assert_called_once()
        self.assertEqual(result['web_research_status'], 'needs_review')
        self.assertTrue((Path(result['run_directory']) / 'web-research.json').exists())
        writer = next(c[2] for c in self.provider.calls if c[0] == 'write')
        self.assertNotIn('WEB-CANDIDATE', json.dumps(writer))
        self.assertTrue(any(x['kind'] == 'web_planning_unusable' for x in result['admin_checks']))
        with patch('services.web_research.research_for_brief') as search:
            self.pipeline.run('CNT-test', prepare_only=True)
        search.assert_not_called()

    def test_web_search_failure_keeps_approved_evidence(self):
        atomic(self.root / 'config/config.json', {'pipeline_web_research_enabled': True})
        with patch('services.web_research.research_for_brief', side_effect=RuntimeError('test')):
            result = self.run_pipeline()
        self.assertEqual(result['web_research_status'], 'failed')
        self.assertEqual(result['outcome'], 'COMPLETED_REVIEW_PENDING')
        self.assertTrue(any(x['kind'] == 'web_research_failed' for x in result['admin_checks']))

    def test_trusted_article_reference_reaches_strategy_without_evidence_gate(self):
        atomic(self.root / 'config/config.json', {'pipeline_web_research_enabled': True})
        original = self.provider.complete
        def review(stage, instruction, context):
            if stage == 'planning_research':
                self.assertNotIn('facts', context)
                value = {'mode': 'related_articles', 'reason': 'Related layout article', 'article_source_ids': ['S1'],
                         'points': [{'segment_id': context['segments'][0]['id'], 'use': 'criteria', 'notes': '좌석 배치를 먼저 확인'}]}
                return json.dumps({'receipt': context['policy_receipt'], 'result': value})
            return original(stage, instruction, context)
        self.provider.complete = review
        candidate = {'status': 'trusted', 'results': [{'document_id': 'S1', 'source_location': 'https://avixa.org/test',
                     'trust_policy_id': 'SYS-WEB-SOURCE-TRUST-003'}],
                     'trusted_segments': [{'text': '좌석 배치를 확인한다', 'source_ids': ['S1']}], 'observed_query_count': 1, 'cache_hit': False}
        with patch('services.web_research.research_for_brief', return_value=candidate):
            result = self.run_pipeline()
        self.assertEqual(result['outcome'], 'COMPLETED_REVIEW_PENDING')
        strategy = next(c[2] for c in self.provider.calls if c[0] == 'strategy')
        writer = next(c[2] for c in self.provider.calls if c[0] == 'write')
        self.assertEqual(strategy['planning_references']['mode'], 'related_articles')
        self.assertEqual(writer['facts'][0]['id'], 'F1')
        self.assertNotIn('web_evidence', writer)
        self.assertTrue((Path(result['run_directory']) / 'web-planning-discovery.json').exists())
        ledger = json.loads((Path(result['run_directory']) / 'rule-audit/planning-research.json').read_text(encoding='utf-8'))
        self.assertEqual(ledger['receipt_status'], 'verified')
        self.assertIn('SYS-WEB-SOURCE-TRUST-003', {e['id'] for e in ledger['entries']})
        from scripts.verify_policy_call_logs import verify_run
        self.assertTrue(verify_run(result['run_directory'])['valid'])

    def test_planning_selection_failure_continues_with_product_facts(self):
        atomic(self.root / 'config/config.json', {'pipeline_web_research_enabled': True})
        original = self.provider.complete
        def fail(stage, instruction, context):
            if stage == 'planning_research':
                raise RuntimeError('selection unavailable')
            return original(stage, instruction, context)
        self.provider.complete = fail
        research = {'status': 'trusted', 'observed_query_count': 1, 'cache_hit': False,
                    'results': [{'document_id': 'A', 'source_location': 'https://psni.org/guide',
                                 'trust_policy_id': 'SYS-WEB-SOURCE-TRUST-003'}],
                    'trusted_segments': [{'text': 'Layout principle', 'source_ids': ['A']}]}
        with patch('services.web_research.research_for_brief', return_value=research):
            result = self.run_pipeline()
        self.assertEqual(result['outcome'], 'COMPLETED_REVIEW_PENDING')
        self.assertTrue(any(c['kind'] == 'web_planning_failed' for c in result['admin_checks']))
        strategy = next(c[2] for c in self.provider.calls if c[0] == 'strategy')
        self.assertEqual(strategy['planning_references']['mode'], 'product_facts_only')
        self.assertEqual(strategy['facts'][0]['id'], 'F1')
    def test_writer_metadata_matches_placeholders_and_is_saved(self):
        self.provider.image = True
        result = self.run_pipeline()
        self.assertEqual(result['writer_metadata']['used_asset_need_ids'], ['image1'])
        saved = json.loads((Path(result['run_directory']) / 'writer-metadata.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['draft_sha256'], result['draft_sha256'])
        self.assertTrue(self.pipeline.validate_writer_metadata({'markdown': '{{asset:image1}}', 'used_asset_need_ids': [], 'unresolved_items': []}, [{'id': 'image1'}]))

    def test_asset_wait_does_not_block_writing_but_evidence_does(self):
        draft = {'markdown': '{{asset:image1}}', 'used_asset_need_ids': ['image1'], 'unresolved_items': [{'kind': 'asset', 'need_id': 'image1', 'detail': '제작 대기'}]}
        self.assertEqual(self.pipeline.validate_writer_metadata(draft, [{'id': 'image1'}]), [])
        draft['unresolved_items'] = [{'kind': 'evidence', 'detail': '지원 조건 근거 부족'}]
        self.assertTrue(self.pipeline.validate_writer_metadata(draft, [{'id': 'image1'}]))
        draft['unresolved_items'] = [{'kind': 'asset', 'need_id': 'unknown', 'detail': '대기'}]
        self.assertTrue(self.pipeline.validate_writer_metadata(draft, [{'id': 'image1'}]))

    def test_context_reaches_writer_and_no_automatic_final(self):
        result = self.run_pipeline()
        self.assertEqual(result['outcome'], 'COMPLETED_REVIEW_PENDING')
        ctx = next(c[2] for c in self.provider.calls if c[0] == 'write')
        self.assertNotIn('cautions', ctx)
        ledger = json.loads((Path(result['run_directory']) / 'rule-audit/r1.write.json').read_text(encoding='utf-8'))
        self.assertIn('RULE-OCEANTECH-BRAND-LINKS', {c['id'] for c in ledger['entries']})
        self.assertEqual(ledger['receipt_status'], 'verified')
        self.assertTrue(all(c['body'] and 'sha256' not in c for c in ctx['rules']))
        self.assertNotIn('knowledge', ctx)
        self.assertNotIn('input_refs', ctx)
        self.assertEqual(ctx['sources']['S1']['body'], '공식 화각 120도')
        self.assertFalse((self.root / 'content-system/05_publish/ready/CNT-test.final.md').exists())
        with self.assertRaises(ValueError): self.pipeline.export('CNT-test')

    def test_block_contract_is_sent_logged_and_gates_qa(self):
        result = self.run_pipeline()
        run = Path(result['run_directory'])
        context = next(c[2] for c in self.provider.calls if c[0] == 'write')
        self.assertTrue(context['block_plan'])
        self.assertTrue((run / 'block-plan/r1.write.json').exists())
        review = json.loads((run / 'block-review/r1.write.json').read_text(encoding='utf-8'))
        self.assertTrue(review['passed'])
        original = self.provider.complete
        def incomplete(stage, instruction, context):
            response = json.loads(original(stage, instruction, context))
            if stage == 'write':
                response['result']['blocks'] = response['result']['blocks'][:-1]
            return json.dumps(response)
        self.provider.complete = incomplete
        failed = self.run_pipeline()
        self.assertEqual(failed['outcome'], 'REVISION_REQUIRED')
        self.assertTrue(failed['qa']['contract_errors'])

    def test_receipt_mismatch_stops_pipeline_and_preserves_raw(self):
        original = self.provider.complete
        def broken(stage, instruction, context):
            response = json.loads(original(stage, instruction, context))
            response['receipt']['ids'] = []
            return json.dumps(response)
        self.provider.complete = broken
        result = self.run_pipeline()
        self.assertEqual(result['outcome'], 'FAILED')
        run = Path(result['run_directory'])
        ledger = json.loads((run / 'rule-audit/strategy.json').read_text(encoding='utf-8'))
        self.assertEqual(ledger['receipt_status'], 'failed')
        self.assertTrue((run / 'responses/strategy.json').exists())
        self.assertFalse((run / 'strategy.json').exists())

    def test_periodic_audit_detects_altered_input_and_missing_receipt(self):
        from scripts.verify_policy_call_logs import verify_run
        result = self.run_pipeline()
        run = Path(result['run_directory'])
        report = verify_run(run)
        self.assertTrue(report['valid'], report['findings'])
        path = run / 'prompts/r1.write.json'
        record = json.loads(path.read_text(encoding='utf-8'))
        record['prompt']['context']['rules'][0]['body'] = '변조'
        atomic(path, record)
        self.assertFalse(verify_run(run)['valid'])
        (run / 'rule-audit/strategy.json').unlink()
        report = verify_run(run)
        self.assertTrue(any(item['call'] == 'strategy' for item in report['findings']))

    def test_token_budget_blocks_generation_and_records_count(self):
        self.provider.count_tokens = lambda *args: 50001
        result = self.run_pipeline()
        self.assertEqual(result['outcome'], 'FAILED')
        self.assertEqual(self.provider.calls, [])
        run = Path(result['run_directory'])
        metrics = json.loads((run / 'context-metrics/strategy.json').read_text(encoding='utf-8'))
        self.assertEqual(metrics['input_tokens'], 50001)
        self.assertFalse(metrics['within_token_budget'])

    def test_token_count_failure_does_not_generate(self):
        def broken(*args):
            raise RuntimeError('counter unavailable')
        self.provider.count_tokens = broken
        result = self.run_pipeline()
        self.assertEqual(result['outcome'], 'FAILED')
        self.assertEqual(self.provider.calls, [])
        metrics = json.loads((Path(result['run_directory']) / 'context-metrics/strategy.json').read_text(encoding='utf-8'))
        self.assertEqual(metrics['token_count_status'], 'failed')
    def test_approval_is_revision_bound(self):
        result = self.run_pipeline()
        approved = self.approve(result)
        self.assertTrue(approved['publish_ready'])
        rendered = self.pipeline.export('CNT-test')
        self.assertIn('화각은 120도입니다.', rendered['html'])
        self.pipeline.save_edit('CNT-test', '수정됨')
        with self.assertRaises(ValueError): self.pipeline.assert_publishable('CNT-test')

    def test_naver_copy_export_checks_selected_approved_revision(self):
        result = self.run_pipeline()
        with self.assertRaises(ValueError):
            self.pipeline.export('CNT-test', expected_run_id=result['run_id'], expected_sha256=result['draft_sha256'])
        self.approve(result)
        with self.assertRaises(ValueError):
            self.pipeline.export('CNT-test', expected_run_id='old-run', expected_sha256=result['draft_sha256'])
        with self.assertRaises(ValueError):
            self.pipeline.export('CNT-test', expected_run_id=result['run_id'], expected_sha256='old-digest')
        exported = self.pipeline.export('CNT-test', expected_run_id=result['run_id'], expected_sha256=result['draft_sha256'])
        self.assertEqual(exported['run_id'], result['run_id'])
        self.assertEqual(exported['draft_sha256'], result['draft_sha256'])
        self.assertIn('화각은 120도입니다.', exported['html'])
        with self.assertRaises(ValueError): self.approve(result)
    def test_failed_qa_exhaustion_never_publishes(self):
        self.provider.bad_qa = True
        result = self.run_pipeline()
        self.assertEqual(result['outcome'], 'REVISION_REQUIRED')
        self.assertEqual(result['draft_revision'], 2)
        with self.assertRaises(ValueError): self.approve(result)
    def test_malformed_official_response_never_passes(self):
        self.provider.bad_official = True
        result = self.run_pipeline()
        self.assertEqual(result['official_review']['status'], 'ERROR')
        self.assertIn('raw', result['official_review'])
        with self.assertRaises(ValueError): self.approve(result)
    def test_missing_fact_source_blocks_before_ai(self):
        (self.root / 'content-system/03_sources/docs/spec.md').unlink()
        self.assertEqual(self.run_pipeline()['outcome'], 'NEEDS_EVIDENCE')
        self.assertEqual(self.provider.calls, [])
    def test_image_request_requires_explicit_binding(self):
        self.provider.image = True
        result = self.run_pipeline()
        with self.assertRaises(ValueError): self.approve(result)
        approved = self.approve(result, {'image1': {'url': 'https://example.com/image.png', 'origin': 'generated',
            'evidence': '설명용 그림 검토', 'caption': '설명', 'asset_id': 'A1'}})
        self.assertTrue(approved['publish_ready'])
    def test_invalid_ids_and_concurrent_runs_blocked(self):
        with self.assertRaises(ValueError): self.pipeline.run('../escape')
        with self.pipeline.lock('CNT-test'):
            with self.assertRaises(ValueError): self.run_pipeline()
    def test_saved_edit_and_feedback_reach_rewriter(self):
        self.pipeline.save_edit('CNT-test', '관리자 수정 원고')
        self.pipeline.run('CNT-test', user_feedback='마감을 수정')
        ctx = next(c[2] for c in self.provider.calls if c[0] == 'write')
        self.assertEqual(ctx['previous_draft']['markdown'], '관리자 수정 원고')
        self.assertEqual(ctx['user_feedback'], '마감을 수정')
    def test_api_uses_shared_pipeline_and_force_cannot_bypass(self):
        from flask import Flask
        from services.content_ops_api import content_ops_bp
        app = Flask(__name__)
        app.register_blueprint(content_ops_bp)
        with patch('services.content_pipeline.ContentPipeline', return_value=self.pipeline):
            client = app.test_client()
            response = client.post('/api/content-system/contents/CNT-test/generate-draft')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['pipeline']['outcome'], 'COMPLETED_REVIEW_PENDING')
            response = client.post('/api/content-system/contents/CNT-test/status', json={'new_status': 'PUBLISHED', 'force': True})
            self.assertEqual(response.status_code, 409)
            response = client.get('/api/content-system/blog-export/CNT-test')
            self.assertEqual(response.status_code, 409)

    def test_resume_from_write_inherits_strategy(self):
        first = self.run_pipeline()
        self.assertEqual(first['outcome'], 'COMPLETED_REVIEW_PENDING')
        self.provider.calls.clear()
        resumed = self.pipeline.run('CNT-test', start_stage='write')
        self.assertEqual(resumed['outcome'], 'COMPLETED_REVIEW_PENDING')
        called_stages = [c[0] for c in self.provider.calls]
        self.assertNotIn('strategy', called_stages)
        self.assertIn('write', called_stages)
        self.assertIn('feedback', called_stages)
        self.assertTrue(len(resumed['natural_logs']) > 3)
        self.assertTrue(any('전략' in log['message'] or '원고' in log['message'] for log in resumed['natural_logs']))

    def test_resume_from_official_runs_only_official(self):
        self.run_pipeline()
        self.provider.calls.clear()
        resumed = self.pipeline.run('CNT-test', start_stage='official')
        self.assertEqual(resumed['outcome'], 'COMPLETED_REVIEW_PENDING')
        self.assertTrue(all(c[0]=='official_interpret' for c in self.provider.calls))
        self.assertEqual(resumed['official_review']['status'], 'REVIEWED')

    def test_resume_from_official_blocks_if_draft_modified(self):
        self.run_pipeline()
        # Modify draft.md externally
        self.pipeline.draft_path('CNT-test').write_text('외부에서 수정된 원고', encoding='utf-8')
        res = self.pipeline.run('CNT-test', start_stage='official')
        self.assertEqual(res['outcome'], 'FAILED')
        self.assertIn('Draft changed', res['error'])

    def test_resume_from_feedback_runs_correction_loop(self):
        self.run_pipeline()
        self.provider.calls.clear()
        # Set bad_qa once then pass on rewrite
        call_count = {'fb': 0}
        orig_complete = self.provider.complete
        def complete_with_retry(stage, instruction, context):
            if stage == 'feedback':
                call_count['fb'] += 1
                if call_count['fb'] == 1:
                    return json.dumps({'receipt': context['policy_receipt'], 'result': {'passed': False, 'issues': [{'category': 'ACCURACY', 'detail': '오류'}], 'missing_claims': []}})
                else:
                    return json.dumps({'receipt': context['policy_receipt'], 'result': {'passed': True, 'issues': [], 'missing_claims': []}})
            return orig_complete(stage, instruction, context)
        self.provider.complete = complete_with_retry

        resumed = self.pipeline.run('CNT-test', start_stage='feedback', max_revisions=3)
        self.assertEqual(resumed['outcome'], 'COMPLETED_REVIEW_PENDING')
        self.assertEqual(call_count['fb'], 2)  # r1 feedback (failed) -> r2 write -> r2 feedback (passed)
        self.assertEqual(resumed['draft_revision'], 2)

    def test_official_error_blocks_completed_status(self):
        self.provider.bad_official = True
        result = self.run_pipeline()
        self.assertEqual(result['outcome'], 'REVISION_REQUIRED')
        self.assertFalse(result['publish_ready'])
        self.assertEqual(result['official_review']['status'], 'ERROR')

    def test_official_surrounding_text_parsed(self):
        orig_official = self.provider.official
        def official_with_text(instruction, context):
            return "검토 결과 설명문입니다.\n\n" + orig_official(instruction, context) + "\n\n참고 사항 끝."
        self.provider.official = official_with_text
        result = self.run_pipeline()
        self.assertEqual(result['outcome'], 'COMPLETED_REVIEW_PENDING')
        self.assertEqual(result['official_review']['status'], 'REVIEWED')

    def test_common_banner_is_loaded_into_assets(self):
        from services.pipeline_context import load_context
        # Create common banner in INDEX.yaml of mock root
        idx_p = self.root / 'content-system/03_sources/assets/INDEX.yaml'
        idx_p.parent.mkdir(parents=True, exist_ok=True)
        idx_p.write_text('assets:\n- asset_id: AST-COMPANY-OCEAN-001\n  url: https://example.com/banner.png\n  product: ALL\n', encoding='utf-8')
        ctx = load_context(self.root, 'CNT-test')
        asset_ids = {a['asset_id'] for a in ctx['assets']}
        self.assertIn('AST-COMPANY-OCEAN-001', asset_ids)

    def test_inquiry_banner_binding_reconciled(self):
        # Setup mock banner in INDEX.yaml
        idx_p = self.root / 'content-system/03_sources/assets/INDEX.yaml'
        idx_p.parent.mkdir(parents=True, exist_ok=True)
        idx_p.write_text('assets:\n- asset_id: AST-COMPANY-OCEAN-001\n  url: https://example.com/banner.png\n  product: ALL\n', encoding='utf-8')
        # Setup strategy with oceantech-inquiry-opening
        def complete_with_banner(stage, instruction, context):
            if stage == 'naver_edit':
                return json.dumps({**context['draft'],'changes':[]})
            if stage == 'strategy':
                return '{"article_goal": "g", "reader": {"questions": ["q"]}, "primary_playbook": "test", "must_cover": [], "can_omit": [], "avoid": [], "technical_depth": {}, "opening": "o", "body": ["b"], "closing": "c", "asset_needs": [{"id": "oceantech-inquiry-opening", "required": true, "mode": "reused_asset"}]}'
            elif stage == 'write':
                return '{"markdown": "# Test\\n\\n화각은 120도입니다.\\n\\n{{asset:oceantech-inquiry-opening}}", "claims": [{"id": "c1", "text": "화각은 120도입니다.", "fact_ids": ["F1"]}], "changes": [], "used_asset_need_ids":["oceantech-inquiry-opening"],"unresolved_items":[]}'
            return '{"passed": true, "issues": [], "missing_claims": []}'
        self.provider.complete = lambda stage, instruction, context: json.dumps({'receipt': context['policy_receipt'], 'result': block_response(json.loads(complete_with_banner(stage, instruction, context)), context)})
        res = self.pipeline.run('CNT-test')
        bindings_file = Path(res['run_directory']) / 'asset-bindings.json'
        bdata = json.loads(bindings_file.read_text(encoding='utf-8'))
        banner_b = next(b for b in bdata['bindings'] if b['need']['id'] == 'oceantech-inquiry-opening')
        self.assertEqual(banner_b['candidate']['asset_id'], 'AST-COMPANY-OCEAN-001')

    def test_assert_publishable_blocks_when_input_refs_modified(self):
        # 1. 정상 파이프라인 실행 및 승인
        result = self.run_pipeline()
        approved = self.approve(result)
        self.assertTrue(approved['publish_ready'])
        # 변경 전에는 assert_publishable 통과
        self.pipeline.assert_publishable('CNT-test')

        # 2. input_refs 중 하나의 파일(예: brief.yaml) 내용 수정
        brief_p = self.root / 'content-system/01_keyword_ai/briefs/CNT-test.brief.yaml'
        brief_p.write_text('topic: "수정된 주제"\nsearch:\n  primary_keyword: "k"\nrequired_sources: ["SRC-1"]\n', encoding='utf-8')

        # 3. 이제 assert_publishable이 변경을 감지하고 ValueError를 발생시켜야 함
        with self.assertRaises(ValueError) as ctx:
            self.pipeline.assert_publishable('CNT-test')
        self.assertIn('Publishing blocked', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()



