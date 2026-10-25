# Writing Task: CNT-2026W39-003 (Playbook-Driven vNext)

- **Content ID**: `CNT-2026W39-003`
- **Batch ID**: `BATCH-2026W39`
- **Primary Keyword**: `회의실 마이크`
- **Layman Search Terms**: 테이블 마이크, 회의실 소리 안 울리는 마이크
- **Canonical Topic**: `meeting_room_microphone_acoustics`
- **Article Goal**: 긴 회의실 테이블에서 말소리가 작거나 울리는 문제를 랠리 마이크 팟 배치로 해결하도록 돕는다.

---

## 📚 Writing Modes (Playbooks)
- **PRIMARY PLAYBOOK**: `PB-PROBLEM-DIAGNOSIS` (`guides/primary.md`)
- **SECONDARY PLAYBOOKS**: PB-TROUBLESHOOTING, PB-PRODUCT-SELECTION (`guides/secondary-*.md`)
- **CORE CONSTITUTION**: `guides/WRITING_CORE.md`, `guides/STYLE_CORE.md`, `guides/SAFETY_CORE.md`

---

## 🙋 핵심 독자 질문 (Reader Questions - 이 순서로 궁금증을 해결하십시오)
- **Q1**: 왜 카메라 내장 마이크로는 회의실 끝자리 발언자의 목소리가 작게 들릴까요?
- **Q2**: 통유리벽이나 긴 테이블에서 소리가 울리는 근본 원인은 무엇인가요?
- **Q3**: 테이블 중앙에 놓는 확장 마이크 팟(Mic Pod)은 몇 개까지 연결할 수 있나요?
- **Q4**: 테이블 위 배선을 지저분하지 않고 깔끔하게 정리하는 방법(마이크 팟 허브)은 무엇인가요?
- **Q5**: 지금 당장 우리 회의실에서 해볼 수 있는 음향 점검 요령은 무엇인가요?

---

## 💡 권장 흐름 (Suggested Flow - 필요 시 자연스럽게 조정 가능)
1. 중대형 회의실에서 끝자리 목소리가 안 들리는 현장 고충 공감
2. 거리와 실내 반사음(잔향)이 마이크 수음에 미치는 메커니즘
3. 단독 마이크 한계 극복: 랠리 마이크 팟(Rally Mic Pod) 데이지체인 토폴로지
4. 깔끔한 인테리어를 위한 Mic Pod Hub 분기 배선 가이드
5. 회의실 길이별 마이크 증설 체크리스트 및 음향 무료 진단 (CTA)

---

## ⚖️ 지식 및 스펙 제어 지침
### ✅ 반드시 포함할 핵심 (Must Cover):
- 끝자리 목소리 픽업 저하 원인 (거리 및 유리벽 잔향)
- Rally Mic Pod 빔포밍 마이크 확장성
- 데이지체인 직렬 연결 및 마이크 팟 허브(Hub) 분기 구성
- 회의실 규모별 마이크 권장 수량

### 🚫 생략할 스펙 (Can Omit - 독자의 의사결정에 방해되는 전기/나사/포트 세부 스펙):
- 카메라 PTZ 모터 스펙
- 비디오 해상도 세부 스펙
- 전력 소비량

### ⚠️ 절대 피할 형식 (Avoid - 기계적 템플릿 금지):
- 기계적 레이블 박스
- 음향 논문 수준의 수식 나열
- 장비 교체만 능사라는 식의 서술

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
- `{{asset:AST-PROD-MIC-POD-001}}` : [IMAGE] Audio.Extension - 긴 테이블이나 대형 룸에서 음성 수음 범위를 확장하는 Rally Mic Pod
  - 추천 활용 맥락: "카메라에서 먼 좌석의 목소리도 마이크 팟을 통해 깨끗하게 전달되어 화자 추적 정확도가 높아집니다."


---

## 🔓 Writer AI 편집 자유도 선언 (Editorial Freedom)
1. **높은 편집 자유도 (HIGH)**: 고정된 목차 체크리스트는 없습니다. 독자의 질문 흐름에 맞춰 소제목을 자유롭고 매력적으로 구성하십시오.
2. **낮은 사실 자유도 (LOW)**: 공식 수치나 스펙 범위를 임의 날조해서는 안 됩니다. 기술 수치는 `knowledge/*`를 엄격히 준수하십시오.
3. **자연스러운 스토리텔링**: `FACT:`나 `WHAT IT MEANS:` 같은 기계적 레이블을 본문에 출력하지 마십시오.

작성 완료 후 초안은 다음 경로에 저장하십시오:
`../../drafts/CNT-2026W39-003.draft.md`
