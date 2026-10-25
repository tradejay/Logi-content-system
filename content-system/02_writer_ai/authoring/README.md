# 조립형 작성 가이드 v3

문서 버전: 3.1.0 / 개정일: 2026-10-02 / 규범 문서 / 공통 실행 연결: [실행 방법과 구현 범위](08-runtime.md)

목표는 글마다 필요한 규칙과 근거를 골라 AI에게 전달하고, 재작성·공식 검토·관리자 검토 결과까지 한 작업으로 남기는 것이다. 규칙을 작은 단위로 나누되 AI에게 모든 문서를 한꺼번에 넣지 않는다.

이 문서 묶음은 기존 가이드와 충돌할 때 작성 흐름·팩트·주의사항·이미지·검토·완료 판정에 우선한다. 기존 스크립트가 이 계약을 집행한다는 뜻은 아니다. 모델 교체나 프롬프트 문구 추가만으로 적용 완료라고 표시할 수 없다.

## 요청한 순서와 문서 연결

2026-10-08 실행 확장: 주제 결정 후 전략 수립 전에 [AVIXA·PSNI 관련 글 우선 탐색](../../00_system/rules/web-planning-discovery.md)을 수행한다. 관련 글 → 개별 사실·설계 원칙 → 기존 제품 Fact만 사용 순으로 대체한다. 기관 자료는 기획 참고자료이며 제품 사양 검증을 대신하지 않는다. 실행 시 추가 계약으로 전달하고 기존 불변 정책 릴리스는 보존한다.

| 순서 | 작업 | 인계 산출물 | 상세 문서 |
|---|---|---|---|
| 1 | 블로그 부족 키워드 진단 | gap_snapshot | [01](01-topic-and-keywords.md) |
| 2 | 검색 의도와 주제 설정 | topic_decision | [01](01-topic-and-keywords.md) |
| 3 | 주제의 검색어·장비·기능 키워드 설정 | keyword_entity_map | [01](01-topic-and-keywords.md) |
| 4 | 장비+기능, 장비+스펙 팩트 추출 | fact_bundle | [02](02-facts-and-cautions.md) |
| 5 | AI에게 주제별 작성 방식 전달 | strategy | [03](03-opening-body-closing.md) |
| 6 | 팩트와 엔티티에 연결된 주의사항 기계적 로딩 | matched_cautions | [02](02-facts-and-cautions.md) |
| 7 | 초반·중반·마감 및 블로그 문체 전달 | writer_context | [03](03-opening-body-closing.md) |
| 8 | 본문 이미지 위치·확보·생성·URL 결정 | asset_plan / asset_bindings | [04](04-images.md) |
| 9 | 초안 피드백 및 재작성 | draft_revision / feedback_resolution | [05](05-feedback-and-review.md) |
| 10 | 로지텍 AI 검토 | official_review | [05](05-feedback-and-review.md) |
| 11 | 틀린 내용·지식 변경 후보 적재 | knowledge_update_queue | [05](05-feedback-and-review.md) |
| 12 | 판단 불가·관리자 판단 항목 적재 | admin_review_queue | [05](05-feedback-and-review.md) |
| 13 | 작성 작업 종료·콘솔 결과·관리자 체크사항 | run_result | [06](06-completion-and-console.md) |

5번은 기획 AI에 대한 작성 전략 전달이다. 실제 Writer의 초안 호출은 6~8번의 필수 입력을 조립한 뒤 수행한다. 재작성에서 장비·기능·주장이 추가되면 4·6·8번을 다시 수행한다.

이미지 계획은 초안 전에 세우되 최종 확보·생성·배치는 편집된 문단과 맞춘다. 문단 순서나 의미가 바뀌면 앵커와 자산도 다시 검토한다. 제품·기능 개요와 비교는 기본 구매 결론을 돕는 설명이며, 한 글 한 결정 원칙이 이를 삭제하거나 독립 글로 분리하라는 뜻은 아니다. 상세 적용은 [본문 구성](03-opening-body-closing.md), [이미지 계획](04-images.md), [편집 검토](05-feedback-and-review.md)를 따른다.

