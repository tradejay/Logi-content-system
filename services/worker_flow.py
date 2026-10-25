"""Read-only projection of recorded pipeline work; never dispatches AI work."""
import csv
import re
from .ide_worker_bridge import ROOT, load


def read(path):
    try:
        return load(path)
    except (OSError, ValueError):
        return {}


def monitor(cid=None, root=ROOT, run_id=None):
    with (root / 'content-system/registry/CONTENT_REGISTRY.csv').open(encoding='utf-8-sig', newline='') as handle:
        articles = [{'id': r['content_id'], 'title': r.get('title') or r['content_id']} for r in csv.DictReader(handle)]
    cid = cid or (articles[0]['id'] if articles else '')
    if not re.fullmatch(r'CNT-[A-Za-z0-9-]+', cid) or cid not in {a['id'] for a in articles}:
        raise ValueError('등록된 글을 선택하세요.')
    latest = read(root / 'content-system/working' / cid / 'pipeline-latest.json')
    if run_id and run_id != latest.get('run_id'):
        if not re.fullmatch(r'[A-Za-z0-9_-]+', run_id):
            raise ValueError('Invalid run ID')
        latest = read(root / 'content-system/working' / cid / 'runs' / run_id / 'run-result.json')
        if not latest:
            raise ValueError('실행 기록이 없습니다.')
    run = root / 'content-system/working' / cid / 'runs' / str(latest.get('run_id', '__missing__'))
    if not run.resolve().is_relative_to((root / 'content-system/working' / cid / 'runs').resolve()):
        raise ValueError('Invalid run path')
    batch = root / 'worker-control/article-reruns' / run.name
    execution = read(batch / 'execution.json')
    article = next((a for a in execution.get('articles', []) if a.get('content_id') == cid), {})
    correction = read(batch / 'official-corrections.json').get('articles', {}).get(cid, {})
    resume = read(batch / 'official-resume.json').get('articles', {}).get(cid, {})
    rounds = sorted((run / 'official-corrections').glob('round-*'))
    returns = sum((p / 'writer-task.json').exists() for p in rounds)
    bindings = read(run / 'asset-bindings.json').get('bindings', [])
    candidate_count = sum(bool(b.get('candidate')) for b in bindings)
    assets_yaml = read(root / 'content-system/assets' / cid / 'assets.yaml').get('assets', [])
    approved_nids = {a.get('need_id') for a in assets_yaml if a.get('review_status') == 'approved'}
    approved_count = sum(1 for b in bindings if b.get('status') == 'approved' or b.get('need', {}).get('id') in approved_nids)
    all_images_approved = bool(bindings) and approved_count == len(bindings)
    official = latest.get('official_review') or {}
    verdicts = official.get('claims', [])
    official_ok = official.get('status') == 'REVIEWED' and bool(verdicts) and all(v.get('verdict') == 'confirmed' for v in verdicts) and official.get('decision', {}).get('passed') is True
    response = read(run / 'official-call.json').get('status') == 'response_received'
    issues = official.get('decision', {}).get('issues', [])
    def node(key, name, tasks, done=False, bounce=0):
        return {'id': key, 'name': name, 'state': 'done' if done else 'waiting', 'returns': bounce,
                'tasks': [{'text': text, 'done': bool(finished)} for text, finished in tasks]}
    nodes = [
        node('manager', '01 운영·배정', [('글 작업 배정 (시스템)', bool(article))], bool(article)),
        node('planner', '02 자료·기획', [('주제·목차·제품 구성', bool(article.get('plan')))], bool(article.get('plan'))),
        node('writer', '03 집필·수정', [('본문 집필', bool(latest.get('draft_file')))] +
             [(f'지적 수정 {i + 1}차', (p / 'candidate-blocks.json').exists()) for i, p in enumerate(rounds)], bool(latest.get('draft_file')), returns),
        node('review', '04 독립 검토', [('초안 검토', read(batch / 'articles' / cid / 'review.json').get('passed') is True)] +
             [(f'수정본 검토 {i + 1}차', read(p / 'review.json').get('passed') is True) for i, p in enumerate(rounds)] +
             [('공식 응답 Claim별 판정', resume.get('status') == 'interpreted' and official.get('status') == 'REVIEWED')],
             latest.get('qa', {}).get('passed') is True and official.get('status') == 'REVIEWED'),
        node('official', '로지텍 AI', [('현재 원고 응답 수신', response and read(run / 'official-call.json').get('draft_sha256') == latest.get('draft_sha256')), ('기술 주장 검증 통과', official_ok)], official_ok),
        node('assets', '05 이미지', [(f'이미지 후보 {candidate_count}/{len(bindings)}', bool(bindings) and candidate_count == len(bindings)), (f'이미지 승인 {approved_count}/{len(bindings)}', all_images_approved)], bool(bindings) and candidate_count == len(bindings)),
    ]
    active = {'rewriting': 'writer', 'independent_review': 'review', 'official_recheck': 'official'}.get(correction.get('status'))
    if resume.get('status') == 'reviewing':
        active = 'review'
    console_jobs = [read(p) for p in (root / 'worker-control/console-actions').glob('*/job.json')]
    for job in console_jobs:
        if job.get('content_id') == cid and job.get('run_id') == run.name and job.get('status') in {'queued', 'running'}:
            active = job.get('action')
    jobs = [read(p) for p in (root / 'worker-control/asset-revisions').glob('*/job.json')]
    relevant = [j for j in jobs if j.get('content_id') == cid and j.get('run_id') == run.name]
    if any(j.get('status') in {'queued', 'running'} for j in relevant):
        active = active or 'assets'
    nodes[-1]['returns'] = sum(j.get('request_kind') != 'add_slot' for j in relevant)
    blocked = correction.get('status') == 'needs_attention'
    for n in nodes:
        if n['id'] == active:
            n['state'] = 'active'
        elif blocked and n['id'] == ('review' if '독립' in correction.get('reason', '') else 'official'):
            n['state'] = 'blocked'
    edges = [{'from': nodes[i]['id'], 'to': nodes[i + 1]['id'],
              'state': 'done' if nodes[i]['state'] == 'done' else 'active' if nodes[i + 1]['state'] == 'active' else 'waiting'} for i in range(5)]
    if returns:
        edges.append({'from': 'official', 'to': 'writer', 'state': 'return', 'count': returns})
    return {'articles': articles, 'content_id': cid, 'run_id': latest.get('run_id'), 'publish_ready': bool(latest.get('publish_ready')), 'nodes': nodes, 'edges': edges,
            'status': correction.get('reason') or latest.get('stage_detail') or '기록된 실행 없음', 'issues': issues,
            'images_approved': all_images_approved, 'approved_images_count': approved_count, 'total_images_count': len(bindings),
            'note': '✓는 해당 작업의 기록상 완료입니다. 최종 승인·발행은 별도이며, 이미지 작업은 본문 검토와 병행될 수 있습니다.'}
