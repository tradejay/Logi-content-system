# 중복 방지 및 업데이트 정책 (duplicate-policy.md)

네이버 검색 엔진의 중복 문서(어뷰징) 패널티를 방지하고, 내부 콘텐츠 간의 검색어 카니발라이제이션(잠식)을 차단하기 위한 엄격한 5단계 판정 기준입니다.

---

## 1. 5단계 중복 검사 절차 (5-Stage Gate)

1. **1차: Exact Keyword (완전 일치 검색)**
   - `CONTENT_REGISTRY.csv`에서 `primary_keyword`가 완전히 일치하는지 조회합니다.
2. **2차: Normalized Keyword (정규화 검색)**
   - 공백, 하이픈, 특수문자, 대소문자를 제거한 정규화 키로 비교합니다.
   - 예: `"화상 회의"` vs `"화상회의"` → 동일 키워드로 취급
3. **3차: Canonical Topic (표준 토픽 매핑)**
   - 다양한 표현을 대표하는 표준 토픽 코드로 묶어 대조합니다.
   - 예: `"말하는 사람 따라가는 카메라"`, `"화자추적카메라"`, `"Speaker Tracking Camera"` → 모두 `speaker_tracking_camera` 토픽으로 판별
4. **4차: Search Intent (검색 의도 분석)**
   - 동일한 토픽이라도 검색 의도가 다르면 다른 가치를 가집니다.
   - 예:
     - "화자추적 카메라 원리" → `mechanism` (원리 이해)
     - "화자추적 카메라 추천" → `comparison` (제품 비교)
     - "화자추적 카메라 설정법" → `how_to` (실제 세팅)
   - *토픽이 같아도 의도(Intent)와 퍼널 단계(Funnel)가 다르면 신규 작성이 허용될 수 있습니다.*
5. **5차: One-line Purpose (글의 핵심 목적 대조)**
   - 레지스트리에 기록된 각 글의 `one_line_purpose`와 비교하여 독자에게 제공하는 핵심 가치가 겹치는지 최종 확인합니다.

---

## 2. 의사결정 매트릭스 (Decision Matrix)

| 상황 판별 | 판정 결과 | 조치 사항 |
| :--- | :--- | :--- |
| 새로운 Topic 발견 | `NEW CONTENT` | 신규 Content ID 발급 후 정상 파이프라인 진행 |
| 같은 Topic + 다른 Intent | `NEW CONTENT` | 신규 글 생성 허용 (기존 글과 상호 내부 링크 연결) |
| 같은 Topic + 같은 Intent + 신규 UI/정보 변화 | `UPDATE EXISTING` | 신규 글 발행 금지. 기존 글의 버전을 올리고 본문 업데이트 |
| 본질적 차이가 없는 유사 내용 | `DUPLICATE` | 작업 즉시 취소 (`status: DUPLICATE`) |
| 과거 글이 완전히 구식이 되어 전면 교체 | `SUPERSEDE` | 신규 글 작성 후 기존 글에 `superseded_by` 링크 기록 |
