# 글 구성 블록별 작성 가이드

‘글 구성 블록’은 인사·문제 제기·제품 설명·점검·판단처럼 역할로 구분하는 작성 단위다. 문단은 표현 형식이고, 블록은 맡은 역할이다. 블록 수와 문단 수를 같게 강제하지 않는다.

한 블록마다 목적 → 필요한 입력 → 포함 내용 → 피할 내용 → 검토 질문을 정한다. 기존 가이드의 적용 조건과 정책 ID를 함께 보존한다. 아래 체크 질문·작성 지침은 기존 가이드를 구체화한 설계안이며 신규 운영 정책의 자동 승인이 아니다.

규칙 연결의 block_specific은 블록 전용, conditional_shared는 해당 내용을 쓸 때 적용하는 공통 규칙, planning_reference는 기획 근거, boundary_link는 다른 블록과의 연결·중복 방지다. 조건부 규칙을 모든 블록에 무조건 적용하지 않는다.

## 공통 기준

- 템플릿이 선택한 블록만 작성한다. 모든 블록을 모든 글에 넣지 않는다.
- 블록 목록은 순서가 아니다. 유형별 템플릿과 글별 독자 질문이 배치를 정한다.
- 입력이 부족하면 기술 사실·경험·URL을 만들어 채우지 않는다.
- 문단 2~3문장은 편집 목표이며 숫자를 맞추기 위해 제약을 삭제하지 않는다.
- 기술 주장·수치·호환·경험이 있는 블록에는 조건별 공통 규칙도 적용한다.
- 제품 인지·추천 보조 노드의 선택과 두 배치는 별도 companion 설계를 따른다.

## 블록별 가이드

### 제목 — `title`

- 목적: 어떤 문제·선택에 답하는 글인지 알린다
- 적용: 모든 유형
- 필요한 입력: 대표 검색어 / 독자 문제 / 글 범위 / 확인된 해법
- 작성 내용: 문제 또는 선택 고민과 다룰 범위를 드러낸다
- 피할 내용: 본문에 없는 해결 약속 / 근거 없는 최고·완벽·수치 효과
- 검토: 제목의 질문을 본문이 회수하는가? / 기술 주장을 제목에 썼다면 근거가 있는가?
- 기존 정책: GUIDE-01-TOPIC-V2N0026, GUIDE-01-TOPIC-V2N0027, GUIDE-01-TOPIC-V2N0028, RULE-EVIDENCE-BOUNDARY-V2N0004

- 규칙 연결: `GUIDE-01-TOPIC-V2N0026` · planning_reference · 독자 질문·범위를 기획할 때 참고. 이 원자를 제목이나 본문의 직접 표현 규칙으로 해석하지 않음
- 규칙 연결: `GUIDE-01-TOPIC-V2N0027` · planning_reference · 독자 질문·범위를 기획할 때 참고. 이 원자를 제목이나 본문의 직접 표현 규칙으로 해석하지 않음
- 규칙 연결: `GUIDE-01-TOPIC-V2N0028` · planning_reference · 독자 질문·범위를 기획할 때 참고. 이 원자를 제목이나 본문의 직접 표현 규칙으로 해석하지 않음
- 규칙 연결: `RULE-EVIDENCE-BOUNDARY-V2N0004` · conditional_shared · 기술 주장을 작성할 때

### 시작 인사 — `opening.greeting`

- 목적: 글의 작성 주체를 알린다
- 적용: 공통 도입
- 필요한 입력: 승인된 회사명·총판 정체성
- 작성 내용: 정중한 인사와 공식 총판 정체성
- 피할 내용: 장비 성능 홍보로 인사를 늘이기 / 회사 자격을 임의 변경
- 검토: 승인된 회사 표현과 일치하는가?
- 기존 정책: RULE-OCEANTECH-BRAND-LINKS-V2N0016, RULE-OCEANTECH-BRAND-LINKS-V2N0037

- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0016` · block_specific · 공통 도입
- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0037` · block_specific · 공통 도입

### B2B 상담·데모 안내 — `opening.business_notice`

- 목적: 독자가 이용할 수 있는 기업 지원을 알린다
- 적용: 공통 도입
- 필요한 입력: 승인된 B2B 견적·데모 안내
- 작성 내용: 주제와 자연스럽게 연결한 기업 지원 안내
- 피할 내용: 무료 대여·무료 설치·무조건 지원을 임의 약속
- 검토: 실제 승인된 지원 범위인가?
- 기존 정책: RULE-OCEANTECH-BRAND-LINKS-V2N0020, RULE-OCEANTECH-BRAND-LINKS-V2N0023, RULE-EXPERIENCE-BUSINESS-V2N0011

- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0020` · block_specific · 공통 도입
- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0023` · block_specific · 공통 도입
- 규칙 연결: `RULE-EXPERIENCE-BUSINESS-V2N0011` · conditional_shared · 경험 또는 기업 정책·정체성을 주장할 때

### 고민 공감·주제 예고 — `opening.problem_topic`

