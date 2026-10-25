# 문단 요소별 기존 가이드 규칙 매칭

기준: 정책 편집본 r27. 기존 템플릿의 구성 요소를 유지하며 원문 규칙을 매칭했다. 문단 순서·개수나 독립 섹션을 새로 강제하지 않는다.

본문 문제 제기는 `body.explanation` 안의 `body.problem_statement` 역할로 구분한다. 이 역할 ID는 조회용 구분이며 운영 요소 enum을 변경하지 않는다.

규칙 연결은 블록 전용 / 조건부 공통 / 기획 참고 / 연결·중복 방지로 구분한다. 제품 인지·추천은 위치가 가변인 보조 블록이며 기존 운영 요소 enum을 추가하지 않는다. 등록된 원자 scope보다 넓게 연결한 경우 JSON에 편집 참조임을 표시한다.

## 요소별 적용 규칙

| 요소·역할 | 적용 시점 | 기존 가이드 요약 | 정책 ID |
|---|---|---|---|
| 제목 (`title`) | 모든 유형 | 독자의 문제·선택 고민과 이번 글의 범위를 드러낸다. 기술 수치·효과를 제목에 썼다면 근거도 필요하다. | GUIDE-01-TOPIC-V2N0026<br>GUIDE-01-TOPIC-V2N0027<br>GUIDE-01-TOPIC-V2N0028<br>RULE-EVIDENCE-BOUNDARY-V2N0004 |
| 시작 인사 (`opening.greeting`) | 공통 도입 | 공식 총판 오우션으로 정중하게 인사한다. 인사·기업 안내는 장비 스펙 Fact와 구분한다. | RULE-OCEANTECH-BRAND-LINKS-V2N0016<br>RULE-OCEANTECH-BRAND-LINKS-V2N0037 |
| B2B 상담·데모 안내 (`opening.business_notice`) | 공통 도입 | 승인된 견적·데모 지원 범위를 자연스럽게 안내한다. 무료 대여·설치·무조건 제공 등 약속을 확대하지 않는다. | RULE-OCEANTECH-BRAND-LINKS-V2N0020<br>RULE-OCEANTECH-BRAND-LINKS-V2N0023<br>RULE-EXPERIENCE-BUSINESS-V2N0011 |
| 고민 공감·주제 예고 (`opening.problem_topic`) | 공통 도입 | 실무자의 구체적 고민에서 주제로 연결한다. 기계적인 “오늘은 … 알아보겠습니다”나 모든 글의 동일한 고충 문장을 반복하지 않는다. | RULE-OCEANTECH-BRAND-LINKS-V2N0026<br>RULE-OCEANTECH-BRAND-LINKS-V2N0028<br>GUIDE-03-STRUCTURE-V2N0130<br>GUIDE-03-STRUCTURE-V2N0132 |
| 첫 문의 문구·배너 (`opening.inquiry_banner`) | 공통 도입 | 지정 문의 문구와 클릭 가능한 승인 배너를 배치한다. 제품 설명용 자산과 별도로 계획한다. | RULE-OCEANTECH-BRAND-LINKS-V2N0031<br>RULE-OCEANTECH-BRAND-LINKS-V2N0106<br>RULE-OCEANTECH-BRAND-LINKS-V2N0108<br>GUIDE-04-IMAGES-V2N0004<br>GUIDE-04-IMAGES-V2N0008 |
| 본문 연결 (`opening.transition`) | 앞의 고민에서 본문으로 연결할 때 | 독자의 궁금증과 기술 설명을 잇는다. 공통 전제는 초반 핵심 답에서 한 번 밝히며, 연결 문장에서 다시 길게 설명하지 않는다. | RULE-OCEANTECH-BRAND-LINKS-V2N0034 |
| 공통 전제·초반 핵심 답 (`opening.answer`) | 공통 시작의 답 제시 | 이번 글이 답할 질문과 조건부 핵심 답을 제시한다. 근거가 없으면 확정 결론을 약속하지 않는다. | GUIDE-03-STRUCTURE-V2N0134<br>GUIDE-03-STRUCTURE-V2N0136<br>GUIDE-03-STRUCTURE-V2N0078 |
| 본문 문제 제기 (`body.problem_statement`) | 유형별 첫 문제·선택 고민 설명 | 구체적인 장면과 불편, 원하는 변화를 설명한다. 고객의 문제보다 제품·포트 나열을 앞세우지 않고, 가정은 관찰 사실과 구분한다. | GUIDE-03-STRUCTURE-V2N0022<br>GUIDE-03-STRUCTURE-V2N0027<br>GUIDE-03-STRUCTURE-V2N0130<br>GUIDE-03-STRUCTURE-V2N0031 |
| 제품·기능 기본 설명 (`body.definition`) | 제품 또는 기능을 처음 실질적으로 소개할 때 | 무엇인가 → 어떤 불편에 필요한가 → 이번 구성의 역할로 설명한다. 기능 비교 전에 기본 의미를 소개하되 고정 용어 사전 장을 필수로 만들지 않는다. | GUIDE-03-STRUCTURE-V2N0036<br>GUIDE-03-STRUCTURE-V2N0179<br>GUIDE-03-STRUCTURE-V2N0181<br>GUIDE-03-STRUCTURE-V2N0183 |
| 질문별 기능·해결 설명 (`body.explanation`) | 해당 독자 질문을 설명할 때 | 한 덩어리는 한 질문에 답한다. 필요한 Fact와 판단을 연결하고 확인된 기능·조건을 쉬운 말로 직접 설명한다. 내부 검토 지시는 독자 본문에 쓰지 않는다. | GUIDE-03-STRUCTURE-V2N0151<br>GUIDE-03-STRUCTURE-V2N0153<br>GUIDE-03-STRUCTURE-V2N0201<br>GUIDE-03-STRUCTURE-V2N0199 |
| 원리·이유 설명 (`body.principle`) | 원리를 알아야 질문에 답하거나 선택할 수 있을 때 | 필요한 원리와 용어만 설명한다. 근거 없는 내부 알고리즘을 추정하지 않고, 수치가 들어가면 값·단위·적용 조건을 보존한다. | GUIDE-03-STRUCTURE-V2N0153<br>GUIDE-03-STRUCTURE-V2N0260<br>RULE-CONFIGURATION-SOURCE-V2N0008<br>RULE-NUMERIC-SCOPE-V2N0004 |
| 스펙 해석 (`body.specification`) | 스펙이 구매 판단 또는 사용 제약에 필요할 때 | 관련 없는 스펙은 생략하되 중요한 제약은 남긴다. 최대/권장·반경/직경·수평/대각선 화각을 구분한다. | RULE-READER-STYLE-V2N0008<br>GUIDE-03-STRUCTURE-V2N0038<br>RULE-NUMERIC-SCOPE-V2N0004<br>RULE-NUMERIC-SCOPE-V2N0008 |
| 비교·선택 기준 (`body.comparison`) | 같은 결정 질문의 비교군을 다룰 때 | 동일 기준의 차이를 설명한다. 역할이 다른 장비를 대안으로 섞지 않고, 표에는 근거가 있는 동작·장면·조건만 넣는다. | GUIDE-03-STRUCTURE-V2N0049<br>GUIDE-03-STRUCTURE-V2N0065<br>GUIDE-03-STRUCTURE-V2N0083<br>GUIDE-03-STRUCTURE-V2N0186<br>GUIDE-03-STRUCTURE-V2N0188 |
| 구성·배선·사용 모습 (`body.configuration`) | 하나의 기본 구성을 설명할 때 | 이미 가진 장비와 도입 구성을 연결하고 역할·사용 모습을 설명한다. 제품·모드·플랫폼의 Fact와 공식 배선 자료로 확인하며 무관한 운영 분기를 늘리지 않는다. | GUIDE-03-STRUCTURE-V2N0027<br>GUIDE-03-STRUCTURE-V2N0049<br>GUIDE-03-STRUCTURE-V2N0040<br>GUIDE-03-STRUCTURE-V2N0069<br>RULE-CONFIGURATION-SOURCE-V2N0004 |
| 설정·점검·조치 (`body.setup`) | 설치·설정 또는 문제 해결 작업이 필요할 때 | 전제 조건 → 작업 순서 → 정상 확인 → 확인된 제약을 포함한다. 메뉴·옵션은 해당 제품/버전 자료를 확인한다. 설정·배치로 해결되면 구매를 강요하지 않는다. | GUIDE-03-STRUCTURE-V2N0024<br>GUIDE-03-STRUCTURE-V2N0087<br>RULE-CONFIGURATION-SOURCE-V2N0004<br>RULE-CONFIGURATION-SOURCE-V2N0011<br>RULE-READER-STYLE-V2N0033 |
| 실증·사례 (`body.case`) | 실제 경험·시험 기록이 있을 때 | 실제 경험·쇼룸 테스트·자체 측정은 기록이 있을 때만 쓴다. 가정은 문제 제기·원리 설명에서 가정임을 명시하며 실증 근거로 쓰지 않는다. | RULE-EXPERIENCE-BUSINESS-V2N0004<br>RULE-EXPERIENCE-BUSINESS-V2N0006<br>RULE-EXPERIENCE-BUSINESS-V2N0008<br>RULE-EXPERIENCE-BUSINESS-V2N0015<br>GUIDE-03-STRUCTURE-V2N0174 |
| 적용 조건·주의사항 (`body.conditions`) | 선택·지원·사용에 중요한 조건이 있을 때 | 확인된 범위·제약을 해당 설명과 연결한다. 모드·플랫폼·펌웨어·라이선스 차이를 지우거나 미확정 조건을 확정된 것처럼 바꾸지 않는다. | GUIDE-03-STRUCTURE-V2N0099<br>GUIDE-03-STRUCTURE-V2N0203<br>GUIDE-03-STRUCTURE-V2N0205<br>RULE-PLATFORM-SCOPE-V2N0006 |
| 조건부 추가 장비 (`body.extension`) | 기본 구성으로 해결되지 않는 문제가 남을 때 | 추가가 필요한 문제·역할·조건·근거를 설명한다. 실제 사진과 등록 링크를 연결하고 별도 절차는 독립 콘티로 분리할 수 있다. | RULE-READER-STYLE-V2N0059<br>RULE-READER-STYLE-V2N0061<br>GUIDE-03-STRUCTURE-V2N0089<br>GUIDE-03-STRUCTURE-V2N0091<br>GUIDE-03-STRUCTURE-V2N0093<br>GUIDE-03-STRUCTURE-V2N0207 |
| 제품 소개 링크 (`body.product_link`) | 각 제품의 실질적 설명 직후 | 해당 제품 ID의 원본 blog_url로 연결한다. 여러 제품은 각각 연결하고 불필요한 반복은 피한다. URL이 없거나 매칭이 모호하면 추정하지 않는다. | RULE-OCEANTECH-BRAND-LINKS-V2N0042<br>RULE-OCEANTECH-BRAND-LINKS-V2N0044<br>RULE-OCEANTECH-BRAND-LINKS-V2N0046<br>RULE-OCEANTECH-BRAND-LINKS-V2N0048<br>RULE-OCEANTECH-BRAND-LINKS-V2N0054<br>RULE-OCEANTECH-BRAND-LINKS-V2N0074<br>RULE-OCEANTECH-BRAND-LINKS-V2N0076 |
| 사진·GIF·도표·이미지 문구 (`media`) | 문단의 시각적 질문에 답할 자료를 계획할 때 | 질문에 맞는 공식/권리 확인 자체 자료를 먼저 찾는다. 상황 사진·설명 카드는 생성할 수 있지만 실제 제품·UI·시험 증거를 생성으로 대체하지 않는다. 초안은 Need ID, 최종 출력은 승인 binding을 쓴다. | GUIDE-04-IMAGES-V2N0031<br>GUIDE-04-IMAGES-V2N0032<br>GUIDE-04-IMAGES-V2N0033<br>GUIDE-04-IMAGES-V2N0035<br>GUIDE-04-IMAGES-V2N0037<br>GUIDE-04-IMAGES-V2N0039<br>GUIDE-04-IMAGES-V2N0098<br>GUIDE-04-IMAGES-V2N0011<br>GUIDE-04-IMAGES-V2N0019<br>GUIDE-03-STRUCTURE-V2N0210 |
| 핵심 답·구성 결론 회수 (`closing.summary`) | 공통 마감 | 초반 질문과 기본 구매·재사용·연결 결론을 짧게 회수한다. 끝에서 기본 결론을 바꾸는 새 스펙·기능을 갑자기 추가하지 않는다. | GUIDE-03-STRUCTURE-V2N0095<br>GUIDE-03-STRUCTURE-V2N0224<br>GUIDE-03-STRUCTURE-V2N0228<br>RULE-OCEANTECH-BRAND-LINKS-V2N0081 |
| 체크리스트·판단·다음 행동 (`closing.next_action`) | 공통 마감의 판단 안내 | 자기 환경에 맞는 판단 기준 또는 다음 행동을 제시한다. 불필요한 구매로 연결하지 않고, 조건부 부속은 역할·근거·사진·링크와 함께 짧게 제시할 수 있다. | GUIDE-03-STRUCTURE-V2N0226<br>GUIDE-03-STRUCTURE-V2N0120<br>GUIDE-03-STRUCTURE-V2N0097<br>GUIDE-03-STRUCTURE-V2N0230 |
| 가치 요약·소회 (`closing.appreciation`) | 공통 마감 | 독자의 선택 고민에 보탬이 되길 바라는 소회를 자연스럽게 적는다. 고정된 맺음 문구를 그대로 복제하지 않는다. | RULE-OCEANTECH-BRAND-LINKS-V2N0086<br>RULE-OCEANTECH-BRAND-LINKS-V2N0083 |
| 상담·데모 연결 (`closing.consultation`) | 공통 마감 | 공간·예산·회의실 조건에 맞는 기술 상담과 데모 문의로 연결한다. 무료 제공·실적·상담 범위를 임의로 약속하지 않는다. | RULE-OCEANTECH-BRAND-LINKS-V2N0087<br>GUIDE-03-STRUCTURE-V2N0242<br>RULE-EXPERIENCE-BUSINESS-V2N0011 |
| 맺음 인사 (`closing.greeting`) | 공통 마감 | 공식 총판 팀으로 정중하고 따뜻하게 인사한다. 분위기를 유지하되 고정 예문을 그대로 복제하지 않는다. | RULE-OCEANTECH-BRAND-LINKS-V2N0088<br>RULE-OCEANTECH-BRAND-LINKS-V2N0083<br>GUIDE-03-STRUCTURE-V2N0240 |
| 마지막 문의 문구·배너 (`closing.inquiry_banner`) | 마지막 인사 바로 뒤 | 도입과 동일한 지정 문의 문구·클릭 가능한 승인 배너를 둔다. 중복 제거로 한쪽을 지우거나 다른 이미지로 대체하지 않는다. | GUIDE-03-STRUCTURE-V2N0238<br>RULE-OCEANTECH-BRAND-LINKS-V2N0091<br>RULE-OCEANTECH-BRAND-LINKS-V2N0100<br>RULE-OCEANTECH-BRAND-LINKS-V2N0102<br>RULE-OCEANTECH-BRAND-LINKS-V2N0106<br>RULE-OCEANTECH-BRAND-LINKS-V2N0110 |
| 제품 인지 보조 블록 (`companion.product_awareness`) | 제품 인지를 선택했으며 기존 설명과 중복되지 않을 때 | 이름·기본 역할·주제와의 관련성·근거·소개 링크를 연결한다. 구매를 권하는 뜻으로 바꾸지 않는다. 본문에서 이미 정의했다면 재정의하지 않는다. | GUIDE-03-STRUCTURE-V2N0036<br>GUIDE-03-STRUCTURE-V2N0179<br>RULE-OCEANTECH-BRAND-LINKS-V2N0042<br>RULE-OCEANTECH-BRAND-LINKS-V2N0046<br>RULE-OCEANTECH-BRAND-LINKS-V2N0048 |
| 제품 추천 보조 블록 (`companion.product_recommendation`) | 확인된 구매·도입·사용·재사용 요구가 있고 제품 추천을 선택했을 때 | 추천 이유·적합 조건·제약·근거·링크와 도입/사용/재사용 행동을 제품별로 연결한다. 대안·함께 쓰는 구성·조건부 추가를 구분하고 본문 추천을 반복하지 않는다. | GUIDE-03-STRUCTURE-V2N0081<br>GUIDE-03-STRUCTURE-V2N0083<br>RULE-READER-STYLE-V2N0033<br>RULE-READER-STYLE-V2N0059<br>GUIDE-03-STRUCTURE-V2N0230<br>RULE-COMPONENT-ROLE-V2N0004<br>RULE-COMPONENT-ROLE-V2N0009<br>RULE-PLATFORM-SCOPE-V2N0006<br>RULE-OCEANTECH-BRAND-LINKS-V2N0046<br>RULE-OCEANTECH-BRAND-LINKS-V2N0048 |

