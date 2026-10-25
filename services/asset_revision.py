"""Single-image IDE regeneration requests; no text rewriting or auto approval."""
import hashlib
import json
import re
import shutil
import subprocess
import time
import uuid
import threading
from datetime import datetime, timezone
from pathlib import Path
from .ide_worker_bridge import ROOT, load, save, local
from .worker_dispatch import enqueue, status


def snapshot(cid, root=ROOT):
    if not re.fullmatch(r'CNT-[A-Za-z0-9-]+', cid):
        raise ValueError('Invalid content ID')
    result = load(root / 'content-system/working' / cid / 'pipeline-latest.json')
    if result.get('outcome') in {'RUNNING', 'CHECKING'}:
        raise ValueError('이 글이 작성·검토 중입니다. 현재 실행이 끝난 뒤 요청하세요.')
    run = local(root / 'content-system/working' / cid / 'runs', result['run_id'])
    draft = local(root, str(Path(result['draft_file']).resolve().relative_to(root.resolve())))
    digest = hashlib.sha256(draft.read_bytes()).hexdigest()
    if digest != result.get('draft_sha256'):
        raise ValueError('현재 원고가 실행 기록과 다릅니다. 먼저 원고를 확인하세요.')
    bindings = load(run / 'asset-bindings.json')['bindings']
    view = {'content_id': cid, 'run_id': result['run_id'], 'draft_sha256': digest,
            'images': [{'need_id': b['need']['id'], 'purpose': b['need'].get('purpose'),
                        'preview_url': (b.get('candidate') or {}).get('public_url') or (b.get('candidate') or {}).get('url'),
                        'asset_id': (b.get('candidate') or {}).get('asset_id')} for b in bindings]}
    requests = []
    for path in (root / 'worker-control/asset-revisions').glob('*/job.json'):
        try:
            job = load(path)
            if job.get('content_id') == cid and job.get('run_id') == result['run_id']:
                requests.append(job)
        except (ValueError, OSError):
            continue
    for image in view['images']:
        matches = [j for j in requests if j.get('need_id') == image['need_id']]
        if matches:
            latest = max(matches, key=lambda j: j.get('created_at') or j.get('task', {}).get('created_at', ''))
            image['last_request'] = {k: latest.get(k) for k in ['request_id', 'status', 'phase', 'taiga_synced', 'error']}
    view['processor'] = processor_status(root)
    text = draft.read_text(encoding='utf-8')
    view['paragraphs'] = [{'anchor': str(m.start()), 'text': m.group(0)[:220]}
                          for m in re.finditer(r'[^\n](?:[^\n]|\n(?!\n))*', text)
                          if m.group(0).strip() and '{{asset:' not in m.group(0)]
    return view


_slot_lock = threading.RLock()


def add_slot(cid, data, root=ROOT):
    with _slot_lock:
        return _add_slot(cid, data, root)


