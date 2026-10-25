---
playbook_id: PB-PLATFORM-INTEGRATION
name: Platform Integration
version: 1.0
category: platform
use_when:
  - 카메라 하드웨어와 화상회의 플랫폼(Zoom Rooms, Teams Rooms, BYOD) 간의 역할 분담과 연동을 설명할 때
  - "이게 카메라 기능인지 플랫폼 기능인지" 혼동하는 독자를 안내할 때
avoid_when:
  - 플랫폼과 무관한 순수 하드웨어 스펙 대조일 때
  - 일반 개인용 화상회의 웹캠 사용법일 때
reader_state: "우리 회사는 Zoom(또는 Teams)을 쓰는데, 로지텍 카메라를 사면 그 플랫폼에서 어떻게 연동되고 제어되는지 궁금함"
primary_goal: "디바이스 고유 기능과 플랫폼 클라우드 기능의 역할을 명확히 구분하고, 매끄러운 연동 환경을 안내한다"
recommended_assets:
  - EXPLAIN
  - SCREENSHOT
  - PROVE
compatible_secondary:
  - PB-CONFIG-HOWTO
  - PB-PRODUCT-SELECTION
---

# Platform Integration Playbook (플랫폼 연동형 글쓰기 가이드)

## 1. PURPOSE
"RightSight 2를 쓰려면 Zoom Rooms 유료 라이선스가 필요한가?", "노트북만 꽂아서 쓰는 BYOD 모드에서도 화자 추적이 되는가?"처럼 **하드웨어 디바이스 기능과 화상회의 플랫폼 소프트웨어 간의 경계와 상호 운용성**을 명쾌하게 정리합니다.

## 2. READER STATE
"회의실 카메라를 사려고 하는데, 우리 회사에서 쓰는 줌(Zoom)이나 팀즈(Teams) 소프트웨어와 호환이 100% 잘 될까?"

## 3. SUCCESS CONDITION
- **디바이스 로컬 기능(Device-Native)**과 **플랫폼 클라우드 기능(Platform-Hosted)**을 시각적 다이어그램이나 텍스트로 명확히 분리한다.
- "플랫폼 라이선스가 없으면 카메라 기능이 아예 동작하지 않는다"는 식의 왜곡 서술을 엄단한다.
- 사용자가 개인 노트북을 USB로 직결하는 **BYOD(Bring Your Own Device) 모드**에서의 실제 동작 여부를 명확히 밝힌다.

## 4. TYPICAL QUESTIONS
- "Zoom Rooms 컨트롤러 화면에서 로지텍 카메라 각도를 직접 바꿀 수 있나요?"
- "Teams Rooms의 IntelliFrame과 로지텍의 Grid View는 서로 충돌하지 않나요?"
- "전용 룸 PC가 없는 작은 방에서 노트북만 꽂아도 화자 추적이 되나요?"

## 5. GOOD OPENING PATTERNS
- **⭕ 좋은 도입**: "회의실 화상 솔루션을 구축할 때 가장 많은 질문을 받는 부분 중 하나가 바로 '카메라 기기 기능'과 '화상회의 프로그램 기능'의 역할 분담입니다. 줌(Zoom)이나 팀즈(Teams)를 쓸 때, 화자 추적 화면을 만들어내는 주체는 카메라 장비일까요, 아니면 클라우드 프로그램일까요? 두 영역의 역할을 명확히 알면 장애가 생겼을 때도 원인을 단번에 찾을 수 있습니다."
- **❌ 나쁜 도입**: "본 문서는 CollabOS와 Zoom Rooms API 간의 IPC 소켓 프로토콜 명세입니다."

## 6. RECOMMENDED FLOW
1. **역할 분담 한눈에 보기**: 디바이스 로컬 연산 vs 플랫폼 클라우드 연산 구조도
2. **대표 플랫폼별 연동 방식**:
   - Zoom Rooms 환경: Tap 컨트롤러의 Camera Control 연동 및 동작 흐름
   - Teams Rooms 환경: 네이티브 렌더링 및 프로파일 매핑
3. **USB BYOD(노트북 직결) 모드의 비밀**:
   - 룸 PC 없이도 카메라 온보드 AI 칩셋이 스스로 화자 추적을 수행하는 원리
4. **플랫폼 전환 시의 유연성**: 줌에서 팀즈로 플랫폼을 바꿔도 하드웨어 재구매가 필요 없는 이유

## 7. ASSET STRATEGY
- **EXPLAIN**: 디바이스 온보드 연산과 플랫폼 클라우드 연산의 2계층 분리 다이어그램
- **SCREENSHOT**: Zoom Rooms 컨트롤러 화면의 카메라 제어 UI
- **PROVE**: 노트북에 USB 케이블 하나만 연결하여 구동하는 BYOD 현장 사진

## 8. DO NOT
- 플랫폼 라이선스 정책을 제조사 하드웨어 필수 조건처럼 왜곡하지 않는다.
- 특정 플랫폼의 클라우드 AI 기능(예: Zoom AI Companion)을 로지텍 하드웨어 기술인 것처럼 뒤섞지 않는다.
