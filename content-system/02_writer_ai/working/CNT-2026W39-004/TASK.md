# Writing Task: CNT-2026W39-004 (Playbook-Driven vNext)

- **Content ID**: `CNT-2026W39-004`
- **Batch ID**: `BATCH-2026W39`
- **Primary Keyword**: `화상회의 구축`
- **Layman Search Terms**: 터치스크린 회의실, 노트북 안 꽂는 화상회의
- **Canonical Topic**: `smart_meeting_room_touch_controller`
- **Article Goal**: 회의 시작 시간을 단축시키는 원터치 터치패널 스마트 회의실 구축법을 안내한다.

---

## 📚 Writing Modes (Playbooks)
- **PRIMARY PLAYBOOK**: `PB-PLATFORM-INTEGRATION` (`guides/primary.md`)
- **SECONDARY PLAYBOOKS**: PB-CONFIG-HOWTO, PB-PRODUCT-SELECTION (`guides/secondary-*.md`)
- **CORE CONSTITUTION**: `guides/WRITING_CORE.md`, `guides/STYLE_CORE.md`, `guides/SAFETY_CORE.md`

---

## 🙋 핵심 독자 질문 (Reader Questions - 이 순서로 궁금증을 해결하십시오)
- **Q1**: 매번 회의실에 노트북 들고 가서 케이블 꽂지 않고 원터치로 시작하는 방법이 있나요?
- **Q2**: 로지텍 Tap(터치 컨트롤러)은 어떻게 연결되고 무엇을 제어할 수 있나요?
- **Q3**: Zoom Rooms나 Teams Rooms 전용 룸 시스템을 구축하면 회의가 어떻게 달라지나요?
- **Q4**: PoE 단일 케이블로 배선을 깔끔하게 끝내는 구축 요령은 무엇인가요?
- **Q5**: 개인 노트북을 가져와서 화면 공유할 때는 어떻게 연결하나요?

---

## 💡 권장 흐름 (Suggested Flow - 필요 시 자연스럽게 조정 가능)
1. 회의 시작 전 케이블 찾고 디스플레이 맞추느라 허비되는 시간 낭비 공감
2. 원터치 스마트 회의실(Zoom/Teams Rooms)과 전용 터치 컨트롤러(Tap)의 개념
3. 배선 혁신: Cat6A 단일 PoE 케이블로 연결되는 깔끔한 테이블 환경
4. 현장 관리자 3단계 연동 및 기기 프로비저닝 가이드
5. 스마트 화상회의실 전환 체크리스트 및 무료 설계 지원

---

## ⚖️ 지식 및 스펙 제어 지침
### ✅ 반드시 포함할 핵심 (Must Cover):
- 노트북 연결 스트레스 없는 원터치 회의 시작
- Logitech Tap / Tap IP 터치 컨트롤러
- Zoom Rooms 및 Teams Rooms 플랫폼 연동
- PoE 케이블 단일 배선 및 테이블 정리

### 🚫 생략할 스펙 (Can Omit - 독자의 의사결정에 방해되는 전기/나사/포트 세부 스펙):
- 카메라 광학 줌 렌즈 내부 모터 스펙
- 스피커 데시벨 세부 출력 수치

### ⚠️ 절대 피할 형식 (Avoid - 기계적 템플릿 금지):
- 기계적 레이블
- 과장된 엔터프라이즈 홍보 문구
- 소프트웨어 라이선스 정책 왜곡

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
- `{{asset:AST-PROD-TAP-IP-001}}` : [IMAGE] Controller.Touch - 네트워크 PoE 기반 터치 컨트롤러 로지텍 Tap IP
  - 추천 활용 맥락: "회의실 테이블에서 터치 한 번으로 미팅에 참여하고 카메라 모드를 간편하게 변경할 수 있습니다."


---

## 🔓 Writer AI 편집 자유도 선언 (Editorial Freedom)
1. **높은 편집 자유도 (HIGH)**: 고정된 목차 체크리스트는 없습니다. 독자의 질문 흐름에 맞춰 소제목을 자유롭고 매력적으로 구성하십시오.
2. **낮은 사실 자유도 (LOW)**: 공식 수치나 스펙 범위를 임의 날조해서는 안 됩니다. 기술 수치는 `knowledge/*`를 엄격히 준수하십시오.
3. **자연스러운 스토리텔링**: `FACT:`나 `WHAT IT MEANS:` 같은 기계적 레이블을 본문에 출력하지 마십시오.

작성 완료 후 초안은 다음 경로에 저장하십시오:
`../../drafts/CNT-2026W39-004.draft.md`
