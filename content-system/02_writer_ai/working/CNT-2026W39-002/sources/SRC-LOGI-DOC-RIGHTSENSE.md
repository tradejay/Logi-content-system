# Logitech RightSense AI 기술 사양 및 버전별 비교 가이드 (SRC-LOGI-DOC-RIGHTSENSE)

- **Source ID**: `SRC-LOGI-DOC-RIGHTSENSE`
- **Vendor**: Logitech
- **Evidence Level**: E1 (제조사 공식 엔지니어링 백서)
- **최종 검증일**: 2026-09-22
- **유효 기간**: 180일 (상태: VALID)

---

# RightSense™ 기능 및 기기별 지원 버전 요약

이 문서는 로지텍 화상회의 솔루션의 핵심 AI 기술인 **RightSense™ (RightSight, RightSound, RightLight)**의 버전별(v1 및 v2) 기능 정의와 기기별 호환성 및 세부 지원 현황을 정리한 가이드라인입니다.

기준 데이터: [rightsense.json](file:///c:/Users/Choijay/Desktop/오우션교육/Logitech 제품 설계하기/data/common/rightsense.json)

---

## 1. RightSense™ 구성 요소 및 버전별 기능 차이

### 📷 RightSight (자동 지능형 카메라 프레이밍)
회의실 내 참석자들을 자동으로 감지하여 최적의 구도로 화면을 조정하는 기술입니다.
*   **RightSight v1 (1세대)**:
    *   **Group View (그룹 전체 프레이밍)**: 회의실 내부의 모든 참가자를 감지하여 화면에 알맞게 담는 1세대 오토 프레이밍 기능입니다.
    *   **주요 모드**:
        *   `Dynamic 모드`: 회의 중 참석자의 이동이나 입/퇴실을 감지하여 실시간 재프레이밍을 수행합니다.
        *   `On-call start 모드`: 회의가 시작될 때 최초 1회만 프레이밍을 수행하고 이후에는 구도를 유지합니다.
    *   **동작 범위**: 약 1m ~ 7m
    *   **시각 자료**: [RightSight 1 데모 GIF](/assets/images/device/meetup-blade-3.gif) (MeetUp 자동 그룹 프레이밍 데모)
*   **RightSight v2 (2세대)**:
    *   **AI 뷰파인더 기반의 다중 프레이밍**: 메인 카메라 외에 보조 AI 뷰파인더가 탑재된 기기군에서 주로 구현됩니다.
    *   **주요 기능**:
        *   `Group View (그룹 뷰)`: 회의실 참석자 전원을 한 화면에 포착 (권장 1m ~ 7m).
        *   `Speaker View (화자 추적 뷰)`: 현재 말하고 있는 발언자를 실시간으로 인식하여 클로즈업 및 추적 (권장 1m ~ 4.5m).
        *   `Grid View (분할 프레이밍)`: 회의실의 참가자들을 여러 개의 개별 프레임으로 분할하여 화면에 균등하게 배치 (권장 1m ~ 6m).
        *   `Camera Zone (프레이밍 영역 지정)`: 창문이나 유리창 밖의 보행자가 프레이밍되지 않도록 촬영 범위를 지정하는 기능.

### 🔊 RightSound (지능형 오디오 최적화)
목소리를 선명하게 전달하고 주변 소음을 제거하는 음향 제어 엔진입니다.
*   **RightSound v1 (1세대)**:
    *   **Noise Suppression (잡음 억제)**: 키보드 타건, 에어컨, 팬 소리 등 일상적인 배경 소음을 제거하여 음성 전달력을 높임.
    *   **Voice Equalization (음성 레벨 보정)**: 마이크와의 거리에 관계없이 속삭이는 소리는 키우고, 너무 큰 목소리는 낮추어 균일한 음량으로 변환.
    *   **Extended Audio (확장 오디오)**: 다중 마이크 포드 연결 시 발언자에게 가장 근접한 마이크의 오디오 소스를 지능적으로 선택.
    *   **Echo Cancellation (에코 제거)**: 하울링 및 음성 피드백 현상을 방지.
    *   **시각 자료**: [RightSound 1 다이어그램](/assets/images/device/right sound 1.webp) (RightSound 1 핵심 오디오 기술 다이어그램)
*   **RightSound v2 (2세대)**:
    *   **AI 기반 고도화 오디오 최적화**: 딥러닝 기반의 소음 차단 알고리즘을 사용합니다.
    *   **주요 기능**:
        *   `AI Noise Suppression`: 배경 소음과 사람의 목소리를 머신러닝 모델로 실시간 식별하여 보다 강력하게 소음을 차단.
        *   `AI Voice Equalization`: 공간 내 다른 위치에 있는 발언자 간의 음량 편차를 매우 세밀하고 정교하게 조정.
        *   `Acoustic Echo Cancellation (AEC)`: 고성능 AEC로 음질 왜곡 없는 완벽한 하울링 억제.
        *   `VAD (Voice Activity Detector) 기술`: 목소리가 감지될 때에만 마이크 성능을 능동적으로 최적화.

### ☀️ RightLight (지능형 조명 및 색상 보정)
자연스럽고 선명한 인물 화면을 구현하는 조명 조절 기술입니다.
*   **RightLight v1 (공통 규격)**:
    *   **WDR (Wide Dynamic Range)**: 역광이나 직사광선이 내리쬐는 열악한 창가 환경에서도 얼굴의 실루엣이 어둡게 뭉개지지 않도록 밝기를 보정.
    *   **피부톤 최적화 (Skin Tone Rendering)**: 노란 조명, 백색광 등 다양한 색온도 아래에서도 참석자의 실제 피부색을 자연스럽고 생생하게 표현.

---

## 2. 기기별 RightSense™ 버전 지원 매트릭스

아래 표는 각 기기의 공식 펌웨어 및 메타데이터(`meta.json`) 기준 지원 현황입니다.

| 기기명 | RightLight | RightSight (비디오) | RightSound (오디오) | 특이사항 및 세부 정보 |
| :--- | :---: | :---: | :---: | :--- |
| **Rally Bar** | v1 | **v2** | **v2** | 메인 비디오 바로서 화자 추적, 그리드 뷰, AI 소음 차단 풀 지원. [Rally Bar meta](file:///c:/Users/Choijay/Desktop/오우션교육/Logitech%20제품%20설계하기/data/devices/logi-rally-bar/meta.json) |
| **Rally Bar Mini** | v1 | **v2** | **v2** | 소소형/중소형 공간용 올인원 바로서 화자 추적 및 그리드 뷰 등 지원. [Rally Bar Mini meta](file:///c:/Users/Choijay/Desktop/오우션교육/Logitech%20제품%20설계하기/data/devices/logi-rally-bar-mini/meta.json) |
| **Rally Bar Huddle** | v1 | **v2** | **v2** | 소형 공간용 올인원 바. RightSight 2 및 RightSound 2 기능 지원. [Rally Bar Huddle meta](file:///c:/Users/Choijay/Desktop/오우션교육/Logitech%20제품%20설계하기/data/devices/logi-rally-bar-huddle/meta.json) |
| **MeetUp 2** | v1 | **v2** | **v2** | 소규모 회의실 및 허들룸용 차세대 바. 2세대 비디오/오디오 AI 장착. [MeetUp 2 meta](file:///c:/Users/Choijay/Desktop/오우션교육/Logitech%20제품%20설계하기/data/devices/logi-meetup-2/meta.json) |
| **MeetUp (1세대)** | v1 | v1 | v1 | 1세대 그룹 프레이밍(Group View)만 지원하며, 개별 화자 추적 및 분할 뷰 미지원. [MeetUp meta](file:///c:/Users/Choijay/Desktop/오우션교육/Logitech%20제품%20설계하기/data/devices/logi-meetup/meta.json) |
| **Rally Plus** | v1 | v1 | v1 | 모듈형 분리 대형 시스템. 카메라 및 마이크 구조상 v1 프레이밍 및 소음 차단 지원. [Rally Plus meta](file:///c:/Users/Choijay/Desktop/오우션교육/Logitech%20제품%20설계하기/data/devices/logi-rally-plus/meta.json) |
| **Logitech RoomMate** | ❌ 미지원 | v1 (Group View) | ❌ 미지원 | 전용 컴퓨팅 장치로, 1세대 Group View(자동 그룹 프레이밍)만 CollabOS 1.7+ 에서 연동해 지원하며, RightSound 및 RightLight 관련 스펙은 지원하지 않습니다. [RoomMate meta](file:///c:/Users/Choijay/Desktop/오우션교육/Logitech%20제품%20설계하기/data/devices/logi-roommate/meta.json) |
| **Logitech Sight** | N/A | **v2** | **v2** | 탁상용 보조 AI 카메라. Rally Bar/Mini와 연동하여 RightSight 2 카메라 모드(Group, Speaker, Grid)와 RightSound 2 기능 지원. [Sight meta](file:///c:/Users/Choijay/Desktop/오우션교육/Logitech%20제품%20설계하기/data/devices/logi-sight/meta.json) |

---

## 3. 주요 기기별 세부 지원 상세 내용

### [Logitech RoomMate](file:///c:/Users/Choijay/Desktop/오우션교육/Logitech 제품 설계하기/data/devices/logi-roommate/meta.json)
*   **특이사항**: RoomMate는 본체 자체에 카메라나 마이크가 없는 컴퓨팅 전용 장치입니다.
*   **기능 제약**:
    *   **RightSight**: CollabOS 1.7 이상에서 연결된 로지텍 USB 카메라(Rally Plus, MeetUp 등)의 Group View(1세대 자동 그룹 프레이밍) 기능을 제어 및 연동할 수 있으나, AI 뷰파인더가 필요한 2세대 액티브 프레이밍(Speaker/Grid View) 및 Camera Zone 등은 지원하지 않습니다.
    *   **RightSound**: RightSound 및 RightSound 2 오디오 기술을 **전혀 지원하지 않습니다**. 음향 처리는 연결된 외부 장비(Rally 오디오 시스템, MeetUp 또는 3rd-party DSP 등) 자체의 하드웨어 연산에 전적으로 의존합니다.
    *   **RightLight**: 역광 보정 및 피부톤 색상 보정 기술인 RightLight에 대해서는 관련 정보가 없으며 지원 대상이 아닙니다.

### [Logitech Sight](file:///c:/Users/Choijay/Desktop/오우션교육/Logitech 제품 설계하기/data/devices/logi-sight/meta.json)
*   **특이사항**: 테이블 중앙에 배치하여 최적의 오디오 및 비디오 앵글을 잡는 지능형 테이블탑 카메라입니다.
*   **지원 기술 및 모드**:
    *   **RightSight 2**:
        *   **카메라 모드**: Rally Bar / Rally Bar Mini와 연동하여 **Group View**, **Speaker View**, **Grid View**를 모두 지원합니다.
        *   **Smart Switching**: 미팅룸 환경에 따라 지능형 프레임 스위칭이 가능하며, CollabOS 2.0부터 기본 활성화(CollabOS 1.15 GA)되었습니다.
        *   **Google Meet 인증**: CollabOS 1.15부터 Google Meet on Android 공식 인증을 획득했으며, CollabOS 2.0부터 Google Meet on ChromeOS 인증도 추가 지원합니다.
        *   **Dual Sight**: 더 넓은 방을 위해 최대 2대의 Sight를 연결(CollabOS 1.15+ Beta)할 수 있으며, 이 때 Speaker View 모드가 필수적으로 동작해야 합니다.
    *   **RightSound 2**:
        *   배경 소음을 제거하는 **AI Noise Suppression**, 음성 반향을 감소시키는 **AI Echo Suppression**, 목소리 볼륨 균형을 조정하는 **Voice Equalization**, 가장 가까운 마이크를 식별해 오디오를 전송하는 **Extended Audio** 기능을 완벽히 지원합니다.

---

> [!NOTE]
> 1세대 기기(MeetUp, Rally Plus)는 USB 연결을 기반으로 작동하거나 구형 칩셋을 사용하여 최신 RightSight 2(화자 추적, 그리드 분할) 및 RightSound 2(머신러닝 소음 차단)의 고부하 연산을 수행할 수 없습니다. 최신 AI 기능을 도입하려는 경우 Rally Bar 제품군 또는 MeetUp 2로의 전환이 필요합니다.
