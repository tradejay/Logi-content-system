"""Per-article image acquisition with candidate-only registration."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import uuid
from datetime import datetime, timezone
import yaml


def generate_image(root, request):
    raise RuntimeError('Gemini API is quarantined by user request. Use IDE workers; restoring API transport requires an explicit user request.')


def acquire_assets(root, cid, run_id, markdown, needs, bindings, generator=None):
    root = Path(root).resolve()
    if not re.fullmatch(r'CNT-[A-Za-z0-9-]+', cid):
        raise ValueError('Invalid content ID')
    generator = generator or (lambda request: generate_image(root, request))
    directory = root / 'content-system/assets' / cid
    registry_path = directory / 'assets.yaml'
    registry = yaml.safe_load(registry_path.read_text(encoding='utf-8-sig')) if registry_path.exists() else {'assets': []}
    report = {'version': 1, 'content_id': cid, 'run_id': run_id, 'items': [], 'generated_count': 0}
    need_map = {n['id']: n for n in needs}
    registry_changed = False
    used = set(re.findall(r'\{\{asset:([^}]+)\}\}', markdown))
    for binding in bindings:
        need = need_map.get(binding.get('need', {}).get('id'), binding.get('need', {}))
        nid = need.get('id')
        if nid not in used:
            continue
        if binding.get('candidate'):
            report['items'].append({'need_id': nid, 'status': 'candidate_available', 'asset': binding['candidate']})
            continue
        if need.get('mode') != 'generation_request':
            report['items'].append({'need_id': nid, 'status': 'source_required', 'detail': '공식 제품 사진·GIF 또는 기존 자산을 확보·등록해야 합니다.'})
            continue
        pos = markdown.find('{{asset:' + nid + '}}')
        paragraph = markdown[max(0, pos - 1400):pos] + markdown[pos:pos + 500]
        request = {'need_id': nid, 'paragraph': paragraph, 'core_message': need.get('purpose', ''),
                   'korean_copy': '', 'forbidden_claims': ['제품 실물·포트·UI 합성', '본문에 없는 수치·지원·효과'],
                   'anchor': need.get('anchor'), 'style': '단정한 2.5D 기업용 설명 카드 또는 가상 회의실 사진',
                   'source_basis': 'final_draft; old planning prompt excluded'}
        request_sha = hashlib.sha256(json.dumps(request, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        reuse = next((a for a in registry.get('assets', []) if a.get('need_id') == nid and a.get('generation_request_sha256') == request_sha
                      and a.get('local_path') and (root / a['local_path']).is_file() and a.get('review_status') != 'rejected'), None)
        try:
            if reuse:
                asset = reuse
            else:
                image_bytes, mime, usage = generator(request)
                from PIL import Image
                with Image.open(io.BytesIO(image_bytes)) as image:
                    dimensions = {'width': image.width, 'height': image.height}
                    expected = 'PNG' if mime == 'image/png' else 'JPEG' if mime == 'image/jpeg' else None
                    if expected != image.format:
                        raise ValueError('Image bytes/MIME mismatch')
                    image.verify()
                asset_id = 'AST-GEN-' + uuid.uuid4().hex[:12].upper()
                filename = asset_id + ('.png' if mime == 'image/png' else '.jpg')
                directory.mkdir(parents=True, exist_ok=True)
                path = directory / filename
                path.write_bytes(image_bytes)
                asset = {'asset_id': asset_id, 'revision': 1, 'content_id': cid, 'need_id': nid,
                         'origin_type': 'generated', 'source_ref': {'run_id': run_id, 'need_id': nid},
                         'rights_status': 'needs_review', 'entity_ids': [], 'fact_ids': [],
                         'local_path': str(path.relative_to(root)).replace('\\', '/'), 'public_url': None,
                         'url': f'/api/content-system/assets/{cid}/{filename}', 'filename': filename,
                         'mime_type': mime, 'dimensions': dimensions, 'sha256': hashlib.sha256(image_bytes).hexdigest(),
                         'alt': need.get('purpose', ''), 'review_status': 'candidate', 'reviewer': None, 'reviewed_at': None,
                         'created_at': datetime.now(timezone.utc).isoformat(), 'generation_request_sha256': request_sha,
                         'generation_request': request, 'usage_metadata': usage, 'lifecycle_status': 'candidate'}
                registry.setdefault('assets', []).append(asset)
                registry_changed = True
                report['generated_count'] += 1
            binding.update(candidate=asset, status='pending_review')
            report['items'].append({'need_id': nid, 'status': 'candidate_available' if reuse else 'generated_pending_review', 'asset': asset})
        except Exception as error:
            # No promotion, no old image substitution and no credential-bearing exception text.
            report['items'].append({'need_id': nid, 'status': 'failed', 'error_type': type(error).__name__,
                                    'detail': '이미지 생성·검증 실패. 설정·결제·모델과 로그를 확인하세요.', 'request': request})
    if registry_changed:
        from services.content_pipeline import atomic
        atomic(registry_path, yaml.safe_dump(registry, allow_unicode=True, sort_keys=False))
    report['status'] = 'needs_attention' if any(i['status'] in ('failed', 'source_required') for i in report['items']) else 'awaiting_review'
    return report
