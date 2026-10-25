# Zoom Rooms 지능형 카메라 제어 및 프레이밍 모드 설정 가이드 (SRC-ZOOM-CAMERA-MODES)

- **Source ID**: `SRC-ZOOM-CAMERA-MODES`
- **Vendor**: Zoom Video Communications
- **Evidence Level**: E2 (플랫폼 공식 관리자 포털 가이드)
- **최종 검증일**: 2026-09-20
- **유효 기간**: 90일 (상태: VALID)

---

## 1. Zoom Rooms 카메라 제어 아키텍처

Zoom Rooms는 연결된 하드웨어(Logitech Rally Bar 등)와 양방향 통신을 통해 카메라 제어 권한을 위임하거나 플랫폼 자체 AI 알고리즘과 결합합니다.

---

## 2. 관리자 설정 경로 (Admin Console Path)

### Zoom Web Portal (중앙 집중 관리)
1. `Room Management` → `Zoom Rooms` 메뉴 진입
2. 해당 회의실 선택 후 `Account Settings` 또는 `Devices` 탭 클릭
3. `Camera Control Mode` 항목에서 옵션 선택:
   - **Manual (수동)**: 터치 컨트롤러(Tap)에서 화살표 및 프리셋으로 직접 이동
   - **Auto-Framing (자동 프레이밍)**: 회의실 전체 참석자 자동 인식 및 센터링
   - **Speaker Focus (화자 추적)**: 발화자 감지 시 자동 줌 및 추적
   - **Multi-Focus Framing (스마트 갤러리)**: 룸 안의 사람들을 2~3개의 독립된 비디오 스트림으로 분할 전송

### 현장 컨트롤러 (Logitech Tap 터치스크린)
1. 통화 중 하단 `카메라 제어(Camera Control)` 아이콘 터치
2. `프레이밍 모드`에서 `Speaker Focus` 또는 `Auto-Framing` 즉시 전환 가능

---

## 3. 권장 실무 가이드라인 (Best Practices)
- **회의 시작 시**: 전원 출석 확인을 위해 30초간 `Auto-Framing(전체 뷰)`으로 시작한 뒤, 발표가 본격화되면 `Speaker Focus`로 전환하는 것을 권장.
- **반사체 간섭 방지**: 회의실 벽면 전면 유리나 거울에 비친 인영을 카메라가 오인하지 않도록 카메라 높이는 지상 1.1m~1.4m(테이블 상단 착석자 눈높이)로 설치 권장.