- 목적: 독자의 고민에 공감하고 다룰 주제를 예고한다
- 적용: 공통 도입
- 필요한 입력: 독자 역할 / 구체적 고민 / 이번 글의 질문
- 작성 내용: 상황과 불편을 짧게 연결한 주제 예고
- 피할 내용: 오늘은 … 알아보겠습니다의 기계적 반복 / 모든 글에 같은 회의실 고충
- 검토: 이번 주제만의 고민이 드러나는가? / 본문 문제 설명을 길게 선행 반복하지 않는가?
- 기존 정책: RULE-OCEANTECH-BRAND-LINKS-V2N0026, RULE-OCEANTECH-BRAND-LINKS-V2N0028, GUIDE-03-STRUCTURE-V2N0130, GUIDE-03-STRUCTURE-V2N0132

- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0026` · block_specific · 공통 도입
- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0028` · block_specific · 공통 도입
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0130` · block_specific · 공통 도입
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0132` · block_specific · 공통 도입

### 첫 문의 문구·배너 — `opening.inquiry_banner`

- 목적: 지정된 첫 문의 안내를 제공한다
- 적용: 공통 도입
- 필요한 입력: 승인된 문의 문구 / 배너 Need ID / 문의 페이지 binding
- 작성 내용: 승인 문구와 클릭 가능한 배너
- 피할 내용: 이미지 단독·텍스트 링크로 대체 / 생성한 회사 배너
- 검토: 배너와 클릭 대상이 승인 binding과 일치하는가?
- 기존 정책: RULE-OCEANTECH-BRAND-LINKS-V2N0031, RULE-OCEANTECH-BRAND-LINKS-V2N0106, RULE-OCEANTECH-BRAND-LINKS-V2N0108, GUIDE-04-IMAGES-V2N0004, GUIDE-04-IMAGES-V2N0008

- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0031` · block_specific · 공통 도입
- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0106` · block_specific · 공통 도입
- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0108` · block_specific · 공통 도입
- 규칙 연결: `GUIDE-04-IMAGES-V2N0004` · block_specific · 공통 도입
- 규칙 연결: `GUIDE-04-IMAGES-V2N0008` · block_specific · 공통 도입

### 본문 연결 — `opening.transition`

- 목적: 도입과 본문의 첫 질문을 잇는다
- 적용: 앞의 고민에서 본문으로 연결할 때
- 필요한 입력: 앞의 고민 / 첫 본문 질문
- 작성 내용: 짧은 연결 문장으로 본문으로 이어간다. 공통 전제는 초반 핵심 답에 맡긴다
- 피할 내용: 도입 전체를 다시 요약 / 무관한 장비 나열 / 공통 전제의 중복 설명
- 검토: 앞뒤 설명이 같은 질문을 향하는가? / 초반 답과 한 문단으로 자연스럽게 합칠 수 있는가?
- 기존 정책: RULE-OCEANTECH-BRAND-LINKS-V2N0034

- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0034` · block_specific · 앞의 고민에서 본문으로 연결할 때

### 공통 전제·초반 핵심 답 — `opening.answer`

- 목적: 무슨 조건에서 어떤 방향으로 답할지 알린다
- 적용: 공통 시작의 답 제시
- 필요한 입력: 핵심 질문 / 공통 전제(기존 장비·운영 방식·공간 조건) / 확인된 Fact / 적용 조건
- 작성 내용: 조건부 핵심 방향과 공통 전제를 한 번 설명한다. 앞에서 이미 밝힌 전제는 반복하지 않는다
- 피할 내용: 검증 전 확정 결론 / 본문 설명의 장황한 복제 / 전제 반복
- 검토: 초반 답과 최종 결론이 일치하는가? / 기존 장비·운영 방식의 전제가 본문과 일치하는가? / 확정하지 못한 범위를 단정하지 않았는가?
- 기존 정책: GUIDE-03-STRUCTURE-V2N0134, GUIDE-03-STRUCTURE-V2N0136, GUIDE-03-STRUCTURE-V2N0078

- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0134` · block_specific · 공통 시작의 답 제시
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0136` · block_specific · 공통 시작의 답 제시
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0078` · boundary_link · 인접 블록과 정의·전제·결론·제품 설명을 연결하거나 중복을 점검할 때

### 본문 문제 제기 — `body.problem_statement`

- 목적: 왜 이 내용을 읽어야 하는지 구체화한다
- 적용: 유형별 첫 문제·선택 고민 설명
- 필요한 입력: 사용 환경 / 관찰 또는 가정 구분 / 불편 / 원하는 변화
- 작성 내용: 문제 장면과 업무상 불편·필요한 변화
- 피할 내용: 제품을 먼저 판매 / 가상 상황을 고객 실화로 서술 / 초반 예고와 똑같은 반복
- 검토: 문제가 구체적인가? / 뒤의 해법이 이 문제에 답하는가?
- 기존 정책: GUIDE-03-STRUCTURE-V2N0022, GUIDE-03-STRUCTURE-V2N0027, GUIDE-03-STRUCTURE-V2N0130, GUIDE-03-STRUCTURE-V2N0031

- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0022` · block_specific · 유형별 첫 문제·선택 고민 설명
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0027` · planning_reference · 독자 질문·범위를 기획할 때 참고. 이 원자를 제목이나 본문의 직접 표현 규칙으로 해석하지 않음
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0130` · block_specific · 유형별 첫 문제·선택 고민 설명
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0031` · block_specific · 유형별 첫 문제·선택 고민 설명

### 제품·기능 기본 설명 — `body.definition`

- 목적: 처음 보는 제품·기능의 역할을 이해시킨다
- 적용: 제품 또는 기능을 처음 실질적으로 소개할 때
- 필요한 입력: 제품·기능 표준 ID / 기본 역할 Fact / 독자 문제
- 작성 내용: 무엇인가 → 어떤 불편에 필요한가 → 이번 구성의 역할. 첫 실질 설명에서 정의하고 인지 보조 블록에서 다시 길게 정의하지 않는다
- 피할 내용: 기능명만 나열 / 모든 용어를 앞에 모은 개요 장 강제 / 보조 블록과 같은 정의 반복
- 검토: 처음 보는 독자가 역할을 설명할 수 있는가? / 비교 전에 의미가 소개됐는가? / 인지 블록과 역할이 겹치지 않는가?
- 기존 정책: GUIDE-03-STRUCTURE-V2N0036, GUIDE-03-STRUCTURE-V2N0179, GUIDE-03-STRUCTURE-V2N0181, GUIDE-03-STRUCTURE-V2N0183

- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0036` · block_specific · 제품 또는 기능을 처음 실질적으로 소개할 때
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0179` · block_specific · 제품 또는 기능을 처음 실질적으로 소개할 때
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0181` · boundary_link · 인접 블록과 정의·전제·결론·제품 설명을 연결하거나 중복을 점검할 때
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0183` · boundary_link · 인접 블록과 정의·전제·결론·제품 설명을 연결하거나 중복을 점검할 때

### 질문별 기능·해결 설명 — `body.explanation`

- 목적: 한 질문에 기능·해법으로 답한다
- 적용: 해당 독자 질문을 설명할 때
- 필요한 입력: 독자 질문 / 선택 Fact와 source / 기능 조건
- 작성 내용: 기능의 동작과 질문의 답·판단을 연결
- 피할 내용: 근거 없는 고객 효과 확대 / 내부 Fact ID·검토 지시를 본문으로 출력
- 검토: 한 덩어리가 한 질문에 답하는가? / 동작 사실과 기대 효과를 혼동하지 않았는가?
- 기존 정책: GUIDE-03-STRUCTURE-V2N0151, GUIDE-03-STRUCTURE-V2N0153, GUIDE-03-STRUCTURE-V2N0201, GUIDE-03-STRUCTURE-V2N0199

- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0151` · block_specific · 해당 독자 질문을 설명할 때
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0153` · block_specific · 해당 독자 질문을 설명할 때
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0201` · block_specific · 해당 독자 질문을 설명할 때
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0199` · block_specific · 해당 독자 질문을 설명할 때

### 원리·이유 설명 — `body.principle`

- 목적: 선택에 필요한 원인·원리를 이해시킨다
- 적용: 원리를 알아야 질문에 답하거나 선택할 수 있을 때
- 필요한 입력: 질문 / 원리 근거 / 필요한 용어·계산
- 작성 내용: 현상·이유·실무상 의미를 연결
- 피할 내용: 공식 문서에 없는 알고리즘 추정 / 관련 없는 기술 강의
- 검토: 원리와 문제의 연결이 보이는가? / 계산에 원본 값·단위·조건이 남는가?
- 기존 정책: GUIDE-03-STRUCTURE-V2N0153, GUIDE-03-STRUCTURE-V2N0260, RULE-CONFIGURATION-SOURCE-V2N0008, RULE-NUMERIC-SCOPE-V2N0004

- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0153` · block_specific · 원리를 알아야 질문에 답하거나 선택할 수 있을 때
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0260` · block_specific · 원리를 알아야 질문에 답하거나 선택할 수 있을 때
- 규칙 연결: `RULE-CONFIGURATION-SOURCE-V2N0008` · conditional_shared · 설정·배선·호환·내부 구조를 설명할 때
- 규칙 연결: `RULE-NUMERIC-SCOPE-V2N0004` · conditional_shared · 수치·계산을 작성할 때

### 스펙 해석 — `body.specification`

- 목적: 수치를 독자의 선택 기준으로 해석한다
- 적용: 스펙이 구매 판단 또는 사용 제약에 필요할 때
- 필요한 입력: 제품·속성·값·단위·조건 / 공식 source
- 작성 내용: 필요한 스펙의 의미와 한계
- 피할 내용: 모든 스펙 나열 / 최대/권장·수평/대각선 혼동 / 임의 반올림
- 검토: 각 수치의 주체·단위·조건이 일치하는가?
- 기존 정책: RULE-READER-STYLE-V2N0008, GUIDE-03-STRUCTURE-V2N0038, RULE-NUMERIC-SCOPE-V2N0004, RULE-NUMERIC-SCOPE-V2N0008

- 규칙 연결: `RULE-READER-STYLE-V2N0008` · block_specific · 스펙이 구매 판단 또는 사용 제약에 필요할 때
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0038` · block_specific · 스펙이 구매 판단 또는 사용 제약에 필요할 때
- 규칙 연결: `RULE-NUMERIC-SCOPE-V2N0004` · conditional_shared · 수치·계산을 작성할 때
- 규칙 연결: `RULE-NUMERIC-SCOPE-V2N0008` · conditional_shared · 수치·계산을 작성할 때

### 비교·선택 기준 — `body.comparison`

