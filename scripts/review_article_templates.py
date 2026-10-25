"""Apply a source-located editorial review to each template design."""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'content-system/00_system/templates/articles'
AUTH=ROOT/'content-system/02_writer_ai/authoring'
catalog=json.loads((OUT/'catalog.json').read_text(encoding='utf-8'))
common=json.loads((OUT/'common.json').read_text(encoding='utf-8'))
if all(t.get('guide_review_version')=='1.1.0' for t in catalog['templates']):
    print('Template guide review already applied.');raise SystemExit(0)
for name in ('catalog.json','common.json','README.md'):
    backup=OUT/'review-baseline-v1'/name
    backup.parent.mkdir(exist_ok=True)
    if not backup.exists(): backup.write_bytes((OUT/name).read_bytes())

def source(path, excerpt):
    body=(AUTH/path).read_text(encoding='utf-8-sig')
    pos=body.index(excerpt)
    return {'path':str((AUTH/path).relative_to(ROOT)).replace('\\','/'),
            'line':body[:pos].count('\n')+1,'excerpt':excerpt,'sha256':hashlib.sha256(body.encode()).hexdigest()}

evidence={
 'opening':source('rules/oceantech-brand-and-links.md','제목 다음에 아래 흐름으로 본문을 자연스럽게 시작한다.'),
 'no_overview':source('03-opening-body-closing.md','고객 문제보다 앞에 모든 용어 정의를 모아 놓는 고정 개요 장은 요구하지 않는다.'),
 'question':source('03-opening-body-closing.md','한 덩어리는 한 질문을 해결한다.'),
 'purchase_flow':source('03-opening-body-closing.md','구매·도입 글은 **고객 장면과 불편 → 필요한 변화 → 기능의 쉬운 설명과 근거 → 기본 구성과 사용 모습 → 적용 조건 → 구매·재사용 결론**으로 전개한다.'),
 'compare':source('03-opening-body-closing.md','| 비교 | 둘 이상의 선택지를 비교 | 동일 기준, 확인된 차이, 적합 조건과 한계 |'),
 'setup':source('03-opening-body-closing.md','| 설정 방법 | 독자가 직접 작업해야 함 | 제품/버전, 공식 메뉴·절차, 확인 방법 |'),
 'principle':source('03-opening-body-closing.md','| 원리 설명 | 왜/어떻게 작동하는가가 핵심 | 공식 확인된 입력·동작·결과·확인 범위 |'),
 'module':source('03-opening-body-closing.md','다음 모듈을 필요에 따라 선택한다.'),
 'reuse':source('rules/reader-and-style.md','문제가 설정·배치 조정으로 해결되면 구매를 강요하지 않는다.'),
 'extension':source('03-opening-body-closing.md','추가 장비는 “어떤 문제가 남을 때 필요한가”와 함께 짧게 설명한다.'),
 'images':source('04-images.md','실제 제품 소개는 공식 제품 사진, 실제 기능 설명은 공식 GIF·영상, 고객 문제와 환경은 생성 이미지로 역할을 구분한다.'),
 'needs':source('04-images.md','각 이미지 요구는 `need_id`, `question_id`, `section_key`, `placement_anchor`, `purpose`, `asset_type`, `entity_ids`, `fact_ids`, `required`, `fallback`을 가진다.'),
 'links':source('rules/oceantech-brand-and-links.md','제품을 설명하는 문단 바로 다음에 해당 제품의 Blog Manager `blog_url` 링크를 넣는다.'),
 'cautions':source('02-facts-and-cautions.md','active인 전역 필수 규칙을 선택한다.'),
 'match':source('02-facts-and-cautions.md','`required`는 선택된 규칙의 로딩/준수가 필수라는 뜻이며 조건부 규칙을 전역 선택한다는 뜻이 아니다.'),
 'closing':source('03-opening-body-closing.md','초반 질문에 대한 답을 짧게 회수한다.'),
}
review=[]
def finding(template, problem, change, keys):
    row={'template_id':template['id'],'finding':problem,'applied_change':change,'sources':[evidence[k] for k in keys],
         'status':'applied_to_design'}
    review.append(row)
    return row

