# Logitech 랠리 마이크 팟 연결 및 토폴로지 가이드 (SRC-LOGI-DOC-MIC-POD-COMPAT)

- **Source ID**: `SRC-LOGI-DOC-MIC-POD-COMPAT`
- **Vendor**: Logitech
- **Evidence Level**: E1 (제조사 공식 엔지니어링 백서)
- **최종 검증일**: 2026-09-22
- **유효 기간**: 180일 (상태: VALID)

---

# Rally Mic Pod 호환성 및 연결 가이드

이 문서는 로지텍의 엔터프라이즈 화상회의 마이크 솔루션인 **Rally Mic Pod**의 호환 기기 정보, 연결 방식, 연장 케이블 제한 및 전용 마운트 연동에 대해 정리한 공식 가이드라인입니다.

---

## 1. 호환 메인 기기 및 최대 연결 대수

Rally Mic Pod는 모든 로지텍 비디오 장치와 호환되지 않으며, **Rally 제품군 메인 시스템**에서만 사용할 수 있습니다.

| 메인 시스템 장치 | 호환 여부 | 최대 Mic Pod 수 | 최대 Mic Pod Hub 수 | 연결 방식 및 특징 |
| :--- | :---: | :---: | :---: | :--- |
| **Rally Bar** | **O** | **최대 4대** | **최대 2대** | 직렬(Daisy-chain) 연결 또는 Mic Pod Hub 활용 지원. |
| **Rally Bar Mini** | **O** | **최대 3대** | **최대 2대** | 직렬(Daisy-chain) 연결 또는 Mic Pod Hub 활용 지원. |
| **Rally Plus** | **O** | **최대 7대** | **최대 7대** | 기본 구성 및 Extension Cable 사용 시 Mic Pod와 Hub 각각 독립적으로 최대 7대씩 지원. 테이블 허브(Table Hub)를 통해 직렬 또는 분기 연결 가능. (단, CAT Coupler 연장 시에는 합산 제한 적용) |
| **Rally Bar Huddle** | **X** | **지원 안 함** | **지원 안 함** | 전용 12핀 마이크 포트가 없어 Rally Mic Pod와 호환되지 않습니다. |
| **MeetUp (1세대)** | **X** | **지원 안 함** | **지원 안 함** | MeetUp 전용 확장 마이크(Expansion Mic, 989-000405)만 호환되며 Rally Mic Pod는 사용할 수 없습니다. |
| **MeetUp 2** | **X** | **지원 안 함** | **지원 안 함** | 확장 마이크 단자가 없어 Rally Mic Pod와 호환되지 않습니다. |
| **Logitech RoomMate** | **X** | **지원 안 함** | **지원 안 함** | RoomMate 본체에는 직접 마이크 연결이 불가하며, 연결된 메인 비디오 기기(Rally Bar / Rally Plus)를 거쳐 수음 사양을 가져옵니다. |

> **참고**: Rally / Rally Plus의 경우 **CAT Coupler를 활용하여 연장할 때에만** Mic Pod와 Mic Pod Hub의 **합산 최대 7대** 제한이 적용됩니다. 기본 구성 및 Extension Cable(10m) 사용 시에는 각각 독립적으로 최대 7대씩 연결할 수 있습니다.

---

## 2. 오디오 연결 토폴로지 (Daisy-chain vs. Star)

Rally Mic Pod는 회의실 구조에 따라 크게 두 가지 방식으로 연결할 수 있습니다.

### ① 직렬 연결 (Daisy-Chain Topology)
* **특징**: 마이크 포드에 연결된 2.95m 하드웨어 케이블을 다음 마이크 포드 뒷면 포트에 순차적으로 연결하는 방식입니다.
* **적용**: 길고 좁은 회의 테이블에 마이크를 일렬로 배치할 때 적합합니다.

### ② 스타형 연결 (Star Topology)
* **필수 액세서리**: **Rally Mic Pod Hub** (939-001647)
* **특징**: 마이크 허브(3개의 12핀 포트 제공)를 테이블 하단에 설치하고, 각 포드에서 개별 케이블을 허브로 모으는 방식입니다.
* **적용**: U자형, V자형 또는 대형 원형 테이블에서 마이크 배선이 드러나지 않도록 테이블 아래로 케이블을 분기시킬 때 필수적입니다.

---

## 3. 배선 연장 솔루션 및 제한 사항

마이크와 시스템 본체 또는 허브 간의 거리가 멀 경우, 다음 배선 연장 솔루션을 사용해야 합니다. 단, 신호 감쇠 방지를 위해 엄격한 규격을 준수해야 합니다.