- 목적: 같은 요구에서 무엇을 선택할지 돕는다
- 적용: 같은 결정 질문의 비교군을 다룰 때
- 필요한 입력: 공통 결정 질문 / 비교 후보 / 동일 비교 기준 / 각 후보 Fact·조건
- 작성 내용: 기본 역할과 같은 기준의 차이·조건별 선택
- 피할 내용: 역할이 다른 부속을 동급 대안으로 나열 / 근거 없는 우열 점수
- 검토: 같은 축으로 비교했는가? / 후보별 적합 조건이 보이는가?
- 기존 정책: GUIDE-03-STRUCTURE-V2N0049, GUIDE-03-STRUCTURE-V2N0065, GUIDE-03-STRUCTURE-V2N0083, GUIDE-03-STRUCTURE-V2N0186, GUIDE-03-STRUCTURE-V2N0188

- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0049` · block_specific · 같은 결정 질문의 비교군을 다룰 때
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0065` · block_specific · 같은 결정 질문의 비교군을 다룰 때
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0083` · block_specific · 같은 결정 질문의 비교군을 다룰 때
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0186` · block_specific · 같은 결정 질문의 비교군을 다룰 때
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0188` · block_specific · 같은 결정 질문의 비교군을 다룰 때

### 구성·배선·사용 모습 — `body.configuration`

- 목적: 무엇을 도입·재사용하여 어떻게 쓰는지 설명한다
- 적용: 하나의 기본 구성을 설명할 때
- 필요한 입력: 공간·운영 요구 / 기존 장비 / 기본 구성 / 각 역할 / 호환·배선 근거
- 작성 내용: 도입/재사용 구분·장비 역할·사용 모습·주요 연결
- 피할 내용: 역할 합성 / 검증되지 않은 호환 / 다른 운영 분기 전부 나열
- 검토: 독자가 기본 구성을 설명할 수 있는가? / 조합 근거가 실제 모드·플랫폼과 맞는가?
- 기존 정책: GUIDE-03-STRUCTURE-V2N0027, GUIDE-03-STRUCTURE-V2N0049, GUIDE-03-STRUCTURE-V2N0040, GUIDE-03-STRUCTURE-V2N0069, RULE-CONFIGURATION-SOURCE-V2N0004

- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0027` · planning_reference · 독자 질문·범위를 기획할 때 참고. 이 원자를 제목이나 본문의 직접 표현 규칙으로 해석하지 않음
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0049` · block_specific · 하나의 기본 구성을 설명할 때
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0040` · block_specific · 하나의 기본 구성을 설명할 때
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0069` · block_specific · 하나의 기본 구성을 설명할 때
- 규칙 연결: `RULE-CONFIGURATION-SOURCE-V2N0004` · conditional_shared · 설정·배선·호환·내부 구조를 설명할 때

### 설정·점검·조치 — `body.setup`

- 목적: 독자가 점검·설정을 수행하고 정상 여부를 판단하게 한다
- 적용: 설치·설정 또는 문제 해결 작업이 필요할 때
- 필요한 입력: 제품·버전 / 전제 조건 / 공식 작업 순서 / 정상 확인 방법
- 작성 내용: 전제 → 순서 → 정상 확인 → 제약
- 피할 내용: 메뉴 경로 추정 / 조정으로 해결되는 문제를 구매로 유도
- 검토: 실행 가능한 순서인가? / 조치 후 정상 확인이 있는가?
- 기존 정책: GUIDE-03-STRUCTURE-V2N0024, GUIDE-03-STRUCTURE-V2N0087, RULE-CONFIGURATION-SOURCE-V2N0004, RULE-CONFIGURATION-SOURCE-V2N0011, RULE-READER-STYLE-V2N0033

- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0024` · block_specific · 설치·설정 또는 문제 해결 작업이 필요할 때
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0087` · block_specific · 설치·설정 또는 문제 해결 작업이 필요할 때
- 규칙 연결: `RULE-CONFIGURATION-SOURCE-V2N0004` · conditional_shared · 설정·배선·호환·내부 구조를 설명할 때
- 규칙 연결: `RULE-CONFIGURATION-SOURCE-V2N0011` · conditional_shared · 설정·배선·호환·내부 구조를 설명할 때
- 규칙 연결: `RULE-READER-STYLE-V2N0033` · block_specific · 설치·설정 또는 문제 해결 작업이 필요할 때

### 실증·사례 — `body.case`

- 목적: 기록에 근거한 관찰을 설명한다
- 적용: 실제 경험·시험 기록이 있을 때
- 필요한 입력: 실제 테스트·경험 기록 / 구성·일자·조건
- 작성 내용: 확인된 조건에서 실제 관찰한 내용만 설명한다. 가상 상황은 문제 제기·원리 블록에 가정으로 표시한다
- 피할 내용: 가짜 쇼룸 테스트 / 생성 사진을 실증 증거로 사용 / 측정 밖의 일반화 / 가정을 실증 블록의 근거로 사용
- 검토: 실제 기록과 조건이 있는가? / 관찰 밖의 해석을 측정 결과로 쓰지 않았는가?
- 기존 정책: RULE-EXPERIENCE-BUSINESS-V2N0004, RULE-EXPERIENCE-BUSINESS-V2N0006, RULE-EXPERIENCE-BUSINESS-V2N0008, RULE-EXPERIENCE-BUSINESS-V2N0015, GUIDE-03-STRUCTURE-V2N0174

- 규칙 연결: `RULE-EXPERIENCE-BUSINESS-V2N0004` · conditional_shared · 실제 경험·시험 결과 또는 설명용 가정을 서술할 때; 실제 경험은 기록 필요, 가정은 실증으로 쓰지 않음
- 규칙 연결: `RULE-EXPERIENCE-BUSINESS-V2N0006` · conditional_shared · 실제 경험·시험 결과 또는 설명용 가정을 서술할 때; 실제 경험은 기록 필요, 가정은 실증으로 쓰지 않음
- 규칙 연결: `RULE-EXPERIENCE-BUSINESS-V2N0008` · conditional_shared · 실제 경험·시험 결과 또는 설명용 가정을 서술할 때; 실제 경험은 기록 필요, 가정은 실증으로 쓰지 않음
- 규칙 연결: `RULE-EXPERIENCE-BUSINESS-V2N0015` · conditional_shared · 실제 경험·시험 결과 또는 설명용 가정을 서술할 때; 실제 경험은 기록 필요, 가정은 실증으로 쓰지 않음
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0174` · block_specific · 실제 경험·시험 기록이 있을 때

