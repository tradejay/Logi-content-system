# 고객 중심 콘텐츠 작성 및 시각 자산 바인딩 규격 (Customer-Friendly Writing & Asset Binding Policy)

- **Version**: 1.2.0
- **Enacted**: 2026-09-23
- **Scope**: All Content Generation (02_writer_ai), Review (04_review), and Export (05_publish)

---

## 1. 이중 레이어 원칙 (Dual-Layer Mandate)

모든 본문 섹션은 단순 기술 나열을 금지하며, 다음 두 층을 반드시 결합해야 한다:
```text
Technical Layer (공학적 수치, 동작 조건, 사양)
       +
Customer Meaning Layer (사용자 체감, 회의 변화, 의사결정 기준)
```

### "So What?" 4단계 변환 공식
본문에 기술적 Fact가 등장할 때마다 다음 4단계를 충족해야 한다:
1. **FACT**: 검증된 공식 수치 및 기술 조건 (예: Speaker View 권장거리 4.5m)
2. **WHAT IT MEANS**: 독자에게 그것이 실질적으로 의미하는 바 (참석자의 테이블 좌석 거리가 추적 품질을 좌우함)
3. **WHEN IT MATTERS**: 어떤 환경이나 상황에서 결정적인가 (세로로 긴 직사각형 중대형 회의실, 끝자리가 먼 경우)
4. **WHAT USER SHOULD DO**: 사용자가 취해야 할 실질적인 조치 (회의실 실측 후 카메라 위치 조정 또는 Group View/마이크 팟 추가)

---

## 2. 고객 친화 필수 모듈 (Customer Modules)

초안 작성 시 기술 모듈 외에 다음 고객 친화 모듈을 적극 배치한다:
- `USER_SCENARIO`: 회의 현장의 불편과 답답함 (발언자가 작게 보여 표정이 안 읽힘 등)
- `BEFORE_AFTER`: 기능 도입 전(수동 리모컨 조작)과 도입 후(자동 프레이밍) 비교
- `WHAT_YOU_WILL_SEE`: 실제 회의 화면이 어떻게 전환되는지 직관적 묘사
- `CHOICE_GUIDE`: 단순 기능 설명 대신 "어떤 화면을 골라야 하는가?" 의사결정 트리 제공
- `WHAT_TO_CHECK`: 도입/설치 전 회의실 환경 셀프 진단 체크리스트

---

## 3. 제약사항(Limitations) 서술 원칙: Limit -> Impact -> Workaround

제약사항을 쓸 때 절대로 **금지사항이나 결함처럼 서술하지 않는다.**
- ❌ **나쁜 예**: "유리벽에서는 음향 반사로 화자 추적이 불가능하거나 오동작한다."
- ⭕ **좋은 예**: "통유리 회의실이라고 해서 화자 추적을 포기할 필요는 없습니다. 반사가 많은 공간에서는 음향 위치 판단에 편차가 생길 수 있으므로, 테이블 중앙에 랠리 마이크 팟을 추가하거나 흡음재를 보완하면 안정적으로 화자를 잡아낼 수 있습니다."

---

## 4. 무관한 제품 데이터시트 스펙 나열 엄격 금지

Product Master에 데이터가 존재한다는 이유만으로 본문에 무관한 스펙을 나열하지 않는다.
- 화자 추적 및 카메라 가이드에서 **전원 어댑터 규격(19V, 4.74A), 소비전력, HDMI 단자 개수, Kensington 락** 등은 본문 삽입 금지.
- **주제와 직접 관련된 스펙만 허용**: 메인 4K 카메라, AI 뷰파인더 서브 렌즈, 6개 빔포밍 마이크, 수음 반경(7m), 화자 추적 권장거리(4.5m).

---

## 5. 시각 자산(Asset) 자동 바인딩 및 문법 규격

1. **표준 본문 문법**:
   - `{{asset:AST-ID}}` 단일 문법으로 고정한다.
   - 예: `{{asset:AST-RS2-SPEAKER-001}}`, `{{asset:AST-RS2-COMPARE-001}}`
2. **기존 자산 존재 시 플레이스홀더 금지**:
   - `03_sources/assets/INDEX.yaml` 및 작업 컨텍스트 `assets/asset-index.yaml`에 일치하는 자산이 있을 경우 **절대로 `[ASSET_REQUIRED]`를 남겨서는 안 된다.**
   - 매칭 자산이 없는 경우에만 `[ASSET_REQUIRED: 구체적 필요 사유]`를 사용한다.
3. **HTML 렌더링 카드 규격**:
   - HTML 컴파일러는 `{{asset:AST-ID}}`를 구글 드라이브 영구 고화질 URL, 공식 캡션, 그리고 `💡 실제 체감 효과 (Customer Message)` 박스가 포함된 카드 블록으로 변환한다.