for t in catalog['templates']:
    body=t['body_sequence']
    for index,s in enumerate(body):
        s['slot_id']=t['id']+'-'+str(index+1)
        s['standalone_section_required']=False
        s['question_binding_required']=True
        s['claim_fact_source_binding_required']=True
        s['source_refs']=[evidence['question']]
        if s['element']=='body.definition':
            s['placement']='첫 관련 기능·제품 설명에 포함; 비교 전에 기본 의미를 소개'
            s['source_refs'].append(evidence['no_overview'])
        if s['element']=='body.conditions':
            s['placement']='관련 주장 옆에 먼저 붙임; 별도 장은 필요할 때만'
        s['visual_plan']={'question':'이 설명에서 독자가 시각적으로 확인할 것은 무엇인가?',
             'fields':['need_id','question_id','section_key','placement_anchor','purpose','asset_type','entity_ids','fact_ids','required','fallback'],
             'selection_order':['matching_official','rights_verified_owned','related_generated_scene_or_korean_card'],
             'official_ui_product_and_test_evidence_cannot_be_generated':True,
             'skip_requires_reason':True,'fixed_image_count':None,'source_refs':[evidence['images'],evidence['needs']]}
    finding(t,'기본 설명·주의사항이 고정된 독립 장으로 읽힐 수 있음',
            '필요한 위치의 역할로 변경; 독립 개요 장·주의사항 장 강제 제거',['no_overview','question'])
    finding(t,'시각 자산 지시가 공통 슬롯 수준에 머무름',
            '각 설명 슬롯에 시각적 질문·AssetNeed 필드·공식 자료 우선·생성 금지 범위를 연결',['images','needs'])
    if t['id']=='product-introduction':
        definition=next(s for s in body if s['element']=='body.definition')
        definition['content_task']='도입의 불편·원하는 변화에 이어 제품의 기본 의미와 이번 구성에서 맡는 역할을 첫 기능 설명에 포함'
        config=next(s for s in body if s['element']=='body.configuration')
        config.update(content_task='구매할 것·재사용할 것·장비 역할·회의 사용 모습 설명. 연결 관계가 핵심일 때만 배선 상세와 도식 추가',
                      include_when='구매·도입 글에서는 사용 모습 포함; 연결 상세는 판단에 필요한 경우')
        # Feature differences must remain available even for a single-product purchase decision.
        comparison={'element':'body.comparison','label':'비교','content_task':'구매 이유에 필요한 기능·모드 차이를 같은 기준으로 설명',
                    'required':False,'include_when':'기능 차이가 구매 이유 또는 독자 질문의 핵심일 때',
                    'repeatable':False,'paragraph_count':None,'standalone_section_required':False,
                    'source_refs':[evidence['compare'],evidence['no_overview']]}
        body.insert(2,comparison)
        finding(t,'제품 소개에서 기능·모드 비교를 선택할 수 없었음',
                '단일 구매 판단에 필요한 기능 비교를 조건부 추가; 배선 상세 강제 제거',['purchase_flow','compare'])
    elif t['id']=='product-comparison':
        comparison=next(s for s in body if s['element']=='body.comparison')
        comparison['content_task']='하나의 결정 질문과 동일한 환경·기준에서 확인된 차이·적합 조건·한계를 설명. 제품과 운영 방식·부속 역할을 섞어 비교하지 않음'
        comparison['source_refs'].append(evidence['compare'])
        finding(t,'비교군과 비교표의 선택 조건이 약했음',
                '동일 결정 질문·공통 전제·기준을 명시하고 표는 이해에 필요한 경우 선택',['compare','purchase_flow'])
    elif t['id']=='room-configuration':
        t['intent_variants']={'purchase_or_adoption':'불편·변화 → 역할·기능 근거 → 기본 구성·사용 → 조건 → 구매·재사용 결론',
                             'installation':'고정된 제품·운영 전제 → 연결·설정 순서 → 정상 확인 → 제약'}
        finding(t,'구매·도입 설명과 설치 절차가 하나의 순서로 섞임',
                '같은 템플릿 안에 구매·도입/설치 의도별 배열 지침을 구분',['purchase_flow','setup'])
    elif t['id']=='feature-explanation':
        principle=next(s for s in body if s['element']=='body.principle')
        principle.update(required=False,include_when='왜·어떻게 작동하는지가 핵심 질문이며 공식 근거가 확보된 경우',
                         content_task='공식 확인된 입력·동작·결과·확인 범위까지만 설명. 미공개 내부 원리를 채우지 않음')
        principle['source_refs'].append(evidence['principle'])
        finding(t,'기능 설명이면 항상 원리 설명을 필수로 요구했음',
                '원리 모듈을 질문·근거에 따라 선택하도록 변경',['principle','module'])
    elif t['id']=='troubleshooting':
        t['decision_question']='증상과 환경을 어떻게 확인하고 공식 절차로 조치·정상 확인할까?'
        body[-1]['content_task']='미해결 시 필요한 증상·환경·점검 기록과 지원 경로를 안내. 근거 없이 원인을 단정하거나 장비 구매를 결론으로 삼지 않음'
        steps=next(s for s in body if s['element']=='body.setup')
        steps['source_refs'].append(evidence['setup'])
        finding(t,'원인별 조치만 강조돼 제품·버전과 정상 확인·구매 비강요 기준이 약했음',
                '공식 절차·제품/버전·조치 후 확인·미해결 기록과 다음 행동을 명시',['setup','reuse','closing'])
    for i,s in enumerate(body):
        s['slot_id']=t['id']+'-'+str(i+1)
        s.setdefault('question_binding_required',True)
        s.setdefault('claim_fact_source_binding_required',True)
        s.setdefault('visual_plan',dict(body[0]['visual_plan']))
    t.update(version='1.1.0',guide_review_version='1.1.0',status='guide_reviewed_design',
             review_scope='작성 구조 설계 검토; 실제 제품 사실·이미지 확보·원고 품질 검토 또는 운영 승인이 아님')
    t['guide_review']=[r for r in review if r['template_id']==t['id']]
    t['common_sequence_ref']='common.json'
    t['product_link_attachment']={'placement':'각 제품의 첫 실질 설명 직후','source_refs':[evidence['links']]}

