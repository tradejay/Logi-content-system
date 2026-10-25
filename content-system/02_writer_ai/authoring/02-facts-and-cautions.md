# 02. Fact 추출과 연결된 주의사항 매칭

## 장비+기능 / 장비+스펙 Fact

질문에 답하는 근거를 두 축으로 추출한다.

- 장비+기능: 어떤 장비에서 어떤 기능이, 어떤 모드·플랫폼·버전·구성 조건으로 지원되는가?
- 장비+스펙: 어떤 장비/부품의 어떤 속성 값인가? 단위·측정 방식·최대/권장·반경/직경을 포함한다.

Fact 최소 항목: `fact_id`, `revision`, `subject_ids`, `feature_ids`, `property_id`, `claim`, `value`, `unit`, `scope`, `limitations`, `does_not_imply`, `source_refs`, `verification_status`, `verified_at`, `caution_rule_ids`.

수치가 없는 지원 여부도 Fact다. source_refs에는 문서 ID·문서 버전·절/표/문장 위치·인용한 원문을 연결한다. 검색 스니펫과 AI 답변 자체를 공식 Fact로 승격하지 않는다. 최신성 기준을 넘었거나 서로 충돌하는 Fact는 검토 대상으로 남긴다.

정렬은 질문 해결에 필요한 정도와 근거 적합성 기준이다. 첫 15개 등 고정 개수로 잘라 중요한 제약을 버리지 않는다. 필수 질문 → Fact 연결이 완성되지 않으면 핵심 주장 작성은 보류한다.

## 주의사항은 Fact와 별도 규칙 객체

규칙 본문은 `rules/*.md`, 기계 판정 조건은 [registry.json](rules/registry.json)에 둔다. Fact 또는 엔티티는 `caution_rule_ids`로 규칙을 직접 참조할 수 있다. 수치와 제품 호환 목록을 주의사항 문장에 복제하지 않고 해당 Fact의 scope/limitations를 읽도록 지시한다.

매칭 절차:

1. 이번 글의 정규화된 제품·기능·속성·주장 종류·주제 intent를 `match_context`에 모은다.
2. active인 전역 필수 규칙을 선택한다.
3. 선택한 Fact와 제품/기능 레코드의 `caution_rule_ids`를 합친다. 존재하지 않거나 비활성인 필수 참조는 오류다.
4. `match.all`은 모든 조건, `match.any`는 하나 이상의 조건이 맞아야 한다. 비어 있는 all/any는 그 부분의 제한 없음이다. 각 조건은 지정 필드의 문자열 집합과 `values`의 정확한 교집합으로 판정한다. 한국어 문장의 부분 문자열로 추정하지 않는다.
5. 조건으로 선택된 규칙과 직접 참조된 규칙을 합쳐 ID/version으로 중복 제거한다. `required`는 선택된 규칙의 로딩/준수가 필수라는 뜻이며 조건부 규칙을 전역 선택한다는 뜻이 아니다.
6. 우선순위는 낮은 숫자부터 읽는 순서다. 서로 충돌하는 의무를 우선순위로 은폐하지 않는다. 충돌·필수 참조 오류는 context 검증 실패로 돌려보낸다.
7. MD 실제 본문과 scope/limitations/does_not_imply를 함께 주입하고, `matched_by`, `matched_entity_ids`, `matched_fact_ids`, `rule_version`, `path`, `sha256`를 기록한다.

직접 참조는 조건 매칭보다 넓게 안전 규칙을 적용할 수 있다. 제품 전용 factual 규칙은 제품 scope가 일치해야 하며 불일치 시 참조 데이터 오류로 분류한다. 현재 초기 규칙 목록은 일반 검증/표현 규칙이며 새 제품 사실을 선언하지 않는다.

## Writer에 전달할 형태

```text
해결할 질문: Q-...
인용 가능한 Fact: FACT-...@revision, 원문 위치, 범위와 제약
주의사항: RULE-...@version + 규칙 MD 본문
매칭 이유: 이 Fact의 속성/장비/기능 또는 명시된 caution_rule_ids
쓸 수 없는 확장: does_not_imply
미확인 항목: 조사 필요 / 생략 가능 / 관리자 판단 필요
```

Writer는 본문과 별도 claim map을 낸다: 문단/표 셀/제목/캡션별 Claim → Fact/source 또는 의견/실증 기록. 내부 ID를 독자용 본문에서 지워도 이 연결은 유지한다.

새 주장이 생기면 근거와 주의사항 매칭을 다시 수행한다. 관리자의 문체 승인이 제품 스펙의 증거를 대신할 수는 없다.
