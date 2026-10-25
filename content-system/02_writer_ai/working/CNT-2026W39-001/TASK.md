# Writing Task: CNT-2026W39-001 (Playbook-Driven vNext)

- **Content ID**: `CNT-2026W39-001`
- **Batch ID**: `BATCH-2026W39`
- **Primary Keyword**: `화자추적카메라`
- **Layman Search Terms**: 말하는 사람 따라가는 카메라, 발표자 자동으로 비춰주는 카메라, 회의실 화면 자동 확대
- **Canonical Topic**: `speaker_tracking_camera`
- **Article Goal**: 화자 추적 카메라의 작동 화면과 원리를 쉽게 이해하고 회의실에 필요한 모드를 판단하게 한다.

---

## 📚 Writing Modes (Playbooks)
- **PRIMARY PLAYBOOK**: `PB-MECHANISM-EXPLAINER` (`guides/primary.md`)
- **SECONDARY PLAYBOOKS**: PB-PRODUCT-SELECTION, PB-CONFIG-HOWTO (`guides/secondary-*.md`)
- **CORE CONSTITUTION**: `guides/WRITING_CORE.md`, `guides/STYLE_CORE.md`, `guides/SAFETY_CORE.md`

---

## 🙋 핵심 독자 질문 (Reader Questions - 이 순서로 궁금증을 해결하십시오)
- **Q1**: 말하는 사람을 알아서 비춰주는 카메라가 진짜 있나요? (실제 화면 데모)
- **Q2**: Group View, Speaker View, Grid View는 무엇이 다르고 내 회의실엔 무엇이 맞나요?
- **Q3**: 기침 소리나 펜 떨어뜨리는 소리에도 카메라가 휙휙 돌아가지 않나요? (센서 퓨전 원리)
- **Q4**: 우리 회의실이 세로로 길거나 통유리벽인데도 잘 될까요? (거리 및 잔향 대처)
- **Q5**: 우리는 Zoom(또는 Teams)을 쓰는데 관리자 메뉴에서 쉽게 켤 수 있나요?
- **Q6**: 이 기능을 쓰려면 어떤 제품을 사야 하고, 마이크 팟 확장이 필요한가요?

---

## 💡 권장 흐름 (Suggested Flow - 필요 시 자연스럽게 조정 가능)
1. 불편 공감 및 실제 발언자 전환 화면 확인 (GIF 시연)
2. 우리 팀 회의에 맞는 뷰 모드 선택 가이드 (결정 트리)
3. 기침 소리를 거르고 사람을 찾는 듀얼 센서 작동 원리
4. 우리 회의실 환경 셀프 점검 (거리 4.5m 및 통유리벽 대응법)
5. Zoom Rooms 및 기기 온스크린 1분 세팅 매뉴얼
6. 화자 추적을 구현하는 대표 장비 및 마이크 팟 확장 팁
7. 회의실 평면도 기반 무료 화각 진단 안내 (Soft CTA)

---

## ⚖️ 지식 및 스펙 제어 지침
### ✅ 반드시 포함할 핵심 (Must Cover):
- 말하는 사람 따라가는 카메라 (일상어 인트로)
- Speaker View vs Group View vs Grid View 체감 차이
- 음향 빔포밍 도달 시간차(TDoA)와 비전 센서 융합
- 화자 추적 권장 거리(4.5m) 및 테이블 끝자리 대응
- 통유리벽 잔향 발생 시 마이크 팟(Mic Pod) 보완책
- Zoom Rooms 연동 및 BYOD 모드 독립 작동
- Logitech Rally Bar 듀얼 렌즈(AI 뷰파인더) 하드웨어

### 🚫 생략할 스펙 (Can Omit - 독자의 의사결정에 방해되는 전기/나사/포트 세부 스펙):
- 전원 어댑터 전압(19V/4.74A) 및 소비전력
- 후면 HDMI 포트 핀맵
- 패키징 나사 규격

