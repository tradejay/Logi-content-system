# 01. 부족 키워드 → 주제 → 기술 엔티티

## 부족 키워드 진단

입력은 게시 URL이 확인된 자사 글 목록, 키워드별 검색 관측, 검색량/수요 자료, 경쟁 콘텐츠, 이전 리뷰다. 각 값에 측정일·조회 범위·데이터 출처·실측/추정/실패 상태를 둔다. API 실패를 검색량 0이나 미노출로 바꾸지 않는다.

부족 사유는 구분한다: 아직 다룬 글이 없음, 관련 글은 있으나 해당 질문을 해결하지 않음, 검색 노출이 낮음, 기존 정보가 오래됨. 검색량만으로 신규 글을 결정하지 않는다. 기존 글 보완·통합이 적합하면 rewrite/update 작업으로 연결한다.

진단 AI는 후보마다 `keyword`, `gap_type`, `observations`, `existing_content_ids`, `reader_need`, `proposed_action`, `confidence`, `selection_reason`을 남긴다. 블로그 자체 추정 지수 하나로 주제를 결정하지 않는다.

## 주제 확정

기획은 다음을 한 문장씩 확정한다.

1. 누구의 어떤 문제에 답할 것인가?
2. 독자가 읽고 어떤 선택/설정을 할 수 있어야 하는가?
3. 이번 글에서 다루지 않을 범위는 무엇인가?
4. 신규 작성인가, 기존 글 보완인가? 중복·잠식 판단 근거는 무엇인가?

핵심 질문의 수와 섹션 수를 코드에서 고정하지 않는다. 독자가 묻지 않은 모든 스펙을 확장해 넣지 않는다.

## 검색어와 장비·기능 키워드 분리

| 종류 | 역할 | 예시 — 연결 사실을 주장하는 예문이 아님 |
|---|---|---|
| primary_keyword | 검색 의도를 대표 | 회의실 화자 추적 카메라 |
| supporting_keywords | 같은 의도의 세부 질문 | 발표자 화면, 카메라 모드 |
| layman_terms | 독자의 일상 표현 | 말하는 사람을 비춰주는 카메라 |
| entity/product | 근거 조회 대상 장비 | 카탈로그에서 확인한 장비 ID |
| entity/feature | 기능 의미와 범위 확인 | 기능 레지스트리의 RightSight 2 ID |
| property | 확인할 속성 | framing_mode, pickup_range 등 등록된 속성 |

`카메라`처럼 넓은 말은 후보 탐색용이다. 이를 특정 장비나 기능으로 자동 확정하지 않는다. 별칭을 표준 ID로 정규화하고 후보가 여러 개면 unresolved로 남긴다. 장비+기능 관계는 공존하는 검색 단어만으로 확정하지 않고 근거로 확인한다.

## 인계

Brief에는 `search.primary_keyword`, `search.supporting_keywords`, `search.layman_terms`, `audience`, `questions`, `product_bridge` 등 기존 필드를 보존한다. 새 구조는 버전이 명시된 adapter로 연결한다. 필드명이 다르다고 빈 문자열/기본 제품으로 대체하지 않는다.

`keyword_entity_map`에는 원래 검색어, 정규화된 entity ID, 타입, 연결 근거, resolved/unresolved 상태를 둔다. Writer가 SEO 목적을 핑계로 무관한 키워드나 장비를 추가하지 않도록 `out_of_scope`도 전달한다.