### 적용 조건·주의사항 — `body.conditions`

- 목적: 해법이 적용되는 범위와 제한을 드러낸다
- 적용: 선택·지원·사용에 중요한 조건이 있을 때
- 필요한 입력: 제품·모드·플랫폼·펌웨어·라이선스 Fact / 미확정 항목
- 작성 내용: 선택과 사용에 중요한 지원 조건·제약
- 피할 내용: 중요 조건 삭제 / 미확정 범위를 표현만 바꿔 확정
- 검토: 독자의 선택을 바꿀 조건이 설명과 연결됐는가?
- 기존 정책: GUIDE-03-STRUCTURE-V2N0099, GUIDE-03-STRUCTURE-V2N0203, GUIDE-03-STRUCTURE-V2N0205, RULE-PLATFORM-SCOPE-V2N0006

- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0099` · block_specific · 선택·지원·사용에 중요한 조건이 있을 때
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0203` · block_specific · 선택·지원·사용에 중요한 조건이 있을 때
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0205` · block_specific · 선택·지원·사용에 중요한 조건이 있을 때
- 규칙 연결: `RULE-PLATFORM-SCOPE-V2N0006` · conditional_shared · 제품 지원 범위를 주장할 때

### 조건부 추가 장비 — `body.extension`

- 목적: 남는 문제를 보완할 추가 장비를 설명한다
- 적용: 기본 구성으로 해결되지 않는 문제가 남을 때
- 필요한 입력: 기본 구성 / 남는 문제 / 추가 조건 / 장비 역할·호환 근거 / 사진·소개 링크
- 작성 내용: 추가가 필요한 조건과 역할·근거
- 피할 내용: 필수품처럼 모든 독자에게 권유 / 목적이 다른 부속의 동급 비교
- 검토: 필요 없는 독자가 생략할 수 있음을 알 수 있는가? / 기본 구성과 호환되는가?
- 기존 정책: RULE-READER-STYLE-V2N0059, RULE-READER-STYLE-V2N0061, GUIDE-03-STRUCTURE-V2N0089, GUIDE-03-STRUCTURE-V2N0091, GUIDE-03-STRUCTURE-V2N0093, GUIDE-03-STRUCTURE-V2N0207

- 규칙 연결: `RULE-READER-STYLE-V2N0059` · conditional_shared · 남는 문제의 조건부 추가 장비를 실제로 제시할 때만 적용. 모든 다음 행동에 추천을 강제하지 않음
- 규칙 연결: `RULE-READER-STYLE-V2N0061` · block_specific · 기본 구성으로 해결되지 않는 문제가 남을 때
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0089` · block_specific · 기본 구성으로 해결되지 않는 문제가 남을 때
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0091` · block_specific · 기본 구성으로 해결되지 않는 문제가 남을 때
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0093` · block_specific · 기본 구성으로 해결되지 않는 문제가 남을 때
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0207` · block_specific · 기본 구성으로 해결되지 않는 문제가 남을 때

### 제품 소개 링크 — `body.product_link`

- 목적: 설명한 제품의 정확한 소개 자료로 연결한다
- 적용: 각 제품의 실질적 설명 직후
- 필요한 입력: 표준 제품 ID / 원본 blog_url·발행 여부·확인 시점
- 작성 내용: 실질적 제품 설명 직후 해당 제품 링크
- 피할 내용: 글 전체 링크 1개 제한 / 다른 제품 링크 / 미발행·추정 URL
- 검토: 제품 ID와 URL이 일치하는가? / 누락을 미해결로 기록했는가?
- 기존 정책: RULE-OCEANTECH-BRAND-LINKS-V2N0042, RULE-OCEANTECH-BRAND-LINKS-V2N0044, RULE-OCEANTECH-BRAND-LINKS-V2N0046, RULE-OCEANTECH-BRAND-LINKS-V2N0048, RULE-OCEANTECH-BRAND-LINKS-V2N0054, RULE-OCEANTECH-BRAND-LINKS-V2N0074, RULE-OCEANTECH-BRAND-LINKS-V2N0076

- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0042` · block_specific · 각 제품의 실질적 설명 직후
- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0044` · block_specific · 각 제품의 실질적 설명 직후
- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0046` · block_specific · 각 제품의 실질적 설명 직후
- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0048` · boundary_link · 인접 블록과 정의·전제·결론·제품 설명을 연결하거나 중복을 점검할 때
- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0054` · block_specific · 각 제품의 실질적 설명 직후
- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0074` · block_specific · 각 제품의 실질적 설명 직후
- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0076` · block_specific · 각 제품의 실질적 설명 직후

