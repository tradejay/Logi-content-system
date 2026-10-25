# 제품 증거 결측 처리 정책 (evidence-gap-policy.md)

기술 및 제품 정보가 부족할 때 AI가 상상으로 내용을 채우지 않고 안전하게 작업을 중단 및 보완하기 위한 **Product Evidence Gap Flow**입니다.

---

## 1. 5대 결측 유형 분류 (Missing Evidence Types)

| 코드 | 유형 명칭 | 정의 및 예시 |
| :--- | :--- | :--- |
| **`MISSING_SPEC`** | 공식 하드웨어 스펙 부재 | 카메라 화각(FOV), 줌 배율, 마이크 수음 직경 등 스펙 누락 |
| **`MISSING_FEATURE_DOC`** | 기능 작동 원리/조건 설명 부족 | RightSight 2 자동 전환 발화 지속시간, CollabOS 펌웨어 요구조건 |
| **`MISSING_CONFIG_DOC`** | 관리자 설정 및 세팅 메뉴얼 부족 | Zoom Rooms 또는 Teams Rooms 관리자 포털 세부 설정 경로 |
| **`MISSING_TEST`** | 실제 현장 검증 데이터 부족 | 15인 회의실 또는 유리벽 반사 환경에서의 실제 화자 추적 체감 |
| **`CONFLICTING_SOURCE`** | 제조사/플랫폼 자료 간 상충 | 데이터시트와 웹사이트 간의 마이크 도달 거리 표기 불일치 |

---

## 2. 결측 심각도(Severity) 및 조치 기준

- **`LOW` (경미)**:
  - 본문의 핵심 주장과 무관한 부가 정보 (예: 제품의 순수 무게 등)
  - **조치**: 해당 단락 생략 후 본문 작성 계속.
- **`MEDIUM` (보통)**:
  - 본문 서술은 가능하나 현장 사진이나 메뉴 캡처가 필요한 경우
  - **조치**: 본문 해당 위치에 `[ASSET_REQUIRED: type=image/gif, purpose=...]` 표기 후 작성 지속.
- **`HIGH` (치명적)**:
  - 핵심 제품 기능 지원 여부 및 성능 한계 확인 불가
  - **조치**: **즉시 글 작성 중단** → `change_status.py`를 통해 `NEEDS_EVIDENCE` 전이 및 `blocked.queue.yaml` 격리 → `03_sources/inbox/`에 `EVREQ-*.yaml` 자동 발행.

---

## 3. Evidence Request (EVREQ) 생애주기

```text
       [Writer AI 또는 사람이 결측 발견]
                      │
                      ▼
       EVREQ-YYYYWww-NNN.yaml 발행 (03_sources/inbox/)
                      │
                      ▼
         [조사 담당자 / 제품 큐레이터 자료 확인]
                      │
                      ├─ Fact 추출 (Fact / Interpretation 분리)
                      ├─ 03_sources/ 팩트시트 추가
                      ├─ INDEX.yaml 및 SOURCE_REGISTRY.csv 등록
                      │
                      ▼
               EVREQ 상태: RESOLVED
                      │
                      ▼
             차단 해제 (Blocked Clear)
                      │
                      ▼
             Writer AI 작성 재개
```
