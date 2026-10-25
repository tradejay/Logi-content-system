# SYS-WEB-RESEARCH-001 — 웹 근거 후보 수집

2026-10-08 업데이트: [AVIXA·PSNI 전용 자동 신뢰 정책](web-source-trust.md)이 아래 일반 수동 검토 규칙보다 우선한다. 웹 검색은 두 기관으로만 제한한다.

후속 단계: [관련 글 우선 기획 탐색](web-planning-discovery.md). 관련 글이 없으면 개별 사실·설계 원칙, 그것도 없으면 기존 제품 Fact로 진행한다. 웹 자료 없음 때문에 집필을 멈추지 않는다.

Gemini API의 Google Search 도구를 집필 전 자료 수집에 사용한다. 기존 불변 작성 정책 릴리스는 변경하지 않는다.

- 기획 주제와 주요 키워드만 전송한다. 원고 전문·내부 Fact·전체 규칙을 검색 호출에 보내지 않는다.
- 실행: 주제 관련 글 탐색 → 기획 참고자료 선별 → 제품 Fact 결합 → 블록 기획·집필. 검색은 AVIXA·PSNI로 한정하고 관련 글이 없으면 같은 기관의 개별 근거를 찾는다.
- 기관 설계 권고와 제조사 제품 사양을 구분한다. 검색 요약을 승인 제품 Fact로 자동 승격하지 않는다. 실제 허용 도메인과 grounding 인용 연결을 확인한 기관 자료는 별도 수동 출처 승인 없이 기획에 활용한다.
- 출처 URL은 API groundingChunks에서 가져온다. Google 리디렉션을 해소하고 실제 원문 도메인을 자동 검사한다. 허용 출처·인용 연결이 없는 응답은 ungrounded로 기록한다.
- SYS-WEB-RESEARCH-001 ID와 실제 전송 지시·질의 해시, API 검색어, 인용 연결 정보, 검색 제안 HTML, 사용량을 저장한다. 검색 수집은 일반 집필 JSON receipt 계약을 사용하지 않는다. 전달/수신 ID 검증이 적용된 집필 호출과 구분한다.
- 요청 한 번에 검색어 3개 이내를 지시하지만 모델의 검색 횟수에 대한 하드 제한은 아니다. observed_query_count는 반환된 검색어 수이며 실제 청구 횟수를 보장하지 않는다.
- 글당 자료 수집 호출 1회, 출력 상한 4,096토큰, 동일 모델·지시·질의 결과 7일 캐시. 재작성/검토 재개 및 prepare-only에서는 호출하지 않는다. 자동 재시도하지 않는다.
- 수집 실패 시 실패 로그와 관리자 항목을 남기고 기존 승인 근거만 사용한다. 키는 인증 헤더로만 사용하며 파일·응답 로그에 기록하지 않는다.

## 설정과 산출물

`config/config.json`의 `pipeline_web_research_enabled: true`로 켠다. 개별 brief에서 `web_research: false`로 끄거나 `web_research: {query: "..."}`로 검색 요청을 지정한다.

실행 기록: `working/<content_id>/runs/<run_id>/web-research.json`. 캐시: `working/<content_id>/web-research-cache.json`.

독립 실행: `python scripts/research_web.py --query "검색할 주제" --output audit/google-search-test.json`.

Google 공식 요금표(2026-10-08 확인): Gemini 3.x 유료 티어 월 5,000 검색 무료 공유, 초과 1,000 검색당 $14. 모델 토큰 비용 별도. 프로젝트 전체 월 사용량/예산을 하드 차단하는 기능은 이 변경에 포함되지 않는다.

출처: https://ai.google.dev/gemini-api/docs/pricing · https://ai.google.dev/gemini-api/docs/generate-content/google-search
