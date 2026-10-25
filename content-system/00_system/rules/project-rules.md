# 프로젝트 불변 규칙 (project-rules.md)

본 시스템은 1년 이상 안정적으로 운영되기 위해 아래의 7대 불변 원칙을 강제합니다.
어떤 Agent나 스크립트도 본 원칙을 위배하여 동작할 수 없습니다.

---

## 1. File = State (대화는 상태가 아니다)
- AI 모델과의 이전 채팅 대화 내용(Conversation History)은 상태로 인정되지 않습니다.
- 모든 상태, 결정, 데이터는 오직 **디렉토리 내 파일(YAML, Markdown, CSV)**에 영구 기록되어야 합니다.
- 새 세션이 시작될 때 AI는 대화 메모리가 아니라 파일 시스템을 읽고 상태를 복원합니다.

## 2. Immutable Content ID (영구 불변 식별자)
- 콘텐츠가 기획되는 즉시 부여되는 `content_id` (예: `CNT-2026W39-001`)는 제목이나 내용이 100번 바뀌어도 **절대 변경할 수 없습니다.**
- 파일명에 글 제목을 포함하지 않으며, 제목은 파일 내부 메타데이터로 관리합니다.

## 3. Finite Status Machine (유한 상태 전이)
- 임의의 자연어 상태(예: "almost done", "pending-final", "working2") 사용을 전면 금지합니다.
- 오직 `status-rules.md`에 명시된 13개의 정규 상태와 승인된 전이(Transition) 경로만 허용됩니다.

## 4. Role Ownership (역할 소유권 격리)
- 각 Agent(Keyword, Writer, QA)는 본인에게 허용된 디렉토리와 파일만 수정할 수 있습니다.
- Writer AI가 Brief의 키워드를 임의 수정하거나, Keyword AI가 초안 본문을 쓰는 행위는 금지됩니다.

## 5. Duplicate Gate (5단계 중복 방지)
- 모든 신규 콘텐츠는 생성 전 반드시 기존 `CONTENT_REGISTRY.csv`와 `KEYWORD_REGISTRY.csv`를 대조하여 5단계 중복 검사를 통과해야 합니다.
- 동일 토픽이라도 의도(Intent)나 퍼널이 완전히 다를 때만 제한적으로 신규 생성이 허용됩니다.

## 6. Evidence Gate (무근거 주장 차단)
- 기술 스펙, 성능, 벤치마크, 설치 호환성은 반드시 `03_sources/`에 존재하는 공인된 출처(E1~E4)에 근거해야 합니다.
- 근거가 없는 경우 AI가 추론하여 날조하지 않고 `[MISSING_EVIDENCE]` 표기 후 `NEEDS_EVIDENCE` 상태로 전이합니다.

## 7. Context Router (컨텍스트 최소화)
- AI에게 전체 저장소를 스캔하도록 요구하지 않습니다.
- 상위 라우터(`AGENTS.md`) → 역할 가이드 → 대기열 1건 → 지정된 소스 2~3건의 단계적 압축 컨텍스트만 주입합니다.