### ① Mic Pod Extension Cable (952-000047)
* **스펙**: 10m 플레넘(Plenum) 등급 전용 연장 케이블.
* **연결 제한**: 
  - **Rally Bar / Rally Bar Mini**: 단일 체인당 **최대 2개(총 20m)**까지 연장 지원 (체인 내 모든 위치에 배치 가능).
  - **Rally / Rally Plus**: **최대 1개(10m)**까지 연장 지원 (반드시 Table Hub에 직접 연결해야 함).

### ② Rally Mic Pod CAT Coupler (952-000181)

Rally Mic Pod CAT Coupler를 이용한 연장 시에는 아래와 같이 기기별 상세 조건이 적용됩니다.

#### 📡 Rally Mic Pod CAT Coupler 연장 — 장비별 상세 조건

##### Rally Bar
* **CAT Coupler 연결 위치**: **Rally Bar 본체**에 직접 연결 (단, Sight 사용 시 Mic Pod Hub에 연결 가능)
* **최대 CAT 케이블 길이**: **20m** (65.6 ft)
* **지원 케이블 타입**: **CAT6 SFTP/SSTP** (공식 Quick Start Guide 기준: CAT6a SFTP/SSTP)
* **연결 가능 구성**: Mic Pod Hub **최대 2개** + Mic Pod **최대 4대** (순서 무관)
* **Extension Cable 동시 사용**: ❌ **불가**

##### Rally Bar Mini
* **CAT Coupler 연결 위치**: **Rally Bar Mini 본체**에 직접 연결 (단, Sight 사용 시 Mic Pod Hub에 연결 가능)
* **최대 CAT 케이블 길이**: **20m** (65.6 ft)
* **지원 케이블 타입**: **CAT6 SFTP/SSTP** (공식 Quick Start Guide 기준: CAT6a SFTP/SSTP)
* **연결 가능 구성**: Mic Pod Hub **최대 2개** + Mic Pod **최대 3대** (순서 무관)
* **Extension Cable 동시 사용**: ❌ **불가**

##### Rally / Rally Plus
* **CAT Coupler 연결 위치**: **Rally Plus Table Hub**에 반드시 연결
* **최대 CAT 케이블 길이**: **20m** (65.6 ft)
* **지원 케이블 타입**: **CAT6 SFTP/SSTP** (공식 Quick Start Guide 기준: CAT6a SFTP/SSTP)
* **연결 가능 구성 (기본)**: Mic Pod Hub + Mic Pod 합산 **최대 7개**
* **Mic Pod 간 CAT 케이블**: 각 Mic Pod/Hub 사이 **최대 3m** CAT 케이블 추가 지원 (이 경우도 합산 최대 7개)
* **Extension Cable 동시 사용**: ❌ **불가**

##### ⚠️ 공통 주의사항 (전 장비 동일)
* **네트워크 포트 연결 절대 금지**: Mic Pod 또는 CAT 케이블을 컴퓨터, 스위칭 허브, 벽면의 인터넷 LAN 단자, 혹은 Rally Bar/Rally Bar Mini/Rally Plus 본체의 RJ45 이더넷 포트에 오연결하는 경우 기기가 영구 손상될 수 있으며, 이는 보증 대상에서 제외됩니다.
* **이더넷 변환 불가**: CAT 케이블은 전송 매체로만 사용될 뿐, Mic Pod/Hub를 이더넷 장치로 변환하지 않습니다.
* **Extension Cable과 동시 사용 불가**: Mic Pod Extension Cable(10m)과 CAT Coupler는 동일 라인에서 함께 사용할 수 없습니다.

> [!TIP]
> **케이블 타입 권장**: 일부 제품 문서에서는 CAT6 SFTP/SSTP로 나와 있으나, 공식 Quick Start Guide의 안전 가이드라인에 따라 안정적인 신호 전송을 위해 **CAT6a SFTP/SSTP** 등급 케이블을 설치할 것을 적극 권장합니다. (규격 외 Cat5e 또는 Cat7 케이블은 신호 이상을 유발하므로 지원하지 않습니다.)

---

## 4. 전용 마운팅 솔루션 호환성

Rally Mic Pod를 테이블이나 천장에 영구 고정하여 케이블을 매립하고 도난을 방지할 수 있습니다.

* **Rally Mic Pod Mount (952-000002 / 952-000020)**:
  - **용도**: 테이블 상판 타공(25-65mm 홀) 또는 드롭 실링 천장에 밀착 설치.
  - **특징**: 내부 스풀에 2.95m의 긴 기본 케이블을 감아 보관하고 깔끔한 외관을 확보할 수 있습니다.
* **Rally Mic Pod Pendant Mount (952-000123 / 952-000125)**:
  - **용도**: 층고가 높은 노출 천장 환경에서 마이크를 펜던트 조명 형태로 내려서 고정.
  - **특징**: 최대 2.6m 조절이 가능한 와이어 서스펜션 케이블과 하우징을 지원합니다.