## 조건에 따라 함께 적용하는 공통 규칙

| 조건 | 규칙 | 정책 ID |
|---|---|---|
| 기술 주장이 있는 곳 | 제목·본문·표·캡션·이미지 문구의 기술 주장을 Fact와 공식 위치에 연결한다. | RULE-EVIDENCE-BOUNDARY-V2N0004<br>RULE-EVIDENCE-BOUNDARY-V2N0006<br>RULE-EVIDENCE-BOUNDARY-V2N0011<br>RULE-EVIDENCE-BOUNDARY-V2N0015 |
| 수치가 있는 곳 | 주체·속성·값·단위·조건을 함께 검증하고 다른 Fact의 숫자를 재사용하지 않는다. | RULE-NUMERIC-SCOPE-V2N0004<br>RULE-NUMERIC-SCOPE-V2N0006<br>RULE-NUMERIC-SCOPE-V2N0008<br>RULE-NUMERIC-SCOPE-V2N0011 |
| 기능·구성·호환을 주장하는 곳 | 각 장비의 역할·성능 인과·지원 범위를 추정하지 않는다. | RULE-COMPONENT-ROLE-V2N0004<br>RULE-COMPONENT-ROLE-V2N0009<br>RULE-PLATFORM-SCOPE-V2N0006<br>RULE-CONFIGURATION-SOURCE-V2N0004 |
| 경험·기업 정책을 주장하는 곳 | 실제 기록과 승인된 기업 자료에 연결한다. | RULE-EXPERIENCE-BUSINESS-V2N0004<br>RULE-EXPERIENCE-BUSINESS-V2N0006<br>RULE-EXPERIENCE-BUSINESS-V2N0011 |
| 문체·분량 | 친절한 경어체와 짧은 문단을 기본으로 한다. 2~3문장은 편집 목표이며 예외를 허용한다. 분량·H2 수는 조정할 수 있고 숫자를 맞추기 위한 군더더기나 제약 삭제는 금지한다. | GUIDE-03-STRUCTURE-V2N0251<br>GUIDE-03-STRUCTURE-V2N0253<br>GUIDE-03-STRUCTURE-V2N0255<br>GUIDE-03-STRUCTURE-V2N0257 |

