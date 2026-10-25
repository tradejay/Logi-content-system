"""Apply the user's problem-first editorial baseline to 20 proposed articles."""
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'content-system/00_system/templates/articles'
catalog=json.loads((OUT/'catalog.json').read_text(encoding='utf-8'))
if all(t.get('version') == '1.2.0' for t in catalog['templates']) and (OUT/'article-plans.json').exists():
    raise SystemExit('Problem-first v1.2 plans already exist; preserve reviewed edits.')
common=json.loads((OUT/'common.json').read_text(encoding='utf-8'))
topics=json.loads((ROOT/'audit/2026-10-06-template-topic-candidates/candidates.json').read_text(encoding='utf-8'))['candidates']
bindings=json.loads((OUT/'topic-bindings.json').read_text(encoding='utf-8'))
backup=OUT/'review-baseline-v1.1'
backup.mkdir(exist_ok=True)
for name in ('catalog.json','common.json','topic-bindings.json','README.md'):
    if not (backup/name).exists(): (backup/name).write_bytes((OUT/name).read_bytes())

# Editorial plans only: no hardware claim is asserted as verified by these headings.
plans=[
('회의실 TV에 노트북을 연결했는데 화면·소리가 안 나올 때', 'TV 화면은 켜졌지만 회의 화면이나 소리가 원하는 장치로 나오지 않는 상황',
 ['화면과 소리 중 무엇이 나오지 않나요?','영상 연결과 소리 출력은 어디에서 정해질까요?','입력 선택·화면 모드·오디오 출력을 차례로 확인하기','현재 장비와 케이블에서 확인할 연결 조건','조치 후 화면·소리 점검과 미해결 기록']),
('화상회의를 켜면 삐 소리·울림이 생길 때 무엇부터 확인할까?', '회의를 시작하자 삐 소리 또는 되돌아오는 목소리 때문에 대화가 어려운 상황',
 ['삐 소리와 되돌아오는 목소리는 같은 문제일까요?','여러 마이크·스피커와 소리 경로가 만드는 가능 원인','중복 접속·출력 장치·배치를 공식 절차로 점검하기','지금 구성에서 조정할 것과 장비 검토가 필요한 조건','다시 통화해 확인할 항목과 지원 요청 기록']),
('화상회의 장비 견적, 꼭 필요한 항목과 추가 옵션은 어떻게 나눌까?', '견적서에 장비와 부속·서비스가 많지만 왜 필요한지 판단하기 어려운 상황',
 ['우리 회의실에서 먼저 해결할 불편은 무엇인가요?','공간·기존 장비·회의 방식이 견적을 바꾸는 이유','영상·음성·조작 역할로 필수 항목 나누기','구매·재사용·조건부 추가로 견적 구성하기','견적 상담 전에 준비할 환경·지원 조건 체크리스트']),
('좁은 소회의실에서 양옆 사람이 화면에 잘릴 때 장비 선택 기준', '테이블 양 끝 참석자가 화면에서 잘려 자리나 자세를 바꾸는 가상 상황',
 ['카메라 가까이에 앉으면 왜 화면에서 잘릴 수 있을까요?','거리·좌석 배치·화각을 함께 확인해야 하는 이유','전체 화면과 자동 프레이밍 기능 구분하기','공식 사양에 맞는 제품과 기존 장비 조합 검토','설치 위치·지원 모드·도입 전 확인 조건']),
('회의 끝자리 목소리가 잘 안 들릴 때, 스피커폰과 확장 마이크 선택', '화면은 보이지만 끝자리 발언을 상대방이 되묻는 상황',
 ['어느 자리·어느 방향의 목소리가 잘 안 들리나요?','거리·배치·실내 소음과 수음 방식의 관계','스피커폰과 확장 마이크를 같은 사용 조건에서 비교','지원 장비와 설치·배선을 포함한 구성 선택','실제 통화로 확인할 위치별 음성 체크리스트']),
('소회의실에서 얼굴·목소리가 잘 전달되지 않을 때 MeetUp 2 검토 기준', '좁은 공간에서 화면 구도와 음성 전달을 함께 개선하려는 상황',
 ['우리 소회의실에서 화면과 소리 중 무엇이 불편한가요?','좌석·설치 위치·기존 장비부터 살펴보기','MeetUp 2의 확인된 영상·음성 기능과 사용 조건','기존 TV·노트북과 연결·사용하는 기본 구성','실제 사진·동작 자료로 확인할 도입 체크리스트']),
('회의실 참석자를 화면·음성에 담기 어려울 때 Rally Bar 검토 기준', '회의실 공간과 좌석 배치 때문에 영상·음성 전달이 만족스럽지 않은 상황',
 ['어떤 좌석에서 얼굴이나 목소리가 놓치기 쉬운가요?','공간과 회의 운영 방식이 장비 선택에 영향을 주는 이유','Rally Bar의 공식 확인된 기능과 역할','기존 장비 재사용과 기본 회의 사용 모습','지원 조건과 필요한 경우의 부속 검토']),
('회의 시작 때마다 조작이 번거롭다면, Tap·Tap IP를 어떻게 검토할까?', '회의를 시작할 때 장치 선택과 조작을 반복하는 상황',
 ['회의 시작 과정에서 어떤 조작이 반복되나요?','회의 실행 장치와 조작 장치의 역할 구분','Tap과 Tap IP의 확인된 연결·지원 방식 비교','선택한 플랫폼·룸 구성에서 사용하는 모습','설치·네트워크·지원 조건 체크리스트']),
('회의실 끝자리 수음이 아쉬울 때 Rally Mic Pod 확장 검토', '기본 장비로 특정 자리의 목소리를 전달하기 어려운 상황',
 ['수음이 부족한 위치와 현재 마이크 배치는 어디인가요?','마이크 추가 전에 배치·소음·음성 설정 점검','Rally Mic Pod의 역할과 확인된 호환 조건','공식 규격에 따른 연결·음소거·설치 구성','추가가 필요한 조건과 실제 통화 확인 항목']),
('Rally Bar와 Mini, 우리 회의실에서는 무엇을 기준으로 고를까?', '제품 이름과 사양표만으로 어떤 모델이 환경에 맞는지 판단하기 어려운 상황',
 ['현재 회의실에서 해결할 불편과 공통 전제','두 제품의 기본 역할과 비교할 기준 정하기','공식 사양으로 영상·음성·확장·지원 조건 비교','같은 운영 환경에서 기본 구성과 사용 모습 비교','규모만으로 단정하지 않는 선택 체크리스트']),
('MeetUp 2와 Rally Bar Mini, 소회의실 장비 선택이 고민될 때', '소회의실 후보 장비 사이에서 필요한 기능과 구성 차이를 판단하려는 상황',
 ['우리 소회의실에서 우선 해결할 문제는 무엇인가요?','비교 전에 좌석·기존 장비·운영 방식 고정하기','확인된 기능·연결·지원 조건을 같은 기준으로 비교','구매·재사용 장비와 사용 흐름 비교','우리 환경에 필요한 차이와 상담 전 확인 항목']),
('노트북을 연결할까, 전용 회의실로 만들까? BYOD와 룸 시스템 선택', '개인 노트북 연결과 회의실 전용 운영 사이에서 회의 시작 방식을 선택하는 상황',
 ['회의 준비·시작 과정의 불편은 무엇인가요?','회의 앱이 실행되는 위치와 조작 장치의 차이','BYOD와 전용 룸 방식을 같은 업무 조건에서 비교','기존 장비·계정·플랫폼을 포함한 기본 구성','운영·관리·지원 조건에 따른 선택 체크리스트']),
('중형 회의실에서 끝자리 얼굴·목소리가 놓칠 때 구성 점검', '테이블 길이와 좌석 배치에 따라 영상·음성 전달이 달라지는 상황',
 ['화면 사각과 수음 문제를 먼저 나누어 보기','카메라·마이크·조작 장치의 역할과 배치 조건','불편에 답하는 기능과 필요한 근거 확인','기존 장비를 포함한 기본 구성·연결도·사용 모습','남는 문제에 따른 부속과 설치 전 체크리스트']),
('회의실에서 Zoom 회의 시작이 번거롭다면, 장비 구성부터 점검하기', 'Zoom을 어떤 장치에서 실행하고 어떻게 조작할지 정리되지 않은 상황',
 ['노트북 회의와 전용 회의실 운영 중 무엇이 필요한가요?','Zoom 실행 위치·계정·조작 장치의 역할','선택한 운영 방식에 맞는 공식 지원 조건 확인','기본 구성과 공식 설치·설정·정상 확인 절차','라이선스·인증·버전·네트워크 점검 항목']),
('회의실 마이크 케이블이 복잡할 때, 설치 위치와 배선 정리 기준', '테이블의 케이블 노출과 마이크 위치 때문에 사용·관리가 불편한 상황',
 ['케이블 정리와 수음 위치 중 무엇부터 해결할까요?','마이크 위치·지원 케이블·가구 조건의 관계','공식 설치 방법과 사용 가능한 부속 확인','고정된 장비 구성에서 설치·배선·정상 확인','타공·유지보수·사용 권한과 설치 전 확인 항목']),
('화면에서 누가 말하는지 찾기 어렵다면, 화자 추적 기능 이해하기', '전체 회의실 화면에서 발언자를 구분하기 어려운 가상 상황',
 ['전체 참석자가 보여도 발언자는 잘 보이지 않을 수 있어요','화자 추적·프레이밍의 기본 의미와 역할','공식 확인된 동작과 화면 변화 설명','관련 모드의 차이와 실제 동작 자료 비교','지원 제품·모드·조건과 선택 체크리스트']),
('회의실에서 목소리가 묻힐 때, 빔포밍 마이크는 무엇을 할까?', '키보드·팬 등 주변 소음과 발언자 목소리를 구분해 이해하려는 상황',
 ['목소리가 작거나 소음에 묻힐 때 살펴볼 환경','빔포밍·노이즈 억제·에코 처리 역할 구분','공식 확인된 입력·동작·범위까지만 원리 설명','제품별 지원 기능과 배치·사용 모습','모든 소리를 제거한다고 오해하지 않는 확인 기준']),
('참석자 화면을 조정해야 할 때, PTZ와 ePTZ는 어떻게 다를까?', '화면 이동·확대 방식에 따라 장비 선택과 사용이 달라지는 상황',
 ['어떤 장면을 이동·확대해 보여주려 하나요?','PTZ와 ePTZ의 기본 의미를 먼저 구분','공식 근거가 있는 동작·화질·사용 조건 비교','실제 제품·모드의 지원 방식과 사용 모습','속도·화질 우열을 단정하지 않는 선택 기준']),
('화상회의 카메라가 안 잡히거나 검은 화면일 때 점검 순서', '회의 앱에서 카메라를 선택할 수 없거나 화면이 검게 나오는 상황',
 ['장치 미인식과 검은 화면 증상 구분','연결·앱 선택·권한·다른 앱 사용 여부의 관계','제품·OS·앱 버전에 맞는 공식 점검·조치 순서','필요한 경우 케이블·연결도·지원 조건 확인','정상 영상 확인과 미해결 지원 요청 기록']),
('화상회의 목소리가 끊겨 들릴 때, 네트워크와 음성 설정 점검', '내 목소리 또는 상대방 목소리가 일부 잘려 대화가 어려운 상황',
 ['내 송신과 상대방 수신 중 어느 쪽에서 끊기나요?','네트워크·입출력·앱 처리의 가능 원인을 구분','환경 기록을 남기며 공식 점검 절차로 확인하기','선택 장치·버전·연결 조건과 조치 후 통화 확인','원인 미확정 시 준비할 로그와 지원 요청 항목']),
]
assert len(plans)==len(topics)==20
common.update(version='1.2.0',status='problem_first_design',editorial_baseline={
    'source':'user-provided blog example and subsequent instruction',
    'principle':'문제 → 이유 → 해결 기능/절차 → 제품·구성 적용 → 도입/조치 판단',
    'title_rule':'문제·선택 고민과 해결 방향을 드러내되 검증되지 않은 수치·효과를 약속하지 않음',
    'scope':'구조·말투·전개만 참조; 예시의 제품 수치·무상 대여·실증 주장은 재사용하지 않음'})
