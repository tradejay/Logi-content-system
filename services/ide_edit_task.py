"""Prepare minimal AI inputs and keep all bookkeeping on the host."""
import hashlib
from datetime import datetime,timezone
from .ide_worker_bridge import ROOT,load,save


def prepare(root=ROOT,cid='CNT-LIVE-20261008-VERIFY-001',base_task_id=None,feedback=None,notify=True):
    worker=root/'worker-workspaces/03_writing_editing'
    latest=load(root/'content-system/working'/cid/'pipeline-latest.json')
    run=root/latest['run_directory']
    source=root/'content-system/02_writer_ai/drafts'/f'{cid}.draft.md'
    original=source.read_text(encoding='utf-8-sig')
    blocks=load(run/'revisions/r1.writer-metadata.json')['blocks']
    claims=load(run/'revisions/r1.claim-map.json')['claims']
    baseline_source=source
    if base_task_id:
        from .ide_worker_bridge import local,verify_report
        base=local(worker,'work/'+base_task_id+'/naver_edit')
        verify_report(worker,base_task_id,load(local(worker,'inbox/'+base_task_id+'/task.json')))
        baseline_source=base/'edited.md'
        original=baseline_source.read_text(encoding='utf-8-sig')
        blocks=load(base/'edited-blocks.json')['blocks']
        claims=load(base/'claim-map.json')['claims']
    if '\n\n'.join(b['markdown'].strip() for b in blocks).strip()!=original.strip():raise ValueError('Stale blocks')
    tid='TEST-NAVER-SLIM-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    folder=worker/'inbox'/tid;folder.mkdir(parents=True)
    (folder/'original.md').write_bytes(baseline_source.read_bytes())
    save(folder/'original-blocks.json',{'blocks':blocks});save(folder/'original-claims.json',{'claims':claims})
    by_id={c['id']:c['text'] for c in claims}
    save(folder/'editing-input.json',{'blocks':[{'id':b['id'],'markdown':b['markdown'],
        'protected_phrases':[by_id[c] for c in b.get('claim_ids',[])]} for b in blocks]})
    (folder/'style-guide.md').write_text('''# 네이버 블로그 편집 기준

전문 전체를 살펴 친절한 경어체·문단·실제 줄바꿈을 개선한다. 긴 사양 나열·정의·체크리스트도 대상이다.
긴 복문은 의미 경계(제약→대안, 조건→조치, 설명→판단)에서 단일 개행한다. 다른 판단·화제는 빈 줄로 분리한다.
글자 수·쉼표 위치만으로 기계적으로 자르지 않는다. 수식어와 대상·제품명·숫자/단위·링크·강조 구문은 붙인다.
문단 역할에 따라 문장·문단 순서를 같은 블록 안에서 조정할 수 있다. 블록 ID·순서는 유지한다.
이미 분명한 대상의 긴 재지칭·불필요한 수식어는 줄이되 모호하게 생략하지 않는다.
제약·부정·조건·예외·수치 귀속·제품명·URL·이미지 자리를 보존하고 새 사실·추천을 추가하지 않는다.
protected_phrases는 표현을 유지하되 의미 단위의 공백/개행만 조정할 수 있다.
체크리스트의 제목과 설명은 한 항목으로 유지하고 긴 설명 안의 의미 단위에서 줄을 나눈다.
제목·소제목·강조는 Markdown으로 표현한다. 글자 크기·여백·HTML 변환은 시스템이 처리한다.
원고의 정보 보존만으로 편집 품질을 통과시키지 않는다. 케이블 문단 한 곳만 수정하는 것은 전문 개선에 부족하다.
''',encoding='utf-8')
    if feedback:
        with (folder/'style-guide.md').open('a',encoding='utf-8') as stream:
            stream.write('\n## 이번 수정 요청\n\n'+feedback+'\n')
    save(folder/'input-manifest.json',{'files':[{'path':p.relative_to(worker).as_posix(),
        'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in folder.iterdir()]})
    out=f'work/{tid}/naver_edit'
    save(folder/'task.json',{'task_id':tid,'worker_id':'BLOG-WRITING-EDITING','content_id':cid,
        'stage':'naver_edit','execution_type':'ide','test_only':True,'scope':'full_article',
        'policy_snapshot':load(worker/'resources/latest.json')['snapshot_id'],
        'assigned_rule_ids':['RULE-NAVER-PARAGRAPH-TEST-001','RULE-NAVER-EDITORIAL-V1'],
        'output_protocol':'content_only_v1','ai_output':f'{out}/result.json',
        'system_inputs':{'blocks':f'inbox/{tid}/original-blocks.json','claims':f'inbox/{tid}/original-claims.json'},
        'input_manifest':f'inbox/{tid}/input-manifest.json',
        'required_outputs':[f'{out}/edited.md',f'{out}/edited-blocks.json',f'{out}/claim-map.json',f'{out}/changes.json'],
        'notification':{'enabled':notify,'authorized_by':'user_authorized_editing_task'},
        'test_review_handoff':{'enabled':True,'worker_folder':'04_review','scope':'full_article',
            'edited_artifacts':{'edited-blocks.json':f'{out}/edited-blocks.json'}}})
    (folder/'START.md').write_text(f'''# 원고 전문 편집

원시인 모드: 계획·중간 설명·변경 이유·결과 부연설명 없이 산출물만 작성한다.
inbox/{tid}/editing-input.json과 style-guide.md만 읽는다.
원고 전문을 기준에 맞게 실제로 편집하고 {out}/result.json에 {{"blocks":[{{"id":"원본 ID","markdown":"편집된 본문"}}]}} 하나만 저장한다.
전체 블록을 반환한다. 로그·검토 설명·변경표·전후 복사·Claim 관리·전문 조립·해시·보고서·검증 스크립트는 작성하지 않는다.
시스템이 기록과 검증 및 독립 리뷰 전달을 수행한다. 다른 입력·원본 메타데이터·정책 전체를 추가 탐색하지 않는다.
실제 원고·승인·본 파이프라인을 변경하지 않는다.
''',encoding='utf-8')
    save(root/'worker-control/current-full-article-test.json',{'task_id':tid,'worker_folder':'03_writing_editing',
        'content_id':cid,'source_draft_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'chars':len(original),'blocks':len(blocks),'claims':len(claims),'output_protocol':'content_only_v1',
        'previous_task_id':base_task_id})
    return tid