## 제품 보조 노드

- 제품 인지: 기존 제품 기본 설명·근거·링크 규칙을 적용한다. 구매 권유를 추가하지 않는 선택·배치·중복 방지 규칙은 [제품 추천 설계안](product-recommendation.md)을 참조한다.
- 제품 추천: 기존 기본 구성·대안·조건부 추가·호환·링크 규칙을 적용한다. 제품 개수와 묶음 계약은 별도 신규 설계안이다.
- 두 배치 선택(본문 설명·점검 뒤 / 다음 행동·상담)은 기존 [보조 노드 설계](companion-nodes.md)를 따른다. 새로 승인된 원문 규칙으로 가장하지 않는다.

## 원문·조건 확인

아래 목록은 매칭한 원자의 실제 본문이다. 위의 요약으로 원문 조건을 대체하지 않는다. 원문 경로·행·해시·정책 revision은 JSON에 함께 저장했다. 원문이나 workspace revision이 변경되면 이 참조표를 다시 생성하고 의미 변경을 검토한다.

### GUIDE-01-TOPIC-V2N0026

1. 누구의 어떤 문제에 답할 것인가?


출처: `content-system/02_writer_ai/authoring/01-topic-and-keywords.md` · 15행 · 정책 revision 4

### GUIDE-01-TOPIC-V2N0027

