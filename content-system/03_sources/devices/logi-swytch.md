# Logitech Logitech Swytch (로지텍 스위치) 공식 하드웨어 사양 및 기술 데이터시트 (SRC-LOGI-LOGI_SWYTCH)

- **Source ID**: `SRC-LOGI-LOGI_SWYTCH`
- **Vendor**: Logitech
- **Device ID**: `logi-swytch`
- **Category**: `extender`
- **Part Number**: `-`
- **Evidence Level**: E1 (제조사 공식 데이터시트 및 엔지니어링 스펙)
- **최종 검증일**: 2026-09-22
- **유효 기간**: 180일 (상태: VALID)
- **네이버 블로그 실발행 링크**: https://blog.naver.com/oceantech01/224325849282

---

## 1. 제품 개요 및 핵심 특징
**원터치로 연결되는 노트북 화상회의 허브**
> 노트북 하나로 회의실 시스템을 장악하세요.
로지텍 Swytch를 사용하면 노트북 한 대로 회의실의 컨퍼런스 카메라와 디스플레이를 즉시 사용할 수 있습니다. USB Type-A와 Type-C를 모두 지원하는 혁신적인 커넥터가 포함되어 있어 모든 최신 노트북과 호환됩니다. 최대 4K 해상도를 지원하며 60W 전원 공급으로 노트북을 항상 충전 상태로 유지합니다.

![Logitech Swytch (로지텍 스위치) 공식 외관](https://drive.google.com/thumbnail?id=1ibrUMInW88PNHEbB1HD41oENzeYGiVkC&sz=w1600)

## 2. 상세 하드웨어 및 기술 사양
### 제품 크기
| 사양 항목 | 상세 내용 |
| :--- | :--- |
| **Swyt치 허브** | 164mm x 90mm x 27.4mm |
| **Swyt치 익스텐더** | 120mm x 120mm x 27.4mm |



### 연결 및 지원 사양
| 사양 항목 | 상세 내용 |
| :--- | :--- |
| **노트북 연결** | USB Type-A 또는 Type-C (단일 커넥터) |
| **최대 해상도** | 디스플레이 4K @ 30fps / 카메라 4K @ 30fps |
| **전원 공급 (PD)** | 최대 60W 노트북 충전 지원 |
| **케이블 길이** | Swytch 커넥터 케이블 1.5m, 링크 케이블 5m |



### 구매 시 박스 구성품

- {'item': 'Swytch 허브', 'length': '-', 'specs': '-'}
- {'item': 'Swytch 익스텐더', 'length': '-', 'specs': '-'}
- {'item': 'Swytch 통합 커넥터', 'length': '1.5m', 'specs': 'USB-A/C 통합'}
- {'item': '링크 케이블', 'length': '5m', 'specs': '허브 간 연결용'}
- {'item': '전원 공급 장치', 'length': '-', 'specs': '100-240V 자동 감지형'}
- {'item': '마운트 플레이트 및 스트랩', 'length': '-', 'specs': '-'}
- {'item': '사용 설명서', 'length': '-', 'specs': '-'}

### 보증 및 지원
![Logitech 연장 보증 (Extended Warranty) 안내](https://drive.google.com/thumbnail?id=1cCaPTnC2wTrDYXyxSyu_aB8jN93QUOvI&sz=w1600)
![Logitech Select 24/7 엔터프라이즈 지원 서비스](https://drive.google.com/thumbnail?id=1wZrw2aGGWN9YSD59NZ3wzBgetFGiCRNk&sz=w1600)
| 사양 항목 | 상세 내용 |
| :--- | :--- |
| **기본 보증** | 2년 제한 하드웨어 보증 |
| **연장 보증 옵션** | 1년(994-000125) 또는 3년(994-000165) 추가 가능 |
| **Logitech Select 서비스** | 24/7 지원, 익일 선배송 RMA, 최대 5년 전체 보장 지원 |



### 구매 가이드 및 제품별 MSRP


## 3. 포트 규격 및 전원 사양 (Interface & Power)
| 구분 | 인터페이스 규격 및 상세 사양 |
| :--- | :--- |
| **device_id** | logi-swytch |
| **slice** | ports |
| **updated** | 2026-03-27 |
| **data** | ports: [{'id': 'port-hub-power', 'label': 'Swytch Hub — 전원', 'connector': 'power-dc', 'role': 'power-in', 'count': 1}, {'id': 'port-hub-hdmi-out', 'label': 'Swytch Hub — HDMI Out (디스플레이)', 'connector': 'hdmi', 'role': 'video-out', 'count': 1}, {'id': 'port-hub-hdmi-in', 'label': 'Swytch Hub — HDMI In (룸 PC)', 'connector': 'hdmi', 'role': 'video-in', 'count': 1}, {'id': 'port-hub-usba', 'label': 'Swytch Hub — USB-A (회의 카메라)', 'connector': 'usb-a', 'role': 'usb-peripheral', 'count': 1}, {'id': 'port-hub-usbc-pc', 'label': 'Swytch Hub — USB-C (룸 PC)', 'connector': 'usb-c', 'role': 'usb-peripheral', 'count': 1}, {'id': 'port-hub-usbc-extender', 'label': 'Swytch Hub — USB-C (Swytch Extender 연결)', 'connector': 'usb-c', 'role': 'usb-peripheral', 'count': 1}, {'id': 'port-ext-usba', 'label': 'Swytch Extender — USB-A (Hub 연결)', 'connector': 'usb-a', 'role': 'usb-peripheral', 'count': 1}, {'id': 'port-ext-usbc', 'label': 'Swytch Extender — USB-C (Swytch Connector)', 'connector': 'usb-c', 'role': 'usb-peripheral', 'count': 1}, {'id': 'port-connector', 'label': 'Swytch Connector — Y자형 USB-A/C (노트북 연결)', 'connector': 'usb-a', 'role': 'usb-peripheral', 'count': 1}] |

## 5. 인증 플랫폼 및 호환 장비
- **공식 인증 플랫폼**: TEAMS, ZOOM, MEET, BYOD
- **추천 연동 장비**: logi-rally-bar, logi-rally-bar-mini, logi-rally-plus, logi-meetup-2