def _add_slot(cid, data, root=ROOT):
    """Insert a new placeholder in a new revision, then use the existing asset queue."""
    identity = str(uuid.UUID(data['request_id']))
    directory = root / 'worker-control/asset-revisions' / identity
    existing = directory / 'job.json'
    if existing.exists():
        job = load(existing)
        if job.get('content_id') != cid or job.get('request_kind') != 'add_slot' or job.get('feedback') != str(data.get('feedback', '')).strip() or job.get('anchor') != str(data.get('anchor')):
            raise ValueError('이미 사용된 요청 ID입니다.')
        return job
    view = snapshot(cid, root)
    if (data.get('run_id'), data.get('draft_sha256')) != (view['run_id'], view['draft_sha256']):
        raise ValueError('원고가 변경됐습니다. 화면을 새로고침하세요.')
    feedback = str(data.get('feedback', '')).strip()
    if not 2 <= len(feedback) <= 3000:
        raise ValueError('이미지 목적·제작 지시를 2~3000자로 입력하세요.')
    for path in (root / 'worker-control/article-reruns').glob('*/official-corrections.json'):
        correction = load(path)
        item = correction.get('articles', {}).get(cid, {})
        if correction.get('status') == 'running' and item.get('status') not in {'confirmed', 'needs_attention'}:
            raise ValueError('원고 수정·재검토 중입니다. 완료 후 새 이미지 자리를 추가하세요.')
    for path in (root / 'worker-control/asset-revisions').glob('*/job.json'):
        job = load(path)
        if job.get('content_id') == cid and job.get('status') in {'queued', 'running'}:
            raise ValueError('이 글의 이미지 작업 완료 후 새 자리를 추가하세요.')
    work = root / 'content-system/working' / cid
    run = work / 'runs' / view['run_id']
    latest = load(work / 'pipeline-latest.json')
    draft = Path(latest['draft_file'])
    text = draft.read_text(encoding='utf-8')
    anchor = str(data.get('anchor'))
    match = next((m for m in re.finditer(r'[^\n](?:[^\n]|\n(?!\n))*', text) if str(m.start()) == anchor and '{{asset:' not in m.group(0)), None)
    if match is None:
        raise ValueError('추가할 문단을 다시 선택하세요.')
    need_id = 'AN-ADD-' + uuid.UUID(identity).hex[:16]
    slot = '\n\n{{asset:' + need_id + '}}'
    updated = text[:match.end()] + slot + text[match.end():]
    metadata_path = Path(latest.get('writer_metadata_file', run / 'revisions/r1.writer-metadata.json'))
    metadata = load(metadata_path) if metadata_path.exists() else None
    if metadata:
        # Locate by absolute article offset, so repeated paragraphs remain unambiguous.
        cursor = 0
        found = False
        for block in metadata['blocks']:
            body = block['markdown'].strip()
            start = text.find(body, cursor)
            if start < 0:
                raise ValueError('블록과 현재 원고가 다릅니다. 원고 동기화가 필요합니다.')
            if start <= match.start() and match.end() <= start + len(body):
                offset = match.end() - start
                block['markdown'] = body[:offset] + slot + body[offset:]
                found = True
            cursor = start + len(body)
        if not found:
            raise ValueError('선택 문단의 구성 블록을 찾지 못했습니다.')
    directory.mkdir(parents=True, exist_ok=True)
    save(directory / 'previous-run-result.json', latest)
    revision = run / 'revisions' / ('asset-add-' + uuid.UUID(identity).hex)
    new_draft = revision.with_suffix('.draft.md')
    new_draft.write_bytes(updated.encode('utf-8'))
    if metadata:
        new_meta = revision.with_suffix('.writer-metadata.json')
        save(new_meta, metadata)
        latest['writer_metadata_file'] = str(new_meta)
    bindings = load(run / 'asset-bindings.json')
    bindings['bindings'].append({'need': {'id': need_id, 'purpose': feedback, 'type': 'image'}, 'candidate': None, 'status': 'missing'})
    save(run / 'asset-bindings.json', bindings)
    latest.update(draft_file=str(new_draft), draft_sha256=hashlib.sha256(new_draft.read_bytes()).hexdigest(),
                  publish_ready=False, approval=None, stage='image_generation',
                  stage_detail='새 이미지 자리 추가 · 제작 대기', outcome='COMPLETED_REVIEW_PENDING',
                  official_review={'status': 'STALE', 'claims': [], 'reason': '새 이미지 자리 추가로 원고 해시 변경'})
    if 'claim_map_file' not in latest:
        latest['claim_map_file'] = str(run / 'revisions/r1.claim-map.json')
    latest['qa'] = {'passed': False, 'issues': [], 'status': 'STALE'}
    save(work / 'pipeline-latest.json', latest)
    save(run / 'run-result.json', latest)
    job = submit(cid, {**data, 'need_id': need_id, 'draft_sha256': latest['draft_sha256']}, root)
    job.update(request_kind='add_slot', anchor=anchor, previous_draft_sha256=view['draft_sha256'])
    save(existing, job)
    return job