2. 독자가 읽고 어떤 선택/설정을 할 수 있어야 하는가?


출처: `content-system/02_writer_ai/authoring/01-topic-and-keywords.md` · 16행 · 정책 revision 4

### GUIDE-01-TOPIC-V2N0028

3. 이번 글에서 다루지 않을 범위는 무엇인가?


출처: `content-system/02_writer_ai/authoring/01-topic-and-keywords.md` · 17행 · 정책 revision 4

### RULE-EVIDENCE-BOUNDARY-V2N0004

제목·본문·표·캡션·이미지 문구의 기술 주장은 선택된 Fact와 공식 source locator에 연결한다.

출처: `content-system/02_writer_ai/authoring/rules/evidence-boundary.md` · 5행 · 정책 revision 3

### RULE-OCEANTECH-BRAND-LINKS-V2N0016

   - 로지텍 화상회의 공식 수입 총판인 **(주)오우션 테크놀러지**로서 신뢰감 있고 정중하게 인사한다.

출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 12행 · 정책 revision 4

### RULE-OCEANTECH-BRAND-LINKS-V2N0037

인사말과 문의 안내는 오우션 테크놀러지의 기업 브랜딩 및 상담 안내이며, 장비 스펙 Fact로 취급하지 않는다.

출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 26행 · 정책 revision 4

### RULE-OCEANTECH-BRAND-LINKS-V2N0020

   - 기업 고객(B2B) 대상 전용 견적 상담과 데모 장비 시연/테스트 지원이 상시 가능하다는 점을 자연스럽게 녹여낸다.

출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 15행 · 정책 revision 4

### RULE-OCEANTECH-BRAND-LINKS-V2N0023

   - *주의*: 무료 대여·무료 설치·무조건 제공 등 근거 없는 약속으로 과장하지 않는다.

출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 17행 · 정책 revision 6

### RULE-EXPERIENCE-BUSINESS-V2N0011

상담 범위, 할인, 무상 대여, 무료 진단, 총판 자격 등 기업 정책과 정체성 표현은 승인된 기업 자료를 참조한다.

출처: `content-system/02_writer_ai/authoring/rules/experience-and-business.md` · 7행 · 정책 revision 3

