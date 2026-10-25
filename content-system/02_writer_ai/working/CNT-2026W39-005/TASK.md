# Writing Task: CNT-2026W39-005 (Playbook-Driven vNext)

- **Content ID**: `CNT-2026W39-005`
- **Batch ID**: `BATCH-2026W39`
- **Primary Keyword**: `대회의실 화상회의`
- **Layman Search Terms**: 큰 회의실 화상회의 장비, 스피커 마이크 분리형 카메라
- **Canonical Topic**: `large_boardroom_conference_system`
- **Article Goal**: 15~30인 대형 회의실에서 분리형 카메라와 듀얼 스피커, 허브 배선으로 완성하는 랠리 플러스 설계법을 제시한다.

---

## 📚 Writing Modes (Playbooks)
- **PRIMARY PLAYBOOK**: `PB-PRODUCT-SELECTION` (`guides/primary.md`)
- **SECONDARY PLAYBOOKS**: PB-PRODUCT-COMPARISON, PB-CONFIG-HOWTO (`guides/secondary-*.md`)
- **CORE CONSTITUTION**: `guides/WRITING_CORE.md`, `guides/STYLE_CORE.md`, `guides/SAFETY_CORE.md`

---

## 🙋 핵심 독자 질문 (Reader Questions - 이 순서로 궁금증을 해결하십시오)
- **Q1**: 왜 15인 이상 대형 룸에서는 올인원 비디오 바 하나로 커버하기 어려운가요?
- **Q2**: 카메라, 스피커, 마이크가 분리된 모듈형 시스템(Rally Plus)의 장점은 무엇인가요?
- **Q3**: Table Hub와 Display Hub로 테이블-디스플레이 사이 배선을 어떻게 단순화하나요?
- **Q4**: 대형 룸에서 듀얼 디스플레이와 다중 마이크를 구축할 때 필수 고려사항은 무엇인가요?
- **Q5**: 우리 회사 임원 회의실 규모에 맞는 최적의 시스템 레이아웃은 어떻게 짜야 하나요?

---

## 💡 권장 흐름 (Suggested Flow - 필요 시 자연스럽게 조정 가능)
1. 대형 이사회실의 특수성 (먼 거리, 큰 스피커 볼륨, 다수 참석자) 및 올인원 바의 한계
2. 모듈형 분리 시스템 로지텍 랠리 플러스(Rally Plus) 아키텍처
3. Table Hub와 Display Hub를 통한 배선 정리 (Cat6A 단일 케이블 링크)
4. 대형 룸 음향 설계: 듀얼 독립 스피커와 다중 마이크 팟 확장
5. 이사회실 구축 체크리스트 및 엔지니어링 1:1 방문 실사 컨설팅 안내

---

## ⚖️ 지식 및 스펙 제어 지침
### ✅ 반드시 포함할 핵심 (Must Cover):
- 15~30인 대형 회의실에서 일체형 바의 물리적 한계
- Logitech Rally Plus 분리형 모듈 아키텍처
- Table Hub & Display Hub 배선 단순화
- 독립 듀얼 스피커와 확장 마이크 팟 구성

### 🚫 생략할 스펙 (Can Omit - 독자의 의사결정에 방해되는 전기/나사/포트 세부 스펙):
- 소형 허들룸 전용 액세서리 스펙
- 나사 규격 및 패키징 박스 크기

### ⚠️ 절대 피할 형식 (Avoid - 기계적 템플릿 금지):
- 기계적 레이블 박스
- 소형 룸 장비와 혼동 유발
- 근거 없는 찬양 일색 문체

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
- `{{asset:AST-PROD-RALLY-PLUS-001}}` : [IMAGE] Hardware.Modular - 대형 회의실을 위한 모듈형 프리미엄 VC 시스템 Logitech Rally Plus
  - 추천 활용 맥락: "최대 7개 마이크 팟과 독립형 듀얼 스피커로 초대형 회의 공간도 완벽하게 커버합니다."


---

## 🔓 Writer AI 편집 자유도 선언 (Editorial Freedom)
1. **높은 편집 자유도 (HIGH)**: 고정된 목차 체크리스트는 없습니다. 독자의 질문 흐름에 맞춰 소제목을 자유롭고 매력적으로 구성하십시오.
2. **낮은 사실 자유도 (LOW)**: 공식 수치나 스펙 범위를 임의 날조해서는 안 됩니다. 기술 수치는 `knowledge/*`를 엄격히 준수하십시오.
3. **자연스러운 스토리텔링**: `FACT:`나 `WHAT IT MEANS:` 같은 기계적 레이블을 본문에 출력하지 마십시오.

작성 완료 후 초안은 다음 경로에 저장하십시오:
`../../drafts/CNT-2026W39-005.draft.md`
