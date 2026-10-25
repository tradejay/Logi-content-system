"""Prepare five self-contained IDE roots. This host-side script is not worker code."""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import uuid
from services.ide_worker_mode import MODE_TEXT

ROOT=Path(__file__).resolve().parents[1]
# Execution ownership is separate from the policy stages a worker needs to read.
OWNED_STAGES={
    '01_management':['routing_proposal'],
    '02_research_planning':['keyword','web_research','strategy','asset_need_plan'],
    '03_writing_editing':['write','naver_edit','rewrite'],
    '04_review':['feedback','official_interpret'],
    '05_assets':['asset_fulfillment']}
STAGE_OUTPUTS={
    'routing_proposal':['routing-proposal.json'],
    'keyword':['topics.json'], 'web_research':['sources.json'],
    'strategy':['strategy.json'], 'asset_need_plan':['asset-plan.json'],
    'write':['draft.md','writer-metadata.json','claim-map.json'],
    'naver_edit':['result.json'],
    'rewrite':['revised-blocks.json','feedback-resolutions.json'],
    'feedback':['feedback.json'], 'official_interpret':['official-decision-proposal.json'],
    'asset_fulfillment':['asset-candidates.json']}
ROLES={
    '01_management':('BLOG-MANAGEMENT','운영 관리',['strategy','write','feedback','official'],
        '시스템이 제공한 상태 요약을 바탕으로 배정·다음 단계·필요 입력을 판단한다. 로그나 상태 기록을 작성·재정리하지 않는다.'),
    '02_research_planning':('BLOG-RESEARCH-PLANNING','자료·기획',['strategy'],
        '키워드·주제·독자 질문과 글 기획, 제공된 공식 근거와 AVIXA/PSNI 참조 정리. 새 근거는 출처·조건을 붙여 후보로 제출한다.'),
    '03_writing_editing':('BLOG-WRITING-EDITING','집필·편집',['write'],
        '블록별 집필, 문단 구성·어투·줄바꿈 편집, 지정 피드백 수정. Claim·Fact 연결·제품 조건·이미지 자리를 보존한다.'),
    '04_review':('BLOG-REVIEW','독립 검토',['feedback','official'],
        '원문·편집본·Claim·Fact·출처를 대조하여 위치와 근거가 있는 피드백을 제출한다. 수신 확인과 의미 준수 판정을 구분한다.'),
    '05_assets':('BLOG-ASSETS','이미지·Asset',['assets','image_generation','write'],
        'AssetNeed에 맞는 공식 자산 연결 또는 제작 도구로 이미지 후보 생성, 캡션·출처·문단 적합도 점검. 생성 완료를 승인으로 선언하지 않는다.')}