### RULE-OCEANTECH-BRAND-LINKS-V2N0026

   - 기계적인 "`오늘은 {주제}에 대해서 알아보도록 하겠습니다.`" 식의 틀에 박힌 표현을 지양한다.

출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 19행 · 정책 revision 4

### RULE-OCEANTECH-BRAND-LINKS-V2N0028

   - 실무자나 IT 담당자가 현업에서 겪는 회의실 이슈(화각 한계, 화자 추적 오작동, 배선 꼬임 등)를 부드럽게 짚으며 이번 글에서 다룰 핵심 해법으로 자연스럽게 이끈다.

출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 20행 · 정책 revision 4

### GUIDE-03-STRUCTURE-V2N0130

- 검색자가 처한 구체적인 상황을 일상어로 짚는다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 58행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0132

모든 글을 동일한 회의실 고충 문장으로 시작하지 않는다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 58행 · 정책 revision 5

### RULE-OCEANTECH-BRAND-LINKS-V2N0031

   - 아래 승인된 공식 문의 문구와 클릭 가능한 문의 배너 이미지(`{{asset:oceantech-inquiry-opening}}`)를 배치한다.

출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 22행 · 정책 revision 4

### RULE-OCEANTECH-BRAND-LINKS-V2N0106

- 배너 이미지를 클릭하면 문의 페이지가 열려야 한다.

출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 57행 · 정책 revision 4

### RULE-OCEANTECH-BRAND-LINKS-V2N0108

이미지 단독 삽입이나 문의 텍스트 링크만으로 대체하지 않는다.

출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 57행 · 정책 revision 4

### GUIDE-04-IMAGES-V2N0004

사용자 지정 [오우션 문의 배너](rules/oceantech-brand-and-links.md)는 도입부와 마지막 인사 뒤의 필수 공통 자산이다.

출처: `content-system/02_writer_ai/authoring/04-images.md` · 5행 · 정책 revision 4

### GUIDE-04-IMAGES-V2N0008

제품 설명용 이미지와 별도로 계획하며, 지정 HTML·URL을 가이드에서 읽어 바인딩한다.

출처: `content-system/02_writer_ai/authoring/04-images.md` · 5행 · 정책 revision 4

### RULE-OCEANTECH-BRAND-LINKS-V2N0034

   - 독자의 궁금증과 실제 장비/기술 원리 설명으로 매끄럽게 연결한다.

출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 24행 · 정책 revision 4

### GUIDE-03-STRUCTURE-V2N0134

- 첫 부분에서 이번 글이 답할 질문과 조건부 핵심 답을 준다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 59행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0136

답을 낼 근거가 없으면 확정 결론을 약속하지 않는다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 59행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0078

- 전제로 고정한 항목은 도입에서 짧게 밝힌다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 35행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0022

자료의 노드·포트 순서를 그대로 본문 순서로 옮기면 설치 절차가 앞서고 구매 이유가 사라지므로, 먼저 고객의 불편과 원하는 변화를 정한다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 11행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0027

기획 AI는 **고객이 겪는 장면 / 구체적인 불편 / 원하는 변화 / 이미 가진 장비·운영 방식 / 기능이 문제에 답하는 이유 / 기본 구성 결론**을 기존 Strategy의 독자 질문·본문 계획·필수 내용에 기록한다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 13행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0031

실재 사례가 없으면 가정한 장면으로 쓰고 실제 고객 경험으로 꾸미지 않는다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 13행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0036

제품 설명은 “무엇인가 → 어떤 불편에 필요한가 → 이번 구성에서 맡는 역할”로 연결한다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 15행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0179

제품을 처음 접하는 독자가 이해할 수 있도록 “어떤 장비인가 / 무엇을 하는 기능인가 / 고객의 불편과 어떤 관계가 있는가”를 필요한 위치에서 설명한다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 82행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0181

고객 문제보다 앞에 모든 용어 정의를 모아 놓는 고정 개요 장은 요구하지 않는다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 82행 · 정책 revision 6

### GUIDE-03-STRUCTURE-V2N0183

기능을 비교하기 전에 각 기능의 기본 의미가 소개되어 있으면 된다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 82행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0151

한 덩어리는 한 질문을 해결한다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 66행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0153

설명에는 필요한 Fact만 쓰고, 독자가 어떤 판단을 할 수 있는지 연결한다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 66행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0201

확인된 기능과 조건은 쉬운 말로 직접 설명한다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 88행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0199

“검토할 항목으로 남깁니다”, “향상의 근거로 삼지 않습니다”처럼 작성자에게 주는 검토 지시를 본문으로 출력하지 않는다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 88행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0260

전문용어는 설명과 함께 도입하고, 무조건적 찬사·정확도·무오작동·업계 보급률 주장은 근거 없으면 쓰지 않는다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 106행 · 정책 revision 5

### RULE-CONFIGURATION-SOURCE-V2N0008

문서에 없는 내부 알고리즘이나 연결 구조를 그럴듯하게 채우지 않는다.

출처: `content-system/02_writer_ai/authoring/rules/configuration-source.md` · 5행 · 정책 revision 3

### RULE-NUMERIC-SCOPE-V2N0004

제품/부품 + 속성 + 값 + 단위 + 적용 조건 전체가 근거와 일치해야 한다.

출처: `content-system/02_writer_ai/authoring/rules/numeric-scope.md` · 5행 · 정책 revision 3

### RULE-READER-STYLE-V2N0008

관련 없는 스펙은 생략하되 선택에 필요한 제한 조건은 남긴다.

출처: `content-system/02_writer_ai/authoring/rules/reader-and-style.md` · 5행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0038

케이블·포트·버전은 구매 판단이나 사용 제약에 필요한 만큼 남긴다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 15행 · 정책 revision 5

