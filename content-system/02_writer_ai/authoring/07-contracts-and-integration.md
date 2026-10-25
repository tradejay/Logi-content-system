# 07. 데이터 계약과 기존 코드 연결 작업

이 문서는 구현 계약이다. 공통 실행기와 콘솔 연결의 현재 범위·실행법·남은 어댑터는 [실행 문서](08-runtime.md)를 확인한다. 계약 전체가 구현됐다는 뜻으로 해석하지 않는다.

## 공통 봉투

모든 글별 산출물은 `schema_version`, `content_id`, `run_id`, `artifact_revision`, `created_at`, `input_refs`를 가진다. input_refs에는 원본 경로/ID와 revision/hash를 둔다. 문서 본문·규칙·Fact·자산의 원본 버전이 실행 도중 변경되어도 이미 시작한 run의 입력은 변하지 않는다.

권장 작업 경로: `working/{content_id}/runs/{run_id}/`. ID를 경로로 쓰기 전에 형식을 검증한다. 아래 파일 이름은 신규 계약이며 기존 파일을 자동 이동하라는 지시가 아니다.

| 파일 | 필수 내용 |
|---|---|
| gap-snapshot.json | 관측값·수집 상태·대상 URL·선정 이유 |
| brief.json | 질문·검색 의도·범위·검색 키워드·독자·콘텐츠 목적 |
| keyword-entity-map.json | 원문 검색어·entity ID/type·매핑 근거·모호성 |
| fact-bundle.json | 선택한 Fact revision·scope·source locator·미확인 항목 |
| strategy.json | 독자 질문, 플레이북, must_cover, can_omit, technical_depth, 초반/중반/마감 계획 |
| matched-cautions.json | 선택한 규칙과 MD 본문 hash·매칭 이유·충돌 목록 |
| writer-context.json | 실제 AI 입력의 구성 요소·본문/참조·토큰 예산·정확한 입력 hash |
| asset-plan.json | 글별 AssetNeed·선택/생성 요청·필수 여부 |
| asset-bindings.json | need ID → 승인 asset ID/revision → 본문 anchor |
| revisions/rN.draft.md | 원고 후보, 임의 덮어쓰기 금지 |
| revisions/rN.claim-map.json | 제목/문단/표/이미지 문구 → Fact/source/test/의견 구분 |
| revisions/rN.feedback.json | 피드백별 변경과 해결 상태 |
| reviews/rN.official.json | AI 원문·구조화 판정·Claim별 근거·오류 |
| run-result.json | 실행 종료 결과·발행 가능 여부·큐 참조·관리자 체크사항 |

지식·관리자 대기열은 별도 파일/DB로 저장하되 위 run/revision을 참조한다. 여러 파일에 상태를 복제할 경우 권위 저장소를 하나로 지정하고 콘솔은 그 값을 읽는다.

## 규칙 레지스트리 계약

[registry.json](rules/registry.json)은 JSON이며 Python 표준 json으로 로드할 수 있다. 각 `path`는 registry 파일의 디렉터리 기준이다. `match_context`의 지원 필드는 `product_ids`, `feature_ids`, `property_ids`, `claim_kinds`, `intents`이며 모두 문자열 배열이다.

제품/기능/속성 ID는 현재 카탈로그·온톨로지 adapter가 제공해야 한다. 존재하지 않는 제품별 ID를 새로 상상해 매칭하지 않는다. 초기 목록은 제품 사실을 하드코딩하지 않는 공통/주장 종류 규칙만 등록한다. 기존 지식의 caution_rule_ids 이관은 별도 검토 후 수행한다.

`claim_kinds` 표준값: `numeric_spec`, `functional_relation`, `compatibility`, `configuration`, `field_test`, `business_policy`, `asset_claim`. 해당 종류는 Claim/Fact의 구조화 타입에서 얻고 자유문장 키워드 탐지 하나로 확정하지 않는다.

검증: ID 유일성, 필수 필드, MD 경로 존재, 지원 필드/조건 연산, version/hash 기록, 규칙 충돌, 필수 직접 참조의 유효성. 파일명만 프롬프트에 넣어서는 안 되며 선택된 MD 본문을 실제로 주입해야 한다.

## 연결할 코드와 인수 조건

| 현재 코드 | 변경해야 하는 책임 | 확인할 조건 |
|---|---|---|
| keyword_explorer / blog_analyzer / performance_db | 진단 관측을 Brief 입력에 연결 | 결측을 0으로 만들지 않고 게시 URL별 측정 |
| build_writing_strategy | 실제 질문과 Fact로 전략 생성 | must_cover/depth 포함, 자기 검증기 통과 |
| build_writer_context | Fact/주의사항/작성 모듈/이미지 계획 조립 | 선택된 규칙의 실제 본문·hash가 입력에 존재 |
| gemini_writer / pipeline_provider | Gemini 공식 API에 Context Pack 전달 | 규칙/필수 입력은 공통 실행기에서 조립 |
| resolve_assets / nano_banana_pipeline | need 매칭·미승인 생성 후보 관리 | 섹션 번호 매칭·전체 글 자동 배포 없음 |
| claim/editorial QA | 근거 확인과 편집 리뷰 분리 | 빈 근거·가짜 asset을 성공 처리하지 않음 |
| verify_blog_with_logitech_ai | revision 고정 검토와 두 큐 적재 | 무응답/파싱 실패 PASS 없음, 중복 적재 없음 |
| content_ops_api / content_ops.js | 작업 결과와 사람 판단 UI | 정확한 원고 revision 표시, 실패와 대기 구분 |
| change_status / export | 승인된 스냅샷만 승격/렌더 | 실패·미승인 원고가 final로 넘어가지 않음 |

문서 적용 완료와 코드 적용 완료는 별도 체크리스트다. 기존 hardcoded prompt, 전체 자산 첫 20개 주입, QA 실패 후 final 복사는 새 규격에 부합하지 않는다.

## 예시 매칭 — 제품 사실을 주장하지 않는 fixture

입력 match_context에 `claim_kinds=[numeric_spec, functional_relation, field_test]`가 있으면 전역 규칙과 수치·기능 관계·실증 주의사항이 선택되어야 한다. configuration 규칙은 해당 kind나 직접 참조가 없으면 선택하지 않는다. Fact가 필수 규칙을 직접 참조하면 함께 선택한다. 알 수 없는 ID를 직접 참조하면 실패해야 한다.

이 fixture는 규칙 선택 계약의 예시다. 모델 생성 품질이나 기존 운영 파이프라인의 통합 성공을 입증하지 않는다.
