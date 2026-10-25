"""Explicit test-only handoff from paragraph editor to independent reviewer."""
import hashlib
import shutil
from .ide_worker_bridge import ROOT, load, save, local


def handoff(worker_folder, task_id, state, root=ROOT):
    if state.get('status') != 'collected' or state.get('result_status') != 'completed':
        return None
    writer = root / 'worker-workspaces' / worker_folder
    task = load(writer / 'inbox' / task_id / 'task.json')
    config = task.get('test_review_handoff')
    host_config = root / 'worker-control/test-review-handoff.json'
    if not config and host_config.exists():
        host = load(host_config)
        if (host.get('worker_folder'), host.get('task_id')) == (worker_folder, task_id):
            config = host['handoff']
    if not task.get('test_only') or not config or not config.get('enabled'):
        return None
    reviewer = local(root / 'worker-workspaces', config['worker_folder'])
    identity = load(reviewer / 'worker.json')
    if 'feedback' not in identity['owned_stages']:
        raise ValueError('Review worker does not own feedback stage')
    review_id = task_id + '-REVIEW'
    target = reviewer / 'inbox' / review_id
    if (target / 'task.json').exists():
        return review_id
    target.mkdir(parents=True, exist_ok=True)
    if task.get('output_protocol')=='content_only_v1':
        from .ide_worker_artifacts import review_packet
        before=load(local(writer,task['system_inputs']['blocks']))['blocks']
        after=load(local(writer,config['edited_artifacts']['edited-blocks.json']))['blocks']
        packet_path=target/'review-input.json';save(packet_path,review_packet(before,after))
        guide_path=target/'style-guide.md';shutil.copyfile(writer/'inbox'/task_id/'style-guide.md',guide_path)
        files=[{'path':p.relative_to(reviewer).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in [packet_path,guide_path]]
        save(target/'input-manifest.json',{'files':files})
        ai_output=f'work/{review_id}/feedback/result.json'
        save(target/'task.json',{'task_id':review_id,'worker_id':identity['worker_id'],
            'stage':'feedback','execution_type':'ide','test_only':True,'content_id':task['content_id'],
            'policy_snapshot':task['policy_snapshot'],'output_protocol':'content_only_v1',
            'assigned_rule_ids':task.get('assigned_rule_ids',[]),
            'input_manifest':f'inbox/{review_id}/input-manifest.json','ai_output':ai_output,
            'required_outputs':[f'work/{review_id}/feedback/review.json'],
            'notification':{'enabled':True,'authorized_by':'explicit_test_review_handoff'}})
        (target/'START.md').write_text(f'''# 문장·문단 편집 품질 리뷰

원시인 모드: 중간 해설·전후 기록·문제 없는 블록 설명 없이 판단과 문제만 반환한다.
inbox/{review_id}/review-input.json과 style-guide.md만 읽는다.
입력은 시스템이 전체 순서대로 묶었다. before가 있는 블록만 변경됐으며 나머지는 edited가 원문과 같다.
기계적 전후 비교·해시·Claim 검증·기록은 시스템이 처리한다. 의미 보존과 문단·어투·줄바꿈 품질만 판단한다.
{ai_output}에 {{"passed": true 또는 false, "issues": [{{"block_id": "문제가 있는 실제 ID", "reason": "문제", "requested_change": "수정 요청"}}]}} 하나만 저장한다.
문제가 없는 블록의 설명, 로그, 변경표, 원문/수정문 재출력, 검증 코드, 제출 보고서는 작성하지 않는다.
''',encoding='utf-8')
        return review_id
    files = []
    # Do not pass writer changes or self-evaluation to the independent reviewer.
    for source, name in [(writer/'inbox'/task_id/'original.md','original.md'),
                         (writer/'inbox'/task_id/'GUIDE.md','GUIDE.md'),
                         (local(writer,config['edited_path']),'edited.md')]:
        destination = target / name
        shutil.copyfile(source,destination)
        files.append({'path':destination.relative_to(reviewer).as_posix(),
                      'sha256':hashlib.sha256(destination.read_bytes()).hexdigest()})
    for name in config.get('extra_inputs', []):
        source=local(writer, f'inbox/{task_id}/{name}')
        destination=local(reviewer, f'inbox/{review_id}/{name}')
        shutil.copyfile(source,destination)
        files.append({'path':destination.relative_to(reviewer).as_posix(),
                      'sha256':hashlib.sha256(destination.read_bytes()).hexdigest()})
    for name, relative in config.get('edited_artifacts', {}).items():
        source=local(writer,relative)
        destination=local(reviewer,f'inbox/{review_id}/{name}')
        shutil.copyfile(source,destination)
        files.append({'path':destination.relative_to(reviewer).as_posix(),
                      'sha256':hashlib.sha256(destination.read_bytes()).hexdigest()})
    save(target/'input-manifest.json',{'task_id':review_id,'files':files})
    out = f'work/{review_id}/feedback/review.json'
    save(target/'task.json',{'task_id':review_id,'worker_id':identity['worker_id'],
        'stage':'feedback','execution_type':'ide','test_only':True,'task_revision':1,
        'content_id':task['content_id'],'policy_snapshot':task['policy_snapshot'],
        'input_manifest':f'inbox/{review_id}/input-manifest.json',
        'notification':{'enabled':True,'authorized_by':'explicit_test_review_handoff'},
        'scope':config.get('scope','paragraph'),
        'objective':'독립 리뷰: input-manifest에 지정된 원문·편집본·근거·가이드만 대조한다. 전문 작업이면 모든 블록·Claim의 보존과 전체 순서·연결까지 검토한다. 제약·조건·수치의 귀속, 의미 보존, 문단 역할, 실제 줄바꿈, 수식어 결합을 검토한다. 사실 자체의 공식 인증이 아니라 제공 원문의 보존·편집 적합성 테스트다. 원고를 수정하지 않는다.',
        'required_outputs':[out],
        'output_contract':{'passed':'boolean','issues':[{'original_quote':'','edited_quote':'','reason':'','requested_change':''}],
                           'applied_rule_ids':['RULE-NAVER-PARAGRAPH-TEST-001']},
        'forbidden_actions':['call_api','read_other_worker','edit_live_draft','approve','publish']})
    (target/'START.md').write_text(f'''# 독립 문단 편집 리뷰

inbox/{review_id}/task.json과 input-manifest.json을 읽고 지정된 모든 파일을 비교한다.
추가 폴더 탐색·전체 정책 읽기는 불필요하다. 결과는 {out}에 JSON으로 저장한다.
테스트의 passed와 작업 수행 완료를 구분한다. 실패도 정상적으로 completed 보고에 포함한다.

python tools/worker_io.py submit --task {review_id} --status completed --summary "독립 문단 리뷰 완료" --artifact {out}
''',encoding='utf-8')
    return review_id
