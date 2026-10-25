# SAFETY CORE (기술 안전성 및 클레임 무결성 규격)

- **Version**: 2.0 (vNext)
- **Scope**: 기술 사실 검증, 제품 스코프 및 플랫폼 분리 규칙

---

## 1. 수치 및 클레임 절대 규칙 (Strict Numerical Verification)
- **단위 포함 수치 엄격 검증**:
  - `m`, `cm`, `mm`, `dB`, `lux`, `°`, `%`, `초`, `ms`, `배` 등 단위가 포함된 모든 숫자는 공식 지식 팩(Knowledge Pack)의 `facts`에 등록된 수치만 사용한다.
  - 임의의 "0.1초 만에 전환", "99.9% 정확도" 등 상상 수치는 시스템에 의해 즉시 차단(HARD BLOCK)된다.

---

## 2. 디바이스 기능 vs 플랫폼 기능의 엄격한 분리
- **디바이스 로컬 기능 (Device-Native)**: 기기 펌웨어(CollabOS)가 로컬 연산으로 처리하는 기능 (RightSight 2, Group/Speaker/Grid View). BYOD 모드에서도 단독 작동.
- **플랫폼 클라우드 기능 (Platform-Hosted)**: Zoom Rooms Smart Gallery, Teams Rooms IntelliFrame 등 클라우드/소프트웨어 기능.
- **금지 서술**: "RightSight 2를 쓰려면 Zoom 유료 라이선스가 필수"라거나 "Teams에서는 RightSight 2가 동작하지 않는다"는 식의 왜곡 서술 엄금.

---

## 3. 결측 증거 처리 (Missing Evidence)
- 글 작성 중 꼭 필요한 설정 경로인데 주입된 지식 팩이나 소스에 없다면, 임의로 경로를 날조하지 말고 상위 메뉴 수준에서 안내하거나 확인된 사실만 서술한다.

---

## 4. 컴포넌트 역할 임의 합성 금지 (오디오 수음 vs 카메라 위치 추적)
- **Rally Mic Pod의 역할**: 테이블 위 발언자의 음성을 수음하여 원격지에 전달하는 **오디오 수음(Audio Pickup/AEC) 장치**일 뿐이다. 마이크 팟에는 3D 공간 방위각이나 카메라를 유도하는 위치 좌표가 일체 없다.
- **RightSight 2 화자 추적의 주체**: 오직 **Rally Bar 본체 전면의 6개 빔포밍 마이크 어레이(TDoA)와 내장 AI 뷰파인더(비전 센서)**로만 발언자의 위치를 연산한다.
- **절대 금지 왜곡 서술**: "마이크 팟을 증설해야 최적의 화자 추적 성능이 보장된다", "사각지대 없는 화자 추적을 위해 마이크 팟을 추가한다" 등의 자의적 기능 결합 엄금. 마이크 팟 증설은 순수하게 **'원격지에 전달되는 음성 수음 품질 개선'** 목적임을 명확히 구분한다.

---

## 5. 공식 고유 기능 명칭 도용 및 임의 차용 엄금 (Smart Switching 오용 금지)
- **Smart Switching의 공식 정의**: **Logitech Sight(테이블 중앙 카메라)와 Rally Bar(전면 카메라) 사이에서 참가자가 응시하는 방향에 따라 두 카메라 간 피드를 자동으로 전환하는 다중 카메라 연동 기능**(CollabOS 1.13+ 지원)의 공식 명칭이다.
- **RightSight 2 Speaker View 프레이밍**: 단일 Rally Bar 내부에서 메인 PTZ 렌즈가 발언자 중심으로 클로즈업 전환하는 것은 Speaker View의 고유 동작(Speaker Framing Transition)일 뿐이며, 이를 `Smart Switching`이라고 표기하는 것은 엄격히 금지된다.
- **원칙**: 기능명은 제조사 공식 기술 백서에 정의된 고유 기능과 1:1로 일치해야 하며, 어감이 그럴듯하다고 해서 다른 제품군의 기술 명칭을 도용해서는 안 된다.


