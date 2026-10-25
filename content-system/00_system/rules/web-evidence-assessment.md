# SYS-WEB-EVIDENCE-002 — 웹 근거 적합성·한계·대안 판단

2026-10-08 기획 역할 변경: 현행 AVIXA·PSNI 경로는 [SYS-WEB-PLANNING-004](web-planning-discovery.md)를 적용한다. 아래는 이전 근거 심사 계약의 기록이며 현행 실행 단계로 사용하지 않는다. 관련 글 우선 탐색과 개별 사실 대체는 집필 전 수동 검증 대기 게이트를 사용하지 않는다.

2026-10-08 업데이트: [SYS-WEB-SOURCE-TRUST-003](web-source-trust.md)에 따라 AVIXA/PSNI 근거는 신뢰도 100%로 자동 채택한다. 아래 일반 수동 검토 요구 및 미검증 대기 게이트보다 이 출처 정책을 우선한다. 다른 사이트의 검색 근거는 제외한다.

흐름: 주제 → 웹 후보 검색 → 원문 검토 기록 → 적합성·대안 AI 판단 → 블록 배정 → 집필 → 누락·왜곡 검토.

## 판단 규칙

1. 브랜드의 유리/불리는 채택 기준이 아니다. 독자의 도입 판단에 중요한 한계는 보완·대체가 없어도 포함한다.
2. 보완 가능하면 설정/배치/추가 구성의 조건을, 대체 가능하면 다른 모델/구성/브랜드의 조건을 조사한다. 조사 제안은 확인된 사실과 구분한다.
3. 정보가 빠진 듯하면 missing_context로 조건·버전·환경·상충 의견을 기록한다. 작성자가 의도적으로 누락했다고 추정하지 않는다.
4. 포럼의 경험담은 원문/댓글 위치와 적용 조건을 밝힌 실무 의견으로만 사용한다. 다양한 브랜드를 다룬다는 사실만으로 중립성을 인정하지 않는다.
5. 기관 권고, 제조사 사양, 실무 의견의 출처 유형을 보존한다. 원문 검토가 끝나지 않은 검색 요약은 집필 근거로 사용할 수 없다.
6. critical/material 근거는 include 또는 investigate다. exclude는 차단한다. 검토자가 지정한 중요도를 AI가 낮출 수 없다. contextual 제외는 판단 이유를 남긴다.
7. 중요한 미검증 내용은 NEEDS_EVIDENCE로 기획 전에 중단한다. 중요한 근거를 원고에서 누락하면 블록 검증/QA가 실패한다.

## 원문 검토 입력

글 작업 폴더 `content-system/working/<content_id>/web-evidence-review.json`에 아래 형태로 검토 기록을 저장한다. 원문 스냅샷은 프로젝트 안에 UTF-8 텍스트로 보관한다.

```json
{
  "items": [{
    "id": "WEB-EVIDENCE-001",
    "statement": "원문에 근거한 주장 또는 출처가 명시된 경험담",
    "conditions": ["환경·버전·발생 조건"],
    "importance": "material",
    "source_type": "forum",
    "source_url": "https://example.com/thread",
    "source_path": "content-system/03_sources/web/thread.txt",
    "source_sha256": "저장한 파일 바이트의 SHA-256",
    "locator": "댓글 영구 링크 또는 문단 위치",
    "quote": "저장한 원문에 실제 존재하는 발췌",
    "verification_status": "verified",
    "reviewed_by": "검토자 식별자",
    "reviewed_at": "2026-10-08"
  }]
}
```

source_type: manufacturer/institution/forum/other. importance: critical/material/contextual. 최대 20개 항목. 파일 해시·원문 발췌 일치·경로·검토자 정보를 기계 검증한다. 원문 실제 열람·주장 해석은 담당자의 검토 책임이며 해시 검증만으로 의미 정확성이 증명되지는 않는다. 원문 수집 및 검토 화면 자동화는 현재 구현에 포함되지 않는다.

## 판단·집필 계약

적합성 AI는 decision_impact, limitations, mitigations, alternatives, missing_context, inclusion_decision, reason, target_roles를 출력한다. 검토된 원문 statement/conditions만 집필용 근거로 전달하고 AI가 요약한 새 주장을 승인 Fact로 승격하지 않는다. 모든 검토 항목은 판단 기록에 남긴다.

target_roles를 블록의 roles와 매칭하여 block_plan.web_evidence_ids에 연결한다. 원문 검토 근거와 판단 메모를 단계별 컨텍스트에 포함한다. 기획/feedback에는 채택·조사·제외 판단 기록을 전달하고 write에는 채택 근거를 전달한다. 일반 Claim-Fact 검증은 기존대로 유지한다.

근거 판단 입력에도 기존 제품 Fact와 scope/제약, Fact locator로 추린 출처 본문·URL·파일 위치를 전달한다. 공식 사양으로 이미 설명 가능한 주장과 포럼 경험담을 비교한다. 기존 Fact를 전달해도 웹 원문 검토가 자동 승인되지는 않는다.

write는 evidence_usage: [{evidence_id, block_id, quote}]를 출력한다. quote가 해당 블록 본문에 있는지, 배정 역할이 일치하는지, 중요한 근거가 누락되지 않았는지 검사한다. 메타데이터는 실제 의미 준수를 증명하지 않으므로 feedback에서 조건 제거·근거 없는 보완책·편향적 생략을 별도로 검토한다.

판단 호출도 짧은 ID receipt·입력 토큰 상한·사용량 로그를 사용한다. 신규 검색 판단은 핵심 후보 6개 이내로 간결하게 요청하고, 실제 호출에서 생각 토큰까지 출력 상한을 소진한 문제를 반영하여 evidence_review 출력 상한은 8,192토큰으로 한다. 결과는 web-evidence-assessment.json, 집필 사용 기록은 writer-metadata.json 및 block-review에 보관한다. 정책 릴리스 원본/승인 Fact/출처 INDEX를 자동 변경하지 않는다.