LOCAL_TOOL='''"""Local task reader and outbox reporter. No parent-project imports."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def inside(relative):
    value=Path(relative)
    if value.is_absolute() or value.drive or '..' in value.parts:raise ValueError('Use a path inside this worker root')
    path=(ROOT/value).resolve()
    if not path.is_relative_to(ROOT):raise ValueError('Path leaves worker root')
    return path
def submit(task,status,summary,artifacts):
    import re
    if not re.fullmatch(r'[A-Za-z0-9_-]+',task):raise ValueError('Invalid task ID')
    source=inside('inbox/'+task+'/task.json')
    data=json.loads(source.read_text(encoding='utf-8'))
    worker=json.loads(inside('worker.json').read_text(encoding='utf-8'))
    if data.get('worker_id')!=worker['worker_id'] or data.get('task_id')!=task:raise ValueError('Task belongs to a different worker or revision')
    if data.get('execution_type')!='ide':raise ValueError('This task is not assigned to an IDE executor')
    if data.get('stage') not in worker.get('owned_stages',[]):raise ValueError('Stage belongs to another worker')
    results=[]
    for relative in artifacts:
        path=inside(relative)
        if not path.is_file() or not path.is_relative_to(inside('work/'+task)):raise ValueError('Artifacts must be files in work/TASK-ID')
        raw=path.read_bytes();results.append({'path':path.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
    report={'task_id':task,'worker_id':worker['worker_id'],
        'status':status,'summary':summary,'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'content_id':data.get('content_id'),'stage':data['stage'],'execution_type':'ide',
        'artifacts':results,'publication_approved':False}
    target=inside('outbox/'+task+'/report.json');target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():raise ValueError('Report already exists; use a new task revision instead of overwriting')
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report
if __name__=='__main__':
    parser=argparse.ArgumentParser();commands=parser.add_subparsers(dest='command',required=True)
    show=commands.add_parser('show');show.add_argument('path')
    report=commands.add_parser('submit');report.add_argument('--task',required=True);report.add_argument('--status',choices=['completed','needs_input','blocked'],required=True);report.add_argument('--summary',default='System artifact submission');report.add_argument('--artifact',action='append',default=[])
    args=parser.parse_args()
    if args.command=='show':print(inside(args.path).read_text(encoding='utf-8'))
    else:print(json.dumps(submit(args.task,args.status,args.summary,args.artifact),ensure_ascii=False))
'''


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def prepare(root=ROOT,cid='CNT-LIVE-20261008-VERIFY-001'):
    root=Path(root).resolve()
    if not re.fullmatch(r'[A-Za-z0-9_-]+',cid):raise ValueError('Invalid content ID')
    destination=root/'worker-workspaces';destination.mkdir(exist_ok=True)
    state=json.loads((root/'content-system/00_system/policy/workspace.json').read_text(encoding='utf-8-sig'))
    snapshot=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:6]
    entries=[]
    shared_files=[root/'content-system/02_writer_ai/drafts'/f'{cid}.draft.md',
        root/'content-system/01_keyword_ai/briefs'/f'{cid}.brief.yaml',
        root/'content-system/working'/cid/'pipeline-latest.json']
    result=json.loads(shared_files[-1].read_text(encoding='utf-8')) if shared_files[-1].is_file() else {}
    for ref in result.get('input_refs',[]):
        relative=ref.get('path','').replace('\\','/')
        if not relative.startswith('content-system/03_sources/') or ref.get('virtual'):continue
        source=(root/relative).resolve()
        if source.is_relative_to(root/'content-system/03_sources') and source.is_file():shared_files.append(source)
    if result.get('run_directory'):
        run=Path(result['run_directory'])
        if not run.is_absolute():run=root/run
        if run.resolve().is_relative_to(root):
            shared_files.extend(run/p for p in ['fact-bundle.json','strategy.json','asset-plan.json','asset-bindings.json','web-planning-discovery.json','sources.json'])
            shared_files.extend((run/'revisions').glob('*.claim-map.json'))
            shared_files.extend((run/'revisions').glob('*.writer-metadata.json'))
    for folder,(worker_id,label,stages,duty) in ROLES.items():
        worker=destination/folder;worker.mkdir(exist_ok=True)
        for sub in ['inbox','work','outbox','logs','tools','resources/snapshots']:(worker/sub).mkdir(parents=True,exist_ok=True)
        if not (worker/'worker.json').exists():write(worker/'worker.json',{'worker_id':worker_id,'role':folder,'model':'gemini-3.8-flash','conversation_id':None,'filesystem_scope':'own_root_only'})
        config=json.loads((worker/'worker.json').read_text(encoding='utf-8'))
        config['owned_stages']=OWNED_STAGES[folder]
        write(worker/'worker.json',config)
        write(worker/'responsibility.json',{'owned_stages':OWNED_STAGES[folder],
            'policy_read_stages':stages,'execution_type':'ide',
            'state_authority':'host_controller','outputs_by_stage':{s:STAGE_OUTPUTS[s] for s in OWNED_STAGES[folder]}})
        for stage in OWNED_STAGES[folder]:
            write(worker/'modules'/stage/'README.md',f'''# {stage}

담당 워커: {worker_id}. 이 단계만 맡으며 다른 단계는 수행하지 않는다.
입력은 inbox/TASK-ID/task.json과 지정된 로컬 스냅샷에서 읽는다.
산출물은 work/TASK-ID/{stage}/ 아래에 저장한다.
기대 산출물: {', '.join(STAGE_OUTPUTS[stage])}.
API 대신 IDE에 배정된 작업만 수행한다. 동일 단계의 API를 다시 호출하지 않는다.
계약과 자료가 부족하면 needs_input으로 보고한다. 운영 상태 변경과 승인은 하지 않는다.
''')
        write(worker/'tools/worker_io.py',LOCAL_TOOL)
        atoms=[deepcopy(a) for a in state['atoms'] if a.get('enabled',True) and a.get('lifecycle')!='retired' and not a.get('retired_by') and a.get('kind')!='reference' and set(a.get('stages',[])).intersection(stages)]
        if folder=='05_assets':atoms=[a for a in atoms if any(t in (a.get('source') or {}).get('path','') for t in ['images','asset','brand','contracts','completion'])]
        pack=worker/'resources/snapshots'/snapshot;manifest=[]
        paths={a.get('source',{}).get('path') for a in atoms};paths.discard(None)
        paths.update(['content-system/02_writer_ai/authoring/README.md','content-system/05_publish/naver-editorial-layout.md','experiments/naver-paragraph/GUIDE.md'])
        for relative in sorted(paths):
            source=(root/relative).resolve()
            if not source.is_relative_to(root) or not source.is_file():continue
            target=pack/'guides'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
            local=target.relative_to(worker).as_posix()
            manifest.append({'path':local,'origin':relative,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
        mapping={m['origin']:m['path'] for m in manifest}
        for atom in atoms:
            origin=atom.get('source',{}).get('path')
            if origin in mapping:atom['source']['origin_path']=origin;atom['source']['path']=mapping[origin]
        write(pack/'policy-atoms.json',{'revision':state['revision'],'stages':stages,'atoms':atoms})
        for source in shared_files:
            if not source.is_file():continue
            target=pack/'article'/source.name
            if target.exists():target=pack/'article'/source.parent.name/source.name
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
            manifest.append({'path':target.relative_to(worker).as_posix(),'origin':source.relative_to(root).as_posix(),'sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
        if folder=='05_assets':
            for relative in [f'content-system/assets/{cid}/assets.yaml','content-system/queue/asset.queue.yaml']:
                source=root/relative
                if source.is_file():
                    target=pack/'assets'/source.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
                    manifest.append({'path':target.relative_to(worker).as_posix(),'origin':relative,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
            # Include only this article's registered local image files, never credentials.
            import yaml
            registry=root/'content-system/assets'/cid/'assets.yaml'
            assets=(yaml.safe_load(registry.read_text(encoding='utf-8')) or {}).get('assets',[]) if registry.is_file() else []
            for asset in assets:
                if not asset.get('local_path'):continue
                source=(root/asset['local_path']).resolve()
                if source.is_relative_to(root) and source.is_file():
                    target=pack/'assets/images'/source.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
                    manifest.append({'path':target.relative_to(worker).as_posix(),'origin':source.relative_to(root).as_posix(),'asset_id':asset.get('asset_id'),'sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
            local_assets={m.get('asset_id'):m['path'] for m in manifest if m.get('asset_id')}
            write(pack/'assets/catalog.json',{'assets':[{'asset_id':a.get('asset_id'),'need_id':a.get('need_id'),
                'caption':a.get('caption') or a.get('alt'),'review_status':a.get('review_status'),
                'source_ref':a.get('source_ref'),'local_file':local_assets.get(a.get('asset_id')),
                'url':a.get('public_url') or a.get('url')} for a in assets]})
        write(pack/'manifest.json',{'snapshot_id':snapshot,'content_id':cid,'policy_revision':state['revision'],
             'policy_release':result.get('guide_release_id'),'files':manifest})
        write(worker/'resources/latest.json',{'snapshot_id':snapshot,'manifest':(pack/'manifest.json').relative_to(worker).as_posix(),'policies':(pack/'policy-atoms.json').relative_to(worker).as_posix()})
        write(worker/'WORKER-MODE.md',MODE_TEXT)
        write(worker/'AGENTS.md',f'''# {worker_id} — {label}

모델: Gemini 3.8 Flash. 역할: {duty}
기본은 WORKER-MODE.md의 원시인 모드다. 불필요한 탐색·설명·기록 작성을 생략한다.

## 작업 시작
0. `responsibility.json`의 담당 단계와 `modules/단계/README.md`를 확인한다. 정책 열람 범위는 실행 책임이 아니다.
1. `worker.json`, `resources/latest.json`을 읽고 그 안의 로컬 manifest와 필요한 정책 원자만 찾는다.
2. `inbox/TASK-ID/task.json`의 범위·입력 버전·요구 산출물을 확인한다. 작업이 없으면 대기한다.
3. content_only_v1 작업은 지정 결과 파일 하나만 저장한다. 시스템이 조립·비교·기록·outbox 보고서를 만든다. 다른 기존 작업의 제출 도구도 기록을 자동 생성하며 AI가 보고서를 직접 작성하지 않는다.

## 파일 접근 경계
이 폴더가 유일한 루트다. 부모 폴더, 다른 워커 폴더, 외부 사용자 설정을 열거나 수정하지 않는다.
`..`, 루트 밖 절대 경로, 링크/정션을 이용한 우회, 부모 프로젝트 import를 사용하지 않는다.
복사된 문서의 원본 경로와 URL은 출처 표시다. 파일을 읽을 때는 manifest의 `path`만 사용한다.
manifest에 없는 자료가 필요하면 `needs_input`으로 자료 ID와 목적을 요청한다.
API 키·인증 파일·환경 비밀을 찾거나 복사하지 않는다. 외부 API/도구 호출은 해당 작업에 명시된 권한에 한한다.

## 상태와 증거
입력 스냅샷을 직접 고치지 않는다. Fact·정책 변경은 변경 제안으로 제출한다.
작업에 지정된 정책 release와 규칙 ID를 우선한다. 실험 가이드는 테스트 지시가 있을 때만 적용한다.
작업 ID·규칙 ID/버전·입력/출력 해시·변경 비교·수행 시간·보고서는 시스템이 기록한다. AI는 이를 재작성하지 않는다.
content_only_v1 작업은 START.md에 지정된 입력만 읽고 편집 내용 또는 리뷰 판단 파일 하나만 저장한다.
이 작업에서는 작업 메타데이터·manifest를 읽어 기록을 만들거나 worker_io 제출 명령·검증 코드를 작성하지 않는다.
도구 로그 없이 실행·검증·승인을 완료했다고 주장하지 않는다.
작업 완료 보고는 글 발행·이미지 승인·Fact 확정·정책 릴리스를 뜻하지 않는다.
관리자 최종 승인과 운영 반영은 상위 운영 코드가 처리한다.
실제 초안과 테스트 원고를 구분하며 테스트 결과를 운영 원고에 덮어쓰지 않는다.

## 중복 작업 방지
task.stage가 owned_stages에 있고 execution_type이 ide인 작업만 수행한다.
관리 워커는 배정·재개 제안만 하며 원고 작성이나 검토를 대신하지 않는다.
자료·기획 워커는 AssetNeed의 목적·위치를 정한다. 이미지 워커는 그 Need를 충족하는 후보만 제출한다.
집필 워커는 승인된 기획을 사용하며 독립 검토를 대체하지 않는다.
독립 검토 워커의 official_interpret는 전달된 로지텍 응답의 해석이다. 로지텍 공식 호출 자체를 대신하지 않는다.
API 호출·토큰 측정·규칙 수신 로그 검증·렌더링·저장·대기열·Taiga 동기화는 운영 코드 책임이다.
''')
        write(worker/'START.md',f'''# {label} 워커 시작

IDE에서 이 폴더 하나만 워크스페이스로 연다. 먼저 `AGENTS.md`를 읽는다.
등록된 작업은 `inbox`에서 확인하고, 없으면 작업 요청을 기다린다.
현재 제공 자료는 {cid}의 읽기 전용 스냅샷이며 작업 지시 자체가 아니다.

```text
python tools/worker_io.py show resources/latest.json
python tools/worker_io.py show inbox/TASK-ID/task.json
python tools/worker_io.py submit --task TASK-ID --status completed --summary "수행 내용" --artifact work/TASK-ID/result.md
```

자신의 conversation ID를 알게 되면 `worker.json`의 conversation_id에 기록한다.
도구는 표준 Python 라이브러리만 사용하며 다른 프로젝트 파일을 import하지 않는다.
''')
        write(worker/'task-template.json',{'task_id':'TASK-ID','worker_id':worker_id,'content_id':cid,
            'stage':OWNED_STAGES[folder][0],'execution_type':'ide',
            'test_only':True,'objective':'','input_manifest':'resources/latest.json','required_outputs':[],
            'allowed_actions':['read_local_inputs','write_local_artifacts','submit_outbox_report'],
            'forbidden_actions':['read_parent_or_other_worker','publish','approve_assets','edit_live_facts_or_policies']})
        write(worker/'report-template.json',{'generated_by':'system','note':'AI는 이 보고서를 작성하지 않는다. 시스템이 작업 정보·해시·변경 내역·완료 기록을 생성한다.'})
        entries.append({'worker_id':worker_id,'role':label,'folder':folder,'root':str(worker),'snapshot_id':snapshot,'policies':len(atoms),'owned_stages':OWNED_STAGES[folder]})
    control=root/'worker-control'
    write(control/'stage-ownership.json',{'schema_version':1,'worker_stages':{
        s:{'worker_id':ROLES[f][0],'folder':f,'execution_options':['ide'],
           'required_assignment_key':['run_id','stage','task_revision'],
           'outputs':STAGE_OUTPUTS[s]} for f,ss in OWNED_STAGES.items() for s in ss},
        'host_only':['api_transport','logitech_official_call','rule_receipt_validation','token_audit',
                     'render','revision_store','queue_sync','taiga_sync','approval_gate'],
        'admin_only':['final_approval','publication'],
        'assignment_policy':'IDE only while Gemini API is quarantined. Choose exactly one executor per run/stage/task_revision.'})
    write(control/'README.md','''# 운영 코드 전용 영역

이 폴더는 AI 워커의 IDE 루트로 등록하지 않는다.
stage-ownership.json은 단계별 담당과 API/IDE 단일 실행 원칙을 정의한다.
관리 AI는 라우팅 제안만 제출하며 실제 배정·실행·상태 저장은 운영 코드가 수행한다.
워커 간 전달은 운영 코드가 outbox를 수집하여 다음 워커 inbox에 복사하는 방식이다.
실패 재시도도 새 task_revision으로 배정하고 같은 단계의 이중 실행을 금지한다.
Antigravity 알림·결과 수집은 BRIDGE.md의 실행 방법으로 연결한다.
임의 작업 생성·운영 단계 자동 배정·최종 승인은 별도이며 현재 연결기가 수행하지 않는다.
''')
    write(destination/'registry.json',{'workers':entries,'model':'gemini-3.8-flash','controller_location':'outside_worker_roots','auto_sync_enabled':False})
    write(destination/'README.md','''# 독립 워커 실행 폴더

각 워커는 registry.json에 있는 자기 root 폴더만 IDE 워크스페이스로 등록한다.
worker-workspaces 전체나 프로젝트 부모를 워커에게 루트로 제공하지 않는다.

각 루트는 AGENTS.md, START.md, worker.json, inbox/work/outbox/logs/tools/resources로 구성한다.
modules/단계는 담당 단계별 지침이다. responsibility.json은 실행 책임을 정의한다.
작업 파일은 work/TASK-ID/단계에 보관한다. 입력·출력 큐는 워커당 하나만 유지한다.
운영 코드 전용 영역은 프로젝트의 worker-control이며 워커 루트 밖에 둔다.
단계별로 API 또는 IDE 하나만 선택한다. 정책 문서를 여러 역할이 읽는 것은 실행 중복이 아니다.
공용 자료는 resources/snapshots에 역할별 복사본으로 전달한다. 심볼릭 링크/정션을 만들지 않는다.
자료 갱신은 상위 운영 코드가 `python -m scripts.prepare_worker_workspaces`로 새 스냅샷을 만든다.
기존 작업 폴더와 보고서는 보존한다. 명시적으로 허용된 inbox 작업은 Antigravity 알림·수집기로 실행할 수 있다.
연결 방법은 프로젝트 worker-control/BRIDGE.md에 있다. 운영 반영과 승인은 자동 실행하지 않는다.

운영 코드가 inbox에 필요한 작업 패키지를 넣고 워커는 outbox에 산출물·보고서를 제출한다.
수집/적용은 이 디렉터리 밖의 운영 코드가 수행해야 한다. 워커는 다른 폴더에 직접 전달하지 않는다.
폴더 접근의 실제 강제는 IDE/실행 환경의 루트 권한 설정으로 적용한다.
AGENTS 지침과 로컬 도구의 경로 검사만으로 OS의 다른 도구 접근까지 차단되지는 않는다.
''')
    return entries


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--content',default='CNT-LIVE-20261008-VERIFY-001');args=parser.parse_args()
    print(json.dumps(prepare(cid=args.content),ensure_ascii=False,indent=2))
