# 규칙 전달·수신 확인 및 입력 토큰 관리

시행 구현: `services/content_pipeline.py`, `services/policy_call_audit.py`, `services/pipeline_provider.py`.
적용 범위: 공통 ContentPipeline의 strategy/write/feedback 호출 및 공식 검토 어댑터 호출.
키워드·이미지 등 다른 실행 경로는 아직 이 전송 계약에 연결되지 않았다.

## 식별 및 저비용 전송

- 기존 정책 ID를 유지한다. UUID 추가를 전제하지 않는다.
- 서버에는 호출 ID, 단계, 고정 릴리스 ID, 원본 규칙/가이드 ID, 버전, 실제 전달 본문 SHA-256을 저장한다.
- 해당 호출에서만 `P01`(프롬프트), `R01`(규칙), `G01`(가이드), `C01`(별도 주의사항) 별칭을 사용한다.
- 원문 본문과 적용 조건은 그대로 전달한다. 동일한 `rules`/`cautions` 중복만 제거한다. 서로 다른 주의사항은 보존한다.
- 규칙 전체 목록·원본 ID·버전·해시를 AI가 반복 출력하지 않는다. 실제 전달한 별칭과 호출별 bundle 값만 확인한다.
- 현재 실행 릴리스가 선택한 문서 단위 규칙을 기록한다. 작업 공간의 565개 원자 정책 전체가 전달되었다는 의미는 아니다.

## 응답 계약 및 실패 처리

```json
{"receipt":{"bundle":"호출별 값","ids":["P01","R01","G01"]},"result":{"markdown":"기존 단계 출력"}}
```

receipt를 출력 앞에 두고, result에는 기존 단계별 출력 계약을 유지한다.
서버는 누락·추가·중복 ID, 잘못된 bundle, 유효하지 않은 result를 거부한다.
응답 원문과 실패 상태를 보존하며, 검증되지 않은 응답을 다음 단계 결과로 사용하지 않는다.
receipt는 수신 자기보고의 일치 확인이다. 규칙을 이해하거나 준수했다는 증명이 아니므로 `compliance_status=not_evaluated`로 기록한다. 기존 Fact·자산·품질 검토와 관리자 승인을 계속 적용한다.

## 토큰 예산

Gemini 호출 전에 동일한 systemInstruction·직렬화된 context·generationConfig로 countTokens를 요청한다.
기본 입력 상한은 50,000토큰이며 `config/config.json`의 `pipeline_input_token_budget` 양의 정수로 변경한다(2026-10-08 사용자 요청 반영). 10,000토큰은 초기 테스트에서 사용한 이전 상한이다.
출력 상한은 집필 8,192토큰, 전략/피드백 등 기타 단계 4,096토큰이다. `pipeline_output_token_budgets`에서 단계별 변경한다. MAX_TOKENS 종료는 정상 완료로 처리하지 않는다.
일반 입력 목표는 10,000~20,000토큰이지만 품질 보장 임계값이나 강제 차단 기준은 아니다. 필요 규칙과 근거가 있으면 50,000토큰까지 허용한다.
실측 실패 또는 초과 시 생성 호출을 중단한다. 필수 규칙을 임의로 삭제하거나 문자 수를 실제 토큰 수로 대체하지 않는다.
기존 조립기의 문자 예산/추정 토큰은 진단값이며 최종 생성 여부는 실측 예산으로 결정한다.
실측 입력 토큰과 응답 usageMetadata를 함께 기록한다. 2~3천/1만 토큰은 모델 품질을 보장하는 임계값이 아니다.

공식 RAG 어댑터에는 토큰 계산 API가 없어 `token_count_status=unavailable`로 기록한다.
해당 어댑터에도 receipt를 요구한다. 지원하지 않는 응답은 공식 검토 ERROR로 처리하고 승인본으로 자동 전환하지 않는다.
실제 외부 모델/공식 RAG의 응답 호환성은 별도 실제 실행에서 확인해야 한다.

## 저장 및 반복 점검

실행 폴더의 `rule-audit/*.json`에 원본 ID 대응표와 수신 상태를 저장한다.
`prompts/*.json`, `responses/*.json`, `context-metrics/*.json`에 정확한 전송/응답/실측 정보를 보존한다.

```powershell
python -m scripts.verify_policy_call_logs <실행폴더>
```

읽기 전용 점검은 전달 본문/지시 해시, 선택 규칙과 전달 규칙 일치, 응답 receipt, 토큰 예산을 다시 확인한다.
불완전·실패·로그 변조가 있으면 비정상 종료 코드 1을 반환한다. 이전 형식 로그를 확인 완료로 간주하지 않는다.
이 명령은 주기적인 검증 작업에 사용할 수 있지만, 일정 등록은 별도로 수행한다.
점검 결과도 수신 무결성 범위이며 의미적 준수를 자동 인증하지 않는다.

토큰 API 근거: https://ai.google.dev/api/tokens (`generateContentRequest`에 system instruction 포함).
