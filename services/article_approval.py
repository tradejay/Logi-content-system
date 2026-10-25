"""Human approval controls reusing the existing image and publication gates."""
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import uuid

from services.content_pipeline import ContentPipeline, atomic
from services.pipeline_context import digest
from services.taiga_tracking import article_details, yaml_file
from services.taiga_workflow import apply_asset_review
from services.article_stage import current_stage


def run_asset(cid, nid, candidate):
    asset = dict(candidate)
    if not asset.get('asset_id'):
        url = asset.get('public_url') or asset.get('url') or ''
        asset.update(asset_id='AST-LINK-' + hashlib.sha256((cid + nid + url).encode()).hexdigest()[:20],
                     need_id=nid, content_id=cid, origin_type='linked',
                     source_ref={'url': url, 'kind': 'existing_run_binding'}, review_status='candidate')
    return asset


class ArticleApproval:
    def __init__(self, root, pipeline=None, uploader=None):
        self.root = Path(root).resolve()
        self.pipeline = pipeline or ContentPipeline(root=self.root)
        self.uploader = uploader

    def snapshot(self, cid):
        self.pipeline.work(cid)
        result = self.pipeline.latest(cid) or {}
        draft = self.pipeline.draft_path(cid)
        markdown = draft.read_text(encoding='utf-8') if draft.is_file() else ''
        assets = yaml_file(self.root/'content-system/assets'/cid/'assets.yaml').get('assets', [])
        queue = yaml_file(self.root/'content-system/queue/asset.queue.yaml')
        used = set(re.findall(r'\{\{asset:([^}]+)\}\}', markdown))
        details = article_details(self.root, cid, result)
        images = []
        for binding in details.get('asset_bindings') or []:
            need = binding.get('need') or {}; candidate = binding.get('candidate') or {}
            nid = need.get('id')
            if not (nid in used or need.get('asset_id') in used or candidate.get('asset_id') in used or need.get('anchor') in {'{{asset:'+s+'}}' for s in used}):
                continue
            jobs = [(jid,j) for jid,j in queue.get('jobs',{}).items() if j.get('content_id')==cid and j.get('need_id')==nid]
            job_id,job = jobs[-1] if jobs else (None,{})
            normalized = run_asset(cid, nid, candidate) if candidate else {}
            asset = next((a for a in assets if a.get('need_id')==nid and a.get('asset_id')==normalized.get('asset_id')), normalized)
            if result.get('execution_type') == 'ide' and candidate and job.get('draft_sha256') != result.get('draft_sha256'):
                job_id = 'RUNIMG-' + hashlib.sha256((cid + result['run_id'] + result['draft_sha256'] + nid).encode()).hexdigest()[:24]
                job = {'draft_sha256': result['draft_sha256']}
            images.append({'need_id':nid,'asset_id':asset.get('asset_id'),'asset_sha256':asset.get('sha256'),
                'job_id':job_id,'job_draft_sha256':job.get('draft_sha256'), 'purpose':need.get('purpose'),
                'caption':asset.get('caption') or asset.get('alt') or need.get('purpose'),
                'preview_url':asset.get('public_url') or asset.get('url'),
                'public_url':asset.get('public_url') or (asset.get('url') if str(asset.get('url','')).startswith('https://') else ''),
                'review_status':asset.get('review_status') or 'candidate'})
        registry = self.root/'content-system/registry/CONTENT_REGISTRY.csv'
        record = {}
        if registry.is_file():
            with registry.open(encoding='utf-8-sig',newline='') as stream:
                record = next((r for r in csv.DictReader(stream) if r['content_id']==cid),{})
        title = record.get('title') or cid
        published_url = record.get('published_url') or ''
        published_date = record.get('published_date') or ''
        fingerprint = digest(json.dumps({'run':result.get('run_id'),'draft':digest(markdown),'images':images},sort_keys=True,ensure_ascii=False))
        return {'content_id':cid,'title':title,'run_id':result.get('run_id'),'draft_sha256':digest(markdown),
                'snapshot_token':fingerprint,'stage':current_stage(result,details,registry_status=record.get('status')), 'outcome':result.get('outcome'),
                'publish_ready':bool(result.get('publish_ready')), 'qa_passed':result.get('qa',{}).get('passed') is True,
                'official_confirmed':result.get('official_review',{}).get('status')=='REVIEWED' and bool(result.get('official_review',{}).get('claims')) and all(c.get('verdict')=='confirmed' for c in result.get('official_review',{}).get('claims',[])),
                'admin_checks':result.get('admin_checks') or [],'images':images,
                'published_url':published_url, 'published_date':published_date,
                'previous_published_url':record.get('previous_published_url') or result.get('previous_published_url') or '',
                'qa':result.get('qa'), 'official_review':result.get('official_review') or result.get('official'),
                'approval':result.get('approval'), 'draft_revision':result.get('draft_revision'),
                'drive_configured':(self.root/'config/service_account.json').is_file()}

    def check_request(self, cid, data):
        current = self.snapshot(cid)
        if data.get('snapshot_token')!=current['snapshot_token'] or data.get('run_id')!=current['run_id'] or data.get('draft_sha256')!=current['draft_sha256']:
            raise ValueError('원고 또는 이미지가 변경됐습니다. 화면을 새로고침하고 다시 확인하세요.')
        if not str(data.get('reviewer') or '').strip():
            raise ValueError('검토자 이름을 입력하세요.')
        return current

    def images(self,cid,data):
        with self.pipeline.lock(cid):
            current=self.check_request(cid,data)
            entries=data.get('images') or []
            if not entries or len({e.get('need_id') for e in entries})!=len(entries):
                raise ValueError('검토할 이미지와 결정이 필요합니다.')
            selected=[]
            registry_path=self.root/'content-system/assets'/cid/'assets.yaml'
            assets=yaml_file(registry_path).get('assets',[])
            # Materialize missing run-scoped review jobs only on an explicit review POST.
            run = self.root / 'content-system/working' / cid / 'runs' / current['run_id']
            bindings = yaml_file(run / 'asset-bindings.json').get('bindings', [])
            queue_path = self.root / 'content-system/queue/asset.queue.yaml'
            queue = yaml_file(queue_path) or {}
            changed = False
            for entry in entries:
                original = next((i for i in current['images'] if i['need_id'] == entry.get('need_id') and i['asset_id'] == entry.get('asset_id')), None)
                if original and str(original.get('job_id', '')).startswith('RUNIMG-'):
                    binding = next((b for b in bindings if b.get('need', {}).get('id') == original['need_id']), None)
                    if not binding or not binding.get('candidate'):
                        raise ValueError('현재 원고의 이미지 후보를 찾을 수 없습니다.')
                    asset = run_asset(cid, original['need_id'], binding['candidate'])
                    if asset['asset_id'] != original['asset_id']:
                        raise ValueError('이미지 후보가 변경됐습니다.')
                    if not any(a.get('asset_id') == asset['asset_id'] and a.get('need_id') == original['need_id'] for a in assets):
                        assets.append(asset)
                    queue.setdefault('jobs', {})[original['job_id']] = {'content_id': cid, 'run_id': current['run_id'],
                        'need_id': original['need_id'], 'draft_sha256': current['draft_sha256'], 'status': 'pending_review',
                        'output': {'asset_id': original['asset_id']}}
                    if original['job_id'] not in queue.setdefault('review', []):
                        queue['review'].append(original['job_id'])
                    changed = True
            if changed:
                import yaml
                registry_data = yaml_file(registry_path) or {}
                registry_data['assets'] = assets
                registry_path.parent.mkdir(parents=True, exist_ok=True)
                registry_path.write_text(yaml.safe_dump(registry_data, allow_unicode=True, sort_keys=False), encoding='utf-8')
                queue_path.parent.mkdir(parents=True, exist_ok=True)
                queue_path.write_text(yaml.safe_dump(queue, allow_unicode=True, sort_keys=False), encoding='utf-8')
            for entry in entries:
                original=next((i for i in current['images'] if i['need_id']==entry.get('need_id') and i['asset_id']==entry.get('asset_id')),None)
                if not original or not original['job_id']:
                    raise ValueError('현재 원고에 연결된 이미지 작업을 찾을 수 없습니다.')
                if entry.get('decision') not in {'approve','revise','reject'} or not str(entry.get('review_note') or '').strip():
                    raise ValueError('이미지 검토 결정과 의견을 입력하세요.')
                if entry['decision']=='approve' and not data.get('confirmed_images'):
                    raise ValueError('이미지 내용을 확인한 뒤 확인 체크를 선택하세요.')
                asset=next(a for a in assets if a.get('need_id')==original['need_id'] and a.get('asset_id')==original['asset_id'])
                raw=self.pipeline.draft_path(cid).read_bytes()
                if original['job_draft_sha256'] not in {current['draft_sha256'],hashlib.sha256(raw).hexdigest()}:
                    raise ValueError('이미지 작업 이후 원고가 변경됐습니다. 문단 적합도 재검토가 필요합니다.')
                if asset.get('local_path') and asset.get('origin_type')=='generated':
                    file=(self.root/asset['local_path']).resolve()
                    if not file.is_relative_to(self.root) or not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()!=asset.get('sha256'):
                        raise ValueError('이미지 파일·hash 검증 실패')
                url=entry.get('public_url') or original['public_url']
                if entry['decision']=='approve' and (not asset.get('source_ref') or not asset.get('origin_type')):
                    raise ValueError('이미지 출처와 생성 유형이 필요합니다.')
                if entry['decision']=='approve' and url and not re.fullmatch(r'https://[^\s<>"\']+',url):
                    raise ValueError('공개 HTTPS 이미지 주소를 확인하세요.')
                if entry['decision']=='approve' and not str(url or '').startswith('https://'):
                    if not data.get('publish_to_drive'):
                        raise ValueError('공개 HTTPS 주소가 필요합니다. 공개 업로드에 동의하거나 주소를 입력하세요.')
                    if not asset.get('local_path'):
                        raise ValueError('공개 업로드할 로컬 이미지 파일이 없습니다.')
                    file=(self.root/asset['local_path']).resolve()
                    if not file.is_relative_to(self.root) or not file.is_file():
                        raise ValueError('공개 업로드할 이미지 파일을 확인하세요.')
                selected.append((entry,original,asset,url))
            results=[]
            for entry,original,asset,url in selected:
                if entry['decision']=='approve' and not str(url or '').startswith('https://'):
                    if self.uploader is None:
                        from services.gdrive_sync import gdrive_sync
                        upload=gdrive_sync.upload_file
                    else:
                        upload=self.uploader
                    name=asset['asset_id']+'-'+asset['sha256'][:12]+Path(asset['local_path']).suffix
                    url=upload(str(self.root/asset['local_path']),filename=name,subfolder_name=cid,require_public=True)
                    if not url:
                        if self.uploader is None and gdrive_sync.last_error:
                            raise ValueError(gdrive_sync.last_error)
                        raise ValueError('공개 주소 연동 실패. Google Drive 설정·권한을 확인하세요. 승인하지 않았습니다.')
                review={'decision':entry['decision'],'asset_id':original['asset_id'],
                        'draft_sha256':original['job_draft_sha256'],'review_note':entry['review_note'],
                        'reviewer':data['reviewer'],'public_url':url or ''}
                apply_asset_review(self.root,self.pipeline,{'refs':{'job_id':original['job_id']}},review)
                results.append({'need_id':original['need_id'],'decision':entry['decision']})
            atomic(self.root/'content-system/operations/approvals'/ (uuid.uuid4().hex+'.json'),
                   {'content_id':cid,'reviewer':data['reviewer'],'run_id':current['run_id'],'draft_sha256':current['draft_sha256'],'images':results})
        return self.snapshot(cid)

    def finalize(self,cid,data):
        current=self.check_request(cid,data)
        if not data.get('confirmed_final'):
            raise ValueError('최종 원고·근거·이미지를 확인한 뒤 승인 체크를 선택하세요.')
        if any(i['review_status']!='approved' for i in current['images']):
            raise ValueError('모든 사용 이미지를 먼저 승인하세요.')
        result=self.pipeline.latest(cid)
        markdown=self.pipeline.draft_path(cid).read_text(encoding='utf-8')
        assets=yaml_file(self.root/'content-system/assets'/cid/'assets.yaml').get('assets',[])
        bindings={}
        for identifier in set(re.findall(r'\{\{asset:([^}]+)\}\}',markdown)):
            image=next((i for i in current['images'] if identifier in {i['need_id'],i['asset_id']}),None)
            if not image:
                raise ValueError('원고의 이미지 위치를 확인하세요: '+identifier)
            asset=next(a for a in assets if a.get('need_id')==image['need_id'] and a.get('asset_id')==image['asset_id'])
            bindings[identifier]={'asset_id':asset['asset_id'],'url':image['public_url'],'caption':image['caption'],
                'origin':asset.get('origin_type'),'evidence':json.dumps(asset.get('source_ref'),ensure_ascii=False),
                'revision':asset.get('revision'),'sha256':asset.get('sha256')}
        self.pipeline.approve(cid,current['run_id'],current['draft_sha256'],data['reviewer'],bindings,data.get('resolutions',[]))
        return self.snapshot(cid)

    def publish(self, cid, data):
        run_id = data.get('run_id')
        draft_sha256 = data.get('draft_sha256')
        current = self.snapshot(cid)
        if not run_id or run_id != current.get('run_id'):
            raise ValueError('과거 실행이거나 유효하지 않은 실행입니다. 최신 실행을 확인하세요.')
        if not draft_sha256 or draft_sha256 != current.get('draft_sha256'):
            raise ValueError('원고 해시가 일치하지 않거나 누락되었습니다. 최신 실행을 확인하세요.')
        raw_url = str(data.get('published_url') or '').strip()
        from services.worker_dispatch import naver_url
        canonical_url, _ = naver_url(raw_url)
        url = canonical_url
        self.pipeline.assert_publishable(cid)
        published_date = str(data.get('published_date') or '').strip()
        if not published_date:
            published_date = datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d')
        registry_path = self.root / 'content-system/registry/CONTENT_REGISTRY.csv'
        with registry_path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            fields = reader.fieldnames
            rows = list(reader)
        row = next((r for r in rows if r['content_id'] == cid), None)
        if not row:
            raise ValueError(f'등록되지 않은 콘텐츠 ID입니다: {cid}')
        previous_url = row.get('published_url') or ''
        backup = self.root / 'archive/publication-registration' / datetime.now().strftime('%Y%m%dT%H%M%S')
        backup.mkdir(parents=True, exist_ok=True)
        shutil.copy2(registry_path, backup / registry_path.name)
        row.update(status='PUBLISHED', published_url=url, published_date=published_date)
        if previous_url and previous_url != url:
            if 'previous_published_url' not in fields:
                fields.append('previous_published_url')
            row['previous_published_url'] = previous_url
        with registry_path.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        latest_path = self.root / 'content-system/working' / cid / 'pipeline-latest.json'
        if latest_path.is_file():
            latest = yaml_file(latest_path) or {}
            latest.update(published_url=url, published_date=published_date, status='PUBLISHED')
            if previous_url and previous_url != url:
                latest['previous_published_url'] = previous_url
            atomic(latest_path, latest)
        try:
            from services.performance_db import register_content
            register_content(
                content_id=cid,
                blog_id=row.get('blog_id') or 'oceantech01',
                title=row.get('title') or cid,
                primary_keyword=row.get('primary_keyword') or '',
                canonical_topic=row.get('canonical_topic') or '',
                published_date=published_date,
                published_url=url
            )
        except Exception:
            pass
        try:
            from services.taiga_tracking import synchronize
            synchronize(self.root)
        except Exception:
            pass
        snapshot = self.snapshot(cid)
        if previous_url and previous_url != url:
            snapshot['previous_published_url'] = previous_url
        return snapshot