common['status']='guide_reviewed_design'
common['version']='1.1.0'
common['runtime_policy_ids_role']='검토용 전체 재고. 모든 글에 무조건 주입할 목록이 아님.'
common['runtime_selection']={'steps':['active인 전역 필수 규칙','Fact·엔티티의 직접 caution_rule_ids','제품·기능·속성·claim_kind·intent 조건 매칭',
                                    'ID/version 중복 제거 후 실제 본문·scope·limitations·does_not_imply 전달'],
                             'source_refs':[evidence['cautions'],evidence['match']]}
for s in common['opening_sequence']: s['source_refs']=[evidence['opening']]
for s in common['closing_sequence']: s['source_refs']=[evidence['closing'],source('rules/oceantech-brand-and-links.md','마무리 문단 바로 뒤에 승인된 공식 문의 배너')]
common['opening_sequence'][-1]['content_task']='공통 전제·기존 환경·핵심 질문과 확인된 조건부 답; 앞의 고민 공감과 같은 문제를 반복하지 않고 연결'
common['guide_review_sources']=list(evidence.values())
for filename,data in [('catalog.json',catalog),('common.json',common),('guide-review.json',{
    'reviewed_at':datetime.now(timezone.utc).isoformat(),'version':'1.1.0','findings':review,
    'source_basis':'authoring MD 현재 본문; 실행 입력의 활성 릴리스는 변경하지 않음'})]:
    (OUT/filename).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# 템플릿별 실제 가이드 적용 검토','', '5개 템플릿을 각각 대조하고 설계 파일에 수정했다. 제품 사실 검증·완성 원고 검토·운영 활성화는 별도다.','']
for t in catalog['templates']:
    lines+=['## '+t['name'],'','| 발견 사항 | 적용한 수정 | 가이드 근거 |','|---|---|---|']
    for r in t['guide_review']:
        refs='<br>'.join(f"[{Path(s['path']).name}:{s['line']}]({(ROOT/s['path']).as_posix()}:{s['line']})" for s in r['sources'])
        lines.append('| '+r['finding']+' | '+r['applied_change']+' | '+refs+' |')
    lines+=['','수정한 본문 역할 순서: '+' → '.join(s['label']+(' (조건부)' if not s['required'] else '') for s in t['body_sequence']),'']
lines+=['공통 수정: 조건부 주의사항을 모든 글에 전역 적용하지 않도록 선택 절차를 명시했다. 원고 출력 필드·Claim 연결·Need 승인 기준은 기존 실행 계약을 유지한다.','',
       '공통 시작·마감은 common.json을 사용한다. 본문 역할은 별도 장이나 고정 문단 수가 아니며 제품 정의는 첫 설명에, 조건은 관련 주장 옆에 통합한다.']
(OUT/'guide-review.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
# Make the main entry point describe the current design, not the superseded baseline.
readme=['# 네이버 화상회의 블로그 템플릿 — 가이드 대조 수정본 v1.1','',
        '[템플릿별 발견 사항·수정·원문 근거](guide-review.md)','',
        '시작: 제목 → 첫인사 → B2B 안내 → 고민 공감·주제 예고 → 문의 문구·배너 → 본문 연결 → 전제·핵심 질문·조건부 답','',
        '마감: 핵심 답·결론 회수 → 다음 행동 → 가치 요약·소회 → 상담/데모 연결 → 맺음 인사 → 마지막 문의 문구·배너','']
for t in catalog['templates']:
    readme+=['## '+t['name'],'',t['decision_question'],'']
    for s in t['body_sequence']:
        readme.append('- '+s['label']+': '+s['content_task']+(' / 포함 조건: '+s['include_when'] if not s['required'] else ''))
    readme+=['','독립 개요 장·고정 문단 수를 강제하지 않는다. 각 설명에 질문·근거·조건·시각 자료를 연결한다.','']
readme+=['20개 후보의 연결은 topic-bindings.json에 유지했다. 후보 제목의 제품 성능·인원·인증·원인은 공식 자료로 별도 확인한다.','',
         '원본 v1은 review-baseline-v1에 보존했다. 현재 실행기와 운영 가이드 릴리스는 변경하지 않았다.']
(OUT/'README.md').write_text('\n'.join(readme)+'\n',encoding='utf-8')
assert len(catalog['templates'])==5 and all(t['guide_review'] for t in catalog['templates'])
print(f'Reviewed 5 templates, applied {len(review)} source-located findings; runtime unchanged.')
