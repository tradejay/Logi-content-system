"""Article roles, independent of execution stages and paragraph numbering."""
ELEMENTS = {
    'all_content':'글 전체', 'title':'제목',
    'opening.greeting':'시작 인사', 'opening.business_notice':'B2B 상담·데모 안내',
    'opening.problem_topic':'고민 공감·주제 예고', 'opening.inquiry_banner':'첫 문의 문구·배너',
    'opening.transition':'본문 연결', 'opening.answer':'공통 전제·질문·초반 핵심 답',
    'body.definition':'제품·기능 기본 설명', 'body.explanation':'질문별 핵심 설명',
    'body.principle':'원리 설명', 'body.specification':'스펙 해석', 'body.comparison':'비교',
    'body.setup':'설정 방법', 'body.configuration':'구성·배선·사용 모습',
    'body.case':'실증·사례', 'body.conditions':'적용 조건·주의사항',
    'body.extension':'조건부 추가 장비', 'body.product_link':'제품 소개 링크',
    'media':'사진·GIF·도표·캡션·이미지 문구',
    'closing.summary':'핵심 답·구성 결론 회수', 'closing.next_action':'판단 기준·다음 행동',
    'closing.appreciation':'가치 요약·소회', 'closing.consultation':'상담·데모 연결',
    'closing.greeting':'마무리 인사', 'closing.inquiry_banner':'마지막 문의 문구·배너',
    'not_applicable':'글 구성 외 실행 계약', 'unassigned':'적용 위치 검토 필요',
}

def infer_elements(atom):
    text, section = atom['text'], atom.get('section', '')
    if atom.get('purpose') in ('reference', 'runtime_contract'):
        return ['not_applicable']
    result=[]
    patterns = [
        ('오늘은', ['opening.problem_topic']),
        ('첫인사', ['opening.greeting']), ('정중하게 인사', ['opening.greeting']),
        ('B2B 견적', ['opening.business_notice','closing.consultation']),
        ('주제 예고', ['opening.problem_topic']), ('주제 제시', ['opening.problem_topic']),
        ('본문 탐색', ['opening.transition']),
        ('oceantech-inquiry-opening', ['opening.inquiry_banner']),
        ('oceantech-inquiry-closing', ['closing.inquiry_banner']),
        ('도입부와 마무리', ['opening.inquiry_banner','closing.inquiry_banner']),
        ('양쪽 배너', ['opening.inquiry_banner','closing.inquiry_banner']),
        ('초반 질문', ['closing.summary']), ('핵심 내용을', ['closing.summary']),
        ('마무리 인사', ['closing.greeting']), ('맺음 인사', ['closing.greeting']),
        ('소회', ['closing.appreciation']), ('다음 행동', ['closing.next_action']),
        ('제품 소개', ['body.product_link']), ('blog_url', ['body.product_link']),
        ('소개 글 링크', ['body.product_link']),
        ('기본 정의', ['body.definition']), ('처음 소개', ['body.definition']),
        ('기능 비교', ['body.comparison']), ('비교표', ['body.comparison']),
        ('배선', ['body.configuration']), ('설정 방법', ['body.setup']),
        ('실증', ['body.case']), ('고객 사례', ['body.case']),
        ('추가 장비', ['body.extension']), ('부속', ['body.extension']),
        ('시각적 질문', ['media']), ('캡션', ['media']), ('GIF', ['media']),
    ]
    for token, ids in patterns:
        if token in text:
            result.extend(ids)
    if not result:
        if atom.get('purpose') == 'runtime_guardrail': return ['all_content']
        if '초반' in section: result=['opening.answer']
        elif '마감' in section: result=['closing.summary','closing.next_action']
        elif atom.get('domain') in ('editorial','images'): result=['body.explanation']
        else: result=['unassigned']
    return list(dict.fromkeys(result))

def migrate(manager, expected):
    manager.ensure()
    with manager.lock():
        state=manager.load()
        manager.check_revision(state,expected)
        if state.get('element_schema_version') == 1: return state
        before=manager.assemble(state)
        for atom in state['atoms']:
            if atom.get('retired_by'): continue
            atom['applies_to_elements']=infer_elements(atom)
            atom['element_scope_status']='needs_review'
        state['element_schema_version']=1
        assert manager.assemble(state)==before
        manager.commit(state,{'policy_id':'ELEMENT-SCOPE-V1','before':None,
                              'after':{'review_note':'글 구성 요소 적용 위치 필드 추가; 본문·실행 입력 보존'}})
    return state