### RULE-NUMERIC-SCOPE-V2N0008

최대와 권장, 반경과 직경, 수평과 대각선 화각, 수음과 카메라 동작 거리를 구분한다.

출처: `content-system/02_writer_ai/authoring/rules/numeric-scope.md` · 5행 · 정책 revision 3

### GUIDE-03-STRUCTURE-V2N0049

구성·설치 글은 하나의 기본 구성을 설명하고, 비교 글은 같은 결정 질문에 답하는 비교군을 다룬다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 21행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0065

Sight는 촬영 시점, Mic Pod는 수음 확장, Tap IP는 회의 조작 등 역할이 다르므로 같은 구매 비교표의 대안으로 나열하지 않는다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 30행 · 정책 revision 7

### GUIDE-03-STRUCTURE-V2N0083

같은 기준으로 비교할 수 없는 장비를 동급 대안으로 취급하지 않는다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 36행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0186

구매 이유가 두 기능의 차이에 기대는 경우에는 명칭만 언급하지 않고 동일 기준의 차이를 설명한다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 84행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0188

비교표가 이해를 돕는다면 동작, 화면 구성, 사용 장면, 적용 조건 중 근거가 있는 항목으로 표를 만든다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 84행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0040

다이어그램으로 확인한 내부 컴퓨팅과 회의 앱 실행 위치 등은 구성 오류를 막는 근거로 활용하되, 이번 글의 전제와 다른 운영 방식을 모두 소개하지 않는다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 15행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0069

실제 적용은 선택한 제품·모드·플랫폼의 Fact와 배선 자료로 확인한다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 30행 · 정책 revision 5

### RULE-CONFIGURATION-SOURCE-V2N0004

메뉴 경로·옵션·배선·호환 연결은 해당 제품/버전 공식 자료를 확인하고 쓴다.

출처: `content-system/02_writer_ai/authoring/rules/configuration-source.md` · 5행 · 정책 revision 3

### GUIDE-03-STRUCTURE-V2N0024

설치·설정 자체가 검색 의도인 글은 그 목적에 맞는 절차를 제공한다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 11행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0087

설치 글은 연결 순서와 동작 확인을 중심으로 조정한다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 37행 · 정책 revision 5

### RULE-CONFIGURATION-SOURCE-V2N0011

독자가 실행할 절차에는 전제 조건, 작업 순서, 정상 확인 방법, 확인된 제약을 포함한다.

출처: `content-system/02_writer_ai/authoring/rules/configuration-source.md` · 7행 · 정책 revision 3

### RULE-READER-STYLE-V2N0033

문제가 설정·배치 조정으로 해결되면 구매를 강요하지 않는다.

출처: `content-system/02_writer_ai/authoring/rules/reader-and-style.md` · 17행 · 정책 revision 6

### RULE-EXPERIENCE-BUSINESS-V2N0004

실제 설치·납품·고객 사례·쇼룸 테스트·자체 측정은 해당 기록이 있을 때만 경험 사실로 쓴다.

출처: `content-system/02_writer_ai/authoring/rules/experience-and-business.md` · 5행 · 정책 revision 3

### RULE-EXPERIENCE-BUSINESS-V2N0006

고객사 사례를 쓸 수 없다는 이유로 본사 쇼룸 실증을 만들어 쓰지 않는다.

출처: `content-system/02_writer_ai/authoring/rules/experience-and-business.md` · 5행 · 정책 revision 3

### RULE-EXPERIENCE-BUSINESS-V2N0008

설명용 예시는 실제 관찰 결과와 구분한다.

출처: `content-system/02_writer_ai/authoring/rules/experience-and-business.md` · 5행 · 정책 revision 3

### RULE-EXPERIENCE-BUSINESS-V2N0015

숫자가 붙은 테스트 결과는 테스트 기록과 조건도 필요하다.

출처: `content-system/02_writer_ai/authoring/rules/experience-and-business.md` · 7행 · 정책 revision 3

### GUIDE-03-STRUCTURE-V2N0174

설명용 가상 상황은 가정임을 명시하고 관찰 사실처럼 쓰지 않는다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 78행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0099

미확정 지원 조건은 숨기지 않는다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 39행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0203

확인되지 않은 범위는 조사·관리자 항목에 기록하고, 본문은 확인된 범위로 좁힌다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 88행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0205

독자의 실제 선택에 중요한 미확정 조건은 숨기거나 표현만 바꿔 확정 사실처럼 만들지 않는다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 88행 · 정책 revision 5

### RULE-PLATFORM-SCOPE-V2N0006

제품명이나 기능명이 같아도 플랫폼·실행 모드·펌웨어·라이선스 조건이 다르면 동일하게 지원된다고 추정하지 않는다.

출처: `content-system/02_writer_ai/authoring/rules/platform-scope.md` · 5행 · 정책 revision 5

### RULE-READER-STYLE-V2N0059

추가 부속은 남는 문제가 있을 때만 제시한다.

출처: `content-system/02_writer_ai/authoring/rules/reader-and-style.md` · 23행 · 정책 revision 6

### RULE-READER-STYLE-V2N0061

결론에서 처음 등장하는 부속도 제품명만 던지지 않고 보완할 문제·역할·근거를 짧게 설명하며, 별도의 구매 분기를 늘리지 않는다.

출처: `content-system/02_writer_ai/authoring/rules/reader-and-style.md` · 23행 · 정책 revision 6

### GUIDE-03-STRUCTURE-V2N0089

- 추가 장비는 “어떤 문제가 남을 때 필요한가”와 함께 짧게 설명한다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 38행 · 정책 revision 7

### GUIDE-03-STRUCTURE-V2N0091

해당 부속의 실제 사진과 등록된 제품 소개 URL을 함께 계획한다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 38행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0093

