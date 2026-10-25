# 역할별 파일 소유권 및 권한 규정 (role-ownership.md)

다중 에이전트 환경에서 파일 경합 및 상호 오염을 방지하기 위한 권한 경계(Logical Boundary)입니다.

---

## 1. 역할별 쓰기(Write) 및 읽기(Read) 매트릭스

| 역할 (Role) | 쓰기 권한 (Write Allowed) | 읽기 권한 (Read Allowed) | 절대 쓰기 금지 (Write Prohibited) |
| :--- | :--- | :--- | :--- |
| **Keyword AI** | `01_keyword_ai/`<br>`queue/writer.queue.yaml`<br>`registry/KEYWORD_REGISTRY.csv`<br>`locks/` | `00_system/`<br>`03_sources/INDEX.yaml`<br>`06_analytics/keyword-feedback/`<br>`registry/CONTENT_REGISTRY.csv` | `02_writer_ai/`<br>`04_qa_ai/`<br>`05_publish/`<br>`03_sources/` 본문 파일들 |
| **Writer AI** | `02_writer_ai/drafts/`<br>`02_writer_ai/working/`<br>`queue/qa.queue.yaml`<br>`locks/` | `02_writer_ai/`<br>`00_system/rules/`<br>`00_system/templates/`<br>현재 작업 Brief 및 지정된 소스 파일 | `00_system/`<br>`01_keyword_ai/` (Brief 수정 금지)<br>`registry/`<br>`04_qa_ai/` |
| **QA AI** | `04_qa_ai/reports/`<br>`queue/writer.queue.yaml` (반려 시)<br>`05_publish/ready/` (승인 시)<br>`locks/` | 현재 작업 Brief, Draft, 지정 소스<br>`00_system/`<br>`04_qa_ai/QA_GUIDE.md` | `01_keyword_ai/`<br>`02_writer_ai/` 본문 직접 수정 금지<br>`registry/` (최종 배포 전 수정 금지) |
| **Publisher** | `05_publish/published/`<br>`registry/CONTENT_REGISTRY.csv` | `05_publish/ready/` | `01_`, `02_`, `04_` 작업 영역 |

---

## 2. Concurrency Lock 규정
동일 콘텐츠를 복수의 AI가 동시에 작업하는 충돌을 막기 위해 작업 시작 시 락을 점유합니다.
- **락 생성**: 작업 시작 즉시 `locks/CNT-YYYYWww-NNN.lock` 파일 생성
  ```yaml
  content_id: CNT-2026W39-001
  role: WRITER
  started_at: "2026-09-22T16:00:00"
  ```
- **락 해제**: 작업 완료 및 큐 전이 즉시 해당 `.lock` 파일 삭제
- **고아 락(Stale Lock)**: 24시간 이상 방치된 락 파일은 관리자 또는 스크립트에 의해 자동 해제 대상이 됩니다.
