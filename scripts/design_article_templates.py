"""Produce reviewable template definitions, without activating runtime changes."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from services.policy_elements import ELEMENTS

OUT=ROOT/'content-system/00_system/templates/articles'
OUT.mkdir(parents=True,exist_ok=True)
if (OUT/'guide-review.json').exists():
    raise SystemExit('Guide-reviewed templates exist. Revise the reviewed design instead of overwriting it with the baseline generator.')
topics=json.loads((ROOT/'audit/2026-10-06-template-topic-candidates/candidates.json').read_text(encoding='utf-8'))['candidates']
policies=json.loads((ROOT/'content-system/00_system/policy/workspace.json').read_text(encoding='utf-8'))

def slot(element, prompt, required=True, condition=None, repeat=False):
    return {'element':element,'label':ELEMENTS[element],'content_task':prompt,'required':required,
            'include_when':condition or 'always','repeatable':repeat,'paragraph_count':None}

opening=[slot('title','围绕读者问题拟题'),slot('opening.greeting','로지텍 공식 수입 총판 오우션의 정중한 인사'),
    slot('opening.business_notice','승인된 B2B 견적·데모 지원 안내'),
    slot('opening.problem_topic','독자 고민에 공감하고 이번 글의 범위를 자연스럽게 예고'),
    slot('opening.inquiry_banner','지정된 문의 문구·클릭 가능한 승인 배너'),
    slot('opening.transition','앞의 고민에서 본문 질문으로 연결'),
    slot('opening.answer','기존 환경·공통 전제와 핵심 질문, 확인된 범위의 조건부 답')]
opening[0]['content_task']='독자 질문과 글의 범위에 맞는 제목'
closing=[slot('closing.summary','처음 질문의 답과 기본 구성·판단을 짧게 회수'),
    slot('closing.next_action','구매·재사용·설정·추가 확인 중 적합한 다음 행동'),
    slot('closing.appreciation','내용이 독자의 판단에 도움 되길 바라는 소회'),
    slot('closing.consultation','승인된 기술 상담·B2B 견적·데모 안내로 연결'),
    slot('closing.greeting','분위기에 맞는 정중한 맺음 인사'),
    slot('closing.inquiry_banner','도입과 동일한 문의 문구·클릭 배너; 중복 제거하지 않음')]

definitions=[
('product-introduction','제품 소개','이 제품이 내 불편을 해결할 구성에 필요한가?',[
 slot('body.definition','어떤 제품이며 이번 환경에서 어떤 역할을 하는지 설명'),
 slot('body.explanation','고객 불편 → 필요한 변화 → 기능의 쉬운 설명과 Fact 근거',repeat=True),
 slot('body.configuration','기존 장비와 함께 어떻게 회의를 사용하는지 기본 구성 설명'),
 slot('body.specification','판단에 필요한 수치·단위·측정 조건만 해석',False,'구매 판단에 수치가 필요한 경우'),
 slot('body.conditions','제품·모드·플랫폼·버전의 적용 조건과 한계'),
 slot('body.extension','남는 문제를 보완하는 부속의 역할·근거',False,'기본 구성으로 해결되지 않는 문제가 있는 경우')]),
('product-comparison','제품 비교','같은 사용 요구에서 어느 선택지가 적합한가?',[
 slot('body.definition','비교할 제품 또는 운영 방식의 기본 의미와 공통 전제'),
 slot('body.comparison','같은 기준의 차이·근거·적합 조건을 비교',repeat=True),
 slot('body.configuration','선택지별 실제 사용 모습; 상세 연결 절차는 필요할 때만',False,'사용 모습이 선택에 영향을 주는 경우'),
 slot('body.conditions','비교 범위·지원 조건·차이의 한계'),
 slot('body.explanation','환경별 선택 기준과 기본 추천의 이유; 효과를 보장하지 않음')]),
('room-configuration','회의실 구성','기존 공간과 장비로 무엇을 구매·재사용해 어떻게 구성할까?',[
 slot('body.definition','기본 구성의 장비별 역할; 서로 대체하지 않는 부속 구분'),
 slot('body.configuration','확인된 기본 연결 관계와 사용 흐름; 도식 ID 바인딩',repeat=True),
 slot('body.setup','공식 설정·연결 순서와 정상 동작 확인',False,'검색 의도가 설치·설정이거나 실행 절차가 필요한 경우'),
 slot('body.conditions','호환성·버전·설치 제약 및 미확정 조건'),
 slot('body.extension','어떤 문제가 남을 때 부속이 필요한지 설명',False,'추가 장비의 필요성이 근거로 확인된 경우')]),
('feature-explanation','기능 설명','이 기능은 무엇을 하며 내 문제에 언제 필요한가?',[
 slot('body.definition','기능을 일상어로 정의하고 제품의 역할과 연결'),
 slot('body.principle','공식 확인된 입력 → 동작 → 결과; 미공개 알고리즘을 채우지 않음'),
 slot('body.explanation','사용 상황과 화면·음향 등 독자가 확인할 모습'),
 slot('body.comparison','혼동하는 기능·모드가 있으면 같은 기준으로 차이 설명',False,'차이 설명이 독자 질문 해결에 필요한 경우'),
 slot('body.conditions','지원 제품·모드·플랫폼·버전과 확인된 한계')]),
('troubleshooting','문제 해결','무엇을 확인하고 어떤 순서로 조치할까?',[
 slot('body.explanation','증상·발생 환경·범위를 확인; 원인을 미리 단정하지 않음'),
 slot('body.conditions','점검 전 제품·버전·권한·호환성 및 작업 전제'),
 slot('body.setup','가능 원인별 공식 확인 방법 → 조치 → 정상 확인; 분기별 반복',repeat=True),
 slot('body.configuration','연결 관계가 원인 판단에 필요한 경우 도식 설명',False,'배선·구성 점검이 필요한 경우'),
 slot('body.explanation','미해결 시 필요한 기록·공식 지원·상담 경로; 구매를 강요하지 않음')]),
]
shared={'schema_version':'1.0.0','status':'design_draft','policy_workspace_revision':policies['revision'],
    'opening_sequence':opening,'closing_sequence':closing,
    'composition_semantics':{'roles_are_not_paragraphs':True,'adjacent_roles_may_merge':True,
        'body_sequence_is_default':True,'change_body_order_requires_reason':True,
        'definition_before_comparison':True,'conditions_attach_to_related_claims':True,
        'no_fixed_h2_or_word_count':True},
    'attachments':{'product_link':{'element':'body.product_link','placement':'対象製品の最初の実質説明直後'},
        'media':{'element':'media','placement':'その資料が答える説明位置','references':['asset_need_id','asset_id','diagram_id'],
                 'approval_required_for_final':True,'missing_required_is_unresolved':True}},
    'optional_modules':[slot('body.case','実際の記録がある場合のみ主體・環境・日付・結果を示す',False,'実証記録が提供され読者質問に必要な場合')],
    'runtime_rule_references':['RULE-EVIDENCE-BOUNDARY','RULE-NUMERIC-SCOPE','RULE-COMPONENT-ROLE','RULE-PLATFORM-SCOPE',
        'RULE-CONFIGURATION-SOURCE','RULE-EXPERIENCE-BUSINESS','RULE-ASSET-TRUTH','RULE-OCEANTECH-BRAND-LINKS'],
    'runtime_policy_ids':[a['id'] for a in policies['atoms'] if a['enabled'] and not a.get('retired_by') and a.get('purpose') in ('runtime_guardrail','runtime_contract')],
    'runtime_note':'실행 계약과 공통 제약은 별도 묶음으로 유지. 현재의 문장 분류·요소 연결은 1차 분류이며 의미 검토 필요.',
    'data_slots':['reader_question','existing_environment','central_decision','product_ids','fact_ids','source_locators','asset_needs','diagram_ids','product_blog_urls'],
    'data_note':'사실·이미지·URL은 현재 자료의 ID로 바인딩. taxonomy와 AI 후보는 공식 제품 사실이 아님.'}
shared['attachments']['product_link']['placement']='해당 제품의 첫 실질적 설명 직후; 필요한 독립 후속 설명에서만 반복'
shared['attachments']['media']['placement']='자료가 답하는 설명 위치'
shared['optional_modules']=[slot('body.case','실제 기록의 주체·환경·일자·측정·관찰 결과를 설명',False,'기록이 제공되고 독자 질문에 필요한 경우')]
templates=[]
for template_id,name,decision,body in definitions:
    templates.append({'id':template_id,'version':'1.0.0','name':name,'status':'design_draft','extends':'common-v1',
        'decision_question':decision,'body_sequence':body,
        'candidate_ids':[t['id'] for t in topics if t['template_type']==name],
        'design_policy_ids':[a['id'] for a in policies['atoms'] if a['enabled'] and not a.get('retired_by') and a.get('purpose')=='template_design'
            and set(a.get('applies_to_elements',[])) & {s['element'] for s in opening+body+closing}],
        'review_checks':['첫 질문과 마감의 답이 연결되는가','중심 결정 하나를 돕는가','조건·근거와 자료 배치가 맞는가','필수 공통 인사·링크·배너가 있는가'],
        'source_guides':['03-opening-body-closing.md','rules/reader-and-style.md','rules/oceantech-brand-and-links.md','04-images.md']})
for item in templates:
    assert all(s['element'] in ELEMENTS for s in item['body_sequence'])
assert len({c for t in templates for c in t['candidate_ids']})==len(topics)==20
for name,data in [('common.json',shared),('catalog.json',{'schema_version':'1.0.0','templates':templates}),
                  ('topic-bindings.json',{'bindings':[{'topic_id':t['id'],'keyword':t['primary_keyword'],'topic':t['topic'],
                   'template_id':next(d['id'] for d in templates if d['name']==t['template_type']),
                   'status':'proposal_requires_fact_review','evidence_needed':t['evidence_needed']} for t in topics]})]:
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# 네이버 화상회의 블로그 글 템플릿 설계','', '설계 초안. 실행기 연결·운영 활성화 전이며 완성 원고를 생성하지 않았다.','',
 '구성 요소는 문단이나 H2 개수가 아니다. 인접 역할은 자연스럽게 합칠 수 있다. 시작·마감 공통 순서를 보존하고 본문은 독자 질문에 따라 조정한다.','',
 '공통 시작: 제목 → 첫인사 → B2B 안내 → 고민 공감·주제 예고 → 문의 문구·배너 → 본문 연결 → 전제·질문·조건부 핵심 답','',
 '공통 마감: 핵심 답·결론 회수 → 다음 행동 → 가치 요약·소회 → 상담/데모 연결 → 맺음 인사 → 문의 문구·배너','']
for t in templates:
    lines+=['## '+t['name'],'',t['decision_question'],'','| 순서 | 역할 | 내용 | 포함 조건 |','|---|---|---|---|']
    for i,s in enumerate(t['body_sequence'],1):
        lines.append(f"| {i} | {s['label']} | {s['content_task']} | {'기본 포함' if s['required'] else s['include_when']} |")
    lines+=['','연결 주제: '+', '.join(t['candidate_ids']),'']
lines+=['## 공통 제약과 자료 바인딩','', '제품 설명 직후 제품 소개 링크를 연결한다. 이미지·GIF·도식·표는 필요한 설명 위치에 배치하며 개별 장으로 강제하지 않는다. 지원 조건은 주장 옆에 남기며 독립 주의사항 장은 필요할 때만 만든다. 실제 기록이 없는 실증/사례는 넣지 않는다.','',
 '템플릿 설계 규칙은 구조 설계에 참조하고, 사실·조건·출처·승인 및 실행·출력 계약은 매 글에 계속 적용한다. 미분류 설계 규칙을 자동 폐기하지 않는다. JSON의 정책 ID 연결은 1차 분류에 기반하므로 검토 후 확정한다.','',
 '20개 후보 제목의 성능 강화·최적·인원수·인증·원인 단정은 검증 대상이다. 관련 근거가 없으면 중립 제목으로 수정한다. 문제 해결 글의 결론은 장비 구매를 전제로 하지 않는다.','',
 '파일: common.json(공통 구조·제약 참조), catalog.json(유형별 본문), topic-bindings.json(20개 주제 연결).']
(OUT/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('Designed 5 templates; validated 20 topic bindings and element IDs. Runtime unchanged.')
