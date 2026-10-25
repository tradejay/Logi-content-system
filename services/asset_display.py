"""Human-readable asset provenance. Missing prompts remain explicitly unknown."""
import re
from pathlib import Path
from services.ide_worker_bridge import load


def describe(root, cid, binding):
    if not isinstance(binding, dict):
        binding = {'need': {'id': str(binding)}}
    need = binding.get('need')
    if not isinstance(need, dict):
        need = {'id': str(need)} if need else {}
    asset = binding.get('candidate')
    if not isinstance(asset, dict):
        asset = {'asset_id': str(asset)} if asset else {}
    generated = asset.get('origin_type') == 'generated'
    result = {'purpose': need.get('purpose') or asset.get('alt') or asset.get('caption') or '용도 미기록',
              'description': asset.get('caption') or asset.get('alt') or '설명 미기록',
              'type': 'AI 생성 이미지' if generated else ('기존 이미지·공통 자산' if asset else '제작·확보 필요'),
              'review': {'approved': '승인 완료', 'rejected': '반려됨'}.get(asset.get('review_status'), '검토·승인 대기') if asset else '제작·확보 필요',
              'dimensions': ' × '.join(map(str, asset.get('dimensions') or [])) or ('크기 미기록' if asset else '미등록'),
              'public': '공개 주소 연결됨' if str(asset.get('public_url') or asset.get('url') or '').startswith('https://') else ('로컬 미리보기 · 공개 주소 필요' if (asset.get('public_url') or asset.get('url')) else ('공개 주소 필요' if asset else '미등록')),
              'generation_prompt': asset.get('generation_prompt') or asset.get('prompt'), 'production_instruction': None}
    source_ref = asset.get('source_ref')
    tid = source_ref.get('task_id') if isinstance(source_ref, dict) else (source_ref if isinstance(source_ref, str) else None)
    if generated and tid and re.fullmatch(r'[A-Za-z0-9_-]+', str(tid)):
        packet = root / 'worker-workspaces/05_assets/inbox' / tid / 'input-1.json'
        try:
            data = load(packet)
            request = next((r for r in data.get('requests', []) if r.get('content_id') == cid and r.get('need_id') == need.get('id')), None)
            result['production_instruction'] = (request or data).get('feedback') or (request or {}).get('purpose')
        except (OSError, ValueError):
            pass
    if generated and not result['generation_prompt']:
        result['prompt_note'] = '실제 이미지 생성 도구에 입력한 프롬프트는 미기록입니다. 아래 제작 지시와는 구분됩니다.'
    return result
