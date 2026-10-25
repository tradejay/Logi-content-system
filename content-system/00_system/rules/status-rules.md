# 콘텐츠 상태 전이 규칙 (status-rules.md)

콘텐츠 생애주기(Lifecycle) 동안 허용되는 정규 상태 및 전이 규칙(Finite State Machine)을 정의합니다.

---

## 1. 허용 상태 목록 (Allowed States)

### 정규 생애주기 상태 (Standard Lifecycle)
1. `NEW`: 키워드 발굴 후 기획 후보 등록
2. `KEYWORD_RESEARCH`: 검색 의도, 연관어, 용어 분석 진행 중
3. `PLANNING`: Content Brief 작성 중
4. `READY_FOR_WRITING`: 기획서 작성 완료 및 작성 대기열(writer.queue) 등록
5. `WRITING`: Writer AI가 초안(Draft) 작성 진행 중
6. `READY_FOR_QA`: 초안 작성 완료 및 검수 대기열(qa.queue) 등록
7. `REVISION_REQUIRED`: QA 결과 보완 필요로 Writer AI에게 반려
8. `READY_TO_PUBLISH`: QA 85점 이상 PASS 및 배포 대기
9. `PUBLISHED`: 실제 네이버 블로그/웹사이트에 게시 완료 및 URL 등록
10. `ARCHIVED`: 게시 후 1년 이상 경과 또는 보관 처리

### 예외 및 차단 상태 (Exceptions & Blockers)
- `NEEDS_EVIDENCE`: 출처 부재로 추가 테스트/스펙 확인 대기
- `BLOCKED`: 사실 오류, 중대한 결함으로 파이프라인 일시 정지
- `CANCELLED`: 주제 폐기 또는 시의성 상실로 작업 중단
- `DUPLICATE`: 5단계 중복 검사 결과 기존 글 잠식 판정으로 취소

---

## 2. 허용된 상태 전이 매트릭스 (Allowed Transitions)

| 현재 상태 (From) | 전이 가능 상태 (To) | 전이 주체 (Triggered By) |
| :--- | :--- | :--- |
| `NEW` | `KEYWORD_RESEARCH`, `CANCELLED`, `DUPLICATE` | Keyword AI |
| `KEYWORD_RESEARCH` | `PLANNING`, `DUPLICATE`, `CANCELLED` | Keyword AI |
| `PLANNING` | `READY_FOR_WRITING`, `CANCELLED` | Keyword AI |
| `READY_FOR_WRITING`| `WRITING`, `BLOCKED` | Writer AI |
| `WRITING` | `READY_FOR_QA`, `NEEDS_EVIDENCE`, `BLOCKED` | Writer AI |
| `NEEDS_EVIDENCE` | `WRITING` (자료 보강 시), `CANCELLED` | Operator / Curator |
| `READY_FOR_QA` | `READY_TO_PUBLISH` (PASS), `REVISION_REQUIRED`, `BLOCKED` | QA AI |
| `REVISION_REQUIRED`| `WRITING` | Writer AI |
| `READY_TO_PUBLISH` | `PUBLISHED` | Publisher / Operator |
| `PUBLISHED` | `ARCHIVED`, `REVISION_REQUIRED` (오래된 글 업데이트 시)| Operator |

---

## 3. 금지된 전이 (Forbidden Transitions)
- `READY_FOR_WRITING` → `PUBLISHED` (검수 건너뛰기 절대 불가)
- `WRITING` → `READY_TO_PUBLISH` (Writer 자가 승인 불가)
- 임의의 문자열 상태값 등록 시 자동 검증 스크립트에서 즉시 에러를 발생시킵니다.