common['opening_sequence'][0]['content_task']='독자의 문제·선택 고민과 글의 해결 방향을 제목에 드러냄'
common['opening_sequence'][3]['content_task']='인사·승인된 기업 안내 다음에 구체적인 불편을 짧게 공감하고 주제를 예고'
common['opening_sequence'][-1]['content_task']='배너 다음에 공통 전제와 조건부 핵심 방향을 짧게 연결; 본문의 구체적인 문제 설명을 중복하지 않음'

from copy import deepcopy
for t in catalog['templates']:
    t.update(version='1.2.0',status='problem_first_design')
    body=t['body_sequence']
    problem=deepcopy(body[0])
    problem.update(element='body.explanation',label='질문별 핵심 설명',
        content_task='독자가 실제로 겪을 수 있는 문제 장면·선택 고민을 구체화하고 원하는 변화를 설명. 가상 장면은 실제 고객 사례로 표현하지 않음',
        required=True,include_when='always',placement='본문 첫 설명; 기능·제품 정의보다 앞',repeatable=False)
    body.insert(0,problem)
    if t['id']=='product-introduction':
        body[1]['content_task']='불편이 생기는 환경·원인 후보와 필요한 변화를 설명하고 제품 기본 의미를 해결 기능 소개에 통합'
    elif t['id']=='product-comparison':
        body[1]['content_task']='선택이 어려운 이유와 동일 기준을 정하고 제품·운영 방식의 정의를 비교 전에 짧게 설명'
    elif t['id']=='room-configuration':
        body[1]['content_task']='공간·좌석·기존 장비가 문제에 영향을 주는 이유와 각 장비 역할을 설명'
    elif t['id']=='feature-explanation':
        body[1]['content_task']='문제에 필요한 변화를 설명한 뒤 기능의 기본 의미와 역할을 일상어로 연결'
    else:
        # Existing symptom slot is now the reason/scope slot, not a duplicate opening.
        body[1]['content_task']='증상 범위와 가능 원인·환경을 구분. 원인을 확정하지 않고 공식 점검 순서를 안내'
    for i,s in enumerate(body):s['slot_id']=t['id']+'-'+str(i+1)
    t['editorial_flow']='문제 장면/선택 고민 → 이유/기준 → 기능/비교/점검 → 제품·구성 적용 → 판단·체크리스트'
    t['review_checks'].append('제품·기능 설명 전에 독자의 구체적인 문제 또는 선택 고민이 제시되는가')