### 사진·GIF·도표·이미지 문구 — `media`

- 목적: 문단의 시각적 질문에 답한다
- 적용: 문단의 시각적 질문에 답할 자료를 계획할 때
- 필요한 입력: 공통: 문단·시각적 질문·필요 자산 역할 / 초안 계획: Need ID·관련 Fact·후보 자료 또는 생성/자료 요청·배치 맥락 / 최종 출력: 검토된 출처·권리와 승인 binding·Asset ID/revision
- 작성 내용: 외형은 공식 사진·동작은 공식 GIF 등 역할에 맞는 자료를 계획한다. 초안은 미확보·미승인 자산도 Need ID로 표시할 수 있다. 최종 출력은 승인된 binding의 Asset ID/revision만 사용한다
- 피할 내용: 제품·UI·시험 증거를 생성으로 대체 / 문단마다 같은 회의 사진 / 생성 성공을 승인으로 간주 / 초안의 자리 표시자를 승인된 최종 이미지로 간주
- 검토: 초안: 문단의 시각적 질문과 Need ID·배치·조달 계획이 연결됐는가? / 최종 출력: 출처·권리·내용 검토와 승인 binding·revision이 확인됐는가?
- 기존 정책: GUIDE-04-IMAGES-V2N0031, GUIDE-04-IMAGES-V2N0032, GUIDE-04-IMAGES-V2N0033, GUIDE-04-IMAGES-V2N0035, GUIDE-04-IMAGES-V2N0037, GUIDE-04-IMAGES-V2N0039, GUIDE-04-IMAGES-V2N0098, GUIDE-04-IMAGES-V2N0011, GUIDE-04-IMAGES-V2N0019, GUIDE-03-STRUCTURE-V2N0210

- 규칙 연결: `GUIDE-04-IMAGES-V2N0031` · block_specific · 문단의 시각적 질문에 답할 자료를 계획할 때
- 규칙 연결: `GUIDE-04-IMAGES-V2N0032` · block_specific · 문단의 시각적 질문에 답할 자료를 계획할 때
- 규칙 연결: `GUIDE-04-IMAGES-V2N0033` · block_specific · 문단의 시각적 질문에 답할 자료를 계획할 때
- 규칙 연결: `GUIDE-04-IMAGES-V2N0035` · block_specific · 문단의 시각적 질문에 답할 자료를 계획할 때
- 규칙 연결: `GUIDE-04-IMAGES-V2N0037` · block_specific · 문단의 시각적 질문에 답할 자료를 계획할 때
- 규칙 연결: `GUIDE-04-IMAGES-V2N0039` · block_specific · 문단의 시각적 질문에 답할 자료를 계획할 때
- 규칙 연결: `GUIDE-04-IMAGES-V2N0098` · block_specific · 문단의 시각적 질문에 답할 자료를 계획할 때
- 규칙 연결: `GUIDE-04-IMAGES-V2N0011` · block_specific · 문단의 시각적 질문에 답할 자료를 계획할 때
- 규칙 연결: `GUIDE-04-IMAGES-V2N0019` · block_specific · 문단의 시각적 질문에 답할 자료를 계획할 때
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0210` · block_specific · 문단의 시각적 질문에 답할 자료를 계획할 때

### 핵심 답·구성 결론 회수 — `closing.summary`

- 목적: 처음 질문의 답과 구성 결론을 회수한다
- 적용: 공통 마감
- 필요한 입력: 초반 질문 / 검증된 핵심 답 / 기본 구매·재사용 결론
- 작성 내용: 핵심 답과 조건을 짧게 회수
- 피할 내용: 결론을 바꾸는 새 기능·수치의 갑작스러운 추가
- 검토: 제목·초반 질문에 답했는가? / 본문과 같은 결론인가?
- 기존 정책: GUIDE-03-STRUCTURE-V2N0095, GUIDE-03-STRUCTURE-V2N0224, GUIDE-03-STRUCTURE-V2N0228, RULE-OCEANTECH-BRAND-LINKS-V2N0081

- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0095` · block_specific · 공통 마감
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0224` · block_specific · 공통 마감
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0228` · boundary_link · 인접 블록과 정의·전제·결론·제품 설명을 연결하거나 중복을 점검할 때
- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0081` · block_specific · 공통 마감

### 체크리스트·판단·다음 행동 — `closing.next_action`

- 목적: 독자가 자기 환경에서 다음 행동을 고르게 한다
- 적용: 공통 마감의 판단 안내
- 필요한 입력: 판단 조건 / 설정/구매/재사용/추가 확인 선택
- 작성 내용: 자기 환경을 점검할 기준과 다음 행동. 추가 장비의 역할·사진·링크 규칙은 남는 문제에 대한 부속을 실제 제시할 때만 적용한다
- 피할 내용: 모든 결론을 구매로 전환 / 확인되지 않은 추천 / 답 회수와 같은 결론의 반복
- 검토: 구체적으로 무엇을 확인·선택할지 알 수 있는가? / 조건부 부속을 모든 독자의 필수품으로 쓰지 않았는가?
- 기존 정책: GUIDE-03-STRUCTURE-V2N0226, GUIDE-03-STRUCTURE-V2N0120, GUIDE-03-STRUCTURE-V2N0097, GUIDE-03-STRUCTURE-V2N0230

- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0226` · block_specific · 공통 마감의 판단 안내
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0120` · block_specific · 공통 마감의 판단 안내
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0097` · block_specific · 공통 마감의 판단 안내
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0230` · conditional_shared · 남는 문제의 조건부 추가 장비를 실제로 제시할 때만 적용. 모든 다음 행동에 추천을 강제하지 않음

### 가치 요약·소회 — `closing.appreciation`

- 목적: 내용의 가치를 자연스럽게 마무리한다
- 적용: 공통 마감
- 필요한 입력: 글의 실제 도움과 분위기
- 작성 내용: 판단에 보탬이 되길 바라는 소회
- 피할 내용: 고정 소회 문구 복제 / 성과를 보장하는 찬사
- 검토: 본문 내용과 이어지는가? / 새 성능 약속이 없는가?
- 기존 정책: RULE-OCEANTECH-BRAND-LINKS-V2N0086, RULE-OCEANTECH-BRAND-LINKS-V2N0083

- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0086` · block_specific · 공통 마감
- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0083` · block_specific · 공통 마감

### 상담·데모 연결 — `closing.consultation`

- 목적: 승인된 상담·데모 지원으로 연결한다
- 적용: 공통 마감
- 필요한 입력: 승인된 지원 범위 / 독자 공간·예산·운영 조건
- 작성 내용: 조건에 맞는 기술 상담·견적·데모 안내
- 피할 내용: 무료 제공·납품 실적·서비스 범위 날조
- 검토: 승인된 기업 안내 범위인가?
- 기존 정책: RULE-OCEANTECH-BRAND-LINKS-V2N0087, GUIDE-03-STRUCTURE-V2N0242, RULE-EXPERIENCE-BUSINESS-V2N0011

- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0087` · block_specific · 공통 마감
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0242` · block_specific · 공통 마감
- 규칙 연결: `RULE-EXPERIENCE-BUSINESS-V2N0011` · conditional_shared · 경험 또는 기업 정책·정체성을 주장할 때

### 맺음 인사 — `closing.greeting`

- 목적: 작성 주체의 인사를 마친다
- 적용: 공통 마감
- 필요한 입력: 공식 총판 팀 정체성 / 글의 분위기
- 작성 내용: 정중하고 따뜻한 맺음 인사
- 피할 내용: 판에 박힌 예문 복제 / 끝에서 새로운 제품 홍보 시작
- 검토: 상담 안내와 배너 사이에 자연스럽게 이어지는가?
- 기존 정책: RULE-OCEANTECH-BRAND-LINKS-V2N0088, RULE-OCEANTECH-BRAND-LINKS-V2N0083, GUIDE-03-STRUCTURE-V2N0240

- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0088` · block_specific · 공통 마감
- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0083` · block_specific · 공통 마감
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0240` · block_specific · 공통 마감