추가 설명이 별도의 구성·설정 절차를 요구하면 상세 절차를 독립 콘티로 분리하되, 구매 판단에 필요한 짧은 설명까지 삭제하지 않는다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 38행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0207

추가 장비는 내부 금지 규정 대신 해당 장비가 실제로 보완하는 문제와 역할을 설명한다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 88행 · 정책 revision 5

### RULE-OCEANTECH-BRAND-LINKS-V2N0042

- 제품을 설명하는 문단 바로 다음에 해당 제품의 Blog Manager `blog_url` 링크를 넣는다.

출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 30행 · 정책 revision 4

### RULE-OCEANTECH-BRAND-LINKS-V2N0044

문구는 `관련 제품 소개: {제품명}`처럼 대상이 명확하도록 쓴다.

출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 30행 · 정책 revision 4

### RULE-OCEANTECH-BRAND-LINKS-V2N0046

- 여러 제품을 설명하면 제품별 링크를 각각 배치한다.

출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 31행 · 정책 revision 6

### RULE-OCEANTECH-BRAND-LINKS-V2N0048

같은 제품이 반복 등장하면 첫 실질적 설명 문단에 한 번 배치하고, 독립된 후속 설명에서 다시 필요할 때만 반복한다.

출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 31행 · 정책 revision 6

### RULE-OCEANTECH-BRAND-LINKS-V2N0054

제품 ID로 정확히 매칭하고, 이름이 모호하면 관리자 확인사항으로 남긴다.

출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 32행 · 정책 revision 4

### RULE-OCEANTECH-BRAND-LINKS-V2N0074

원본 미로딩, URL 누락, 미발행 또는 매칭 실패 시 URL을 추정하지 않는다.

출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 36행 · 정책 revision 4

### RULE-OCEANTECH-BRAND-LINKS-V2N0076

해당 제품 링크를 미해결 항목으로 남겨 관리자에게 노출하고 발행 전 보완한다.

출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 36행 · 정책 revision 4

### GUIDE-04-IMAGES-V2N0031

1. 현재 질문과 제품·기능·버전이 맞는 승인된 공식 이미지/GIF/매뉴얼 화면 확인.


출처: `content-system/02_writer_ai/authoring/04-images.md` · 13행 · 정책 revision 4

### GUIDE-04-IMAGES-V2N0032

2. 사용 권한과 실증 기록이 확인된 자체 자료 확인.


출처: `content-system/02_writer_ai/authoring/04-images.md` · 14행 · 정책 revision 4

### GUIDE-04-IMAGES-V2N0033

3. 적합한 자산이 없으면 문단의 시각적 질문에 따라 생성 요청을 고른다.

출처: `content-system/02_writer_ai/authoring/04-images.md` · 15행 · 정책 revision 4

### GUIDE-04-IMAGES-V2N0035

고객 상황·환경은 간단한 회의 모습 사진, 개념·차이·핵심 정리는 문단 내용에 맞는 한글 설명 카드로 계획한다.

출처: `content-system/02_writer_ai/authoring/04-images.md` · 15행 · 정책 revision 4

### GUIDE-04-IMAGES-V2N0037

공식 자료 부재만으로 모든 문단에 회의 사진을 자동 배치하지 않는다.

출처: `content-system/02_writer_ai/authoring/04-images.md` · 15행 · 정책 revision 4

### GUIDE-04-IMAGES-V2N0039

4. 공식 UI, 실제 제품 구조, 테스트 결과의 증거가 필요하면 생성으로 대체하지 않고 자료 요청.


출처: `content-system/02_writer_ai/authoring/04-images.md` · 16행 · 정책 revision 4

### GUIDE-04-IMAGES-V2N0098

- 실제 제품 소개는 공식 제품 사진, 실제 기능 설명은 공식 GIF·영상, 고객 문제와 환경은 생성 이미지로 역할을 구분한다.

출처: `content-system/02_writer_ai/authoring/04-images.md` · 40행 · 정책 revision 4

### GUIDE-04-IMAGES-V2N0011

초안 작성 시 문단별 시각적 질문을 정하고 `{{asset:NEED-ID}}`로 이미지 자리를 표시한다.

출처: `content-system/02_writer_ai/authoring/04-images.md` · 7행 · 정책 revision 4

### GUIDE-04-IMAGES-V2N0019

최종 출력은 Need ID에 연결된 승인된 Asset ID/revision만 사용한다.

출처: `content-system/02_writer_ai/authoring/04-images.md` · 7행 · 정책 revision 4

### GUIDE-03-STRUCTURE-V2N0210

이미지는 설명을 읽다가 ‘어떻게 생겼지/어떻게 다르지/어디에 연결하지’를 확인하는 지점에 둔다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 90행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0095

- 마무리는 기본 구매·재사용·연결 구성을 회수한다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 39행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0224

- 초반 질문에 대한 답을 짧게 회수한다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 96행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0228

기본 결론을 바꾸는 새 스펙·새 기능을 끝에서 갑자기 추가하지 않는다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 97행 · 정책 revision 5

### RULE-OCEANTECH-BRAND-LINKS-V2N0081

본문 핵심 내용을 2~3줄로 명쾌하게 요약한 뒤, 글의 분위기와 자연스럽게 이어지도록 마무리 인사말을 작성한다.

출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 40행 · 정책 revision 4

### GUIDE-03-STRUCTURE-V2N0226

- 독자가 자기 환경에서 판단할 기준 또는 다음 행동을 제시한다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 97행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0120

설치 글은 연결과 동작 확인, 비교·개념 글은 그 목적에 맞는 선택 기준이나 다음 판단이 남는지 확인한다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 52행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0097

설정·배치 조정만으로 해결되는 문제는 불필요한 구매로 연결하지 않는다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 39행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0230