article_plans=[]
for topic,(title,scene,headings) in zip(topics,plans):
    template=next(t for t in catalog['templates'] if t['name']==topic['template_type'])
    item={'topic_id':topic['id'],'template_id':template['id'],'keyword':topic['primary_keyword'],
          'proposed_title':title,'problem_scene':scene,'reader_question':headings[0],
          'original_ai_reader_question':topic['reader_question'],
          'central_decision':template['decision_question'],
          'body_outline':[{'order':i+1,'heading':h,'role':role,'question_id':topic['id']+'-Q'+str(i+1),
                          'fact_refs':[],'source_refs':[],'visual_need':{'purpose':'해당 설명의 이해를 도울 자료; 실제 자료 ID 매칭 필요','asset_need_id':None}}
             for i,(h,role) in enumerate(zip(headings,['problem','reason_or_criteria','solution_or_comparison','application_or_conditions','decision_checklist']))],
          'evidence_needed':topic['evidence_needed'],'product_ids_to_verify':topic['product_ids'],
          'keyword_origin':topic['keyword_origin'],'status':'editorial_plan_requires_source_binding',
          'example_use':'일반적인 상황 예시이며 실증·고객 경험이 아님'}
    article_plans.append(item)
    b=next(b for b in bindings['bindings'] if b['topic_id']==topic['id'])
    b.update(proposed_title=title,original_ai_topic=b['topic'],plan_ref='article-plans.json#'+topic['id'])