### ⚠️ 절대 피할 형식 (Avoid - 기계적 템플릿 금지):
- FACT: ... WHAT IT MEANS: 기계적 레이블 박스
- 첫머리부터 TDoA 등 약어 도배
- 완벽한/최적의 등 미사여구

---

## 🖼️ 활용 가능한 시각 자산 (Candidate Assets)
*독자가 눈으로 확인하고 싶은 가장 자연스러운 순간에 `{{asset:AST-ID}}` 문법으로 배치하십시오.*
- `{{asset:AST-RS2-SPEAKER-001}}` : [GIF] RightSight2.SpeakerView - 발언자가 바뀔 때 음향 위치 감지와 AI 분석으로 새 화자를 부드럽게 클로즈업하는 Speaker View 동작
  - 추천 활용 맥락: "원격 참석자도 회의실에서 지금 누가 말하고 있는지 즉각 알아볼 수 있어 회의 몰입도가 극대화됩니다."
- `{{asset:AST-RS2-GROUP-001}}` : [GIF] RightSight2.GroupView - 참석자 구성이나 위치가 달라져도 회의실 전체를 자동으로 한 화면에 맞춰주는 Group View 동작
  - 추천 활용 맥락: "회의 시작 전 리모컨으로 카메라 각도를 맞출 필요 없이, 참석자 전원이 자연스럽게 화면에 들어옵니다."
- `{{asset:AST-RS2-GRID-001}}` : [GIF] RightSight2.GridView - 각 참석자를 개별 타일로 감지하여 균등하게 배치하는 Grid View 다인 프레이밍
  - 추천 활용 맥락: "테이블 끝자리에 앉은 사람도 앞자리 사람과 동일한 크기의 타일로 표시되어 회의 평등성이 확보됩니다."
- `{{asset:AST-RS2-COMPARE-001}}` : [DIAGRAM] RightSight2.Comparison - 회의 목적과 룸 크기에 따라 선택하는 RightSight 2의 3대 모드 (Group / Speaker / Grid View)
  - 추천 활용 맥락: "전체 보고에는 Group View, 토론 회의에는 Speaker View, 동등한 참여에는 Grid View를 선택하면 됩니다."
- `{{asset:AST-RS2-HARDWARE-001}}` : [DIAGRAM] RightSight2.AIFinder - 메인 4K PTZ 카메라와 인원 감지 전용 AI 뷰파인더의 듀얼 렌즈 퓨전 아키텍처
  - 추천 활용 맥락: "카메라가 화자를 비추는 동안에도 AI 뷰파인더가 룸 전체를 감시하므로 움직임에 딜레이 없이 반응합니다."
- `{{asset:AST-PROD-RALLY-BAR-001}}` : [IMAGE] Hardware.Overview - 중대형 회의실을 위한 올인원 비디오 바 로지텍 랠리바 (Rally Bar)
  - 추천 활용 맥락: "스피커, 빔포밍 마이크, 듀얼 카메라가 하나로 통합되어 배선과 설치가 깔끔합니다."


---

## 🔓 Writer AI 편집 자유도 선언 (Editorial Freedom)
1. **높은 편집 자유도 (HIGH)**: 고정된 목차 체크리스트는 없습니다. 독자의 질문 흐름에 맞춰 소제목을 자유롭고 매력적으로 구성하십시오.
2. **낮은 사실 자유도 (LOW)**: 공식 수치나 스펙 범위를 임의 날조해서는 안 됩니다. 기술 수치는 `knowledge/*`를 엄격히 준수하십시오.
3. **자연스러운 스토리텔링**: `FACT:`나 `WHAT IT MEANS:` 같은 기계적 레이블을 본문에 출력하지 마십시오.

작성 완료 후 초안은 다음 경로에 저장하십시오:
`../../drafts/CNT-2026W39-001.draft.md`
