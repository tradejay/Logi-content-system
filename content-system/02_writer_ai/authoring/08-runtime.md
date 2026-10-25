# 공통 실행 경로

실행 종료마다 `execution-contract.json`과 `pipeline-verification.json`을 저장한다. AVIXA·PSNI 탐색부터 제품 Fact 전달·블록 집필·QA·공식 검토까지의 로그 연결을 검증한다. 재검사 명령과 범위는 [SYS-PIPELINE-VERIFY-005](../../00_system/rules/pipeline-mechanical-verification.md)를 참고한다.

2026-10-08: 전략 수립 전에 AVIXA·PSNI 관련 글을 먼저 탐색한다. 관련 글이 없으면 개별 설계 근거, 둘 다 없으면 기존 제품 Fact로 진행한다. `planning_research` 호출과 `web-planning-discovery.json`에 선택 이유·출처·규칙 수신 로그를 남긴다. 상세 계약은 [SYS-WEB-PLANNING-004](../../00_system/rules/web-planning-discovery.md)를 따른다. 기관 자료는 제품 Fact 승인이나 로지텍 AI 검증을 대체하지 않는다.

실행 제어는 `services/content_pipeline.py`의 `ContentPipeline.run()` 한 곳에 있다. 입력 로딩은 `pipeline_context.py`, Gemini 공식 API 통신은 `pipeline_provider.py`, 글쓰기 지시는 이 폴더의 MD와 `prompts/*.md`에 둔다. 웹 작성 버튼, Gemini 호환 CLI, `content-system/scripts/batch_rewrite.py`가 공통 경로를 호출한다. 엔진 선택 옵션은 없다.

```powershell
python -m pip install -r requirements-pipeline.txt
python -m services.content_pipeline CNT-2026W39-002 --prepare-only
python -m services.content_pipeline CNT-2026W39-002
```

### 단계별 수동 재실행 및 피드백 제어 CLI (`scripts/pipeline_cli.py`)

기존 결과물(전략, 에셋 바인딩, 초안)을 보존한 상태에서 특정 단계부터 작업을 재실행하거나 사용자의 추가 피드백/지시사항을 주입하여 글을 재교정할 수 있는 전용 CLI 도구를 제공합니다. (웹 콘솔 Workbench의 `▶ 이 단계부터 재실행` 및 피드백 입력창과 100% 동일한 백엔드 엔진 연동)

```powershell
# 1. 처음부터 전체 파이프라인 실행
python scripts/pipeline_cli.py CNT-2026W39-001

# 2. 기획 전략(strategy)은 유지하고 본문 작성(write)부터 다시 실행
python scripts/pipeline_cli.py CNT-2026W39-001 --stage write

# 3. 작성된 초안을 유지한 채, 추가 피드백을 전달하여 품질 검토(feedback) 루프부터 재실행
python scripts/pipeline_cli.py CNT-2026W39-001 --stage feedback --feedback "도입부 인삿말을 더 친근한 오우션 비즈니스 화법으로 교정하고, 랠리 마이크 팟 연결 제약 강조"

# 4. 로지텍 공식 AI(Kapa RAG) 검증만 단독 실행
python scripts/pipeline_cli.py CNT-2026W39-001 --stage official

# 5. 최대 검토 버전 수(기본 3회, 최초 원고 포함) 지정
# max_revisions=3은 최초 원고(r1)를 포함한 최대 3개 검토 버전을 의미하며, feedback 시작 시 추가 재작성은 최대 2회(r2, r3)까지 시도됩니다.
python scripts/pipeline_cli.py CNT-2026W39-001 --stage feedback -r 3 -f "표 포맷을 가독성 높게 수정"
```

| 지원 단계 (`--stage`) | 시작 지점 및 동작 | 승계되는 기존 데이터 |
| :--- | :--- | :--- |
| `inputs` | 기획서 및 팩트 점검 (기본값) | 처음부터 전체 재실행 |
| `strategy` | 독자 분석 및 8대 플레이북 기획 전략 수립 | 기획서(`brief.yaml`) 및 Knowledge Pack |
| `assets` | 이미지 에셋 계획 및 바인딩 수립 | 직전 수립된 기획 전략(`strategy.json`) |
| `write` | 본문 원고 집필 (`r1.write`) | 직전 전략 및 이미지 바인딩 계획 유지 |
| `feedback` | 품질 검토 및 다회차 교정 루프 (`r1` 검토 후 불합격 시 `r2`, `r3` 재작성) | 직전 생성된 초안(`draft.md`) 및 claim-map 승계, 사용자 피드백 반영 |
| `official` | 로지텍 공식 AI Kapa RAG 교차 검증 | 직전 확정 초안의 기술적 사실 검증만 단독 수행 |

`--prepare-only`는 외부 AI를 호출하지 않고 기존 brief·관측값·팩트·출처·규칙을 조립한다. PREPARED는 작성/검토 완료 상태가 아니다. 작성은 Gemini 공식 API만 사용한다. 모델 ID는 config/config.json의 gemini_model(현재 gemini-3.8-flash), 키는 gemini_api_key 또는 gemini_api_keys의 첫 항목을 읽는다. GEMINI_API_KEY/GEMINI_MODEL 환경변수가 있으면 우선한다. 코드에 API 키 기본값은 없다. 로지텍 검토 서버 주소는 logitech_ai_url 설정이며 기본은 http://127.0.0.1:5050/ask다.

