# 로지텍 AI 커맨드 및 CollabOS 통합 가이드 (SRC-LOGI-DOC-AI-COMMAND)

- **Source ID**: `SRC-LOGI-DOC-AI-COMMAND`
- **Vendor**: Logitech
- **Evidence Level**: E1 (제조사 공식 엔지니어링 백서)
- **최종 검증일**: 2026-09-22
- **유효 기간**: 180일 (상태: VALID)

---

# Technical Atelier — AI Command API Reference

이 문서를 AI에게 제공하면, AI는 이 명세에 따라 서버와 직접 통신하여 기술 지원 보고서를 작성할 수 있습니다.

## 서버 주소
```
http://localhost:8000
```

---

## 🤖 AI가 사용할 수 있는 명령어 (도구)

### 1. 장비 추가 제안 조회
> 선택된 장비들을 기반으로 **빠뜨린 권장 장비**를 확인합니다.

```
GET /api/ai/suggest_devices?devices={장비ID들}
```

**예시:**
```
GET /api/ai/suggest_devices?devices=logi-rally-bar,logi-tap
```

**응답 예시:**
```json
{
  "devices_checked": ["logi-rally-bar", "logi-tap"],
  "recommendations": {
    "logi-rally-bar": {
      "source_device": "Rally Bar",
      "recommended": [
        { "id": "logi-rally-mic-pod", "label": "Rally Mic Pod" },
        { "id": "logi-sight", "label": "Logitech Sight" }
      ],
      "optional": [
        { "id": "logi-rally-mic-pod-hub", "label": "Rally Mic Pod Hub" }
      ],
      "reason": "Rally Bar는 Mic Pod와 Sight 카메라 추가를 권장합니다."
    }
  },
  "summary": "1개 장비에서 추가 권장 장비가 있습니다."
}
```

---

### 2. 관련 다이어그램 검색
> 선택된 장비와 플랫폼에 매칭되는 **배선 다이어그램(레퍼런스 도면)** 목록을 반환합니다.

```
GET /api/ai/query_diagrams?devices={장비ID들}&platforms={플랫폼}&mode={모드}
```

**파라미터:**
| 파라미터 | 필수 | 설명 | 예시 값 |
|:---|:---|:---|:---|
| `devices` | 필수 | 쉼표로 구분된 장비 ID 목록 | `logi-rally-bar,logi-tap` |
| `platforms` | 선택 | 플랫폼 필터 | `teams`, `zoom`, `meet` |
| `mode` | 선택 | 동작 모드 필터 | `appliance`, `pc`, `byod` |

**예시:**
```
GET /api/ai/query_diagrams?devices=logi-rally-bar,logi-tap&platforms=teams&mode=appliance
```

**응답 예시:**
```json
{
  "total_found": 12,
  "diagrams": [
    {
      "id": "wd-001",
      "label": "Rally Bar + Single Display (Appliance Mode)",
      "platform": "teams",
      "device_mode": "appliance",
      "image_url": "images/page_1.png",
      "match_score": 2
    }
  ]
}
```

---

### 3. 이슈 폼 자동 채우기
> 수집된 정보를 Issue Tracker 폼에 **자동으로 채워** 넣습니다.
> Issue Tracker가 실행 중인 상태에서 2초마다 폴링하여 명령을 가져갑니다.

```
POST /api/ai/fill_issue
Content-Type: application/json
```

**요청 본문:**
```json
{
  "title": "이슈 제목",
  "description": "상세 이슈 설명",
  "severity": "high",
  "partner_name": "파트너사명",
  "partner_manager": "파트너사 담당자",
  "customer_name": "고객사명",
  "customer_manager": "고객사 담당자",
  "project": "프로젝트명",
  "os_mode": "appliance",
  "devices": [
    { "id": "logi-rally-bar", "count": 1 },
    { "id": "logi-tap", "count": 1 }
  ],
  "platforms": ["teams"],
  "ver_platform": {
    "teams": "v5.12.0"
  }
}
```

**Severity 값:** `low` | `medium` | `high` | `critical`
**OS Mode 값:** `appliance` | `pc` | `byod`

**응답:**
```json
{ "status": "queued", "message": "Issue Tracker가 다음 폴링에 적용합니다." }
```

---

### 4. 기술 보고서 로컬 저장
> 이슈 데이터를 **마크다운(.md) 파일**로 로컬에 저장합니다.
> 저장 위치: `reports/` 폴더
> **주의:** 이 명령을 호출하면 개별 사례 데이터 파일(`.json`)에 보고서 링크가 자동으로 생성되어 아카이브 목록에 **DOC 배지**가 나타납니다.