### 마지막 문의 문구·배너 — `closing.inquiry_banner`

- 목적: 지정된 마지막 문의 안내를 제공한다
- 적용: 마지막 인사 바로 뒤
- 필요한 입력: 마지막 문의 Need ID / 동일 승인 배너·클릭 대상
- 작성 내용: 마지막 인사 뒤 문의 문구와 클릭 가능한 배너
- 피할 내용: 중복 제거로 배너 삭제 / 다른 회사·생성 이미지로 대체
- 검토: 도입과 동일한 지정 자산인가? / 문의 페이지로 연결되는가?
- 기존 정책: GUIDE-03-STRUCTURE-V2N0238, RULE-OCEANTECH-BRAND-LINKS-V2N0091, RULE-OCEANTECH-BRAND-LINKS-V2N0100, RULE-OCEANTECH-BRAND-LINKS-V2N0102, RULE-OCEANTECH-BRAND-LINKS-V2N0106, RULE-OCEANTECH-BRAND-LINKS-V2N0110

- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0238` · block_specific · 마지막 인사 바로 뒤
- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0091` · block_specific · 마지막 인사 바로 뒤
- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0100` · block_specific · 마지막 인사 바로 뒤
- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0102` · block_specific · 마지막 인사 바로 뒤
- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0106` · block_specific · 마지막 인사 바로 뒤
- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0110` · block_specific · 마지막 인사 바로 뒤

### 제품 인지 보조 블록 — `companion.product_awareness`

- 목적: 관련 제품의 정체성과 역할을 알려준다
- 적용: 제품 인지를 선택했으며 기존 설명과 중복되지 않을 때
- 필요한 입력: 선택 이유·연결 문단 / 제품 ID·기본 역할 / Fact·source / 등록 소개 링크 / 본문 소개 여부
- 작성 내용: 무엇인지·역할·주제 관련성을 설명한다. 이미 본문에서 설명했으면 짧게 참조하거나 생략을 제안한다
- 피할 내용: 구매 필요성·해결 효과 암시 / 본문 정의를 길게 반복 / 인지 선택을 임의 추천으로 변경
- 검토: 제품 인지 선택과 내용이 일치하는가? / 본문 설명을 반복하지 않는가? / 링크·역할 근거가 확인됐는가?
- 기존 정책: GUIDE-03-STRUCTURE-V2N0036, GUIDE-03-STRUCTURE-V2N0179, RULE-OCEANTECH-BRAND-LINKS-V2N0042, RULE-OCEANTECH-BRAND-LINKS-V2N0046, RULE-OCEANTECH-BRAND-LINKS-V2N0048

- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0036` · block_specific · 제품 인지를 선택했으며 기존 설명과 중복되지 않을 때
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0179` · block_specific · 제품 인지를 선택했으며 기존 설명과 중복되지 않을 때
- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0042` · block_specific · 제품 인지를 선택했으며 기존 설명과 중복되지 않을 때
- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0046` · block_specific · 제품 인지를 선택했으며 기존 설명과 중복되지 않을 때
- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0048` · boundary_link · 인접 블록과 정의·전제·결론·제품 설명을 연결하거나 중복을 점검할 때

### 제품 추천 보조 블록 — `companion.product_recommendation`

- 목적: 확인된 구매·도입·사용·재사용 요구에 맞는 제품 또는 조합을 권한다
- 적용: 확인된 구매·도입·사용·재사용 요구가 있고 제품 추천을 선택했을 때
- 필요한 입력: 확인된 구매·도입·사용·재사용 요구와 기존 장비 / 추천 이유·적합 조건 / 제품별 역할·제약 / Fact·source·호환 근거 / 등록 소개 링크 / 대안/구성/조건부 추가 관계
- 작성 내용: 각 제품을 도입하거나 사용·재사용할 이유와 조건을 연결한다. 본문에서 추천했으면 새 내용을 길게 반복하지 않고 판단을 회수한다. 추가 부속 규칙은 조건부 추가를 실제 제시할 때만 적용한다
- 피할 내용: 인지 블록의 강제 추천 전환 / 근거 없는 호환 / 추천 개수 채우기 / 설정으로 해결할 문제의 구매 강요 / 재사용 권고를 새 구매 권유로 바꾸기
- 검토: 추천 묶음 관계가 명확한가? / 조건별 추천 근거가 있는가? / 도입·사용·재사용 행동이 독자 요구에 맞는가? / 본문 추천과 중복되지 않는가?
- 기존 정책: GUIDE-03-STRUCTURE-V2N0081, GUIDE-03-STRUCTURE-V2N0083, RULE-READER-STYLE-V2N0033, RULE-READER-STYLE-V2N0059, GUIDE-03-STRUCTURE-V2N0230, RULE-COMPONENT-ROLE-V2N0004, RULE-COMPONENT-ROLE-V2N0009, RULE-PLATFORM-SCOPE-V2N0006, RULE-OCEANTECH-BRAND-LINKS-V2N0046, RULE-OCEANTECH-BRAND-LINKS-V2N0048

- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0081` · block_specific · 확인된 구매·도입·사용·재사용 요구가 있고 제품 추천을 선택했을 때
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0083` · block_specific · 확인된 구매·도입·사용·재사용 요구가 있고 제품 추천을 선택했을 때
- 규칙 연결: `RULE-READER-STYLE-V2N0033` · block_specific · 확인된 구매·도입·사용·재사용 요구가 있고 제품 추천을 선택했을 때
- 규칙 연결: `RULE-READER-STYLE-V2N0059` · conditional_shared · 남는 문제의 조건부 추가 장비를 실제로 제시할 때만 적용. 모든 다음 행동에 추천을 강제하지 않음
- 규칙 연결: `GUIDE-03-STRUCTURE-V2N0230` · conditional_shared · 남는 문제의 조건부 추가 장비를 실제로 제시할 때만 적용. 모든 다음 행동에 추천을 강제하지 않음
- 규칙 연결: `RULE-COMPONENT-ROLE-V2N0004` · conditional_shared · 장비 역할·조합 효과를 주장할 때
- 규칙 연결: `RULE-COMPONENT-ROLE-V2N0009` · conditional_shared · 장비 역할·조합 효과를 주장할 때
- 규칙 연결: `RULE-PLATFORM-SCOPE-V2N0006` · conditional_shared · 제품 지원 범위를 주장할 때
- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0046` · block_specific · 확인된 구매·도입·사용·재사용 요구가 있고 제품 추천을 선택했을 때
- 규칙 연결: `RULE-OCEANTECH-BRAND-LINKS-V2N0048` · boundary_link · 인접 블록과 정의·전제·결론·제품 설명을 연결하거나 중복을 점검할 때

## 제품 인지·추천 보조 블록

제품 인지는 무엇인지·역할·관련성·근거·링크를 설명한다. 제품 추천은 여기에 추천 이유·적합 조건·중요 제약·대안/구성/조건부 추가 관계를 연결한다. 인지를 구매 권유로 바꾸지 않으며 추천 수를 임의로 고정하지 않는다.

두 보조 블록의 위치와 선택·미해결 상태는 [제품 추천 설계](product-recommendation.md)와 [보조 노드 계약](companion-nodes.md)을 따른다.

## 적용과 관리

기획 단계에서 block_id·독자 질문·필요 입력·Fact/자산·인접 블록을 계획한다. 집필 후 해당 블록의 검토 질문으로 확인하고, 문단 재배치·주장 변경 시 해당 입력과 근거를 다시 확인한다. 새 블록별 필드를 기존 Writer 응답에 임의로 추가하지 않는다.

원문·조건은 [기존 가이드 매칭표](paragraph-element-rules.md)에 있다. 이 설계안을 운영 Planner·Writer·QA에 자동 전달하는 연결은 아직 구현하지 않았다.