웹 콘솔의 ‘파이프라인 결과 / 관리자 확인’에서 현재 실행 결과를 다시 열 수 있다. QA 통과 후에도 관리자 검토 전에는 COMPLETED_REVIEW_PENDING이다. 관리자 승인은 run ID와 원고 hash에 묶인다. 초안 수정 시 무효화하며 재실행 시 수정된 초안을 입력으로 사용한다. 이미지 출처·URL·검토 정보가 없는 바인딩은 최종본으로 내보낼 수 없다. 로지텍 연결·내부 구조화 변환이 실패하거나 판정 계약과 다르면 ERROR로 남기며 통과시키지 않는다. 자연어 공식 응답의 내부 AI 해석·집필 수정·재검토 연결은 [SYS-OFFICIAL-FEEDBACK-007](../../00_system/rules/official-feedback-routing.md)을 따른다. 이전 final 파일이 남아 있어도 현재 승인 없이는 export가 차단된다.

실행별 입력·정확한 프롬프트·모델 원문·각 수정본·QA·공식 검토·지식 업데이트 후보·관리자 확인사항은 content-system/working/{content_id}/runs/{run_id}/에 저장한다. pipeline-latest.json은 현재 실행 상태다. 중단된 실행이 lock을 남기면 실행 프로세스 종료 여부를 확인한 뒤 해당 글의 pipeline.lock을 정리한다. 실행 중 lock을 지우지 않는다.

## 현재 연결 범위와 남은 어댑터

### 가이드 변경의 실행 반영

공통 실행은 `GuideRepository.load_bundle_for_run()`으로 활성 가이드 릴리스를 읽어 실행에 고정한다. 원본 MD만 수정하면 기존 활성 릴리스의 지시문은 바뀌지 않는다. 원본·레지스트리 수정 후 `scripts/build_guide_release.py build --release-id <새 ID>`로 새 묶음을 만들고, `verify <새 ID>`로 무결성을 확인한 뒤 `activate <새 ID>`로 다음 실행에 적용한다. 진행 중이거나 저장된 실행의 가이드 묶음은 바꾸지 않는다. 가이드 활성화만으로 이미지 API 호출이나 새 검토기의 구현이 완료되는 것은 아니다.

### 현황 점검 버튼과 실시간 표시

대시보드의 ‘전체 현황 점검 후 실행’은 `/api/content-system/pipeline/dispatch`로 비동기 실행을 시작한다. 클릭 시점의 기획서, 열린 근거 요청, 출처 유효기간, 원고 및 입력 hash, 승인/실패/잠금 기록을 점검한다. 완료 기록이 없거나 입력이 변경된 글만 순차 실행한다. 변경 없는 승인본과 관리자 확인 대기본은 건너뛰고, 같은 입력의 실패를 자동 반복하지 않는다. 워크벤치 버튼은 같은 점검을 선택한 글 하나에 적용한다.

작업 현황 API는 2초 간격으로 조회하며 글별 단계·진행사항·대기 사유·단계별 건수를 표시한다. 원고 토큰 스트리밍이나 정확한 퍼센트 진행률은 아니다. 상태와 이벤트는 `content-system/operations/latest-job.json`, `operations/jobs/{job_id}.json`에 남아 새로고침 후 다시 볼 수 있다. 실행 중 중복 클릭은 기존 작업을 반환한다. 서버가 종료되면 백그라운드 작업도 중단되며, 중단된 잠금은 프로세스와 결과를 확인한 뒤 복구해야 한다. 재시작 후 자동 재실행하지 않는다.

이 버튼은 등록된 글의 필요한 새 실행을 만든다. 기획서 없는 글의 주제/brief를 자동 생성하거나 새로운 검색 수집을 수행하는 기능은 아직 포함하지 않는다.

- 키워드 진단은 기존 SQLite 관측값을 읽으며 기존 brief의 주제/검색어를 사용한다. 실시간 수집과 신규 주제·brief 자동 생성은 이 실행기에 추가하지 않았다. 관측값이 없으면 관리자 항목에 표시한다.
- 기존 facts는 source.id/source.source_id 모두 지원한다. claim_kinds가 없으면 규칙 누락 방지를 위해 관련 규칙 종류를 넓게 로딩한다. 자동 구조 검증은 근거의 의미적 진실까지 보장하지 않으므로 공식 검토와 관리자 검토가 남는다.
- 이미지 계획, 생성 요청 대기, 업로드 후보, 명시적 승인 바인딩을 연결했다. 이미지 생성 서비스 직접 호출은 아직 없으며 요청을 생성 완료로 처리하지 않는다. 기존 nano_banana_pipeline.py의 전역 배포 경로는 공통 실행에서 호출하지 않는다.
- 자동 성과 수집 스케줄과 발행 URL 등록은 기존 수집기에 남아 있다. 이 실행기는 저장된 관측값을 다음 작성의 입력으로 사용한다.
- 자동 검토 실패/근거 부족은 발행 준비 상태가 아니다. 지식 후보는 실행별 큐에 저장하고 원본 지식은 자동 수정하지 않는다.

## 검증

AI 입력은 `services/pipeline_payload.py`에서 단계별로 조립한다. 원본 snapshot·input_refs·해시는 기록에 보관하지만 모델 요청에는 넣지 않는다. 전략 단계에는 플레이북 설명 목록만 전달하고 집필에는 선택된 본문을 전달한다. 중복 knowledge 전체와 asset_needs 중복, 과거 수정 내역은 제거하되 Fact의 값·단위·scope·제약·출처를 보존한다. 집필/QA의 출처 본문은 임의 절단하지 않는다. 각 요청의 `context-metrics/` 기록에서 축소 전후 문자 수를 확인할 수 있다. 과거 실행 기록은 변경하지 않으며 이후 실행부터 적용된다.

`python -m unittest discover -s tests -v`는 외부 AI 대신 계약에 맞는 모의 응답으로 규칙 전달, 재작성, 승인, 이미지 바인딩, API 공통 경로, 강제 발행 차단을 확인한다. 실제 외부 모델과 로지텍 서비스의 연결 성공을 의미하지 않는다.