def processor_status(root=ROOT):
    path = root / 'worker-control/asset-revisions/health.json'
    health = load(path) if path.exists() else {}
    alive = bool(health.get('heartbeat') and time.time()-health['heartbeat'] < 90)
    if alive:
        import os
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.OpenProcess.restype = wintypes.HANDLE
            kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel.OpenProcess(0x1000, False, int(health.get('pid', 0)))
            if handle:
                code = wintypes.DWORD()
                alive = bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
                kernel.CloseHandle(handle)
            else:
                alive = False
        else:
            try:
                os.kill(int(health.get('pid', 0)), 0)
            except OSError:
                alive = False
    return {**health, 'alive': alive}


def ensure_processor(root=ROOT):
    if processor_status(root)['alive']:
        return
    request = root / 'worker-control/asset-revisions/start-request.json'
    if request.exists() and time.time()-request.stat().st_mtime < 20:
        return
    save(request, {'requested_at': time.time()})
    subprocess.Popen(['powershell', '-NoProfile', '-File', str(root / 'scripts/start_ide_worker_bridge.ps1')],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def submit(cid, data, root=ROOT):
    view = snapshot(cid, root)
    if data.get('run_id') != view['run_id'] or data.get('draft_sha256') != view['draft_sha256']:
        raise ValueError('원고가 변경됐습니다. 화면을 새로고침하세요.')
    need = next((n for n in view['images'] if n['need_id'] == data.get('need_id')), None)
    if not need:
        raise ValueError('현재 원고에 없는 이미지 자리입니다.')
    feedback = str(data.get('feedback', '')).strip()
    if not 2 <= len(feedback) <= 3000:
        raise ValueError('수정 지시를 2~3000자로 입력하세요.')
    identity = str(uuid.UUID(data['request_id']))
    directory = root / 'worker-control/asset-revisions' / identity
    if (directory / 'job.json').exists():
        existing = load(directory / 'job.json')
        if (existing['content_id'], existing['need_id'], existing['feedback'], existing['draft_sha256']) != (cid, need['need_id'], feedback, view['draft_sha256']):
            raise ValueError('이미 사용된 요청 ID입니다.')
        return existing
    for path in (root / 'worker-control/asset-revisions').glob('*/job.json'):
        other = load(path)
        if other['content_id'] == cid and other['need_id'] == need['need_id'] and other['status'] in {'queued', 'running'}:
            raise ValueError('이 이미지의 재제작 작업이 이미 대기·진행 중입니다.')
    job = {k: view[k] for k in ['content_id', 'run_id', 'draft_sha256']}
    job.update(request_id=identity, need_id=need['need_id'], feedback=feedback, status='queued', approved=False,
               created_at=datetime.now(timezone.utc).isoformat())
    save(directory / 'job.json', job)
    return job


def result_fingerprint(worker, task):
    result_path = local(worker, task['ai_output'])
    output = load(result_path)
    candidates = output.get('candidates', [])
    image = local(worker, candidates[0]['path']) if len(candidates) == 1 and candidates[0].get('path') else None
    return {'result_sha256': hashlib.sha256(result_path.read_bytes()).hexdigest(),
            'image_sha256': hashlib.sha256(image.read_bytes()).hexdigest() if image and image.is_file() else None}


def step(root=ROOT):
    directory = root / 'worker-control/asset-revisions'
    jobs = []
    for path in sorted(directory.glob('*/job.json')):
        try:
            job = load(path)
            if not isinstance(job, dict) or not {'status', 'content_id', 'need_id', 'request_id'}.issubset(job):
                raise ValueError('Invalid queue record')
            jobs.append((path, job))
        except (ValueError, OSError):
            save(directory / 'queue-errors' / (path.parent.name + '.json'), {'error': '요청 파일을 읽을 수 없습니다.', 'path': str(path)})
    # A user may rerun the same IDE conversation after a quota/login failure.
    # Preserve its original report; accept a changed successful result as a new submission.
    for path, job in jobs:
        if job['status'] not in {'failed', 'completed'} or not job.get('task'):
            continue
        same_slot = [j for _, j in jobs if j['content_id'] == job['content_id'] and j['need_id'] == job['need_id']]
        newest = max(same_slot, key=lambda j: j.get('created_at') or j.get('task', {}).get('created_at', ''))
        if newest['request_id'] != job['request_id']:
            continue
        worker = root / 'worker-workspaces/05_assets'
        tid = job['task']['task_id']
        task_file = worker / 'inbox' / tid / 'task.json'
        try:
            task = load(task_file)
            result_path = local(worker, task['ai_output'])
            if not result_path.exists():
                continue
            output = load(result_path)
            if len(output.get('candidates', [])) != 1 or output['candidates'][0].get('need_id') != job['need_id']:
                continue
            fingerprint = result_fingerprint(worker, task)
            report_path = worker / 'outbox' / tid / 'report.json'
            original = load(report_path)
            pointer = worker / 'outbox' / tid / 'current-report.json'
            if pointer.exists():
                selected = local(worker, load(pointer)['path'])
                if not selected.is_relative_to(worker / 'outbox' / tid / 'resubmissions'):
                    raise ValueError('Invalid resubmission report path')
                original = load(selected)
            original_digest = next((a['sha256'] for a in original['artifacts'] if a['path'] == task['ai_output']), None)
            expected = (job.get('last_failed_fingerprint') if job['status'] == 'failed' else job.get('accepted_fingerprint'))
            if expected is None:
                image_digest = next((a['sha256'] for a in original['artifacts'] if a['path'] == output['candidates'][0]['path']), None)
                if image_digest is None and job.get('asset_id'):
                    import yaml
                    registry = root / 'content-system/assets' / job['content_id'] / 'assets.yaml'
                    if registry.exists():
                        data = yaml.safe_load(registry.read_text(encoding='utf-8-sig')) or {}
                        image_digest = next((a.get('sha256') for a in data.get('assets', []) if a.get('asset_id') == job['asset_id']), None)
                expected = {'result_sha256': original_digest, 'image_sha256': image_digest}
            if fingerprint == expected:
                continue
            digest = hashlib.sha256(json.dumps(fingerprint, sort_keys=True).encode()).hexdigest()
            view = snapshot(job['content_id'], root)
            if (view['run_id'], view['draft_sha256']) != (job['run_id'], job['draft_sha256']):
                continue
            if hashlib.sha256(task_file.read_bytes()).hexdigest() != original['input_sha256']:
                raise ValueError('Resubmission task inputs changed')
            for item in load(local(worker, task['input_manifest']))['files']:
                if hashlib.sha256(local(worker, item['path']).read_bytes()).hexdigest() != item['sha256']:
                    raise ValueError('Resubmission input snapshot changed')
            image_path = local(worker, output['candidates'][0]['path'])
            from PIL import Image
            with Image.open(image_path) as image:
                image.verify()
            report = {**original, 'resubmission_of': original_digest, 'artifacts': [
                {'path': p.relative_to(worker).as_posix(), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size}
                for p in [result_path, image_path]]}
            revised = worker / 'outbox' / tid / 'resubmissions' / digest / 'report.json'
            save(revised, report)
            save(worker / 'outbox' / tid / 'current-report.json', {'path': revised.relative_to(worker).as_posix()})
            job.setdefault('attempt_history', []).append({'status': job['status'], 'error': job.get('error'), 'result_sha256': original_digest})
            job.update(status='running', recovery_digest=digest)
            job['taiga_synced'] = False
            job.pop('sync_retry_at', None)
            job.pop('taiga_sync_error', None)
            job.pop('error', None)
            save(path, job)
        except (ValueError, KeyError, OSError):
            continue
    for path, job in jobs:
        if job['status'] != 'running':
            continue
        record = job['task']
        worker = root / 'worker-workspaces/05_assets'
        try:
            task = load(worker / 'inbox' / record['task_id'] / 'task.json')
            if not local(worker, task['ai_output']).exists():
                return
        except (ValueError, OSError, KeyError) as error:
            job.update(status='failed', error=str(error)[:400])
            save(path, job)
            continue
        collected = False
        try:
            if status(record['task_id'], root=root)['status'] != 'collected':
                raise ValueError('워커 결과 수집 실패')
            collected = True
            view = snapshot(job['content_id'], root)
            if view['run_id'] != job['run_id'] or view['draft_sha256'] != job['draft_sha256']:
                raise ValueError('작업 중 원고가 변경돼 새 이미지를 적용하지 않았습니다.')
            output = load(local(worker, task['ai_output']))
            candidates = output.get('candidates', [])
            if len(candidates) != 1 or candidates[0].get('need_id') != job['need_id']:
                raise ValueError('해당 이미지 1개가 완성되지 않았습니다: ' + str(output.get('unresolved_items', []))[:300])
            candidate = candidates[0]
            source = local(worker, candidate['path'])
            from PIL import Image
            with Image.open(source) as image:
                dimensions, mime = list(image.size), Image.MIME.get(image.format)
                image.verify()
            suffix = { 'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp' }.get(mime)
            if not suffix:
                raise ValueError('PNG/JPEG/WebP 이미지가 필요합니다.')
            cid = job['content_id']
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            aid = 'AST-GEN-' + identity_hash(job['request_id'] + ':' + digest)
            destination = root / 'content-system/assets' / cid / 'generated' / (aid + suffix)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            asset = {'asset_id': aid, 'revision': 1, 'content_id': cid, 'need_id': job['need_id'], 'origin_type': 'generated',
                     'source_ref': {'run_id': job['run_id'], 'task_id': record['task_id'], 'request_id': job['request_id']},
                     'local_path': destination.relative_to(root).as_posix(), 'url': f'/api/content-system/assets/{cid}/generated/{destination.name}',
                     'public_url': None, 'sha256': digest, 'mime_type': mime, 'dimensions': dimensions,
                     'alt': candidate.get('caption', ''), 'review_status': 'candidate', 'rights_status': 'pending_review'}
            import yaml
            registry = root / 'content-system/assets' / cid / 'assets.yaml'
            registry.parent.mkdir(parents=True, exist_ok=True)
            data = yaml.safe_load(registry.read_text(encoding='utf-8-sig')) if registry.exists() else {'assets': []}
            data['assets'] = [a for a in data.get('assets', []) if a.get('asset_id') != aid] + [asset]
            temporary = registry.with_suffix('.yaml.tmp')
            temporary.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding='utf-8')
            temporary.replace(registry)
            run = root / 'content-system/working' / cid / 'runs' / job['run_id']
            bindings = load(run / 'asset-bindings.json')
            current_view = snapshot(cid, root)
            if current_view['run_id'] != job['run_id'] or current_view['draft_sha256'] != job['draft_sha256']:
                raise ValueError('원고가 변경돼 이미지 후보만 보존하고 연결하지 않았습니다.')
            binding = next(b for b in bindings['bindings'] if b['need']['id'] == job['need_id'])
            if not (path.parent / 'previous-binding.json').exists():
                save(path.parent / 'previous-binding.json', binding)
            save(path.parent / 'history' / digest / 'previous-binding.json', binding)
            binding.update(candidate=asset, status='pending_review')
            save(run / 'asset-bindings.json', bindings)
            latest_path = root / 'content-system/working' / cid / 'pipeline-latest.json'
            latest = load(latest_path)
            save(path.parent / 'previous-run-result.json', latest)
            latest.update(publish_ready=False)
            latest.pop('approval', None)
            approved = dict(latest.get('approved_assets') or {})
            prior = load(path.parent / 'previous-binding.json')
            for key in [job['need_id'], (prior.get('candidate') or {}).get('asset_id')]:
                approved.pop(key, None)
            latest['approved_assets'] = approved
            save(latest_path, latest)
            job.update(status='completed', asset_id=aid, preview_url=asset['url'], taiga_synced=False,
                       accepted_fingerprint=result_fingerprint(worker, task), phase='content_applied', updated_at=datetime.now(timezone.utc).isoformat())
            job.pop('last_failed_fingerprint', None)
        except Exception as error:
            job.update(status='failed', error=str(error)[:400])
            try:
                if collected:
                    job['last_failed_fingerprint'] = result_fingerprint(worker, task)
            except (OSError, ValueError, KeyError):
                pass
        save(path, job)
        return
    # Do not interrupt an already active 05 task from another workflow.
    for path in (root / 'worker-control/notifications/05_assets').glob('*.json'):
        notification = load(path)
        if notification.get('status') in {'sending', 'notified', 'delivery_unknown'}:
            tid = notification.get('task_id')
            if not (root / 'worker-workspaces/05_assets/outbox' / str(tid) / 'report.json').exists():
                return
    for path, job in jobs:
        if job['status'] != 'queued':
            continue
        try:
            view = snapshot(job['content_id'], root)
            if view['draft_sha256'] != job['draft_sha256'] or view['run_id'] != job['run_id']:
                raise ValueError('원고가 변경돼 요청을 보류했습니다.')
            run = root / 'content-system/working' / job['content_id'] / 'runs' / job['run_id']
            binding = next(b for b in load(run / 'asset-bindings.json')['bindings'] if b['need']['id'] == job['need_id'])
            markdown = Path(load(root / 'content-system/working' / job['content_id'] / 'pipeline-latest.json')['draft_file']).read_text(encoding='utf-8')
            parts = markdown.split('\n\n')
            positions = [i for i, p in enumerate(parts) if '{{asset:' + job['need_id'] + '}}' in p]
            selected = sorted({i for pos in positions for i in range(max(0, pos-2), min(len(parts), pos+3))})
            paragraphs = [parts[i] for i in selected]
            packet = {**job, 'need': binding['need'], 'nearby_paragraphs': paragraphs, 'previous_candidate': binding.get('candidate'),
                      'facts': load(run / 'fact-bundle.json').get('facts', [])}
            save(path.parent / 'input.json', packet)
            inputs = [path.parent / 'input.json', root / 'content-system/02_writer_ai/authoring/04-images.md']
            previous = (binding.get('candidate') or {}).get('local_path')
            if previous:
                inputs.append(local(root, previous))
            record = enqueue('assets', '지정 need_id 이미지 1개만 수정 지시에 맞춰 IDE 내장 이미지 도구로 실제 재생성하세요. 기존 이미지가 입력되면 함께 확인하세요. 파일은 자기 work/TASK-ID/asset_fulfillment/images/need_id.png에 저장. 제품 실물·포트·설정 화면은 추측 생성하지 말고 공식 자료 필요 시 미해결 사유를 반환하세요. 출력은 candidates 배열 1개(need_id,path,caption)와 unresolved_items뿐입니다. 원고·로그·자산대장·승인은 변경하지 마세요.', inputs, kind='asset-revision', root=root, operational=True)
            job.update(status='running', task=record)
            save(path, job)  # Persist identity before notification; retries never duplicate it.
            delivery = status(record['task_id'], root=root)
            if delivery.get('status') in {'error', 'delivery_unknown'}:
                job.update(phase='delivery_unknown', error=delivery.get('error', '전송 여부를 확인해야 합니다. 중복 전송하지 않습니다.'))
                save(path, job)
        except Exception as error:
            job.update(status='failed', error=str(error)[:400])
            save(path, job)
        return


def identity_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()[:20]