```
POST /api/ai/save_report
Content-Type: application/json
```

**요청 본문:** `fill_issue`와 동일한 형식

**응답:**
```json
{
  "status": "success",
  "file": "C:\\...\\reports\\LAT-260401-001_20260401.md",
  "id": "LAT-260401-001",
  "file_name": "LAT-260401-001_20260401.md"
}
```

---

## 📋 사용 가능한 장비 ID 목록

| ID | 이름 | 분류 |
|:---|:---|:---|
| `logi-rally-bar` | Rally Bar | 핵심 장비 |
| `logi-rally-bar-mini` | Rally Bar Mini | 핵심 장비 |
| `logi-rally-bar-huddle` | Rally Bar Huddle | 핵심 장비 |
| `logi-rally-plus` | Rally Plus (Rally System) | 핵심 장비 |
| `logi-meetup` | MeetUp | 핵심 장비 |
| `logi-meetup-2` | MeetUp 2 | 핵심 장비 |
| `logi-roommate` | Logitech RoomMate | 컴퓨트 |
| `generic-mtr-pc` | 회의실 전용 PC (MTR-PC) | 컴퓨트 |
| `logi-tap` | Tap (with Cat5e Kit) | 터치 컨트롤러 |
| `logi-tap-ip` | Tap IP | 터치 컨트롤러 |
| `logi-tap-scheduler` | Tap Scheduler | 스케줄러 |
| `logi-rally-mic-pod` | Rally Mic Pod | 마이크 |
| `logi-rally-mic-pod-hub` | Rally Mic Pod Hub | 마이크 허브 |
| `logi-rally-mic-pod-ext-cable` | Rally Mic Pod Extension Cable | 케이블 |
| `logi-rally-mic-pod-cat-coupler` | Rally Mic Pod CAT Coupler | 연결 |
| `logi-sight` | Logitech Sight | AI 카메라 |
| `logi-dual-sight` | Dual Sight | AI 카메라 |
| `logi-scribe` | Logitech Scribe | 화이트보드 카메라 |
| `logi-rally-camera` | Rally Camera | PTZ 카메라 |
| `logi-swytch` | Swytch | BYOD 허브 |
| `logi-extend` | Logitech Extend | 연결 장치 |
| `logi-strong-usb` | Logitech Strong USB | 케이블 |
| `generic-display` | TV/모니터 | 디스플레이 |
| `generic-laptop` | 일반 노트북 | BYOD 소스 |

---

## 💬 AI와의 대화 흐름 예시

```
사용자: "Rally Bar랑 TAP 쓰는데, 빠진 장비 있어?"

AI 동작:
  1. GET /api/ai/suggest_devices?devices=logi-rally-bar,logi-tap
  2. 결과 분석: "Mic Pod와 Sight 카메라가 없습니다."
  3. 사용자에게 추가 권장 장비 안내

---

사용자: "Teams 회의 중 화면이 안 나와요"

AI 동작:
  1. GET /api/ai/query_diagrams?devices=logi-rally-bar&platforms=teams&mode=appliance
  2. 상위 매칭 다이어그램 목록 사용자에게 안내
  3. 추가 정보 수집: 고객사, 심각도, 해결 시도 내용 질문

---

사용자: "정보 다 모았고 저장해줘"

AI 동작:
  1. POST /api/ai/fill_issue { ...수집된 정보... }
  2. POST /api/ai/save_report { ...수집된 정보... }
  3. "폼이 자동으로 채워졌고 reports/ 폴더에 보고서가 저장되었습니다." 안내
```

---

## 🔑 체크리스트 — 이슈 보고서 작성 전 확인사항

AI는 다음 정보가 모두 수집되었는지 확인한 후 저장해야 합니다:

- [ ] 이슈 제목 (무엇이 문제인가?)
- [ ] 상세 설명 (언제, 어떤 상황에서 발생?)
- [ ] 고객사명
- [ ] 프로젝트명
- [ ] 심각도 (low / medium / high / critical)
- [ ] 관련 장비 목록 + 수량
- [ ] 플랫폼 (teams / zoom / meet / byod)
- [ ] OS 모드 (appliance / pc / byod)
- [ ] 플랫폼 소프트웨어 버전
- [ ] 해결 시도 여부 / 해결 방법
