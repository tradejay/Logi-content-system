"""Package missing images and register actual IDE-generated files by need_id."""
import argparse
import hashlib
import json
import shutil
import time
import uuid
from pathlib import Path
import yaml
from services.ide_worker_bridge import ROOT, load, save, local
from services.worker_dispatch import status


def prepare(directory):
    state = load(directory / 'execution.json')
    if state['stage'] != 'finished':
        raise ValueError('Wait for the existing batch to finish; do not race its asset worker')
    requests, manual = [], []
    for article in state['articles']:
        cid = article['content_id']
        output = directory / 'articles' / cid
        assets = load(output / 'asset-candidates.json') if (output / 'asset-candidates.json').exists() else {}
        missing = {x if isinstance(x, str) else x.get('need_id') for x in assets.get('unresolved_items', [])}
        context = load(directory / (cid + '.context.json'))
        for need in article['plan'].get('asset_needs', []):
            nid = need.get('asset_need_id', need.get('id'))
            if nid not in missing:
                continue
            item = {'content_id': cid, 'need_id': nid, 'purpose': need.get('purpose'), 'asset_type': need.get('type')}
            if need.get('type') == 'screenshot':
                manual.append(item)
                continue
            specs = [b for b in article['plan']['ordered_blocks'] if b.get('role') == need.get('section_role')]
            fids = {fid for b in specs for fid in b.get('fact_ids', [])}
            item.update(facts=[f for f in context['facts'] if f['id'] in fids], paragraphs=[b['markdown'] for b in article['blocks'] if b.get('role') == need.get('section_role')])
            requests.append(item)
    packet = {'batch_id': state['batch_id'], 'requests': requests, 'manual_source_required': manual}
    save(directory / 'image-generation-input.json', packet)
    print(json.dumps({'generate': len(requests), 'official_screenshot_required': len(manual), 'input': str((directory / 'image-generation-input.json').relative_to(ROOT))}, ensure_ascii=False))


def collect(directory, task_id):
    record = load(ROOT / 'worker-control/dispatch/tasks' / (task_id + '.json'))
    if record['worker_folder'] != '05_assets':
        raise ValueError('Expected the asset worker')
    worker = ROOT / 'worker-workspaces/05_assets'
    task = load(worker / 'inbox' / task_id / 'task.json')
    if not local(worker, task['ai_output']).exists():
        return False
    result_status = status(task_id)
    if result_status['status'] != 'collected':
        raise ValueError('Asset task failed mechanical collection')
    result = load(local(worker, result_status['result_file']))
    packet = load(directory / 'image-generation-input.json')
    expected = {(r['content_id'], r['need_id']) for r in packet['requests']}
    candidates = result.get('candidates', [])
    seen = set()
    registered = []
    from PIL import Image
    for candidate in candidates:
        key = (candidate.get('content_id'), candidate.get('need_id'))
        if key not in expected or key in seen:
            raise ValueError('Unexpected or duplicate generated asset identity')
        seen.add(key)
        source = local(worker, candidate.get('path', ''))
        if not source.is_file() or source.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'}:
            raise ValueError('A real generated raster file is required')
        with Image.open(source) as image:
            dimensions = list(image.size)
            mime_type = Image.MIME.get(image.format)
            image.verify()
        cid, nid = key
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        asset_id = 'AST-GEN-' + uuid.uuid5(uuid.NAMESPACE_URL, ':'.join([packet['batch_id'], cid, nid, digest])).hex[:20]
        destination = ROOT / 'content-system/assets' / cid / 'generated' / (asset_id + source.suffix.lower())
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        registry = destination.parents[1] / 'assets.yaml'
        data = yaml.safe_load(registry.read_text(encoding='utf-8-sig')) if registry.exists() else {'assets': []}
        asset = {'asset_id': asset_id, 'revision': 1, 'content_id': cid, 'need_id': nid, 'origin_type': 'generated',
                 'source_ref': {'run_id': packet['batch_id'], 'task_id': task_id, 'need_id': nid},
                 'local_path': destination.relative_to(ROOT).as_posix(), 'public_url': None,
                 'url': f'/api/content-system/assets/{cid}/generated/{destination.name}',
                 'sha256': digest, 'dimensions': dimensions, 'mime_type': mime_type,
                 'rights_status': 'pending_review', 'alt': candidate.get('caption', ''),
                 'review_status': 'candidate', 'lifecycle_status': 'candidate', 'reviewer': None, 'reviewed_at': None}
        data['assets'] = [a for a in data.get('assets', []) if a.get('asset_id') != asset_id] + [asset]
        temporary = registry.with_suffix('.yaml.tmp')
        temporary.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding='utf-8')
        temporary.replace(registry)
        run = ROOT / 'content-system/working' / cid / 'runs' / packet['batch_id']
        bindings = load(run / 'asset-bindings.json')
        matches = [b for b in bindings['bindings'] if b.get('need', {}).get('id') == nid]
        if not matches:
            raise ValueError('Generated image has no matching draft slot')
        for binding in matches:
            binding.update(candidate=asset, status='pending_review')
        save(run / 'asset-bindings.json', bindings)
        output = directory / 'articles' / cid / 'asset-candidates.json'
        prior = load(output)
        prior['candidates'] = [a for a in prior.get('candidates', []) if a.get('need_id') != nid] + [asset]
        prior['unresolved_items'] = [x for x in prior.get('unresolved_items', []) if (x if isinstance(x, str) else x.get('need_id')) != nid]
        save(output, prior)
        registered.append({'content_id': cid, 'need_id': nid, 'asset_id': asset_id})
    save(directory / 'image-generation-result.json', {'task_id': task_id, 'registered': registered, 'missing': [{'content_id': c, 'need_id': n} for c, n in sorted(expected - seen)], 'worker_unresolved': result.get('unresolved_items', []), 'approved': False})
    state_path = directory / 'execution.json'
    state = load(state_path)
    if state['stage'] == 'finished' and not (directory / 'controller.lock').exists():
        from services.logitech_review_status import inspect_failure
        for article in state['articles']:
            path = directory / 'articles' / article['content_id'] / 'asset-candidates.json'
            current = load(path) if path.exists() else {}
            missing = current.get('unresolved_items', [])
            article['unresolved_assets'] = missing
            if article.get('official_pending'):
                failure = inspect_failure(RuntimeError('Previous official review failed'))
                article['official_failure'] = failure
                save(directory / 'articles' / article['content_id'] / 'official-failure.json', failure)
            article['reason'] = ' '.join(x for x in [article.get('official_failure', {}).get('action_required', ''), f'이미지 제작·확보 미완료 {len(missing)}건' if missing else '이미지 후보 검토·최종 원고 승인 대기'] if x)
        save(state_path, state)
        from scripts.run_ide_article_batch import snapshot
        snapshot(directory, state)
    from services.taiga_tracking import synchronize
    synchronize()
    print(json.dumps({'registered': len(registered), 'missing': len(expected - seen), 'approved': False}))
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'collect'])
    parser.add_argument('--directory', required=True)
    parser.add_argument('--task')
    parser.add_argument('--watch', action='store_true')
    args = parser.parse_args()
    directory = local(ROOT, args.directory)
    if args.action == 'prepare':
        prepare(directory)
        return
    if not args.task:
        parser.error('--task is required for collection')
    save(directory / 'image-generation-task.json', {'task_id': args.task, 'status': 'collecting'})
    deadline = time.monotonic() + 86400
    while True:
        if collect(directory, args.task) or not args.watch or time.monotonic() > deadline:
            return
        time.sleep(10)


if __name__ == '__main__':
    main()
