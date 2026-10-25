"""Single entry point for the authoring lifecycle. Policy comes from MD inputs."""
import argparse
import hashlib
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time
import uuid

from services.pipeline_context import load_context, gap_snapshot, digest
from services.pipeline_provider import ModelProvider, parse_object, configuration
from services.policy_call_audit import prepare_call, verify_receipt
from services.block_authoring import build_block_plan, validate_blocks, BLOCK_INSTRUCTION, planner_instruction, repair_targets, validate_preserved_blocks
from services.pipeline_payload import compact_payload, payload_size
from services.guide_repository import GuideRepository
from services.context_assembler import ContextAssembler
from services.prompt_repository import LocalPromptRepository
from services.guide_contracts import ReviewReport, ReviewItem, ReviewCheckCategory, ReviewStatus, CoverageReport

ROOT = Path(__file__).resolve().parents[1]


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    tmp.write_text(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    for attempt in range(6):
        try:
            os.replace(tmp,path)
            break
        except PermissionError as error:
            if os.name!='nt' or getattr(error,'winerror',None) not in {5,32} or attempt==5:
                raise
            time.sleep(.05*(attempt+1))


class ContentPipeline:
    def __init__(self, root=ROOT, provider=None, progress=None):
        self.root = Path(root)
        self.system = self.root / 'content-system'
        self.provider = provider or ModelProvider(self.root)
        self.progress = progress

    def work(self, cid):
        if not re.fullmatch(r'CNT-[A-Za-z0-9-]+', cid):
            raise ValueError('Invalid content_id')
        return self.system / 'working' / cid

    @contextmanager
    def lock(self, cid, run_id=None):
        import psutil
        import threading
        import uuid
        from services.pipeline_status import (
            SERVER_INSTANCE_TOKEN, read_pipeline_lock, check_process_liveness,
            cross_process_gate
        )
        lock_token = uuid.uuid4().hex
        path = self.work(cid) / 'pipeline.lock'
        path.parent.mkdir(parents=True, exist_ok=True)

        with cross_process_gate(self.root, cid):
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                existing = read_pipeline_lock(self.root, cid)
                liveness = check_process_liveness(existing) if existing else 'UNKNOWN'
                if liveness == 'ALIVE':
                    raise ValueError(f'Pipeline busy: content {cid} is currently being processed by PID {existing.get("pid")}')
                elif liveness == 'DEAD':
                    raise ValueError(f'Pipeline lock from terminated process detected for {cid}; inspect and recover interrupted run before starting')
                else:
                    raise ValueError('Pipeline busy; inspect pipeline.lock before recovering an interrupted run')
            try:
                cur_proc = psutil.Process()
                lock_payload = {
                    'content_id': cid,
                    'run_id': run_id,
                    'lock_token': lock_token,
                    'pid': os.getpid(),
                    'process_create_time': cur_proc.create_time(),
                    'server_token': SERVER_INSTANCE_TOKEN,
                    'thread_id': threading.get_ident(),
                    'started_at': datetime.now(timezone.utc).isoformat(),
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                    'status': 'RUNNING',
                    'stage': 'init'
                }
                os.write(fd, json.dumps(lock_payload, ensure_ascii=False).encode('utf-8'))
            finally:
                os.close(fd)

        try:
            yield lock_token
        finally:
            with cross_process_gate(self.root, cid):
                current = read_pipeline_lock(self.root, cid)
                if current and current.get('lock_token') == lock_token:
                    path.unlink(missing_ok=True)

    def latest(self, cid):
        path = self.work(cid) / 'pipeline-latest.json'
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None

    def draft_path(self, cid):
        self.work(cid)
        latest = self.latest(cid) or {}
        if latest.get('execution_type') == 'ide' and latest.get('draft_file'):
            path = Path(latest['draft_file']).resolve()
            if not path.is_relative_to((self.work(cid) / 'runs').resolve()) or not path.is_file():
                raise ValueError('현재 IDE 원고 파일을 확인하세요.')
            return path
        return self.system / f'02_writer_ai/drafts/{cid}.draft.md'

    def _generate_coverage_and_review_report(
        self,
        cid,
        run_id,
        revision,
        markdown,
        claims,
        feedback,
        errors,
        official,
        admin_checks,
        guide_manifest,
        requirements=None,
        selected_rule_ids=None,
    ):
        structural_items = []
        for err in (errors or []):
            structural_items.append(ReviewItem(
                id=f"ERR-{uuid.uuid4().hex[:6]}",
                category=ReviewCheckCategory.STRUCTURAL,
                status=ReviewStatus.VIOLATION,
                detail=str(err)
            ))

        semantic_items = []
        for issue in (feedback.get('issues') or []):
            semantic_items.append(ReviewItem(
                id=issue.get('id', f"ISSUE-{uuid.uuid4().hex[:6]}"),
                rule_id=issue.get('rule_id'),
                category=ReviewCheckCategory.SEMANTIC,
                status=ReviewStatus.UNRESOLVED,
                detail=issue.get('detail', str(issue))
            ))
        for mc in (feedback.get('missing_claims') or []):
            semantic_items.append(ReviewItem(
                id=f"MISSING-{uuid.uuid4().hex[:6]}",
                category=ReviewCheckCategory.SEMANTIC,
                status=ReviewStatus.UNRESOLVED,
                detail=f"누락된 핵심 주장/팩트: {mc}"
            ))

        # Official review contradictions/insufficient evidence as semantic items
        if official and isinstance(official.get('claims'), list):
            for c in official['claims']:
                v = c.get('verdict')
                if v in ('contradicted', 'insufficient_evidence', 'out_of_scope'):
                    semantic_items.append(ReviewItem(
                        id=f"OFFICIAL-{c.get('id')}",
                        category=ReviewCheckCategory.SEMANTIC,
                        status=ReviewStatus.UNRESOLVED,
                        detail=f"공식 검증 불일치({v}): {c.get('text', '')} (근거: {c.get('evidence', '없음')})"
                    ))

        human_items = []
        for chk in (admin_checks or []):
            human_items.append(ReviewItem(
                id=f"ADMIN-{uuid.uuid4().hex[:6]}",
                category=ReviewCheckCategory.HUMAN,
                status=ReviewStatus.UNRESOLVED,
                detail=chk.get('detail') or str(chk)
            ))

        # Comprehensive requirements coverage evaluation
        reqs_map = dict(requirements or {})
        if not reqs_map:
            for rid, rdata in guide_manifest.rules.items():
                reqs_map[rid] = {'id': rid, 'kind': 'rule', 'severity': rdata.get('severity', 'blocking')}

        coverage_details = {}
        satisfied_reqs = []
        unresolved_reqs = []
        not_app_reqs = []

        active_rule_ids = set(guide_manifest.rules.keys())
        applied_rules = set(selected_rule_ids) if selected_rule_ids is not None else active_rule_ids
        violated_rules = {it.rule_id for it in semantic_items if it.rule_id}

        cited_fact_ids = set()
        fact_evidence_map = {}
        for c in (claims or []):
            c_text = c.get('text', '')
            citation = c.get('citation', '')
            c_in_md = False
            if markdown:
                if (c_text and c_text in markdown) or (citation and citation in markdown):
                    c_in_md = True
                elif c_text:
                    words = [w for w in c_text.split() if len(w) > 1]
                    if words and sum(1 for w in words if w in markdown) >= max(1, len(words) // 2):
                        c_in_md = True

            for fid in c.get('fact_ids', []):
                if c_in_md:
                    cited_fact_ids.add(fid)
                    fact_evidence_map[fid] = f"원고 인용 확인 (주장 {c.get('id')}: {c_text[:30]}...)"

        # Check official review evidence for facts
        if official and isinstance(official.get('claims'), list):
            for oc in official['claims']:
                claim_id = oc.get('id')
                # Find matching claim to get fact_ids
                matching_claim = next((c for c in (claims or []) if c.get('id') == claim_id), None)
                if matching_claim:
                    for fid in matching_claim.get('fact_ids', []):
                        if oc.get('verdict') == 'confirmed':
                            fact_evidence_map[fid] = f"공식 AI 일치 확인: {oc.get('evidence', '')}"
                        elif oc.get('verdict') in ('contradicted', 'insufficient_evidence'):
                            fact_evidence_map[fid] = f"공식 AI 검증 불일치({oc.get('verdict')}): {oc.get('detail', '')}"

        for req_id, req_data in sorted(reqs_map.items()):
            kind = req_data.get('kind', 'rule')
            if kind == 'rule':
                if req_id not in applied_rules:
                    not_app_reqs.append(req_id)
                    coverage_details[req_id] = {
                        'kind': 'rule',
                        'status': 'not_applicable',
                        'reason': '이번 문단/단계에 선택/배정되지 않음'
                    }
                elif req_id in violated_rules or errors:
                    unresolved_reqs.append(req_id)
                    coverage_details[req_id] = {
                        'kind': 'rule',
                        'status': 'unresolved',
                        'evidence': '규칙 위반 이슈 또는 계약 오류 발생'
                    }
                elif feedback.get('passed', False):
                    satisfied_reqs.append(req_id)
                    coverage_details[req_id] = {
                        'kind': 'rule',
                        'status': 'satisfied',
                        'evidence': f"피드백 QA 검토 통과 (r{revision})"
                    }
                else:
                    unresolved_reqs.append(req_id)
                    coverage_details[req_id] = {
                        'kind': 'rule',
                        'status': 'unresolved',
                        'evidence': '피드백 미통과 상태'
                    }
            elif kind == 'fact':
                if req_id in cited_fact_ids:
                    # Check if official contradicted this fact
                    ev = fact_evidence_map.get(req_id, '')
                    if '불일치' in ev:
                        unresolved_reqs.append(req_id)
                        coverage_details[req_id] = {
                            'kind': 'fact',
                            'status': 'unresolved',
                            'evidence': ev
                        }
                    else:
                        satisfied_reqs.append(req_id)
                        coverage_details[req_id] = {
                            'kind': 'fact',
                            'status': 'satisfied',
                            'evidence': ev
                        }
                else:
                    unresolved_reqs.append(req_id)
                    coverage_details[req_id] = {
                        'kind': 'fact',
                        'status': 'unresolved',
                        'evidence': '원고 본문 내 인용 또는 Claim 연결 없음'
                    }

        for req_id in unresolved_reqs:
            req_info = coverage_details.get(req_id, {})
            if not any(it.rule_id == req_id for it in semantic_items):
                semantic_items.append(ReviewItem(
                    id=f"UNRES-{req_id}",
                    rule_id=req_id if req_info.get('kind') == 'rule' else None,
                    category=ReviewCheckCategory.SEMANTIC,
                    status=ReviewStatus.UNRESOLVED,
                    detail=f"요구사항 미충족({req_info.get('kind', 'requirement')}): {req_id} - {req_info.get('evidence', '미해결')}"
                ))

        all_unresolved = [it for it in (structural_items + semantic_items) if it.status != ReviewStatus.SATISFIED]
        official_ok = (official is None) or (official.get('status') == 'REVIEWED' and not any(c.get('verdict') != 'confirmed' for c in official.get('claims', [])))
        final_passed = (len(all_unresolved) == 0 and len(unresolved_reqs) == 0 and bool(feedback.get('passed', False)) and not errors and official_ok)

        cov = CoverageReport(
            requirements=coverage_details,
            satisfied=satisfied_reqs,
            unresolved=unresolved_reqs,
            not_applicable=not_app_reqs,
            passed=final_passed
        )

        rep = ReviewReport(
            run_id=run_id,
            content_id=cid,
            passed=final_passed,
            structural_checks=structural_items,
            semantic_checks=semantic_items,
            human_checks=human_items,
            unresolved_items=all_unresolved,
            satisfied_requirements=satisfied_reqs,
            summary=f"검토 완료: 합격 여부={final_passed}, 구조적 결함={len(structural_items)}, 의미적 이슈={len(semantic_items)}, 사람 확인 대기={len(human_items)}"
        )

        md_lines = [
            f"# 종합 검토 보고서: {cid} (r{revision})",
            f"- **실행 ID**: `{run_id}`",
            f"- **정책 릴리스**: `{guide_manifest.release_id}`",
            f"- **최종 판정**: {'✅ 합격 (Passed)' if final_passed else '❌ 미흡 (Action Required)'}",
            f"- **원고 글자수**: {len(markdown or ''):,}자",
            f"- **원고 해시**: `{digest(markdown or '')}`",
            f"- **요구사항 커버리지**: 충족 {len(satisfied_reqs)}건 / 미해결 {len(unresolved_reqs)}건 / 비해당 {len(not_app_reqs)}건",
            "",
            "## 1. 구조 검증 (Structural Checks)",
        ]
        if not structural_items:
            md_lines.append("- 결함 없음 (구조 계약 및 포맷 100% 통과)")
        else:
            for s in structural_items:
                md_lines.append(f"- ❌ [{s.status.value}] {s.detail}")

        md_lines.extend(["", "## 2. 의미 검토 (Semantic Checks)"])
        if not semantic_items:
            md_lines.append("- 이슈 없음 (팩트 일치 및 가이드 요구사항 충족)")
        else:
            for m in semantic_items:
                md_lines.append(f"- ⚠️ [{m.status.value}] {m.detail}")

        md_lines.extend(["", "## 3. 관리자 확인 대기 (Human Approval Items)"])
        if not human_items:
            md_lines.append("- 관리자 수동 조치 사항 없음")
        else:
            for h in human_items:
                md_lines.append(f"- 🔍 [{h.status.value}] {h.detail}")

        return cov, rep, "\n".join(md_lines)

    def run(self, cid, max_revisions=3, prepare_only=False, user_feedback='', start_stage=None, resume_run_id=None, naver_edit_existing=False):
        if not 1 <= max_revisions <= 5:
            raise ValueError('max_revisions must be 1..5')
        if start_stage and start_stage not in {'inputs', 'strategy', 'assets', 'write', 'feedback', 'official'}:
            raise ValueError(f'Invalid start_stage: {start_stage}')
        if naver_edit_existing and start_stage!='feedback':
            raise ValueError('Existing Naver edit must resume from feedback')
        run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]
        with self.lock(cid, run_id=run_id):
            return self._run(cid, max_revisions, prepare_only, user_feedback, start_stage, resume_run_id, run_id=run_id,naver_edit_existing=naver_edit_existing)

    def _run(self, cid, max_revisions, prepare_only, user_feedback, start_stage=None, resume_run_id=None, run_id=None,naver_edit_existing=False):
        if not run_id:
            run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]
        run_dir = self.work(cid) / 'runs' / run_id
        meta = {'schema_version': '1.0.0', 'content_id': cid, 'run_id': run_id,
                'artifact_revision': 1, 'created_at': datetime.now(timezone.utc).isoformat(), 'input_refs': []}
        result = {**meta, 'outcome': 'RUNNING', 'publish_ready': False, 'admin_checks': [],
                  'knowledge_queue': [], 'run_directory': str(run_dir),
                  'start_stage': start_stage or 'inputs', 'natural_logs': []}
        execution_contract = {'version': 1, 'start_stage': start_stage or 'inputs',
                              'naver_edit_existing':naver_edit_existing,
                              'prepare_only': prepare_only, 'calls': [], 'resume_source_run_id': None}

        def save(name, data):
            atomic(run_dir / name, {**meta, **data} if isinstance(data, dict) else data)

        def log_entry(stage, title, message, status='INFO'):
            entry = {
                'at': datetime.now(timezone.utc).isoformat(),
                'stage': stage,
                'title': title,
                'message': message,
                'status': status
            }
            result['natural_logs'].append(entry)
            return entry

        def progress(stage, detail, natural_title=None, natural_msg=None, status='INFO'):
            entry = log_entry(stage, natural_title or stage, natural_msg or detail, status)
            result.update(stage=stage, stage_detail=detail, updated_at=entry['at'])
            atomic(self.work(cid) / 'pipeline-latest.json', result)
            lock_path = self.work(cid) / 'pipeline.lock'
            if lock_path.is_file():
                try:
                    cur_lock = json.loads(lock_path.read_text(encoding='utf-8'))
                    if isinstance(cur_lock, dict):
                        cur_lock['stage'] = stage
                        cur_lock['updated_at'] = entry['at']
                        lock_path.write_text(json.dumps(cur_lock, ensure_ascii=False), encoding='utf-8')
                except Exception:
                    pass
            if self.progress:
                try:
                    self.progress(cid, stage, detail, entry)
                except TypeError:
                    self.progress(cid, stage, detail)

        def finish(outcome):
            # Post-processing runs on the final available revision, never on an older run's draft.
            revisions = sorted((run_dir / 'revisions').glob('r*.draft.md'),
                               key=lambda p: int(re.search(r'r(\d+)', p.name).group(1)))
            if revisions and not prepare_only:
                from services.article_publish_checks import inspect_article
                final_text = revisions[-1].read_text(encoding='utf-8')
                settings_path = self.root / 'config/pipeline-postprocess.json'
                settings = json.loads(settings_path.read_text(encoding='utf-8')) if settings_path.exists() else {}
                binding_path = run_dir / 'asset-bindings.json'
                final_bindings = json.loads(binding_path.read_text(encoding='utf-8')).get('bindings', []) if binding_path.exists() else []
                brief_path = run_dir / 'brief.json'
                final_brief = json.loads(brief_path.read_text(encoding='utf-8')).get('brief', {}) if brief_path.exists() else {}
                if outcome == 'COMPLETED_REVIEW_PENDING' and settings.get('image_generation_enabled', False):
                    try:
                        from services.article_assets import acquire_assets
                        progress('image_generation', '이미지 제작·후보 자산 등록', '이미지 제작', '기술 검토를 통과한 원고를 기준으로 생성하며 승인 대기 후보로 등록합니다.')
                        need_path = run_dir / 'asset-plan.json'
                        needs = json.loads(need_path.read_text(encoding='utf-8')).get('needs', []) if need_path.exists() else []
                        image_report = acquire_assets(self.root, cid, run_id, final_text, needs, final_bindings)
                        save('image-production.json', image_report)
                        save('asset-bindings.json', {'bindings': final_bindings})
                        result['image_production'] = {'status': image_report['status'], 'generated_count': image_report['generated_count']}
                        log_entry('image_generation', '이미지 제작 결과', f"생성 {image_report['generated_count']}건 / {image_report['status']}. 승인·공개 URL 확인은 별도입니다.")
                    except Exception as error:
                        save('image-production.json', {'status': 'failed', 'error_type': type(error).__name__})
                        result['image_production'] = {'status': 'failed'}
                        result['admin_checks'].append({'kind': 'image_generation', 'detail': '이미지 제작·등록 실패. 자산을 확보하고 검토해야 합니다.'})
                if settings.get('publish_checks_enabled', True):
                    progress('publish_checks', '발행 전 콘텐츠 점검', '발행 전 검사', '제목·검색어·반복·가독성·미승인 자산을 점검합니다. 노출 순위나 블로그 지수 점수는 생성하지 않습니다.')
                    publish_report = inspect_article(final_text, final_brief, final_bindings)
                    save('publish-checks.json', publish_report)
                    result['publish_checks'] = {'status': publish_report['status'], 'issues_count': len(publish_report['issues'])}
                    log_entry('publish_checks', '발행 전 검사 결과', f"확인 항목 {len(publish_report['issues'])}건. 자동 재작성 없이 관리자에게 전달합니다.")
            outcome_korean_map = {
                'COMPLETED_REVIEW_PENDING': '원고 검증 통과 · 관리자 승인 대기',
                'COMPLETED_READY': '발행 준비 완료 (최종 승인)',
                'REVISION_REQUIRED': '수정 필요 (검토 이슈 발생)',
                'NEEDS_EVIDENCE': '근거 보완 필요 (팩트/출처 확인)',
                'FAILED': '실행 중단 / 오류 발생',
                'PREPARED': '사전 점검 완료'
            }
            korean_status = outcome_korean_map.get(outcome, outcome)
            result['outcome'] = outcome
            progress('finished', outcome, '파이프라인 실행 종료', f'최종 상태: {korean_status}',
                     'SUCCESS' if 'COMPLETED' in outcome else 'WARN')
            save('knowledge-update-queue.json', {'items': result['knowledge_queue']})
            save('admin-review-queue.json', {'items': result['admin_checks']})
            save('run-result.json', result)
            from services.pipeline_token_audit import audit_saved_run
            save('token-audit.json', audit_saved_run(run_dir))
            execution_contract['outcome'] = outcome
            execution_contract['artifacts'] = {str(p.relative_to(run_dir)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in run_dir.rglob('*') if p.is_file() and p.name != 'execution-contract.json'}
            save('execution-contract.json', execution_contract)
            # Offline verification never calls an AI or changes the editorial outcome.
            try:
                from services.pipeline_verifier import verify_pipeline
                verification = verify_pipeline(run_dir)
            except Exception as error:
                verification = {'valid': False, 'status': 'FAIL', 'pipeline_complete': False,
                                'findings': [{'check': 'verifier', 'detail': type(error).__name__}]}
            save('pipeline-verification.json', verification)
            atomic(self.work(cid) / 'pipeline-latest.json', result)
            print(json.dumps({k: result.get(k) for k in ['content_id', 'run_id', 'outcome', 'publish_ready',
                'draft_file', 'error', 'admin_checks', 'knowledge_queue']}, ensure_ascii=False, default=str), flush=True)
            return result

        # Locate previous run artifacts BEFORE updating pipeline-latest.json
        prior = self.latest(cid)
        prev_dir = None
        if resume_run_id:
            p = self.work(cid) / 'runs' / resume_run_id
            if p.is_dir():
                prev_dir = p
        if not prev_dir and prior and prior.get('run_directory'):
            p = Path(prior['run_directory'])
            if p.is_dir():
                prev_dir = p
        if not prev_dir:
            runs_dir = self.work(cid) / 'runs'
            if runs_dir.is_dir():
                subdirs = sorted([d for d in runs_dir.iterdir() if d.is_dir() and d.name != run_id],
                                 key=lambda d: d.name, reverse=True)
                if subdirs:
                    prev_dir = subdirs[0]

        atomic(self.work(cid) / 'pipeline-latest.json', result)

        try:
            execution_contract['resume_source_run_id'] = prev_dir.name if prev_dir and start_stage in ('assets', 'write', 'feedback', 'official') else None
            execution_contract['web_research_enabled'] = configuration(self.root).get('pipeline_web_research_enabled', False)
            from services.web_research import INSTRUCTION as SEARCH_INSTRUCTION
            execution_contract['web_search_instruction_sha256'] = digest(SEARCH_INSTRUCTION)
            # ── Stage 0: Inputs & Facts Verification ──
            stage_start_label = f" ({start_stage} 단계부터 시작)" if start_stage and start_stage != 'inputs' else ""
            progress('inputs', '기존 기획·팩트·출처·규칙 확인', '자료 및 기획 점검',
                     f'기획서, 제품 팩트, 공식 출처 및 안전 작성 규칙을 점검합니다.{stage_start_label}')
            context = load_context(self.root, cid)
            meta['input_refs'] = context['input_refs']
            result['input_refs'] = context['input_refs']

            # Guide Release & Requirements Integration
            guide_repo = GuideRepository(self.root)
            guide_manifest, release_dir = guide_repo.load_bundle_for_run()
            assembler = ContextAssembler(guide_manifest, release_dir=release_dir)
            save('guide-manifest.json', guide_manifest.model_dump())
            result['guide_release_id'] = guide_manifest.release_id

            requirements = {}
            for rid, rdata in guide_manifest.rules.items():
                if rdata.get('status') == 'active':
                    requirements[rid] = {
                        'id': rid,
                        'kind': 'rule',
                        'required': rdata.get('required', False),
                        'severity': rdata.get('severity', 'blocking'),
                        'description': rdata.get('description'),
                        'stages': rdata.get('stages', []),
                        'path': rdata.get('path')
                    }
            for f in context.get('facts', []):
                fid = f.get('id')
                if fid:
                    requirements[fid] = {
                        'id': fid,
                        'kind': 'fact',
                        'property': f.get('canonical_property') or f.get('property'),
                        'source_id': (f.get('source', {}) or {}).get('id') if isinstance(f.get('source'), dict) else f.get('source')
                    }
            save('requirements.json', {'requirements': requirements})

            gap = gap_snapshot(self.root, cid)
            save('gap-snapshot.json', gap)
            save('brief.json', {'brief': context['brief']})
            save('keyword-entity-map.json', {'keywords': context['brief']['search'], 'entities': context['entities'],
                 'mapping_basis': 'brief.knowledge_packs', 'legacy_claim_metadata': context['legacy_claim_metadata']})
            save('fact-bundle.json', {'facts': context['facts'], 'sources': context['sources'], 'missing': context['missing']})
            save('matched-cautions.json', {'rules': context['cautions']})
            save('input-snapshot.json', context)

            fact_count = len(context.get('facts', []))
            source_count = len(context.get('sources', {}))
            caution_count = len(context.get('cautions', []))
            log_entry('inputs', '자료 점검 완료',
                      f'총 {fact_count}건의 팩트, {source_count}건의 공식 출처, {caution_count}건의 준수 규칙을 확인했습니다. (정책 릴리스: {guide_manifest.release_id})')

            if gap['collection_status'] == 'NOT_COLLECTED':
                result['admin_checks'].append({'kind': 'keyword_diagnosis', 'detail': '저장된 키워드 관측값 없음. 기존 brief를 사용함.'})
            research = None
            # Discovery runs once before strategy, never during QA/rewrite or prepare-only.
            if not prepare_only and start_stage in (None, 'inputs', 'strategy') and configuration(self.root).get('pipeline_web_research_enabled', False):
                from services.web_research import research_for_brief
                try:
                    research = research_for_brief(self.root, context['brief'], self.work(cid) / 'web-research-cache.json')
                    save('web-research.json', research)
                    result['web_research_status'] = research['status']
                    if research['status'] == 'needs_review':
                        result['admin_checks'].append({'kind': 'web_planning_unusable', 'detail': '신뢰 출처·인용 연결이 확인되지 않아 기획 참고자료에서 제외. 기존 제품 Fact로 진행.', 'artifact': 'web-research.json'})
                    if research['status'] != 'disabled':
                        web_status_label = 'AVIXA/PSNI 자동 신뢰 채택' if research['status'] == 'trusted' else '검토 가능한 근거 없음' if research['status'] == 'ungrounded' else '원문 검토 대기'
                        log_entry('inputs', '웹 자료 수집', f'출처 {len(research["results"])}건 / 검색어 {research["observed_query_count"]}개 / 캐시 {research["cache_hit"]}. {web_status_label}.')
                except Exception as error:
                    # Existing approved evidence remains usable; no invented replacement.
                    save('web-research.json', {'status': 'failed', 'error_type': type(error).__name__, 'approved_for_writing': False})
                    result['web_research_status'] = 'failed'
                    result['admin_checks'].append({'kind': 'web_research_failed', 'detail': '웹 검색 실패. 기존 승인 근거만 사용하며 재확인이 필요함.'})
                    log_entry('inputs', '웹 자료 수집 실패', '기존 승인 근거를 유지합니다.', status='WARN')
            if (context['missing'] or not context['facts']) and start_stage not in ['feedback', 'official']:
                result['admin_checks'].extend(context['missing'])
                log_entry('inputs', '근거 보완 필요', f'누락된 팩트/출처 {len(context["missing"])}건이 감지되었습니다.', status='WARN')
                return finish('NEEDS_EVIDENCE')
            if prepare_only:
                return finish('PREPARED')

            # Use immutable release prompts repository
            prompt_repo = LocalPromptRepository(release_dir / 'prompts', release_manifest=guide_manifest)
            context.pop('prompts', None)
            selected_rules_in_run = set()

            def audited_call(stage, instruction, model_payload, suffix, prompt_sha, prompt_src, official=False, before=0, optimization=None):
                block_plan = None
                targets = []
                runtime_rule_ids = []
                previous = model_payload.get('previous_draft') or {}
                if model_payload.get('fact_policy'):
                    instruction += '\n구조화된 fact_policy는 이번 글의 근거 변경 지시이다. excluded_fact_ids는 기존 전략·이미지 요청에 있어도 근거로 쓰지 않는다. block_fact_ids로 갱신된 블록 근거를 따른다. 원고의 모든 기술 Claim은 이번 입력 facts와 해당 블록 허용 목록 안에서 작성한다.'
                # Remove the legacy duplicate before adding runtime-only rules.
                if model_payload.get('cautions') == model_payload.get('rules') and 'cautions' in model_payload:
                    model_payload = {k: v for k, v in model_payload.items() if k != 'cautions'}
                if model_payload.get('planning_references') and stage in ('strategy', 'write', 'feedback'):
                    from services.web_planning import CONTEXT_INSTRUCTION as PLANNING_CONTEXT, RULE_ID as PLANNING_RULE_ID
                    instruction += '\n\n' + PLANNING_CONTEXT
                    model_payload = {**model_payload, 'rules': list(model_payload.get('rules', [])) + [{'id': PLANNING_RULE_ID, 'body': PLANNING_CONTEXT}]}
                    runtime_rule_ids.append(PLANNING_RULE_ID)
                if model_payload.get('web_evidence') and stage in ('strategy', 'write', 'feedback'):
                    from services.web_evidence import CONTEXT_INSTRUCTION, RULE_ID
                    instruction += '\n\n' + CONTEXT_INSTRUCTION
                    model_payload = {**model_payload, 'rules': list(model_payload.get('rules', [])) + [{'id': RULE_ID, 'body': CONTEXT_INSTRUCTION}]}
                    runtime_rule_ids.append(RULE_ID)
                if stage == 'strategy':
                    instruction += '\n\n' + planner_instruction(self.root)
                if stage == 'feedback' and (model_payload.get('draft') or {}).get('blocks'):
                    instruction += '\n검토 issues에 block_id를 추가해 해당 블록을 특정한다. 글 전체 문제는 null이다. Claim 및 블록 계약 오류도 검토한다.'
                if stage == 'feedback':
                    instruction += '\n초안의 승인 대기 AssetNeed 자리표시자와 kind=asset인 확보·생성·검토 대기만으로 집필 실패 이슈를 만들지 않는다. 이는 관리자 자산 확인 항목이다. 본문·이미지 계획의 내용 불일치, 잘못된 Need ID, 허위 생성 완료 주장은 오류로 검토한다.'
                if stage == 'write':
                    block_plan, block_meta = build_block_plan(self.root, model_payload)
                    model_payload = {**model_payload, 'block_plan': block_plan, 'block_plan_metadata': block_meta}
                    instruction += '\n\n' + BLOCK_INSTRUCTION
                    targets = repair_targets(previous, model_payload.get('feedback') or {})
                    if targets:
                        model_payload['repair_block_ids'] = targets
                        instruction += '\nrepair_block_ids에 지정한 블록만 수정한다. 그 외 blocks 항목은 previous_draft와 완전히 동일하게 반환한다. 전체 조립 markdown과 Claim/자산 메타데이터도 일치시킨다.'
                    save(f'block-plan/{suffix}.json', {'blocks': block_plan, **block_meta})
                instruction, model_payload, ledger = prepare_call(
                    stage, instruction, model_payload, f'{run_id}-{suffix}',
                    guide_manifest.release_id, prompt_src, prompt_sha,
                    {'rules': guide_manifest.rules, 'guides': guide_manifest.guides})
                if official:
                    from services.official_feedback import MANUFACTURER_INSTRUCTION
                    instruction = MANUFACTURER_INSTRUCTION
                    ledger['instruction_sha256'] = digest(instruction)
                    ledger['external_receipt_expected'] = False
                ledger_path = f'rule-audit/{suffix}.json'
                ledger['runtime_rule_ids'] = runtime_rule_ids
                if optimization is not None:
                    ledger['context_optimization'] = optimization
                ledger['sequence'] = len(execution_contract['calls']) + 1
                execution_contract['calls'].append({'sequence': ledger['sequence'], 'stage': stage, 'label': suffix})
                save(ledger_path, ledger)
                exact = {'instruction': instruction, 'context': model_payload,
                         'prompt_version': prompt_src, 'prompt_sha256': prompt_sha,
                         'release_id': guide_manifest.release_id}
                save(f'prompts/{suffix}.json', {'prompt': exact, 'sha256': digest(json.dumps(exact, ensure_ascii=False, default=str))})
                metrics = {'stage': stage, 'before_chars': before,
                           'sent_chars': payload_size(model_payload), 'input_tokens': None,
                           'token_count_status': 'unavailable', 'timestamp': datetime.now(timezone.utc).isoformat()}
                from services.context_optimization import field_sizes
                metrics['input_fields_chars'] = field_sizes(model_payload)
                metrics['instruction_chars'] = len(instruction)
                from services.pipeline_token_audit import estimate_input
                metrics['token_accounting'] = estimate_input(stage, instruction, model_payload)
                budget = configuration(self.root).get('pipeline_input_token_budget', 50000)
                if type(budget) is not int or budget <= 0:
                    raise ValueError('pipeline_input_token_budget must be a positive integer')
                metrics['input_token_budget'] = budget
                metrics['token_accounting'] = estimate_input(stage, instruction, model_payload, budget=budget)
                try:
                    if not official:
                        counter = getattr(self.provider, 'count_tokens', None)
                        if not callable(counter):
                            raise ValueError('Provider must implement count_tokens before generation')
                        count = counter(stage, instruction, model_payload)
                        if type(count) is not int or count < 0:
                            raise ValueError('Provider returned invalid token count')
                        metrics.update(input_tokens=count, token_count_status='measured', within_token_budget=count <= budget)
                        metrics['token_accounting'] = estimate_input(stage, instruction, model_payload, budget=budget, measured=count)
                        save(f'context-metrics/{suffix}.json', metrics)
                        if count > budget:
                            ledger['dispatch_status'] = 'blocked_token_budget'
                            raise ValueError(f'Input token budget exceeded at {stage}: {count} > {budget}')
                    ledger['dispatch_status'] = 'started'
                    save(ledger_path, ledger)
                    raw = (self.provider.official(instruction, model_payload) if official else
                           self.provider.complete(stage, instruction, model_payload))
                    ledger['dispatch_status'] = 'responded'
                    save(f'responses/{suffix}.json', {'raw': raw})
                    last_meta = getattr(self.provider, 'last_metadata', {})
                    metrics.update(usage_metadata=last_meta.get('usage_metadata', 'unavailable'),
                                   finish_reason=last_meta.get('finish_reason', 'STOP'),
                                   model_version=last_meta.get('model_version', 'default'))
                    parsed = parse_object(raw)
                    ledger.update(verify_receipt(parsed, ledger))
                    if ledger['receipt_status'] != 'verified':
                        raise ValueError(f'Rule receipt failed at {stage}: {ledger["errors"]}')
                    if block_plan is not None:
                        errors = validate_blocks(parsed['result'], block_plan)
                        errors.extend(validate_preserved_blocks(parsed['result'], previous, targets))
                        from services.web_evidence import validate_usage
                        errors.extend(validate_usage(parsed['result'], model_payload.get('web_evidence', []), block_plan))
                        parsed['result']['_block_errors'] = errors
                        save(f'block-review/{suffix}.json', {'errors': errors, 'passed': not errors,
                             'blocks': parsed['result'].get('blocks'), 'contract': block_plan, 'repair_block_ids': targets})
                    return parsed['result']
                except Exception as error:
                    if official and ledger.get('dispatch_status') == 'responded' and isinstance(locals().get('raw'), str) and raw.strip():
                        ledger['receipt_status'] = 'external_response_preserved'
                        return {'_natural_review': raw}
                    if ledger['receipt_status'] == 'pending':
                        ledger['receipt_status'] = 'not_verified'
                    ledger['failure_type'] = type(error).__name__
                    if metrics['token_count_status'] != 'measured' and not official:
                        metrics['token_count_status'] = 'failed'
                    raise
                finally:
                    last_meta = getattr(self.provider, 'last_metadata', {})
                    if ledger.get('dispatch_status') in {'started', 'responded'} and last_meta:
                        metrics['provider_routing'] = {k: last_meta[k] for k in ('key_slot', 'key_tier', 'routing_attempts') if k in last_meta}
                        alternate_count = last_meta.get('actual_input_tokens')
                        if type(alternate_count) is int and not official:
                            metrics.update(input_tokens=alternate_count, within_token_budget=alternate_count <= metrics.get('input_token_budget', 50000))
                            metrics['token_accounting'] = estimate_input(stage, instruction, model_payload,
                                budget=metrics.get('input_token_budget', 50000), measured=alternate_count)
                        if last_meta.get('http_status'):
                            metrics['http_status'] = last_meta['http_status']
                            ledger['http_status'] = last_meta['http_status']
                        metrics.update(usage_metadata=last_meta.get('usage_metadata', 'unavailable'),
                                       finish_reason=last_meta.get('finish_reason', 'UNKNOWN'),
                                       model_version=last_meta.get('model_version', 'default'))
                    save(ledger_path, ledger)
                    save(f'context-metrics/{suffix}.json', metrics)

            def edit_for_naver(response, suffix, assembled_input=None):
                assembled_input=assembled_input or {}
                settings_path=self.root/'config/pipeline-postprocess.json'
                settings=json.loads(settings_path.read_text(encoding='utf-8')) if settings_path.exists() else {}
                if settings.get('naver_edit_enabled',True) and not response.get('_block_errors'):
                    from services.naver_editor import INSTRUCTION, RULE_ID, apply_edit
                    progress('naver_edit','네이버 문단·어투 다듬기','네이버 편집','짧은 문단과 의미별 줄바꿈을 편집한 뒤 자체·공식 검토로 전달합니다.')
                    payload={'draft':{k:response[k] for k in ('markdown','claims','blocks') if k in response},
                             'rules':[{'id':RULE_ID,'body':INSTRUCTION}],
                             'topic':context['brief'].get('topic')}
                    editing_targets=repair_targets(assembled_input.get('previous_draft') or {},assembled_input.get('feedback') or {})
                    if editing_targets:payload['editable_block_ids']=editing_targets
                    edit_label=suffix.replace('.write','.naver-edit')
                    edited=audited_call('naver_edit',INSTRUCTION,payload,edit_label,digest(INSTRUCTION),
                                        'services/naver_editor.py#'+RULE_ID,before=payload_size(payload))
                    polished=apply_edit(response,edited,editing_targets)
                    save('naver-edit/'+edit_label+'.json',{'rule_id':RULE_ID,'before_sha256':digest(response['markdown']),
                         'after_sha256':digest(polished['markdown']),'changes':edited.get('changes',[]),
                         'source_call':suffix,'edited_draft':polished,'preservation_passed':True})
                    log_entry('naver_edit','네이버 편집 완료','Claim·Fact 연결, 수치·링크·이미지 자리 보존 확인. 편집본을 다음 검토로 전달합니다.')
                    return polished
                return response

            def call(stage, payload, suffix):
                progress(stage, suffix, f'{stage} AI 모델 생성', f'{stage} 단계의 AI 지시 및 컨텍스트를 모델로 전달합니다.')
                instruction, prompt_sha, prompt_src = prompt_repo.get_prompt(stage)
                before = payload_size(payload)
                call_id = f"{run_id}-{suffix}"

                # Assemble modular context & track selection
                assembled_input, sel_report = assembler.assemble_context(stage, None, payload, call_id=call_id)
                save(f'context-selection/{suffix}.json', sel_report.model_dump())
                if sel_report.missing_required:
                    result['admin_checks'].extend(sel_report.missing_required)

                for r in sel_report.selected_rules:
                    selected_rules_in_run.add(r['id'])

                # Character estimates remain diagnostic; actual complete input tokens govern dispatch.
                response = audited_call(stage, instruction, assembled_input, suffix, prompt_sha, prompt_src, before=before, optimization=sel_report.optimization)
                return edit_for_naver(response,suffix,assembled_input) if stage=='write' else response

            # Institutional discovery supports planning, not product Fact approval.
            from services.web_planning import planning_input, finalize as finalize_planning, product_only, INSTRUCTION as PLANNING_INSTRUCTION
            if research is None and start_stage in ('assets', 'write', 'feedback', 'official') and configuration(self.root).get('pipeline_web_research_enabled', False) and context['brief'].get('web_research') is not False and prev_dir and (prev_dir / 'web-research.json').exists():
                research = json.loads((prev_dir / 'web-research.json').read_text(encoding='utf-8'))
                from services.web_source_policy import apply_policy, POLICY_ID
                if research.get('source_policy', {}).get('id') != POLICY_ID:
                    import requests
                    research = apply_policy(research, requests)
                save('web-research.json', research)
            planning = product_only('관련 글·개별 설계 근거 없음. 기존 제품 Fact로 진행')
            if start_stage in ('assets', 'write', 'feedback', 'official') and prev_dir and (prev_dir / 'web-planning-discovery.json').exists():
                planning = json.loads((prev_dir / 'web-planning-discovery.json').read_text(encoding='utf-8'))
                planning = {k: v for k, v in planning.items() if k not in meta}
            elif research:
                web_payload = planning_input(context['brief'], research)
                if web_payload['segments']:
                    try:
                        selection = audited_call('planning_research', PLANNING_INSTRUCTION, web_payload,
                            'planning-research', digest(PLANNING_INSTRUCTION), 'SYS-WEB-PLANNING-004')
                        planning = finalize_planning(selection, web_payload)
                    except Exception as exc:
                        planning = product_only('기획 참고자료 선별 실패. 기존 제품 Fact로 진행')
                        planning['status'] = 'failed'
                        result['admin_checks'].append({'kind': 'web_planning_failed', 'detail': str(exc)})
            save('web-planning-discovery.json', planning)
            context['planning_references'] = planning
            log_entry('inputs', '기획 참고자료 선별', f'{planning["mode"]}: 참고 항목 {len(planning["points"])}건. 제품 Fact 승인과 구분합니다.')

            # ── Stage 1: Strategy Formulation ──
            strategy = None
            if start_stage in ['assets', 'write', 'feedback', 'official'] and prev_dir and (prev_dir / 'strategy.json').exists():
                try:
                    strategy = json.loads((prev_dir / 'strategy.json').read_text(encoding='utf-8'))
                    strategy = {k: v for k, v in strategy.items() if k not in meta}
                    save('strategy.json', strategy)
                    progress('strategy', '기존 수립 전략 승계', '작성 전략 승계',
                             f'이전 실행의 전략(플레이북: {strategy.get("primary_playbook")})을 그대로 승계하여 다음 단계를 진행합니다.')
                except Exception:
                    strategy = None

            if not strategy:
                strategy = call('strategy', {**context, 'gap': gap, 'user_feedback': user_feedback}, 'strategy')
                required = ['article_goal', 'reader', 'primary_playbook', 'must_cover', 'can_omit', 'avoid',
                            'technical_depth', 'opening', 'body', 'closing', 'asset_needs']
                if any(k not in strategy for k in required) or not isinstance(strategy['asset_needs'], list):
                    raise ValueError('Incomplete strategy response')
                save('strategy.json', strategy)
                log_desc = f'플레이북 \'{strategy.get("primary_playbook")}\' 채택. 이미지 {len(strategy.get("asset_needs", []))}장 계획 수립.'
                if user_feedback:
                    log_desc += f' (추가 지시사항 반영: "{user_feedback}")'
                log_entry('strategy', '작성 전략 수립 완료', log_desc)

            selected = [strategy['primary_playbook']] + strategy.get('secondary_playbooks', [])
            if context.get('playbooks'):
                if any(book not in context['playbooks'] for book in selected):
                    raise ValueError('Unknown playbook ID in strategy')
                context['playbooks'] = {book: context['playbooks'][book] for book in selected}

            plan = strategy['asset_needs']
            if any(not isinstance(n, dict) or not re.fullmatch(r'[A-Za-z0-9_-]+', n.get('id', '')) for n in plan):
                raise ValueError('Invalid asset need IDs')
            if len({n['id'] for n in plan}) != len(plan):
                raise ValueError('Duplicate asset need IDs')
            save('asset-plan.json', {'needs': plan})

            # ── Stage 2: Asset Plan & Bindings ──
            BANNER_NEED_IDS = {'oceantech-inquiry-opening', 'oceantech-inquiry-closing',
                               'AST-OCEANTECH-INQUIRY-BANNER', 'oceantech-inquiry-banner'}
            COMPANY_BANNER_ID = 'AST-COMPANY-OCEAN-001'
            assets_by_id = {a['asset_id']: a for a in context['assets']}
            assets_by_need = {a.get('need_id'): a for a in context['assets']
                              if a.get('need_id') and a.get('review_status') != 'rejected'}
            company_banner_asset = assets_by_id.get(COMPANY_BANNER_ID)

            bindings = None
            if start_stage in ['write', 'feedback', 'official'] and prev_dir and (prev_dir / 'asset-bindings.json').exists():
                try:
                    bindings_data = json.loads((prev_dir / 'asset-bindings.json').read_text(encoding='utf-8'))
                    raw_bindings = bindings_data.get('bindings', [])
                    rechecked_bindings = []
                    for b in raw_bindings:
                        need = b.get('need', {})
                        cand = b.get('candidate')
                        need_id = need.get('id', '')
                        if need_id in BANNER_NEED_IDS:
                            if not cand or cand.get('asset_id') != COMPANY_BANNER_ID:
                                b['candidate'] = company_banner_asset
                                b['need']['asset_id'] = COMPANY_BANNER_ID
                                b['status'] = 'pending_review'
                                b['reconciliation_note'] = f"Inquiry banner candidate reconciled to {COMPANY_BANNER_ID}"
                        else:
                            fresh_candidate = assets_by_need.get(need_id) or assets_by_id.get(need.get('asset_id'))
                            if fresh_candidate and fresh_candidate != cand:
                                b['candidate'] = fresh_candidate
                                b['status'] = 'pending_review'
                                b['reconciliation_note'] = 'Refreshed from current asset registry; approval still required'
                        rechecked_bindings.append(b)
                    bindings = rechecked_bindings
                    save('asset-bindings.json', {'bindings': bindings})
                    progress('assets', '기존 에셋 바인딩 승계 및 검증', '에셋 계획 승계',
                             f'이전 실행의 에셋 바인딩({len(bindings)}건)을 승계하고 배너 후보를 정합성 검증했습니다.')
                except Exception:
                    bindings = None

            if bindings is None:
                progress('assets', '이미지 계획과 승인 대기 항목 구성', '이미지 에셋 계획',
                         f'원고 본문에 삽입할 {len(plan)}장의 이미지 위치 및 승인 대기 항목을 구성합니다.')
                bindings = []
                for need in plan:
                    need_id = need.get('id', '')
                    if need_id in BANNER_NEED_IDS:
                        need['asset_id'] = COMPANY_BANNER_ID
                        candidate = company_banner_asset
                    else:
                        candidate = assets_by_id.get(need.get('asset_id')) or assets_by_need.get(need.get('id'))
                    bindings.append({'need': need, 'candidate': candidate, 'status': 'pending_review'})
                    result['admin_checks'].append({'kind': 'asset', 'need_id': need['id'],
                        'detail': '생성 또는 업로드 후 출처·내용·배치 검토 필요', 'request': need})
                save('asset-bindings.json', {'bindings': bindings})

            save('writer-context.json', {'context': context, 'strategy': strategy, 'asset_plan': plan})

            # ── Stage 3: Draft Writing & Feedback QA Loop ──
            feedback = {'user_feedback': user_feedback} if user_feedback else None
            previous_path = self.draft_path(cid)
            final = {'markdown': previous_path.read_text(encoding='utf-8')} if previous_path.exists() else None
            save('revision-input.json', {'previous_draft': final, 'user_feedback': user_feedback})
            qa = None
            revision = 1
            markdown = None
            claims = None
            errors = []
            writer_metadata = {}

            # Helper to find latest revision number in a run directory
            def find_latest_rev_in_run(r_dir):
                if not r_dir or not Path(r_dir).is_dir():
                    return None
                rev_dir = Path(r_dir) / 'revisions'
                if not rev_dir.is_dir():
                    return None
                nums = []
                for p in rev_dir.glob('r*.claim-map.json'):
                    m = re.match(r'r(\d+)\.claim-map\.json', p.name)
                    if m:
                        nums.append(int(m.group(1)))
                return max(nums) if nums else None

            # Check if we can inherit existing draft & claims when start_stage is feedback or official
            if start_stage in ['feedback', 'official']:
                current_draft_text = None
                if previous_path.exists():
                    current_draft_text = previous_path.read_text(encoding='utf-8')
                latest_rev = find_latest_rev_in_run(prev_dir)
                if not current_draft_text and prev_dir and latest_rev:
                    p_prev_draft = prev_dir / f'revisions/r{latest_rev}.draft.md'
                    if p_prev_draft.exists():
                        current_draft_text = p_prev_draft.read_text(encoding='utf-8')

                if not current_draft_text:
                    raise ValueError(f"No existing draft found for {cid}. Start from 'write' stage.")

                current_draft_sha = digest(current_draft_text)

                if not prev_dir or not latest_rev:
                    raise ValueError(f"No previous revision data found for {cid}. Start from 'write' stage.")

                cm_path = prev_dir / f'revisions/r{latest_rev}.claim-map.json'
                if not cm_path.exists():
                    raise ValueError(f"Claim map r{latest_rev} missing in previous run. Start from 'write' stage.")

                try:
                    cm_data = json.loads(cm_path.read_text(encoding='utf-8'))
                except Exception as err:
                    raise ValueError(f"Failed to read claim map: {err}. Start from 'write' stage.")

                if cm_data.get('draft_sha256') != current_draft_sha:
                    raise ValueError(f"Draft changed (sha256: {current_draft_sha[:12]}) vs claim-map r{latest_rev} ({str(cm_data.get('draft_sha256'))[:12]}). Run from 'write' stage to regenerate claim map.")

                existing_claims = cm_data.get('claims', [])
                if not existing_claims:
                    raise ValueError(f"No claims found in claim map r{latest_rev}. Start from 'write' stage.")

                markdown = current_draft_text
                claims = existing_claims
                metadata_path = prev_dir / f'revisions/r{latest_rev}.writer-metadata.json'
                if metadata_path.exists():
                    writer_metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
                    if writer_metadata.get('draft_sha256') != current_draft_sha:
                        raise ValueError('Writer metadata does not match current draft')
                else:
                    writer_metadata = {'changes': [], 'used_asset_need_ids': sorted(set(re.findall(r'\{\{asset:([^}]+)\}\}', markdown))), 'unresolved_items': [], 'legacy_inferred': True}
                final = {'markdown': markdown, 'claims': claims, **writer_metadata}
                previous_block_review = prev_dir / f'block-review/r{latest_rev}.write.json'
                if previous_block_review.exists():
                    block_review = json.loads(previous_block_review.read_text(encoding='utf-8'))
                    final['blocks'] = block_review.get('blocks')
                    writer_metadata['blocks'] = final['blocks']
                    writer_metadata['_block_errors'] = validate_blocks(final, block_review['contract'])
                    from services.web_evidence import validate_usage
                    writer_metadata['_block_errors'].extend(validate_usage(final, context.get('web_evidence', []), block_review['contract']))
                    final['_block_errors'] = writer_metadata['_block_errors']
                    save('block-review/r1.write.json', {**block_review, 'errors': writer_metadata['_block_errors'],
                         'passed': not writer_metadata['_block_errors'], 'inherited_from': str(previous_block_review)})
                save('revisions/r1.writer-metadata.json', {**writer_metadata, 'draft_sha256': current_draft_sha})

                # Save inherited as r1 in current run
                atomic(run_dir / 'revisions/r1.draft.md', markdown)
                save('revisions/r1.claim-map.json', {'claims': claims, 'draft_sha256': current_draft_sha})
                progress('write', '기존 원고 승계', '원고 초안 승계',
                         f'기존 원고({len(markdown):,}자, 주장 {len(claims)}개, r{latest_rev} 승계)를 그대로 승계하여 검토를 진행합니다.')

                if start_stage == 'official':
                    metadata_errors = self.validate_writer_metadata({'markdown': markdown, **writer_metadata}, plan)
                    if metadata_errors:
                        raise ValueError('Writer metadata requires feedback review: ' + '; '.join(metadata_errors))
                    fb_path = prev_dir / f'revisions/r{latest_rev}.feedback.json'
                    if not fb_path.exists():
                        raise ValueError(f"Passed feedback QA report r{latest_rev} missing for {cid}. Run 'feedback' stage first.")
                    try:
                        qa_data = json.loads(fb_path.read_text(encoding='utf-8'))
                    except Exception as err:
                        raise ValueError(f"Failed to read feedback QA: {err}. Run 'feedback' stage first.")
                    if qa_data.get('draft_sha256') != current_draft_sha or not qa_data.get('passed'):
                        raise ValueError(f"Official review requires a passed QA report matching current draft (sha256: {current_draft_sha[:12]}). Run 'feedback' stage first.")
                    qa = qa_data
                    feedback = qa.get('feedback', {})
                    save('revisions/r1.feedback.json', qa)
                    progress('feedback', '기존 품질 검토 승계', '품질 검토 승계',
                             '이전 품질 검토 합격 결과를 승계하여 로지텍 공식 검증으로 이동합니다.')

                elif start_stage == 'feedback':
                    if naver_edit_existing:
                        final=edit_for_naver(final,'r1.write')
                        markdown,claims=final['markdown'],final['claims']
                        current_draft_sha=digest(markdown)
                        writer_metadata={k:final.get(k) for k in ('changes','used_asset_need_ids','unresolved_items','blocks','_block_errors','evidence_usage')}
                        atomic(run_dir/'revisions/r1.draft.md',markdown)
                        save('revisions/r1.claim-map.json',{'claims':claims,'draft_sha256':current_draft_sha})
                        save('revisions/r1.writer-metadata.json',{**writer_metadata,'draft_sha256':current_draft_sha})
                        if previous_block_review.exists():
                            save('block-review/r1.write.json',{**block_review,'blocks':final.get('blocks'),
                                 'edited_by':'naver_edit','inherited_from':str(previous_block_review)})
                    # Run 1st feedback QA on existing draft (r1)
                    errors = self.validate_draft(markdown, claims, context['facts'], plan)
                    errors.extend(self.validate_writer_metadata({'markdown': markdown, **writer_metadata}, plan))
                    feedback = call('feedback', {**context, 'strategy': strategy, 'draft': {'markdown': markdown, 'claims': claims, **writer_metadata}, 'user_feedback': user_feedback}, 'r1.feedback')
                    if not isinstance(feedback.get('passed'), bool) or not isinstance(feedback.get('issues'), list) or not isinstance(feedback.get('missing_claims'), list):
                        raise ValueError('Invalid feedback response')
                    qa = {'passed': feedback['passed'] and not feedback['issues'] and not feedback['missing_claims'] and not errors,
                          'feedback': feedback, 'contract_errors': errors, 'draft_sha256': current_draft_sha}
                    feedback['contract_errors'] = errors
                    save('revisions/r1.feedback.json', qa)
                    issues_cnt = len(feedback.get('issues', []))
                    status_text = '합격(통과)' if qa['passed'] else f'수정 필요 (이슈 {issues_cnt}건)'
                    log_entry('feedback', '품질 검토 (r1)', f'정합성 검토: {status_text}',
                              'SUCCESS' if qa['passed'] else 'WARN')
                    revision = 1

                    # If not passed, run revision loop up to max_revisions
                    if not qa['passed']:
                        final = {'markdown': markdown, 'claims': claims}
                        for revision in range(2, max_revisions + 1):
                            draft = call('write', {**context, 'strategy': strategy, 'asset_plan': plan,
                                'previous_draft': final, 'feedback': feedback, 'user_feedback': user_feedback}, f'r{revision}.write')
                            markdown, claims = draft.get('markdown'), draft.get('claims')
                            if not isinstance(markdown, str) or not markdown.strip() or not isinstance(claims, list):
                                raise ValueError('Writer must return markdown and claims')
                            atomic(run_dir / f'revisions/r{revision}.draft.md', markdown)
                            save(f'revisions/r{revision}.claim-map.json', {'claims': claims, 'draft_sha256': digest(markdown)})
                            final = draft
                            write_log = f'본문 {len(markdown):,}자 및 주장 {len(claims)}개 작성 완료.'
                            if user_feedback:
                                write_log += f' (추가 지시사항 반영: "{user_feedback}")'
                            log_entry('write', f'원고 작성 (r{revision})', write_log)
                            errors = self.validate_draft(markdown, claims, context['facts'], plan)
                            writer_metadata = {k: draft.get(k) for k in ('changes', 'used_asset_need_ids', 'unresolved_items', 'blocks', '_block_errors', 'evidence_usage')}
                            errors.extend(self.validate_writer_metadata(draft, plan))
                            save(f'revisions/r{revision}.writer-metadata.json', {**writer_metadata, 'draft_sha256': digest(markdown)})
                            feedback = call('feedback', {**context, 'strategy': strategy, 'draft': draft, 'user_feedback': user_feedback}, f'r{revision}.feedback')
                            if not isinstance(feedback.get('passed'), bool) or not isinstance(feedback.get('issues'), list) or not isinstance(feedback.get('missing_claims'), list):
                                raise ValueError('Invalid feedback response')
                            qa = {'passed': feedback['passed'] and not feedback['issues'] and not feedback['missing_claims'] and not errors,
                                  'feedback': feedback, 'contract_errors': errors, 'draft_sha256': digest(markdown)}
                            feedback['contract_errors'] = errors
                            save(f'revisions/r{revision}.feedback.json', qa)
                            issues_cnt = len(feedback.get('issues', []))
                            status_text = '합격(통과)' if qa['passed'] else f'수정 필요 (이슈 {issues_cnt}건)'
                            log_entry('feedback', f'품질 검토 (r{revision})', f'검토 결과: {status_text}',
                                      'SUCCESS' if qa['passed'] else 'WARN')
                            if qa['passed']:
                                break
            else:
                for revision in range(1, max_revisions + 1):
                    draft = call('write', {**context, 'strategy': strategy, 'asset_plan': plan,
                        'previous_draft': final, 'feedback': feedback, 'user_feedback': user_feedback}, f'r{revision}.write')
                    markdown, claims = draft.get('markdown'), draft.get('claims')
                    if not isinstance(markdown, str) or not markdown.strip() or not isinstance(claims, list):
                        raise ValueError('Writer must return markdown and claims')
                    atomic(run_dir / f'revisions/r{revision}.draft.md', markdown)
                    save(f'revisions/r{revision}.claim-map.json', {'claims': claims, 'draft_sha256': digest(markdown)})
                    final = draft
                    write_log = f'본문 {len(markdown):,}자 및 주장 {len(claims)}개 작성 완료.'
                    if user_feedback:
                        write_log += f' (추가 지시사항 반영: "{user_feedback}")'
                    log_entry('write', f'원고 작성 (r{revision})', write_log)
                    errors = self.validate_draft(markdown, claims, context['facts'], plan)
                    writer_metadata = {k: draft.get(k) for k in ('changes', 'used_asset_need_ids', 'unresolved_items', 'blocks', '_block_errors', 'evidence_usage')}
                    errors.extend(self.validate_writer_metadata(draft, plan))
                    save(f'revisions/r{revision}.writer-metadata.json', {**writer_metadata, 'draft_sha256': digest(markdown)})
                    feedback = call('feedback', {**context, 'strategy': strategy, 'draft': draft, 'user_feedback': user_feedback}, f'r{revision}.feedback')
                    if not isinstance(feedback.get('passed'), bool) or not isinstance(feedback.get('issues'), list) or not isinstance(feedback.get('missing_claims'), list):
                        raise ValueError('Invalid feedback response')
                    qa = {'passed': feedback['passed'] and not feedback['issues'] and not feedback['missing_claims'] and not errors,
                          'feedback': feedback, 'contract_errors': errors, 'draft_sha256': digest(markdown)}
                    feedback['contract_errors'] = errors
                    save(f'revisions/r{revision}.feedback.json', qa)
                    issues_cnt = len(feedback.get('issues', []))
                    status_text = '합격(통과)' if qa['passed'] else f'수정 필요 (이슈 {issues_cnt}건)'
                    log_entry('feedback', f'품질 검토 (r{revision})', f'검토 결과: {status_text}',
                              'SUCCESS' if qa['passed'] else 'WARN')
                    if qa['passed']:
                        break

            # Generate coverage & review reports for latest revision (pre-official)
            cov, rep, rep_md = self._generate_coverage_and_review_report(
                cid=cid,
                run_id=run_id,
                revision=revision,
                markdown=markdown,
                claims=claims,
                feedback=feedback or {},
                errors=errors or [],
                official=None,
                admin_checks=result['admin_checks'],
                guide_manifest=guide_manifest,
                requirements=requirements,
                selected_rule_ids=selected_rules_in_run,
            )
            save(f'coverage/r{revision}.json', cov.model_dump())
            save('review-report.json', rep.model_dump())
            atomic(run_dir / 'review-report.md', rep_md)

            result.update({'draft_revision': revision, 'draft_sha256': digest(markdown), 'draft_file': str(self.draft_path(cid)), 'qa': qa, 'review_report': rep.model_dump()})
            result['writer_metadata'] = writer_metadata
            for item in writer_metadata.get('unresolved_items') or []:
                if isinstance(item, dict) and item.get('kind') != 'asset':
                    result['admin_checks'].append({'kind': 'writer_unresolved', **item})
            save('writer-metadata.json', {**writer_metadata, 'draft_sha256': digest(markdown)})
            atomic(self.draft_path(cid), markdown)
            for item in (feedback.get('issues') or []):
                if item.get('category') in ['KNOWLEDGE_CHANGE_CANDIDATE', 'SOURCE_CONFLICT']:
                    result['knowledge_queue'].append(item)
            if not qa or not qa['passed']:
                return finish('REVISION_REQUIRED')

            # Manufacturer feedback -> internal interpretation -> bounded writer repair.
            from services.official_feedback import INSTRUCTION as INTERPRET_INSTRUCTION, RULE_ID as INTERPRET_RULE, validate_interpretation, writer_feedback
            repair_limit = configuration(self.root).get('pipeline_official_repair_limit', 1)
            if type(repair_limit) is not int or not 0 <= repair_limit <= 3:
                raise ValueError('Official repair limit must be between 0 and 3')
            for repair_round in range(repair_limit + 1):
                official = {'status': 'ERROR', 'claims': []}
                try:
                    progress('official', '로지텍 AI 응답 대기', '로지텍 공식 검증',
                             f'{len(claims)}개 주장 검토 / 수정 회차 {repair_round}')
                    official_instruction, off_sha, off_src = prompt_repo.get_prompt('official')
                    official_payload = compact_payload('official', {'claims': claims, 'facts': context['facts'],
                        'draft': {'markdown': markdown}, 'sources': context['sources']})
                    suffix = f'r{revision}.official'
                    parsed = audited_call('official', official_instruction, official_payload, suffix, off_sha, off_src, official=True)
                    raw = json.loads((run_dir / f'responses/{suffix}.json').read_text(encoding='utf-8'))['raw']
                    official['raw'] = raw
                    interpretation = None
                    progress('official_interpret', '공식 답변 해석', '공식 피드백 판정', '형식 면책과 실제 수정 요청을 구분합니다.')
                    payload = {**official_payload, 'official_raw': raw,
                               'rules': [{'id': INTERPRET_RULE, 'body': INTERPRET_INSTRUCTION}]}
                    interpreted = audited_call('official_interpret', INTERPRET_INSTRUCTION, payload,
                        f'r{revision}.official-interpret', digest(INTERPRET_INSTRUCTION), INTERPRET_RULE)
                    interpretation = validate_interpretation(interpreted, claims, raw)
                    interpretation['draft_sha256'] = digest(markdown)
                    save(f'reviews/r{revision}.official-interpret.json', interpretation)
                    parsed = interpretation
                    reviewed = parsed.get('claims')
                    if not isinstance(reviewed, list) or len(reviewed) != len(claims) or {c['id'] for c in reviewed} != {c['id'] for c in claims}:
                        raise ValueError('Official review must cover each claim exactly once')
                    allowed = {'confirmed', 'contradicted', 'insufficient_evidence', 'out_of_scope'}
                    if any(c.get('verdict') not in allowed or (c['verdict'] == 'confirmed' and not c.get('evidence')) for c in reviewed):
                        raise ValueError('Invalid official verdict/evidence')
                    official.update(status='REVIEWED', claims=reviewed, interpretation=interpretation, draft_sha256=digest(markdown))
                    save(f'reviews/r{revision}.official.json', official)
                    decision = interpretation['decision'] if interpretation else ('continue' if all(c['verdict'] == 'confirmed' for c in reviewed) else 'hold')
                    log_entry('official', '공식 피드백 판정', decision)
                    if decision != 'rewrite' or repair_round == repair_limit:
                        if decision == 'rewrite':
                            official['repair_limit_exhausted'] = True
                        break
                    repair_feedback = writer_feedback(interpretation)
                    save(f'reviews/r{revision}.writer-handoff.json', {
                        'draft_sha256': digest(markdown), 'official_raw': raw, 'feedback': repair_feedback,
                        'preserve_fact_ids': [f['id'] for f in context['facts']], 'decision': 'rewrite'})
                    previous = final
                    revision += 1
                    draft = call('write', {**context, 'strategy': strategy, 'asset_plan': plan,
                        'previous_draft': previous, 'feedback': repair_feedback,
                        'official_feedback': interpretation, 'official_raw': raw,
                        'user_feedback': user_feedback + '\n공식 피드백의 필요한 부분만 수정한다. 영향 없는 문단·근거·이미지 자리는 보존한다. 피드백이 사실과 맞지 않으면 changes에 이유를 남기고 유지한다. 새 사실을 만들지 않는다.'}, f'r{revision}.write')
                    markdown, claims = draft.get('markdown'), draft.get('claims')
                    if not isinstance(markdown, str) or not markdown.strip() or not isinstance(claims, list):
                        raise ValueError('Invalid official repair draft')
                    final = draft
                    atomic(run_dir / f'revisions/r{revision}.draft.md', markdown)
                    save(f'revisions/r{revision}.claim-map.json', {'claims': claims, 'draft_sha256': digest(markdown)})
                    errors = self.validate_draft(markdown, claims, context['facts'], plan) + self.validate_writer_metadata(draft, plan)
                    writer_metadata = {k: draft.get(k) for k in ('changes', 'used_asset_need_ids', 'unresolved_items', 'blocks', '_block_errors', 'evidence_usage')}
                    save(f'revisions/r{revision}.writer-metadata.json', {**writer_metadata, 'draft_sha256': digest(markdown)})
                    feedback = call('feedback', {**context, 'strategy': strategy, 'asset_plan': plan, 'draft': draft,
                        'official_feedback': interpretation, 'user_feedback': user_feedback}, f'r{revision}.feedback')
                    qa = {'passed': feedback.get('passed') is True and feedback.get('issues') == [] and feedback.get('missing_claims') == [] and not errors,
                          'feedback': feedback, 'contract_errors': errors, 'draft_sha256': digest(markdown)}
                    save(f'revisions/r{revision}.feedback.json', qa)
                    result['qa'] = qa
                    if not qa['passed']:
                        official = {'status': 'ERROR', 'claims': [], 'error': 'Official repair failed QA; requires revision'}
                        break
                except Exception as error:
                    response_path = run_dir / f'responses/r{revision}.official.json'
                    if response_path.exists():
                        official['raw'] = json.loads(response_path.read_text(encoding='utf-8'))['raw']
                    official.update(status='ERROR', error=type(error).__name__ + ': official review unavailable or invalid')
                    log_entry('official', '공식 검증 실패', official['error'], status='ERROR')
                    break
            official['draft_sha256'] = digest(markdown)
            save(f'reviews/r{revision}.official.json', official)
            result.update(draft_revision=revision, draft_sha256=digest(markdown), qa=qa)
            result['writer_metadata'] = writer_metadata
            save('writer-metadata.json', {**writer_metadata, 'draft_sha256': digest(markdown)})
            atomic(self.draft_path(cid), markdown)
            result['official_review'] = official
            for item in official.get('claims', []):
                if item['verdict'] == 'contradicted':
                    result['knowledge_queue'].append({'category': 'SOURCE_CONFLICT', 'claim': item})
                if item['verdict'] != 'confirmed':
                    result['admin_checks'].append({'kind': 'claim', 'claim': item})

            # Update coverage & review report with official findings
            cov_final, rep_final, rep_md_final = self._generate_coverage_and_review_report(
                cid=cid,
                run_id=run_id,
                revision=revision,
                markdown=markdown,
                claims=claims,
                feedback=feedback or {},
                errors=errors or [],
                official=official,
                admin_checks=result['admin_checks'],
                guide_manifest=guide_manifest,
                requirements=requirements,
                selected_rule_ids=selected_rules_in_run,
            )
            save(f'coverage/r{revision}.json', cov_final.model_dump())
            save('review-report.json', rep_final.model_dump())
            atomic(run_dir / 'review-report.md', rep_md_final)
            result['review_report'] = rep_final.model_dump()

            if official['status'] == 'ERROR':
                result['admin_checks'].append({'kind': 'official_review', 'detail': official['error']})
                final_outcome = 'REVISION_REQUIRED'
            elif official.get('repair_limit_exhausted') or (official.get('interpretation') or {}).get('decision') == 'hold' or any(c.get('verdict') != 'confirmed' for c in official.get('claims', [])):
                final_outcome = 'REVISION_REQUIRED'
            else:
                final_outcome = 'COMPLETED_REVIEW_PENDING'
            result['admin_checks'].append({'kind': 'human_review', 'detail': '현재 원고와 근거의 관리자 최종 확인 필요'})
            save('knowledge-update-queue.json', {'items': result['knowledge_queue']})
            save('admin-review-queue.json', {'items': result['admin_checks']})
            return finish(final_outcome)
        except Exception as error:
            result['error'] = str(error) if isinstance(error, (ValueError, FileNotFoundError)) else type(error).__name__ + ': pipeline stage failed'
            failure = getattr(self.provider, 'last_metadata', {})
            if failure.get('http_status'):
                result['error'] = f'Gemini HTTP {failure["http_status"]} at {failure.get("error_stage", "unknown")}'
            return finish('FAILED')

    @staticmethod
    def validate_writer_metadata(draft, plan):
        """Validate writer-reported needs; asset approval remains pipeline-owned."""
        errors = list(draft.get('_block_errors') or [])
        ids = draft.get('used_asset_need_ids')
        used = set(re.findall(r'\{\{asset:([^}]+)\}\}', draft['markdown']))
        if not isinstance(ids, list) or any(not isinstance(x, str) or not x for x in ids):
            errors.append('used_asset_need_ids must be a string array')
        elif len(ids) != len(set(ids)) or set(ids) != used:
            errors.append('used_asset_need_ids must exactly match draft placeholders without duplicates')
        items = draft.get('unresolved_items')
        if not isinstance(items, list):
            errors.append('unresolved_items must be an array')
            return errors
        known = {n['id'] for n in plan}
        for item in items:
            if not isinstance(item, dict) or item.get('kind') not in {'asset', 'link', 'evidence', 'other'} or not isinstance(item.get('detail'), str) or not item['detail'].strip():
                errors.append('Invalid unresolved item: kind and detail required')
                continue
            if item['kind'] == 'asset':
                if item.get('need_id') not in known:
                    errors.append('Unresolved asset must reference a planned need_id')
            else:
                errors.append('Unresolved writing issue: ' + item['detail'])
        return errors

    @staticmethod
    def validate_draft(markdown, claims, facts, plan):
        errors = []
        fact_ids = {f['id'] for f in facts}
        if not claims or len({c.get('id') for c in claims}) != len(claims):
            errors.append('Missing/duplicate claims')
        for claim in claims:
            if not claim.get('text') or claim['text'] not in markdown or not claim.get('fact_ids') or set(claim['fact_ids']) - fact_ids:
                errors.append('Unmapped claim: ' + str(claim.get('id')))
        if re.search(r'!\[|<\s*(img|script|iframe)\b', markdown, re.I):
            errors.append('Unbound image or executable HTML')
        used = set(re.findall(r'\{\{asset:([^}]+)\}\}', markdown))
        if used - {n['id'] for n in plan}:
            errors.append('Unknown asset placeholders')
        if {n['id'] for n in plan if n.get('required')} - used:
            errors.append('Required image placement missing')
        return errors

    def save_edit(self, cid, markdown, expected_sha256=None, source='console'):
        with self.lock(cid):
            before = self.draft_path(cid).read_text(encoding='utf-8') if self.draft_path(cid).exists() else ''
            if expected_sha256 is not None and digest(before) != expected_sha256:
                raise ValueError('원고가 다른 작업에서 변경되었습니다. 최신 원고를 확인하세요.')
            if not isinstance(markdown, str) or not markdown.strip():
                raise ValueError('원고를 비워 저장할 수 없습니다.')
            edit_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]
            edit = {'edit_id': edit_id, 'source': source, 'base_sha256': digest(before),
                    'draft_sha256': digest(markdown), 'at': datetime.now(timezone.utc).isoformat(),
                    'requires_review': True}
            atomic(self.work(cid) / 'edits' / (edit_id + '.before.md'), before)
            atomic(self.work(cid) / 'edits' / (edit_id + '.draft.md'), markdown)
            atomic(self.work(cid) / 'edits' / (edit_id + '.json'), edit)
            atomic(self.draft_path(cid), markdown)
            result = self.latest(cid)
            if result:
                result.update(outcome='REVISION_REQUIRED', publish_ready=False, approval=None,
                              draft_sha256=digest(markdown), manual_edit=edit,
                              qa={'passed': False, 'feedback': {'issues': [], 'contract_errors': ['수정 원고 재검토 대기']}},
                              official_review={'status': 'STALE', 'claims': []}, approved_assets={},
                              error='Draft changed; rerun pipeline before approval')
                atomic(self.work(cid) / 'pipeline-latest.json', result)
            return result

    def assert_publishable(self, cid):
        result = self.latest(cid)
        reason = None
        if not isinstance(result, dict) or result.get('outcome') != 'COMPLETED_READY' or result.get('publish_ready') is not True:
            reason = 'Current pipeline revision is not approved for publishing'
        elif not isinstance(result.get('qa'), dict) or result.get('error') or result['qa'].get('passed') is not True:
            reason = 'Writing QA failed or did not return a valid pass'
        else:
            official = result.get('official_review')
            claims = official.get('claims') if isinstance(official, dict) else None
            if (not isinstance(claims, list) or not claims or official.get('status') != 'REVIEWED'
                    or official.get('draft_sha256') != result.get('draft_sha256')
                    or any(not isinstance(claim, dict) or claim.get('verdict') != 'confirmed' for claim in claims)):
                reason = 'Official review failed, malformed, unresolved, or does not match the draft'
            elif result.get('admin_checks') and (not isinstance(result.get('approval'), dict)
                    or not isinstance(result['approval'].get('resolutions'), list)
                    or len(result['approval']['resolutions']) != len(result['admin_checks'])
                    or any(not isinstance(x, str) or not x.strip() for x in result['approval']['resolutions'])):
                reason = 'Admin review items remain unresolved'
            elif (not isinstance(result.get('approval'), dict)
                    or result['approval'].get('draft_sha256') != result.get('draft_sha256')
                    or not result['approval'].get('reviewer')):
                reason = 'Final approval is missing or belongs to another draft'
            else:
                try:
                    current_hash = digest(self.draft_path(cid).read_text(encoding='utf-8'))
                except (OSError, ValueError):
                    current_hash = None
                if not current_hash or current_hash != result.get('draft_sha256'):
                    reason = 'Draft changed after review; rerun review and approval'
                else:
                    from services.pipeline_status import calculate_effective_status
                    st_info = calculate_effective_status(self.root, cid, latest_run=result)
                    if not st_info.get('publish_ready') or st_info.get('effective_status') != 'READY_TO_PUBLISH':
                        reason = st_info.get('reason') or 'Effective status is not ready to publish'
        event = {'time': datetime.now(timezone.utc).isoformat(), 'content_id': cid,
                 'run_id': result.get('run_id') if isinstance(result, dict) else None,
                 'action': 'PUBLISH_PREPARE', 'allowed': reason is None,
                 'reason': reason or 'Review and approval verified'}
        log_path = self.work(cid) / 'publish-gate.jsonl'
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + '\n')
        if reason:
            raise ValueError('Publishing blocked: ' + reason)
        return result
    def approve(self, cid, run_id, draft_sha256, reviewer, bindings, resolutions):
        """Explicit console sign-off on a precise revision; never a force bypass."""
        with self.lock(cid):
            result = self.latest(cid)
            if not result or result['run_id'] != run_id or result.get('draft_sha256') != draft_sha256:
                raise ValueError('Stale approval: reload the current run')
            official = result.get('official_review', {})
            ide_rechecked = (result.get('execution_type') == 'ide' and result['outcome'] == 'REVISION_REQUIRED'
                            and official.get('status') == 'REVIEWED' and official.get('draft_sha256') == draft_sha256
                            and official.get('decision', {}).get('passed') is True and bool(official.get('claims'))
                            and all(c.get('verdict') == 'confirmed' for c in official['claims']))
            if (result['outcome'] != 'COMPLETED_REVIEW_PENDING' and not ide_rechecked) or not result.get('qa', {}).get('passed'):
                raise ValueError('Writing QA must pass before approval')
            markdown = self.draft_path(cid).read_text(encoding='utf-8')
            if digest(markdown) != draft_sha256 or not reviewer.strip():
                raise ValueError('Draft changed or reviewer missing')
            official = result.get('official_review', {})
            if (official.get('status') != 'REVIEWED' or official.get('draft_sha256') != draft_sha256
                    or not isinstance(official.get('claims'), list) or not official['claims']
                    or any(not isinstance(c, dict) or c.get('verdict') != 'confirmed' for c in official['claims'])):
                raise ValueError('Official claim review is incomplete; resolve evidence and rerun')
            if not isinstance(resolutions, list) or any(not isinstance(x, str) or not x.strip() for x in resolutions) or len(resolutions) != len(result['admin_checks']):
                raise ValueError('Provide one written resolution for each admin checkpoint')
            used = set(re.findall(r'\{\{asset:([^}]+)\}\}', markdown))
            if not isinstance(bindings, dict) or set(bindings) != used:
                raise ValueError('Approve exactly the images used in this revision')
            for asset in bindings.values():
                if not isinstance(asset, dict) or not all(asset.get(k) for k in ['url', 'origin', 'evidence', 'caption', 'asset_id']):
                    raise ValueError('Asset URL, ID, origin, evidence and caption required')
                if not re.fullmatch(r'https://[^\s<>"\']+', asset['url']):
                    raise ValueError('Approved image requires an HTTPS URL')
            result.update(outcome='COMPLETED_READY', publish_ready=True,
                approval={'reviewer': reviewer, 'draft_sha256': draft_sha256,
                          'at': datetime.now(timezone.utc).isoformat(), 'resolutions': resolutions},
                approved_assets=bindings)
            atomic(self.work(cid) / 'pipeline-latest.json', result)
            atomic(Path(result['run_directory']) / 'approval.json', result)
            return result

    def export(self, cid, expected_run_id=None, expected_sha256=None):
        with self.lock(cid):
            result = self.assert_publishable(cid)
            if (expected_run_id is not None and result.get('run_id') != expected_run_id) or (expected_sha256 is not None and result.get('draft_sha256') != expected_sha256):
                raise ValueError('선택한 원고 버전이 현재 승인본과 다릅니다. 최신 실행을 확인하세요.')
            from services.naver_blog_compiler import compile_markdown_to_naver_html
            markdown = self.draft_path(cid).read_text(encoding='utf-8')
            rendered = compile_markdown_to_naver_html(markdown, content_id=cid, assets_map=result['approved_assets'])
            atomic(self.system / f'05_publish/ready/{cid}.final.md', markdown)
            atomic(self.system / f'05_publish/ready/{cid}.naver.html', rendered['html'])
            return {**rendered, 'run_id': result['run_id'], 'draft_sha256': result['draft_sha256']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('content_id')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--max-revisions', type=int, default=3)
    parser.add_argument('--start-stage', choices=['inputs', 'strategy', 'assets', 'write', 'feedback', 'official'], default=None)
    parser.add_argument('--resume-run-id', default=None)
    parser.add_argument('--naver-edit-existing',action='store_true')
    parser.add_argument('--user-feedback', default='')
    args = parser.parse_args()
    result = ContentPipeline().run(args.content_id, args.max_revisions, args.prepare_only,
                                   user_feedback=args.user_feedback, start_stage=args.start_stage,
                                   resume_run_id=args.resume_run_id,naver_edit_existing=args.naver_edit_existing)
    return 1 if result['outcome'] in ['FAILED', 'NEEDS_EVIDENCE', 'REVISION_REQUIRED'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