여러 콘티로 분리할 때는 [글의 범위와 선택지](03-opening-body-closing.md#글의-범위와-선택지--한-글에서-한-가지-결정을-돕기)를 적용한다. 한 글의 중심 결정과 공통 전제를 먼저 정하고, 같은 기준의 비교군과 조건부 추가 장비를 구분한다.

구매·도입 글은 [고객 관점의 기획](03-opening-body-closing.md#고객이-읽는-글--자료의-구조를-독자의-문제로-바꾸기)과 [작성 지시·편집 검토](rules/reader-and-style.md)를 기획·집필·재작성에 적용한다. 배선과 스펙은 정확성의 근거로 활용하고 고객의 불편, 필요한 기능, 구매·재사용 결론을 글의 중심에 둔다.

## 무엇을 작은 단위로 나누는가

- 검색 키워드와 기술 엔티티는 서로 다른 객체다. 예: `회의실 카메라` 검색어, 특정 장비 ID, `RightSight 2` 기능 ID.
- Fact 하나는 하나의 주장이다. 장비·기능·속성·값·단위·적용 조건·근거를 가진다.
- 주의사항 하나는 한 가지 오해/금지/표현 경계다. [규칙 목록](rules/registry.json)의 ID로 선택하고 연결된 MD 본문을 읽는다.
- 작성 모듈 하나는 도입, 설명, 비교, 설정, 한계, 마감 등의 역할이다. 섹션 번호와 제품을 묶지 않는다.
- AssetNeed 하나는 독자의 시각적 질문 하나다. 이미지 개수를 채우기 위한 요청을 만들지 않는다.
- 피드백 하나는 한 위치의 수정 요구이며, 검토 항목 하나는 한 Claim의 판정이다.

## 단일 책임과 우선순위

| 구분 | 보관할 내용 |
|---|---|
| Markdown | 작성 방식·문체·주의사항 본문·검토 절차 |
| 정책/규칙 레지스트리 | rule ID/version, 적용 조건, MD 경로, 심각도, required 여부 |
| 근거 데이터 | 장비별 수치·기능·호환성·제약·source locator·검증 상태 |
| 글별 계획 | 주제, 키워드, 선택된 팩트·규칙·흐름·이미지 요구 |
| 코드 | 계약 확인, 조건 매칭, 입력 조립, 호출, 결과 저장, 버전·상태 관리 |

적용 순서: 사용자 명시 요구 → 출처/검증 경계 → 일치하는 주의사항 → 글별 Strategy → 선택된 플레이북 → 기본 문체. 사용자 요구가 검증되지 않은 사실을 포함하면 요구 자체를 근거로 간주하지 않고 조사 항목으로 분리한다. 양립할 수 없는 동일 권한 규칙은 조용히 덮어쓰지 않고 conflict로 보고한다.

제품 수치와 실제 지원 여부는 MD의 예문이나 코드 문자열에서 얻지 않는다. 기업의 실적·서비스·테스트 경험 역시 관리자가 제공한 자료와 기록으로 확인한다.

## 실행에 전달할 묶음

`working/{content_id}/runs/{run_id}/`에 아래 항목의 revision/hash와 선택 이유를 기록한다. 디렉터리와 필드 계약은 [07](07-contracts-and-integration.md)에 정의한다.

```text
입력: gap_snapshot → brief → keyword_entity_map → fact_bundle
계획: strategy + matched_cautions + 적용 MD 본문 + asset_plan
결과: draft revisions + claim map + feedback + 공식 review
종료: knowledge/admin 대기열 참조 + run_result + 관리자 체크사항
```

필수 가이드 로딩 실패, 모호한 장비 매핑, 핵심 근거 누락은 작성 가능한 것으로 위장하지 않는다. 선택적 내용은 생략 이유를 기록하고 글의 약속 범위를 줄인다. 작성 작업 종료와 발행 승인은 [06](06-completion-and-console.md)의 별도 판정이다.
