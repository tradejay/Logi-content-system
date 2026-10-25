"""Inspect existing work, dispatch eligible items once, expose durable progress."""
import csv
from datetime import datetime, timezone, date
import json
import os
from pathlib import Path
import threading
import uuid

from services.content_pipeline import ContentPipeline, ROOT, atomic
from services.pipeline_context import digest, read_yaml, contained


def now():
    return datetime.now(timezone.utc).isoformat()


class PipelineDispatcher:
    def __init__(self, root=ROOT, factory=ContentPipeline):
        self.root = Path(root)
        self.factory = factory
        self.directory = self.root / 'content-system/operations'
        self.gate = threading.Lock()

    def read_job(self):
        path = self.directory / 'latest-job.json'
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None

    def inspect(self, content_id=None):
        pipeline = self.factory(root=self.root)
        registry = self.root / 'content-system/registry/CONTENT_REGISTRY.csv'
        rows = []
        if registry.exists():
            with registry.open(encoding='utf-8-sig', newline='') as stream:
                rows = list(csv.DictReader(stream))
        if content_id:
            pipeline.work(content_id)
            rows = [r for r in rows if r['content_id'] == content_id]
            if not rows:
                raise ValueError('등록된 글을 찾을 수 없습니다')
        items = []
        for row in rows:
            cid = row['content_id']
            item = {'content_id': cid, 'title': row.get('title') or row.get('canonical_topic') or cid,
                    'registry_status': row.get('status'), 'checked_at': now(), 'action': 'WAIT', 'stage': 'planning'}
            try:
                latest = pipeline.latest(cid)
                item['run_id'] = (latest or {}).get('run_id')
                item['outcome'] = (latest or {}).get('outcome')
                item['updated_at'] = (latest or {}).get('updated_at') or (latest or {}).get('created_at')
                item['admin_count'] = len((latest or {}).get('admin_checks', []))

                from services.pipeline_status import calculate_effective_status
                st_info = calculate_effective_status(self.root, cid, registry_row=row, latest_run=latest)
                item['effective_status'] = st_info['effective_status']
                item['publish_ready'] = st_info['publish_ready']
                item['qa_passed'] = st_info['qa_passed']
                item['is_interrupted'] = st_info['is_interrupted']

                if row.get('status') in ['PUBLISHED', 'ARCHIVED', 'CANCELLED', 'DUPLICATE']:
                    item.update(stage='published', reason='발행 또는 종료된 글은 자동 재작성하지 않음')
                elif st_info['effective_status'] == 'RUNNING':
                    item.update(stage=(latest or {}).get('stage', 'running'), reason=st_info['reason'])
                elif st_info['effective_status'] in ['INTERRUPTED', 'RUNNING_UNKNOWN']:
                    item.update(stage='blocked', reason=st_info['reason'])
                else:
                    self._decide(pipeline, row, latest, item)
            except Exception as error:
                item.update(action='WAIT', stage='blocked', reason='현황 확인 실패: ' + type(error).__name__)
            items.append(item)
        return {'checked_at': now(), 'items': items}

    def _decide(self, pipeline, row, latest, item):
        cid = row['content_id']
        brief_path = self.root / f'content-system/01_keyword_ai/briefs/{cid}.brief.yaml'
        if not brief_path.exists():
            item.update(reason='기획서 작성 필요', stage='planning')
            return
        brief = read_yaml(brief_path)
        if not brief.get('topic') or not brief.get('search', {}).get('primary_keyword'):
            item.update(reason='주제·검색어 보완 필요', stage='planning')
            return
        requests = []
        for path in (self.root / 'content-system/03_sources/inbox').glob('*.y*ml'):
            entry = read_yaml(path)
            if entry.get('status') == 'OPEN' and entry.get('content_id') == cid:
                requests.append(entry.get('evidence_request_id', path.stem))
        if requests:
            item.update(reason=f'열린 근거 요청 {len(requests)}건 보완 필요', stage='evidence', blockers=requests)
            return
        # Date-sensitive source freshness is evaluated at the time of each click.
        from services.pipeline_context import load_context
        context = load_context(self.root, cid)
        missing = list(context['missing'])
        for source in context['sources'].values():
            try:
                verified = date.fromisoformat(str(source['last_verified'])[:10])
                if (datetime.now(timezone.utc).date() - verified).days > int(source['freshness_limit_days']):
                    missing.append({'kind': 'expired_source', 'id': source['id']})
            except (KeyError, ValueError, TypeError):
                missing.append({'kind': 'source_freshness_unknown', 'id': source.get('id')})
        if missing:
            item.update(stage='evidence', reason=f'근거 보완 또는 최신성 확인 {len(missing)}건 필요', blockers=missing)
            return
        changed = []
        for ref in (latest or {}).get('input_refs', []):
            ref_path_str = ref.get('path', '')
            if ref.get('virtual') or ref_path_str.startswith('virtual:'):
                if ref_path_str.startswith('virtual:product_links:'):
                    try:
                        cur_digest = digest(json.dumps(context.get('product_links', {}), sort_keys=True, ensure_ascii=False))
                        if cur_digest != ref.get('sha256'):
                            changed.append(ref_path_str)
                    except Exception:
                        pass
                continue
            path = contained(self.root, ref_path_str)
            if not path.exists() or digest(path.read_text(encoding='utf-8-sig')) != ref['sha256']:
                changed.append(ref_path_str)
        draft_path = pipeline.draft_path(cid)
        draft_changed = bool(latest and latest.get('draft_sha256') and
            (not draft_path.exists() or digest(draft_path.read_text(encoding='utf-8')) != latest['draft_sha256']))
        outcome = (latest or {}).get('outcome')
        if outcome == 'RUNNING':
            item.update(stage='blocked', reason='이전 실행이 중단됨 · 결과와 잠금 확인 필요')
        elif draft_changed or changed:
            item.update(action='RUN', stage='queued', reason='원고 또는 입력 변경 → 재검토 실행', changed_inputs=changed)
        elif outcome == 'COMPLETED_READY':
            pipeline.assert_publishable(cid)
            item.update(stage='ready', reason='승인 완료 · 변경 없음')
        elif outcome == 'COMPLETED_REVIEW_PENDING':
            item.update(stage='human', reason='관리자 확인 대기 · 동일 원고 재작성 생략')
        elif outcome in ['FAILED', 'REVISION_REQUIRED', 'NEEDS_EVIDENCE']:
            item.update(stage='blocked', reason='이전 실패·수정 요청 확인 필요 · 입력 변경 없이 자동 반복하지 않음')
        else:
            item.update(action='RUN', stage='queued', reason='공통 파이프라인의 완료된 검토 기록 없음')

    def start(self, content_id=None, start_stage=None, user_feedback="", force=False):
        if content_id:
            self.factory(root=self.root).work(content_id)
        with self.gate:
            self.directory.mkdir(parents=True, exist_ok=True)
            lock = self.directory / 'dispatch.lock'
            if lock.exists():
                try:
                    from services.pipeline_status import check_process_liveness
                    raw_data = lock.read_text(encoding='utf-8').strip()
                    try:
                        lock_obj = json.loads(raw_data)
                    except Exception:
                        lock_obj = {'pid': int(raw_data)} if raw_data.isdigit() else None
                    if check_process_liveness(lock_obj) == 'DEAD':
                        lock.unlink(missing_ok=True)
                except Exception:
                    pass
            try:
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                job = self.read_job()
                if job and job.get('status') in ['CHECKING', 'RUNNING']:
                    return job, False
                raise ValueError('이전 실행 잠금이 남아 있습니다. 프로세스와 실행 기록 확인이 필요합니다.')
            import psutil
            lock_payload = {
                'pid': os.getpid(),
                'process_create_time': psutil.Process().create_time(),
                'started_at': now()
            }
            os.write(fd, json.dumps(lock_payload).encode('utf-8'))
            os.close(fd)
            job = {'job_id': uuid.uuid4().hex, 'status': 'CHECKING', 'started_at': now(),
                   'checked_at': None, 'scope': content_id or 'ALL', 'items': [], 'events': [],
                   'current_content_id': None, 'start_stage': start_stage, 'user_feedback': user_feedback, 'force': force}
            self._save(job)
            threading.Thread(target=self._execute, args=(job, content_id, lock), daemon=True).start()
            return dict(job), True

    def _save(self, job):
        job['updated_at'] = now()
        atomic(self.directory / 'jobs' / (job['job_id'] + '.json'), job)
        atomic(self.directory / 'latest-job.json', job)

    def _execute(self, job, content_id, lock):
        def event(cid, stage, detail, entry=None):
            evt = {'at': now(), 'content_id': cid, 'stage': stage, 'detail': detail}
            if isinstance(entry, dict):
                evt['title'] = entry.get('title')
                evt['message'] = entry.get('message')
                evt['status'] = entry.get('status', 'INFO')
            job['events'].append(evt)
            job['events'] = job['events'][-200:]
            for item in job['items']:
                if item['content_id'] == cid:
                    item.update(stage=stage, progress=detail, updated_at=now())
            self._save(job)
        try:
            event(None, 'checking', '현재 시각 기준으로 전체 기획·근거·수정·승인 상태 확인')
            snapshot = self.inspect(content_id)
            job.update(items=snapshot['items'], checked_at=snapshot['checked_at'], status='RUNNING')
            self._save(job)
            start_stage = job.get('start_stage')
            user_feedback = job.get('user_feedback', '')
            is_targeted = (content_id is not None)
            force_run = job.get('force') or (start_stage is not None)

            for item in job['items']:
                cid = item['content_id']
                should_run = (item['action'] == 'RUN') or (is_targeted and cid == content_id and force_run)
                if not should_run:
                    event(cid, item['stage'], item['reason'])
                    continue

                if not (is_targeted and cid == content_id and force_run):
                    fresh = self.inspect(cid)['items'][0]
                    if fresh['action'] != 'RUN':
                        item.update(fresh)
                        event(cid, item['stage'], item['reason'])
                        continue

                job['current_content_id'] = cid
                stage_label = f" ({start_stage} 단계부터 시작)" if start_stage else ""
                event(cid, start_stage or 'inputs', f'작업 실행 시작{stage_label}')
                try:
                    pipeline = self.factory(root=self.root, progress=event)
                    result = pipeline.run(cid, start_stage=start_stage, user_feedback=user_feedback)
                    item.update(outcome=result['outcome'], run_id=result['run_id'],
                                admin_count=len(result.get('admin_checks', [])))
                    stage = 'human' if result['outcome'] == 'COMPLETED_REVIEW_PENDING' else 'blocked'
                    event(cid, stage, result['outcome'])
                except Exception as error:
                    item.update(outcome='FAILED')
                    event(cid, 'blocked', type(error).__name__ + ': 실행 실패 - ' + str(error))
            job.update(status='FINISHED', current_content_id=None, finished_at=now())
        except Exception as error:
            job.update(status='FAILED', error=type(error).__name__ + ': 현황 점검 실패', finished_at=now())
        finally:
            self._save(job)
            lock.unlink(missing_ok=True)


dispatcher = PipelineDispatcher()
