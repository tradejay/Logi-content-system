"""Build a curated paragraph-role guide index; does not modify policy releases."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'content-system/00_system/templates/articles'
PREFIXES = {
    'B': 'RULE-OCEANTECH-BRAND-LINKS', 'S': 'GUIDE-03-STRUCTURE',
    'T': 'GUIDE-01-TOPIC', 'I': 'GUIDE-04-IMAGES',
    'E': 'RULE-EVIDENCE-BOUNDARY', 'N': 'RULE-NUMERIC-SCOPE',
    'C': 'RULE-CONFIGURATION-SOURCE', 'X': 'RULE-EXPERIENCE-BUSINESS',
    'R': 'RULE-READER-STYLE', 'P': 'RULE-PLATFORM-SCOPE',
    'K': 'RULE-COMPONENT-ROLE',
}

# Role IDs refine existing elements; they do not define paragraph order/count.
ROWS = [
    ('title', 'title', '제목', '모든 유형', '독자의 문제·선택 고민과 이번 글의 범위를 드러낸다. 기술 수치·효과를 제목에 썼다면 근거도 필요하다.', 'T0026 T0027 T0028 E0004'),
    ('opening.greeting', 'opening.greeting', '시작 인사', '공통 도입', '공식 총판 오우션으로 정중하게 인사한다. 인사·기업 안내는 장비 스펙 Fact와 구분한다.', 'B0016 B0037'),
    ('opening.business_notice', 'opening.business_notice', 'B2B 상담·데모 안내', '공통 도입', '승인된 견적·데모 지원 범위를 자연스럽게 안내한다. 무료 대여·설치·무조건 제공 등 약속을 확대하지 않는다.', 'B0020 B0023 X0011'),
    ('opening.problem_topic', 'opening.problem_topic', '고민 공감·주제 예고', '공통 도입', '실무자의 구체적 고민에서 주제로 연결한다. 기계적인 “오늘은 … 알아보겠습니다”나 모든 글의 동일한 고충 문장을 반복하지 않는다.', 'B0026 B0028 S0130 S0132'),
    ('opening.inquiry_banner', 'opening.inquiry_banner', '첫 문의 문구·배너', '공통 도입', '지정 문의 문구와 클릭 가능한 승인 배너를 배치한다. 제품 설명용 자산과 별도로 계획한다.', 'B0031 B0106 B0108 I0004 I0008'),
    ('opening.transition', 'opening.transition', '본문 연결', '앞의 고민에서 본문으로 연결할 때', '독자의 궁금증과 기술 설명을 잇는다. 공통 전제는 초반 핵심 답에서 한 번 밝히며, 연결 문장에서 다시 길게 설명하지 않는다.', 'B0034'),
    ('opening.answer', 'opening.answer', '공통 전제·초반 핵심 답', '공통 시작의 답 제시', '이번 글이 답할 질문과 조건부 핵심 답을 제시한다. 근거가 없으면 확정 결론을 약속하지 않는다.', 'S0134 S0136 S0078'),
    ('body.problem_statement', 'body.explanation', '본문 문제 제기', '유형별 첫 문제·선택 고민 설명', '구체적인 장면과 불편, 원하는 변화를 설명한다. 고객의 문제보다 제품·포트 나열을 앞세우지 않고, 가정은 관찰 사실과 구분한다.', 'S0022 S0027 S0130 S0031'),
    ('body.definition', 'body.definition', '제품·기능 기본 설명', '제품 또는 기능을 처음 실질적으로 소개할 때', '무엇인가 → 어떤 불편에 필요한가 → 이번 구성의 역할로 설명한다. 기능 비교 전에 기본 의미를 소개하되 고정 용어 사전 장을 필수로 만들지 않는다.', 'S0036 S0179 S0181 S0183'),
    ('body.explanation', 'body.explanation', '질문별 기능·해결 설명', '해당 독자 질문을 설명할 때', '한 덩어리는 한 질문에 답한다. 필요한 Fact와 판단을 연결하고 확인된 기능·조건을 쉬운 말로 직접 설명한다. 내부 검토 지시는 독자 본문에 쓰지 않는다.', 'S0151 S0153 S0201 S0199'),
    ('body.principle', 'body.principle', '원리·이유 설명', '원리를 알아야 질문에 답하거나 선택할 수 있을 때', '필요한 원리와 용어만 설명한다. 근거 없는 내부 알고리즘을 추정하지 않고, 수치가 들어가면 값·단위·적용 조건을 보존한다.', 'S0153 S0260 C0008 N0004'),
    ('body.specification', 'body.specification', '스펙 해석', '스펙이 구매 판단 또는 사용 제약에 필요할 때', '관련 없는 스펙은 생략하되 중요한 제약은 남긴다. 최대/권장·반경/직경·수평/대각선 화각을 구분한다.', 'R0008 S0038 N0004 N0008'),
    ('body.comparison', 'body.comparison', '비교·선택 기준', '같은 결정 질문의 비교군을 다룰 때', '동일 기준의 차이를 설명한다. 역할이 다른 장비를 대안으로 섞지 않고, 표에는 근거가 있는 동작·장면·조건만 넣는다.', 'S0049 S0065 S0083 S0186 S0188'),
    ('body.configuration', 'body.configuration', '구성·배선·사용 모습', '하나의 기본 구성을 설명할 때', '이미 가진 장비와 도입 구성을 연결하고 역할·사용 모습을 설명한다. 제품·모드·플랫폼의 Fact와 공식 배선 자료로 확인하며 무관한 운영 분기를 늘리지 않는다.', 'S0027 S0049 S0040 S0069 C0004'),
    ('body.setup', 'body.setup', '설정·점검·조치', '설치·설정 또는 문제 해결 작업이 필요할 때', '전제 조건 → 작업 순서 → 정상 확인 → 확인된 제약을 포함한다. 메뉴·옵션은 해당 제품/버전 자료를 확인한다. 설정·배치로 해결되면 구매를 강요하지 않는다.', 'S0024 S0087 C0004 C0011 R0033'),
    ('body.case', 'body.case', '실증·사례', '실제 경험·시험 기록이 있을 때', '실제 경험·쇼룸 테스트·자체 측정은 기록이 있을 때만 쓴다. 가정은 문제 제기·원리 설명에서 가정임을 명시하며 실증 근거로 쓰지 않는다.', 'X0004 X0006 X0008 X0015 S0174'),
    ('body.conditions', 'body.conditions', '적용 조건·주의사항', '선택·지원·사용에 중요한 조건이 있을 때', '확인된 범위·제약을 해당 설명과 연결한다. 모드·플랫폼·펌웨어·라이선스 차이를 지우거나 미확정 조건을 확정된 것처럼 바꾸지 않는다.', 'S0099 S0203 S0205 P0006'),
    ('body.extension', 'body.extension', '조건부 추가 장비', '기본 구성으로 해결되지 않는 문제가 남을 때', '추가가 필요한 문제·역할·조건·근거를 설명한다. 실제 사진과 등록 링크를 연결하고 별도 절차는 독립 콘티로 분리할 수 있다.', 'R0059 R0061 S0089 S0091 S0093 S0207'),
    ('body.product_link', 'body.product_link', '제품 소개 링크', '각 제품의 실질적 설명 직후', '해당 제품 ID의 원본 blog_url로 연결한다. 여러 제품은 각각 연결하고 불필요한 반복은 피한다. URL이 없거나 매칭이 모호하면 추정하지 않는다.', 'B0042 B0044 B0046 B0048 B0054 B0074 B0076'),
    ('media', 'media', '사진·GIF·도표·이미지 문구', '문단의 시각적 질문에 답할 자료를 계획할 때', '질문에 맞는 공식/권리 확인 자체 자료를 먼저 찾는다. 상황 사진·설명 카드는 생성할 수 있지만 실제 제품·UI·시험 증거를 생성으로 대체하지 않는다. 초안은 Need ID, 최종 출력은 승인 binding을 쓴다.', 'I0031 I0032 I0033 I0035 I0037 I0039 I0098 I0011 I0019 S0210'),
    ('closing.summary', 'closing.summary', '핵심 답·구성 결론 회수', '공통 마감', '초반 질문과 기본 구매·재사용·연결 결론을 짧게 회수한다. 끝에서 기본 결론을 바꾸는 새 스펙·기능을 갑자기 추가하지 않는다.', 'S0095 S0224 S0228 B0081'),
    ('closing.next_action', 'closing.next_action', '체크리스트·판단·다음 행동', '공통 마감의 판단 안내', '자기 환경에 맞는 판단 기준 또는 다음 행동을 제시한다. 불필요한 구매로 연결하지 않고, 조건부 부속은 역할·근거·사진·링크와 함께 짧게 제시할 수 있다.', 'S0226 S0120 S0097 S0230'),
    ('closing.appreciation', 'closing.appreciation', '가치 요약·소회', '공통 마감', '독자의 선택 고민에 보탬이 되길 바라는 소회를 자연스럽게 적는다. 고정된 맺음 문구를 그대로 복제하지 않는다.', 'B0086 B0083'),
    ('closing.consultation', 'closing.consultation', '상담·데모 연결', '공통 마감', '공간·예산·회의실 조건에 맞는 기술 상담과 데모 문의로 연결한다. 무료 제공·실적·상담 범위를 임의로 약속하지 않는다.', 'B0087 S0242 X0011'),
    ('closing.greeting', 'closing.greeting', '맺음 인사', '공통 마감', '공식 총판 팀으로 정중하고 따뜻하게 인사한다. 분위기를 유지하되 고정 예문을 그대로 복제하지 않는다.', 'B0088 B0083 S0240'),
    ('closing.inquiry_banner', 'closing.inquiry_banner', '마지막 문의 문구·배너', '마지막 인사 바로 뒤', '도입과 동일한 지정 문의 문구·클릭 가능한 승인 배너를 둔다. 중복 제거로 한쪽을 지우거나 다른 이미지로 대체하지 않는다.', 'S0238 B0091 B0100 B0102 B0106 B0110'),
    ('companion.product_awareness', None, '제품 인지 보조 블록', '제품 인지를 선택했으며 기존 설명과 중복되지 않을 때', '이름·기본 역할·주제와의 관련성·근거·소개 링크를 연결한다. 구매를 권하는 뜻으로 바꾸지 않는다. 본문에서 이미 정의했다면 재정의하지 않는다.', 'S0036 S0179 B0042 B0046 B0048'),
    ('companion.product_recommendation', None, '제품 추천 보조 블록', '확인된 구매·도입·사용·재사용 요구가 있고 제품 추천을 선택했을 때', '추천 이유·적합 조건·제약·근거·링크와 도입/사용/재사용 행동을 제품별로 연결한다. 대안·함께 쓰는 구성·조건부 추가를 구분하고 본문 추천을 반복하지 않는다.', 'S0081 S0083 R0033 R0059 S0230 K0004 K0009 P0006 B0046 B0048'),
]

GLOBAL = [
    ('기술 주장이 있는 곳', '제목·본문·표·캡션·이미지 문구의 기술 주장을 Fact와 공식 위치에 연결한다.', 'E0004 E0006 E0011 E0015'),
    ('수치가 있는 곳', '주체·속성·값·단위·조건을 함께 검증하고 다른 Fact의 숫자를 재사용하지 않는다.', 'N0004 N0006 N0008 N0011'),
    ('기능·구성·호환을 주장하는 곳', '각 장비의 역할·성능 인과·지원 범위를 추정하지 않는다.', 'K0004 K0009 P0006 C0004'),
    ('경험·기업 정책을 주장하는 곳', '실제 기록과 승인된 기업 자료에 연결한다.', 'X0004 X0006 X0011'),
    ('문체·분량', '친절한 경어체와 짧은 문단을 기본으로 한다. 2~3문장은 편집 목표이며 예외를 허용한다. 분량·H2 수는 조정할 수 있고 숫자를 맞추기 위한 군더더기나 제약 삭제는 금지한다.', 'S0251 S0253 S0255 S0257'),
]


def build():
    state = json.loads((ROOT / 'content-system/00_system/policy/workspace.json').read_text(encoding='utf-8'))
    atoms = {a['id']: a for a in state['atoms']}
    registry = {}

    def references(shorts):
        ids = []
        for short in shorts.split():
            aid = PREFIXES[short[0]] + '-V2N' + short[1:]
            a = atoms[aid]
            assert a.get('lifecycle') == 'active' and a.get('enabled', True) and a.get('kind') != 'reference', aid
            registry[aid] = {k: a.get(k) for k in ('id', 'revision', 'text', 'kind', 'purpose', 'condition', 'source')}
            ids.append(aid)
        return ids

    rows = []
    for role, element, label, when, summary, shorts in ROWS:
        policy_ids = references(shorts)
        bindings = []
        for aid in policy_ids:
            short = next(k + aid.split('-V2N')[1] for k, prefix in PREFIXES.items() if aid.startswith(prefix + '-V2N'))
            category = 'block_specific'
            condition = when
            if short.startswith('T') or short == 'S0027':
                category = 'planning_reference'
                condition = '독자 질문·범위를 기획할 때 참고. 이 원자를 제목이나 본문의 직접 표현 규칙으로 해석하지 않음'
            elif short.startswith(('E', 'N', 'C', 'X', 'P', 'K')):
                category = 'conditional_shared'
                condition = {'E':'기술 주장을 작성할 때', 'N':'수치·계산을 작성할 때', 'C':'설정·배선·호환·내부 구조를 설명할 때', 'X':'경험 또는 기업 정책·정체성을 주장할 때', 'P':'제품 지원 범위를 주장할 때', 'K':'장비 역할·조합 효과를 주장할 때'}[short[0]]
                if short in ('X0004', 'X0006', 'X0008', 'X0015'):
                    condition = '실제 경험·시험 결과 또는 설명용 가정을 서술할 때; 실제 경험은 기록 필요, 가정은 실증으로 쓰지 않음'
            elif short in ('S0181', 'S0183', 'S0078', 'S0228', 'B0048'):
                category = 'boundary_link'
                condition = '인접 블록과 정의·전제·결론·제품 설명을 연결하거나 중복을 점검할 때'
            elif short in ('S0230', 'R0059'):
                category = 'conditional_shared'
                condition = '남는 문제의 조건부 추가 장비를 실제로 제시할 때만 적용. 모든 다음 행동에 추천을 강제하지 않음'
            scope = atoms[aid].get('applies_to_elements', [])
            mismatch = element is not None and element not in scope and 'all_content' not in scope
            bindings.append({'policy_id': aid, 'category': category, 'apply_when': condition,
                             'registered_elements': scope,
                             'scope_alignment': 'semantic_mapping_extension' if mismatch else 'registered_or_dynamic_position',
                             'scope_note': '등록된 요소보다 넓게 원문 취지를 연결한 편집 참조이며 운영 scope 변경은 아님' if mismatch else ''})
        rows.append({'role_id': role, 'element': element, 'label': label, 'apply_when': when,
                     'summary': summary, 'policy_ids': policy_ids, 'rule_bindings': bindings,
                     'is_companion': role.startswith('companion.'), 'status': 'curated_existing_guide_mapping'})
    global_rules = [{'apply_when': when, 'summary': summary, 'policy_ids': references(refs)} for when, summary, refs in GLOBAL]
    data = {'schema_version': '1.1.0', 'workspace_revision': state['revision'],
            'status': 'design_reference_only', 'defines_order_or_count': False,
            'roles': rows, 'cross_cutting_rules': global_rules, 'policy_registry': registry,
            'companion_design_reference': 'product-recommendation.md',
            'note': '조건을 확인하여 적용한다. 현재 원자 메타데이터의 자동 묶음 대신 원문을 읽고 매칭한 참조표다. 운영 입력 조립에는 아직 연결하지 않았다.'}
    (DEST / 'paragraph-element-rules.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'static/paragraph-element-rules.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    md = ['# 문단 요소별 기존 가이드 규칙 매칭', '', f'기준: 정책 편집본 r{state["revision"]}. 기존 템플릿의 구성 요소를 유지하며 원문 규칙을 매칭했다. 문단 순서·개수나 독립 섹션을 새로 강제하지 않는다.', '',
          '본문 문제 제기는 `body.explanation` 안의 `body.problem_statement` 역할로 구분한다. 이 역할 ID는 조회용 구분이며 운영 요소 enum을 변경하지 않는다.', '',
            '규칙 연결은 블록 전용 / 조건부 공통 / 기획 참고 / 연결·중복 방지로 구분한다. 제품 인지·추천은 위치가 가변인 보조 블록이며 기존 운영 요소 enum을 추가하지 않는다. 등록된 원자 scope보다 넓게 연결한 경우 JSON에 편집 참조임을 표시한다.', '',
            '## 요소별 적용 규칙', '', '| 요소·역할 | 적용 시점 | 기존 가이드 요약 | 정책 ID |', '|---|---|---|---|']
    for r in rows:
        md.append(f'| {r["label"]} (`{r["role_id"]}`) | {r["apply_when"]} | {r["summary"]} | ' + '<br>'.join(r['policy_ids']) + ' |')
    md += ['', '## 조건에 따라 함께 적용하는 공통 규칙', '', '| 조건 | 규칙 | 정책 ID |', '|---|---|---|']
    for g in global_rules:
        md.append(f'| {g["apply_when"]} | {g["summary"]} | ' + '<br>'.join(g['policy_ids']) + ' |')
    md += ['', '## 제품 보조 노드', '',
           '- 제품 인지: 기존 제품 기본 설명·근거·링크 규칙을 적용한다. 구매 권유를 추가하지 않는 선택·배치·중복 방지 규칙은 [제품 추천 설계안](product-recommendation.md)을 참조한다.',
           '- 제품 추천: 기존 기본 구성·대안·조건부 추가·호환·링크 규칙을 적용한다. 제품 개수와 묶음 계약은 별도 신규 설계안이다.',
           '- 두 배치 선택(본문 설명·점검 뒤 / 다음 행동·상담)은 기존 [보조 노드 설계](companion-nodes.md)를 따른다. 새로 승인된 원문 규칙으로 가장하지 않는다.', '',
           '## 원문·조건 확인', '', '아래 목록은 매칭한 원자의 실제 본문이다. 위의 요약으로 원문 조건을 대체하지 않는다. 원문 경로·행·해시·정책 revision은 JSON에 함께 저장했다. 원문이나 workspace revision이 변경되면 이 참조표를 다시 생성하고 의미 변경을 검토한다.', '']
    for aid, a in registry.items():
        src = a.get('source') or {}
        md += [f'### {aid}', '', a['text'], '', f'출처: `{src.get("path", "")}` · {src.get("line", "")}행 · 정책 revision {a["revision"]}', '']
    (DEST / 'paragraph-element-rules.md').write_text('\n'.join(md), encoding='utf-8')
    return data


if __name__ == '__main__':
    result = build()
    print(f'{len(result["roles"])} roles, {len(result["policy_registry"])} source policies; workspace r{result["workspace_revision"]}')
