# 1년 장기 운영 및 정기 유지보수 프로토콜 (maintenance-protocol.md)

주간 AI 콘텐츠 운영 시스템이 시간이 지나도 데이터가 엉키거나 성능이 저하되지 않도록 정기적으로 수행하는 유지보수 및 복구 규범입니다.

제품 추천 이력·근거 검증·제품별 추천 빈도와 조합 분포는 [제품 추천 기록·검증·빈도 관리](product-recommendation-tracking.md)를 따른다. 매일 검토를 강제하지 않고 작성·수정·발행 시 기록, 주제 선정·콘텐츠 검토 시 집계한다. 자동 집계 도구 연결은 후속 구현 대상이다.

---

## 1. 정기 유지보수 주기별 점검 매트릭스

| 주기 | 중점 점검 항목 | 실행 도구 및 방법 | 기대 효과 |
| :--- | :--- | :--- | :--- |
| **주간 (Weekly)**<br>매주 금요일 | **대기열 정합성 및 고아 락 정리** | - `python scripts/repair_queue.py --dry-run`<br>- `python scripts/recover_locks.py --clean`<br>- `weekly/YYYY-Www/summary.md` 작성 | 작업 중단이나 비정상 종료로 인한 대기열 꼬임 및 방치된 락 해제 |
| **월간 (Monthly)**<br>매월 마지막 영업일 | **소스 신선도 감사 및 레지스트리 백업** | - `python scripts/audit_sources.py`<br>- `python scripts/backup_registry.py`<br>- `06_analytics/monthly/` 리포트 생성 | UI 개편에 따른 STALE 소스 식별 및 중앙 데이터 영구 보존 |
| **분기 (Quarterly)**<br>분기말 | **가이드 및 용어집 업데이트** | - 제조사 신제품(Sight, MeetUp 2 등) 팩트시트 보강<br>- `00_system/taxonomy/terminology.md` 최신화<br>- 네이버 검색 알고리즘 변화에 따른 가이드 튜닝 | 신규 장비 및 최신 검색 트렌드 즉각 반영 |
| **반기 (Semi-Annual)**<br>매 6개월 | **발행 콘텐츠 신선도 감사 (Content Revalidation)** | - `CONTENT_REGISTRY.csv`에서 발행 180일 이상 콘텐츠 추출<br>- 기술/UI 변경 여부 검토 후 업데이트(`v1.0 → v2.0`) 대상 선정 | 구형 정보 방치로 인한 독자 신뢰 저하 방지 |

---

## 2. 장애 유형별 긴급 복구 절차 (Disaster Recovery Runbook)

### 상황 A: 프로세스 비정상 종료 또는 락 방치로 파이프라인이 중단되었을 때
1. 과거 레지스트리 CSV의 텍스트 상태를 맹신하여 일괄 강제 복구하지 않으며, 공통 상태 계산 모듈(`services/pipeline_status.py`)을 기준으로 현재 실행·원고 해시·QA·승인 유효성을 대조합니다.
2. 중단 복구 도구(`scripts/recover_pipeline.py`)를 통해 실제 프로세스 생존(PID 및 생성시각)을 검증하고 안전하게 복구합니다:
   - 복구 대상 및 영향도 미리보기: `python scripts/recover_pipeline.py [CID]` (기본 dry-run 모드)
   - 안전 복구 적용: `python scripts/recover_pipeline.py [CID] --apply --reason "비정상 종료 프로세스 복구"`
   - 복구 적용 시 고아 잠금이 안전하게 해제되고, `pipeline-latest.json` 및 해당 run 결과가 `outcome=FAILED`, `stage=finished`, `publish_ready=false`로 일관되게 정리됩니다.
3. 살아 있는 활성 프로세스는 복구 도구가 자동으로 보호하므로 동시 실행을 파괴하지 않습니다.

### 상황 B: 원고 또는 입력이 변경되어 승인이 무효화되었을 때
1. 관리자 승인본(`COMPLETED_READY`)이라도 현재 원고의 해시(`draft_sha256`)나 관련 입력(`input_refs`, `product_links`)이 변경되면 공통 상태 엔진이 자동으로 `REVISION_REQUIRED`로 강등하고 `publish_ready=false`로 전환합니다.
2. 이 경우 수동으로 레지스트리를 조작하지 않고, 변경된 원고/입력에 대해 파이프라인 재검토(`feedback` 또는 `write`)를 실행하여 새로운 run을 통해 검증과 승인을 다시 획득해야 합니다.

### 상황 C: 소스가 STALE로 판정되었을 때
1. 제조사 공식 포털(Logitech ProSupport, Zoom Docs)의 최신 릴리스 노트를 확인합니다.
2. 팩트시트의 수치나 UI 경로를 수정한 후 `last_verified` 날짜를 갱신합니다.

### 상황 D: 특정 콘텐츠가 중간 단계(QA 실패, 피드백 교정 등)에서 멈추거나 관리자 수동 재지시가 필요할 때
1. 파이프라인 전체를 처음부터 다시 돌릴 필요 없이 `scripts/pipeline_cli.py`를 활용해 중간 단계부터 재실행합니다.
   - 원고 작성부터 재시작: `python scripts/pipeline_cli.py <CID> --stage write`
   - 사용자 피드백을 반영하여 교정 루프 재실행: `python scripts/pipeline_cli.py <CID> --stage feedback --feedback "수정 지시사항"`
   - 로지텍 공식 AI 검증만 단독 재수행: `python scripts/pipeline_cli.py <CID> --stage official`
2. 웹 콘솔(`http://localhost:5000/content-ops/workbench/<CID>`)에서도 단계별 재실행 버튼과 피드백 입력창을 통해 동일하게 조치 가능합니다.
