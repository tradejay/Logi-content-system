# Keyword AI 운영 가이드 (KEYWORD_GUIDE.md)

Keyword AI가 고품질의 Content Brief를 작성할 때 따라야 하는 상세 행동 지침입니다.

---

## 1. 검색어 선정 및 용어 브릿징 원칙 (Term Bridging)
네이버 검색 사용자는 기술적 용어(PTZ, RightSight 등) 대신 일상적인 문제 표현을 검색합니다. 따라서 Brief에는 반드시 두 가지 층위의 용어를 함께 배치해야 합니다.

1. **일반인 표현 (Layman Terms)**:
   - "말하는 사람 따라가는 카메라", "회의실 마이크 울림 잡는 법", "노트북 하나로 회의실 TV 연결"
   - 독자의 클릭을 유도하고 공감을 형성하는 도입부 훅(Hook)으로 활용
2. **전문 기술 표현 (Technical Terms)**:
   - "Speaker Tracking", "Acoustic Echo Cancellation (AEC)", "BYOD Room System", "Beamforming Mic"
   - 글의 권위와 신뢰성을 부여하고 기술적 원리를 규명하는 본문 핵심부로 활용

---

## 2. 콘텐츠 구성 비율 (Content Type Mix)
Brief 작성 시 `content_type_mix`는 아래 5개 요소의 합계가 **정확히 100%**가 되도록 배분합니다:

```yaml
content_type_mix:
  problem: 20      # 사용자가 현장에서 겪는 고통 및 증상 분석
  mechanism: 35    # 왜 그런 문제가 생기고 기술적으로 어떻게 해결되는지 원리
  howto: 30        # 실제 환경 세팅 가이드 및 단계별 설정법
  comparison: 10   # 대안 기술 또는 하드웨어 방식 비교
  review: 5        # 실제 구축 후 체감 효과 및 요약
```

---

## 3. 자연스러운 제품 연결 (Product Bridge)
- **과도한 광고성 배제**: 글의 70% 이상은 순수한 정보 전달 및 기술 원리 설명이어야 합니다.
- **논리적 브릿지**: "이 원리를 가장 안정적으로 구현한 대표적 하드웨어 아키텍처"로서 제품(Logitech Rally Bar, MeetUp 2 등)을 제시합니다.
- **명확한 한계 고지**: 완벽한 만능 장비로 묘사하지 않고, 수용 인원 및 공간 크기(예: 8인 이하, 15인 이상 시 오디오 수음을 위한 마이크포드 추가 필요 등)의 명확한 제약 사항을 함께 기재하도록 지시합니다.

---

## 4. 5단계 중복 검사 절차 (Duplicate Check Gate)
새로운 Brief를 작성하기 전, 반드시 다음 5단계를 거쳐 기존 글과의 중복을 방지합니다:
1. **1차 (Exact Keyword)**: `CONTENT_REGISTRY.csv`에서 대표 키워드 일치 여부 확인
2. **2차 (Normalized Keyword)**: 공백 및 특수문자 제거 후 정규화 비교 (예: "화상 회의" == "화상회의")
3. **3차 (Canonical Topic)**: 표준 주제 개념군(예: `speaker_tracking_camera`) 비교
4. **4차 (Search Intent)**: 동일 주제라도 `mechanism`(원리) vs `how_to`(설정법) vs `comparison`(비교)에 따라 신규 발행 가능 여부 판별
5. **5차 (One-line Purpose)**: 기존 글의 핵심 한 줄 목적과 대조하여 고유한 가치가 입증될 때만 신규 생성
   
---

## 5. 시각 자산 계획 (Asset Plan) 및 마스터 에셋 연동 규격
Keyword AI는 Brief 기획 시 독자의 이탈을 방지하고 체감 가치를 전달하기 위해 반드시 `asset_plan` 항목을 설계해야 합니다.

### Brief 내 asset_plan 스키마 예시:
```yaml
asset_plan:
  - asset_need_id: AN-001
    section: SEC-01
    purpose: 화자 전환 및 트래킹 시각적 훅 (3초 루프)
    asset_type: gif
    suggested_feature: RightSight2.SpeakerView
  - asset_need_id: AN-002
    section: SEC-03
    purpose: 화각 3대 모드(Group/Speaker/Grid) 비교 다이어그램
    asset_type: diagram
    suggested_feature: RightSight2.Comparison
  - asset_need_id: AN-003
    section: SEC-07
    purpose: 대표 하드웨어(Rally Bar) 제품 외관 및 마운트 샷
    asset_type: image
    suggested_product: LOGI-RALLY-BAR
```

- **자동 바인딩 원리**: Brief가 생성되면 파이프라인(`resolve_assets.py`)이 마스터 레지스트리(`03_sources/assets/INDEX.yaml`)에서 해당 제품/기능과 일치하는 공인 미디어(GIF/다이어그램/사진)를 자동 탐색하여 `working/{content_id}/assets/asset-index.yaml`로 연결합니다.
- **Writer AI 전달**: 조립된 에셋은 `TASK.md`에 `{{asset:AST-ID}}` 형태로 주입되어, 테크니컬 라이터가 글을 쓸 때 즉시 활용할 수 있게 됩니다.

---

## 6. 가이드 변경 이력 (Changelog)

| 버전 (Version) | 개정일자 (Date) | 개정 내용 (Changes) | 승인자 |
| :--- | :--- | :--- | :--- |
| **v1.0.0** | 2026-09-22 | - 초기 주간 AI 콘텐츠 운영 시스템 v1.0 가이드 제정<br>- 5대 구성 비율(총합 100%) 및 5단계 중복 검사 규정 확정 | System Architect |
| **v1.1.0** | 2026-09-28 | - 시각 자산 계획(`asset_plan`) 설계 규격 추가<br>- 마스터 레지스트리(`INDEX.yaml`) 자동 바인딩 및 Writer AI 연동 원칙 명시 | System Architect |

