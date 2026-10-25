"""Separate template authoring requirements from continuing execution constraints."""
import re
from copy import deepcopy
from services.policy_manager import write

PURPOSES = ('template_design', 'runtime_guardrail', 'runtime_contract', 'reference', 'needs_review')
LABELS = {'template_design':'템플릿 설계', 'runtime_guardrail':'공통 적용 규칙',
          'runtime_contract':'실행·출력 계약', 'reference':'출처·참고', 'needs_review':'분류 검토'}

def classify(atom):
    text, domain = atom['text'], atom['domain']
    if atom.get('entry_type') == 'source' or atom.get('kind') == 'reference':
        return 'reference', '문서 메타데이터·참고 자료'
    # Truth, scope, approval and failure handling stay effective across every template.
    safety = re.search(r'근거|미확인|Fact|조건|제약|scope|허구|만들어내|실증|실재|고객 경험|승인|권한|실패|무응답|미해결|unresolved|추정|과장|확인되지|출처|정밀도|단위|원본|약속|가정|미확정|사실|정확|확인사항|검증되지|스펙.*취급하지', text)
    if safety:
        return 'runtime_guardrail', '사실·조건·승인·실패 처리 제약은 템플릿과 무관하게 유지'
    if domain in ('response-contract', 'operations', 'review') or re.search(
            r'JSON|필드|항목:|레코드:|revision|hash|claim.map|Claim ID|검토 출력:|큐|대기열|adapter|API|used_asset_need_ids|changes|AssetNeed|템플릿 연결|발행 전|수정 이력|날짜', text):
        return 'runtime_contract', '출력 구조·검토·이력·상태 처리 계약'
    if domain in ('brand', 'editorial', 'planning') or atom['target'] in ('GUIDE-CORE-STYLE', 'GUIDE-CORE-WRITING'):
        return 'template_design', '글의 순서·말투·독자 질문·브랜드 배치 설계'
    if domain == 'images' and re.search(r'문단|섹션|배치|시각적 질문|상황 사진|설명 카드|이미지 수', text):
        return 'template_design', '템플릿의 이미지 슬롯·시각적 설명 설계'
    if domain in ('evidence', 'business', 'images'):
        return 'runtime_guardrail', '제품 사실·업무 사실·자산 사용의 공통 제약'
    return 'needs_review', '문맥을 보고 용도를 추가 분류해야 하는 지시'

def partition(manager, expected):
    manager.ensure()
    with manager.lock():
        state = manager.load()
        manager.check_revision(state, expected)
        if state.get('purpose_partition_version') == 2:
            return state
        before = manager.assemble(state)
        changes = []
        for a in state['atoms']:
            if a.get('retired_by'): continue
            old = deepcopy(a)
            purpose, reason = classify(a)
            a.update(purpose=purpose, purpose_reason=reason, revision=a['revision']+1)
            # Routing classifications are separate from final natural-language correctness.
            a['review_note'] = reason + '; 문서 조립 본문은 보존.'
            changes.append({'policy_id':a['id'], 'before':old, 'after':deepcopy(a)})
        state['purpose_partition_version'] = 2
        if manager.assemble(state) != before:
            raise ValueError('용도 분류 중 조립 본문이 변경됐습니다.')
        manager.commit(state, {'policy_id':'PURPOSE-PARTITION-V1', 'before':None,
                              'after':{'review_note':'템플릿 설계와 공통 제약·실행 계약 분리'}, 'changes':changes})
        for purpose in PURPOSES:
            selected = [a for a in state['atoms'] if not a.get('retired_by') and a['enabled'] and a.get('purpose') == purpose]
            write(manager.directory / 'collections' / (purpose+'.json'),
                  {'workspace_revision':state['revision'], 'purpose':purpose, 'label':LABELS[purpose], 'policies':selected})
    return state
