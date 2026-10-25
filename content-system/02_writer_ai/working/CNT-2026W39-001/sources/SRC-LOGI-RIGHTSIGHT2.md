# Logitech RightSight 2 자동 프레이밍 및 화자 추적 기술 백서 (SRC-LOGI-RIGHTSIGHT2)

- **Source ID**: `SRC-LOGI-RIGHTSIGHT2`
- **Vendor**: Logitech
- **Evidence Level**: E1 (제조사 공식 기술 백서)
- **최종 검증일**: 2026-09-20
- **유효 기간**: 90일 (상태: VALID)

---

## 1. RightSight 2 기술 원리 (Sensor Fusion)

RightSight 2는 하드웨어 센서 퓨전(Sensor Fusion) 기술을 통해 발화자를 실시간 식별하고 추적합니다:

1. **음향 위치 추정 (TDoA - Time Difference of Arrival)**:
   - 6개의 빔포밍 마이크 어레이에 음파가 도달하는 미세한 시간차를 마이크로초 단위로 계산하여 음원의 방위각(Azimuth)을 즉각 판별합니다.
2. **시각적 인물 검출 (Computer Vision)**:
   - AI 뷰파인더의 130° 광각 렌즈가 방 전체의 인체 실루엣과 안면 랜드마크를 실시간 스캔합니다.
3. **카메라 구동 및 프레이밍 (PTZ Actuation)**:
   - 음원 위치와 일치하는 인물을 특정하고, 메인 PTZ 카메라의 모터를 구동하여 최적의 줌 배율로 클로즈업합니다.

---

## 2. 3대 프레이밍 모드 (Framing Modes)

1. **그룹 뷰 (Group View)**:
   - 회의실에 있는 모든 사람을 감지하여 화면 전체에 고르게 보이도록 줌과 화각을 자동 조정합니다.
2. **화자 뷰 (Speaker View)**:
   - 현재 말하고 있는 메인 발화자를 클로즈업하여 단독 송출하거나, 발화자 클로즈업 + 룸 전경의 픽처 인 픽처(PiP) 듀얼 스트림을 제공합니다.
3. **그리드 뷰 (Grid View / CollabOS 1.8+)**:
   - 참석자들을 개별 인물 타일로 분할하여 리모트 접속자에게 각자 1인 전용 화상 타일로 균등하게 노출합니다.

---

## 3. 작동 요구사항 및 설정 (Requirements)
- **소프트웨어**: CollabOS 버전 1.5 이상 필수 (그리드 뷰는 1.8 이상 권장)
- **플랫폼 호환성**:
  - Zoom Rooms (Intelligent Director 및 Multi-stream 지원)
  - Microsoft Teams Rooms on Android / Windows
- **전환 지연 방지 알고리즘**:
  - 헛기침, 기침, 짧은 감탄사("네", "아하")에는 카메라가 급작스럽게 전환되지 않도록 1.5~2.0초 이상의 유효 발화 지속 시간을 필터링하는 지능형 스무딩(Smoothing) 로직이 내장되어 있습니다.