for name,value in [('common.json',common),('catalog.json',catalog),('topic-bindings.json',bindings),
                   ('article-plans.json',{'version':'1.2.0','created_at':datetime.now(timezone.utc).isoformat(),'plans':article_plans})]:
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# 문제 제기 중심의 20개 글 작성 계획','',
 '사용자가 제시한 블로그 전개를 기준으로 개선한 편집 계획이다. 아래 장면과 제목은 제안이며 제품 기능·원인·수치의 검증 결과가 아니다. Fact·출처·이미지 ID 바인딩은 남아 있다.','',
 '공통 시작: 문제와 해결 방향의 제목 → 첫인사 → 승인된 기업 안내 → 불편 공감·주제 예고 → 첫 문의 배너 → 본문 연결','',
 '본문 기본 흐름: 문제 → 이유/선택 기준 → 해결 기능/점검 → 제품·구성 적용 → 체크리스트·판단','',
 '공통 마감: 문제의 답 회수 → 다음 행동 → 소회·상담 연결·맺음 인사 → 마지막 문의 배너. 실제 실증 기록이 있을 때만 사례를 추가한다.','']
for p in article_plans:
    lines+=['## '+p['topic_id']+' · '+p['proposed_title'],'',
            f"키워드: {p['keyword']} / 템플릿: {p['template_id']}",'','문제 장면: '+p['problem_scene'],'']
    lines += [f"{s['order']}. {s['heading']}" for s in p['body_outline']]
    lines+=['','필요한 근거: '+' / '.join(p['evidence_needed']),'']
