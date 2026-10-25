# Writing Task: CNT-2026W39-002 (Playbook-Driven vNext)

- **Content ID**: `CNT-2026W39-002`
- **Batch ID**: `BATCH-2026W39`
- **Primary Keyword**: `소형 회의실 카메라`
- **Layman Search Terms**: 작은 회의실 카메라, 양옆 안 잘리는 웹캠
- **Canonical Topic**: `huddle_room_conference_camera`
- **Article Goal**: 3~5인 소형 회의실에서 양옆 사람 잘림 없이 깔끔하게 화상회의를 세팅하는 방식을 안내한다.

---

## 📚 Writing Modes (Playbooks)
- **PRIMARY PLAYBOOK**: `PB-PRODUCT-SELECTION` (`guides/primary.md`)
- **SECONDARY PLAYBOOKS**: PB-CONFIG-HOWTO, PB-PROBLEM-DIAGNOSIS (`guides/secondary-*.md`)
- **CORE CONSTITUTION**: `guides/WRITING_CORE.md`, `guides/STYLE_CORE.md`, `guides/SAFETY_CORE.md`

---

## 🙋 핵심 독자 질문 (Reader Questions - 이 순서로 궁금증을 해결하십시오)
- **Q1**: 테이블이 카메라와 가까워 양옆 사람이 화면에서 잘리는데 해결 방법이 있나요? (초광각 화각)
- **Q2**: 카메라, 마이크, 스피커가 하나로 합쳐진 올인원 비디오 바는 소형 룸에 어떻게 설치하나요?
- **Q3**: 로지텍 MeetUp 2는 기존 밋업 대비 무엇이 달라졌나요?
- **Q4**: 노트북 하나만 USB로 꽂아서 쓰는 BYOD 모드 세팅은 어떻게 하나요?
- **Q5**: 우리 허들룸에 설치할 때 벽걸이나 모니터 거치는 어떻게 구성하나요?

---

## 💡 권장 흐름 (Suggested Flow - 필요 시 자연스럽게 조정 가능)
1. 소형 허들룸의 고질적 불편 (양옆 사람 잘림, 어지러운 케이블) 공감
2. 허들룸 맞춤 화각 기준 제시 (초광각 120° 시야각의 필요성)
3. 콤팩트 올인원 비디오 바 MeetUp 2의 핵심 강점 (오디오/비전 통합)
4. 개인 노트북 원케이블 직결(USB-C BYOD) 연결 1분 세팅 가이드
5. 소형 회의실 공간 최적화 체크리스트 및 무상 상담 안내

---

## ⚖️ 지식 및 스펙 제어 지침
### ✅ 반드시 포함할 핵심 (Must Cover):
- 허들룸 양옆 사람 잘림 현상 공감
- 초광각 시야각과 자동 프레이밍
- MeetUp 2 올인원 폼팩터
- USB-C 원케이블 BYOD 연결법
- 소형 회의실 거치 및 설치 팁

### 🚫 생략할 스펙 (Can Omit - 독자의 의사결정에 방해되는 전기/나사/포트 세부 스펙):
- 대형 룸 전용 마이크 팟 확장 스펙
- 외부 DSP 믹서 연결
- 소비전력 세부 수치

### ⚠️ 절대 피할 형식 (Avoid - 기계적 템플릿 금지):
- 기계적 레이블 박스
- 완벽한/최적의 등 상투적 수식어
- 소형 룸에 대형 장비 강요

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
- `{{asset:AST-PROD-MEETUP2-001}}` : [IMAGE] Hardware.Overview - 소형 회의실 및 포커스 룸을 위한 차세대 AI 비디오 바 MeetUp 2
  - 추천 활용 맥락: "소형 룸에서도 USB 연결 하나로 최신 RightSight AI 기능을 바로 활용할 수 있습니다."


---

## 🔓 Writer AI 편집 자유도 선언 (Editorial Freedom)
1. **높은 편집 자유도 (HIGH)**: 고정된 목차 체크리스트는 없습니다. 독자의 질문 흐름에 맞춰 소제목을 자유롭고 매력적으로 구성하십시오.
2. **낮은 사실 자유도 (LOW)**: 공식 수치나 스펙 범위를 임의 날조해서는 안 됩니다. 기술 수치는 `knowledge/*`를 엄격히 준수하십시오.
3. **자연스러운 스토리텔링**: `FACT:`나 `WHAT IT MEANS:` 같은 기계적 레이블을 본문에 출력하지 마십시오.

작성 완료 후 초안은 다음 경로에 저장하십시오:
`../../drafts/CNT-2026W39-002.draft.md`