남는 문제의 조건부 부속은 역할과 근거를 짧게 설명하고 실제 사진·소개 링크를 연결할 수 있다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 97행 · 정책 revision 5

### RULE-OCEANTECH-BRAND-LINKS-V2N0086

  1. **가치 요약 및 소회**: 이번 글에서 설명한 기술 원리/제품 비교가 독자의 회의실 설계나 제품 선택 고민을 덜어주는 데 실질적인 보탬이 되었기를 바라는 진정성 있는 멘트.


출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 43행 · 정책 revision 4

### RULE-OCEANTECH-BRAND-LINKS-V2N0083

**고정된 판에 박힌 멘트를 그대로 복제하지 않는다.**


출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 40행 · 정책 revision 4

### RULE-OCEANTECH-BRAND-LINKS-V2N0087

  2. **전문 컨설팅/데모 문의 연결**: 기업 회의실 규모, 현장 공간 구조, 예산 조건에 꼭 맞는 맞춤형 B2B 솔루션 및 데모 시연이 필요할 때 오우션 테크놀러지를 통해 전문 기술 상담을 받아볼 수 있음을 편안하게 권유.


출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 44행 · 정책 revision 4

### GUIDE-03-STRUCTURE-V2N0242

무료 제공, 납품 실적, 상담 범위를 임의로 약속하지 않는다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 99행 · 정책 revision 5

### RULE-OCEANTECH-BRAND-LINKS-V2N0088

  3. **맺음 인사**: 로지텍 공식 총판 오우션 테크놀러지 팀의 정중하고 따뜻한 맺음 인사.


출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 45행 · 정책 revision 4

### GUIDE-03-STRUCTURE-V2N0240

구체적인 인사말은 [공통 규칙](rules/oceantech-brand-and-links.md)을 따른다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 99행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0238

- 마지막 인사말 뒤에 도입부와 동일한 오우션 문의 문구·클릭 가능한 배너를 반드시 넣는다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 99행 · 정책 revision 5

### RULE-OCEANTECH-BRAND-LINKS-V2N0091

- 마무리 문단 바로 뒤에 승인된 공식 문의 배너(`{{asset:oceantech-inquiry-closing}}`)를 반드시 배치한다.

출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 48행 · 정책 revision 4

### RULE-OCEANTECH-BRAND-LINKS-V2N0100

- 도입부와 마무리 두 위치에 같은 배너를 사용한다.

출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 56행 · 정책 revision 4

### RULE-OCEANTECH-BRAND-LINKS-V2N0102

중복 제거로 한쪽을 지우지 않는다.

출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 56행 · 정책 revision 4

### RULE-OCEANTECH-BRAND-LINKS-V2N0110

다른 회사 이미지·생성 이미지로 대체하지 않는다.

출처: `content-system/02_writer_ai/authoring/rules/oceantech-brand-and-links.md` · 57행 · 정책 revision 4

### GUIDE-03-STRUCTURE-V2N0081

- 선택지는 **기본 구성 / 조건부 추가 / 다른 글에서 다룰 대안**으로 정리한다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 36행 · 정책 revision 7

### RULE-COMPONENT-ROLE-V2N0004

동일한 시스템에 연결되는 부품이라는 이유로 한 장비의 기능을 다른 장비에 부여하지 않는다.

출처: `content-system/02_writer_ai/authoring/rules/component-role.md` · 5행 · 정책 revision 5

### RULE-COMPONENT-ROLE-V2N0009

장비 추가가 다른 기능의 정확도나 성능을 높인다고 쓰려면 그 인과 관계의 별도 근거가 필요하다.

출처: `content-system/02_writer_ai/authoring/rules/component-role.md` · 7행 · 정책 revision 5

### RULE-EVIDENCE-BOUNDARY-V2N0006

의견, 설명용 가정, 자체 실증은 공식 스펙과 구분한다.

출처: `content-system/02_writer_ai/authoring/rules/evidence-boundary.md` · 5행 · 정책 revision 3

### RULE-EVIDENCE-BOUNDARY-V2N0011

매칭된 Fact가 없거나 scope가 다르면 미확인이다.

출처: `content-system/02_writer_ai/authoring/rules/evidence-boundary.md` · 7행 · 정책 revision 3

### RULE-EVIDENCE-BOUNDARY-V2N0015

핵심 근거가 없으면 조사 요청, 선택적 내용이면 삭제/유보와 이유 기록을 한다.

출처: `content-system/02_writer_ai/authoring/rules/evidence-boundary.md` · 7행 · 정책 revision 3

### RULE-NUMERIC-SCOPE-V2N0006

같은 숫자가 다른 Fact에 있다는 이유로 재사용하지 않는다.

출처: `content-system/02_writer_ai/authoring/rules/numeric-scope.md` · 5행 · 정책 revision 3

### RULE-NUMERIC-SCOPE-V2N0011

단위 변환은 계산과 원본 값을 추적 가능하게 남긴다.

출처: `content-system/02_writer_ai/authoring/rules/numeric-scope.md` · 7행 · 정책 revision 3

### GUIDE-03-STRUCTURE-V2N0251

기본은 친절한 경어체와 짧은 문단이다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 104행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0253

한 문단 2~3문장을 편집 목표로 삼되 내용상 필요한 예외를 허용한다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 104행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0255

2,000~3,000자와 H2 4~5개는 시작 목표로만 사용하며 검색 의도와 근거에 따라 Strategy에서 조정한다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 104행 · 정책 revision 5

### GUIDE-03-STRUCTURE-V2N0257

숫자를 맞추기 위한 군더더기나 중요 제약 삭제를 금지한다.

출처: `content-system/02_writer_ai/authoring/03-opening-body-closing.md` · 104행 · 정책 revision 5