(OUT/'article-plans.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
(OUT/'README.md').write_text('# 블로그 템플릿 v1.2 — 문제 제기 중심\n\n[20개 주제별 제목·문제 장면·본문 전개](article-plans.md)\n\n[기존 가이드 대조 기록](guide-review.md)\n\n문제 → 이유 → 해결 기능/절차 → 제품·구성 적용 → 판단을 기본으로 한다. 5개 유형 모두 제품 정의 앞에 문제 장면·선택 고민을 배치했다. 공통 시작·마감은 common.json, 유형별 흐름은 catalog.json에 정의했다.\n\n인사·주제 예고는 짧게 연결하고 본문 첫 설명에서 문제를 구체화한다. 기존 기업 안내·양쪽 문의 배너·제품 설명 위치의 링크를 유지한다. 제품·기능·부속의 실제 자료는 설명 위치에 연결하며 실증은 실제 기록이 있을 때만 넣는다.\n\n샘플의 “오늘은 …” 고정 문구·무료 대여·제품 수치·실증 주장은 복제하지 않는다. 편집기 메뉴와 ASSET_REQUIRED 표시는 원고 구성에 포함하지 않는다.\n\n작성 계획이며 실제 원고 생성·사실 검증·운영 활성화는 아직 수행하지 않았다.\n',encoding='utf-8')
assert len(article_plans)==20 and len({p['topic_id'] for p in article_plans})==20
assert all(t['body_sequence'][0]['placement'].startswith('본문 첫') for t in catalog['templates'])
print('Improved 5 templates; wrote 20 topic-specific problem-first plans. Runtime unchanged.')
