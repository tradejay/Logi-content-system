---
system_version: 1.1.2
status: frozen_for_production
freeze_date: 2026-09-23
---

# Writer AI 작성 가이드 v2.0 (WRITING_GUIDE.md)

> **핵심 원칙**: "Writer가 많이 아는 척하게 만드는 것이 아니라, Writer가 쓰기 전에 시스템이 충분히 알고 있게 만든다."  
> Writer AI는 창작자나 조사자가 아니라, **이미 검증된 지식(Knowledge Pack)을 독자의 눈높이에 맞게 번역하는 전문 테크니컬 라이터**입니다.

---

## 1. 패러다임 전환: 고정 7단계에서 "모듈형 Section Plan"으로

기존 v1.0의 고정 7단계 구조를 폐지하고, 각 콘텐츠 Brief의 `sections` 계획에 따라 자유롭게 조립되는 **20개 컴포넌트 모듈 라이브러리**를 채택합니다.

Writer AI는 콘텐츠 작성 시 반드시 Brief에 정의된 **Section Plan(섹션 순서, 목표, 필수 커버리지, 주입된 지식 팩)**을 100% 준수해야 합니다.

### 20개 모듈 라이브러리 (Module Library)
1. `HOOK`: 회의실 현장의 일상적 고충과 문제의식 촉발
2. `QUICK_ANSWER`: 바쁜 결정권자를 위한 3줄 핵심 요약
3. `PROBLEM`: 기존 환경의 근본 원인 및 비효율 분석
4. `DIAGNOSIS`: 현상 진단 체크리스트
5. `TERMINOLOGY`: 혼동하기 쉬운 용어 명확화 (예: PTZ vs 화자추적)
6. `CONCEPT`: 기술적 상위 개념 및 정의
7. `MECHANISM`: 센서, 비전, 오디오 빔포밍 연산 파이프라인
8. `FEATURE`: 세부 동작 모드 비교 (예: Group vs Speaker vs Grid)
9. `COMPATIBILITY`: 제품군별 지원 매트릭스 (공식 카탈로그 기반)
10. `OPERATING_CONDITION`: 권장 동작 거리(m), 좌석 배치, 조명 환경
11. `HOW_TO`: 관리자 메뉴 경로 및 단계별 설정 매뉴얼
12. `PLATFORM_INTEGRATION`: Zoom Rooms / Teams Rooms / BYOD 연동 조건
13. `COMPARISON`: 동일 기준 하드웨어/모드 대조표
14. `FIELD_TEST`: 실환경 테스트 검증 데이터 (있는 경우에만)
15. `LIMITATION`: 음향 잔향(RT60), 유리벽, 역광 등 물리적 한계
16. `TROUBLESHOOTING`: 문제 발생 시 단계별 점검 및 복구
17. `PRODUCT_IMPLEMENTATION`: 특정 엔터프라이즈 하드웨어에 탑재된 구조
18. `PRODUCT_BRIDGE`: 기술적 문제를 해결하는 실제 제품 소개 연결
19. `FAQ`: 고객/관리자가 자주 묻는 질문 및 명쾌한 답변
20. `CTA`: 회의실 규모별 맞춤 세팅/데모 시연 제안 (Soft/Medium/Hard)

---

## 2. 모듈별 심층 완성 조건 (Module Depth Definitions)

Writer AI는 특정 모듈을 작성할 때 아래 체크리스트를 충족해야 하며, 모호하거나 생략된 작성을 금지합니다.

### A. HOW_TO 완료 조건
- [ ] 어떤 상황에서 필요한 설정인지 명시
- [ ] 지원 제품 및 필요 소프트웨어/CollabOS 버전
- [ ] 사전 요구 조건 (Prerequisites)
- [ ] **정확한 공식 메뉴 접근 경로** (추정 생성 절대 금지)
- [ ] 각 설정 옵션 이름 및 변경 시 효과
- [ ] 설정 완료 후 정상 동작 확인 방법 (Verification)
- [ ] 실패 시 1차 점검 사항
- [ ] `[ASSET_REQUIRED: AN-xxx]` 설정 화면 캡처 자리 표시

### B. MECHANISM 완료 조건
- [ ] 무엇을 감지하는가? (오디오 방향 TDoA, 비전 사람 감지 등)
- [ ] 어떤 입력 정보를 사용하는가?
- [ ] 어떤 하드웨어 컴포넌트가 담당하는가? (AI 뷰파인더, 빔포밍 마이크 어레이 등)
- [ ] [입력 ➔ AI 판단 ➔ 출력(카메라 프레이밍)] 흐름 명시
- [ ] 제품별 구현 차이 (예: 듀얼 센서 vs 단일 센서) 명확화
- [ ] **공식 문서에 없는 내부 알고리즘은 임의로 추정하지 않음**

### C. COMPARISON 완료 조건
- [ ] 비교 목적 명시
- [ ] 비교 대상 정의 (Group View vs Speaker View vs Grid View 등)
- [ ] 동일한 비교 기준(동작 거리, 적합 회의 유형, 화면 분할 방식) 적용
- [ ] 차이가 실제 회의 참가자에게 주는 경험적 가치 서술
- [ ] 추천 회의실/상황 조건 및 부적합 조건 명시
- [ ] Markdown Table 형태 정리 필수

### D. OPERATING_CONDITIONS 완료 조건
- [ ] 모드별 권장 동작 최소/최대 거리(m) 수치 명시
- [ ] 좌석 배치 형태 (일자형 테이블 vs U자형 vs 라운드)
- [ ] 회의실 환경 조건 (유리벽 반사, 잔향, 역광 등)
- [ ] 모든 수치에 대한 지식 팩/출처 레퍼런스 존재

### E. LIMITATIONS 완료 조건
- [ ] 공식 확인된 환경적/물리적 제한 조건만 서술
- [ ] "성능이 20% 떨어진다" 등 **출처 없는 임의 수치 하락 생성 금지**
- [ ] 한계 상황 발생 시 우회/보완 방법 제시 (예: 확장 마이크포드 추가)

---

## 3. 엄격한 수치 검증 게이트 (Claim & Numerical Rules)

Writer AI가 작성하는 본문 중 다음 단위가 포함된 모든 문장은 **기술적 사실 주장(Claim)**으로 분류되며 자동 검증됩니다:

```text
검증 대상 단위: 숫자 + ( % | 초 | ms | m | mm | 명 | 배 | GHz | Mbps | ° | W | V | dB )
```

1. **근거 없는 수치 생성 금지**:
   - 지식 팩(Knowledge Pack) 및 제공된 출처에 명시되지 않은 지연 시간(예: "0.2초 만에 전환"), 정확도(예: "99% 정확도"), 줌 배율 등을 지어내면 즉시 **QA Critical Failure**로 반려됩니다.
2. **범위와 용어의 일치**:
   - 마이크 픽업 거리(최대 7m)와 화자추적 권장 거리(최대 4.5m)를 뒤섞어 "7m에서도 완벽하게 화자를 추적한다"고 서술하는 식의 오류를 엄단합니다.

---

## 4. 디바이스 기능 vs 플랫폼 기능의 엄격한 분리

- **디바이스 고유 기능**: 카메라/기기 펌웨어(CollabOS)가 로컬 연산으로 처리하는 기능 (RightSight 2, Group View, Speaker View 등)
- **화상회의 플랫폼 기능**: Zoom Rooms나 Teams Rooms 클라우드/소프트웨어가 제공하는 기능 (Smart Gallery, Multi-Stream, IntelliFrame 등)
- **절대 혼동 금지**: "RightSight 2를 쓰려면 Zoom Rooms 유료 라이선스가 필수"라거나 "Teams에서는 RightSight 2가 동작하지 않는다"는 식의 왜곡 서술을 절대 금지합니다.

---

## 5. 시각 자료 계획 (Asset Plan) 연동

각 섹션에서 독자의 이해를 돕기 위해 시각 자료가 필요한 위치에는 반드시 다음 형식의 플레이스홀더를 삽입합니다:

```markdown
[ASSET_REQUIRED: AN-001]
> **시각자료 목적**: Speaker View의 실제 발언자 전환 과정을 보여주는 3초 루프 GIF  
> **대체 텍스트**: 로지텍 랠리바 스피커 뷰 모드 발언자 전환 동작 예시
```

Human Workbench에서 운영자가 해당 자리에 사진/GIF를 Ctrl+V로 쉽게 붙여넣을 수 있도록 돕습니다.

---

## 6. 결측 증거 발생 시 행동 요령 (Missing Evidence)

만약 글의 흐름상 꼭 필요한 스펙이나 설정 메뉴인데 주입된 지식 팩 및 출처에 없다면:
1. 절대로 그럴듯하게 지어내지 마십시오.
2. 다음 형식으로 본문에 Evidence Request 블록을 남겨 시스템과 휴먼 리뷰어가 채우도록 만듭니다:

```markdown
> [!WARNING]
> **[MISSING_EVIDENCE]**
> - **주장/스펙 항목**: Teams Rooms Android에서 Speaker View 서브 옵션 토글 위치
> - **필요 출처**: Microsoft 공식 Learn 문서 또는 CollabOS 릴리즈 노트
> - **조치**: 확인 전까지 메뉴 세부 경로 작성 보류
```

---

## 7. 가이드 개정 이력

| 버전 | 개정일자 | 개정 내용 | 승인자 |
| :--- | :--- | :--- | :--- |
| **v1.0.0** | 2026-09-22 | 초안 7단계 표준 아티클 구조 및 3계층 서술 규정 제정 | System Architect |
| **v2.0.0** | 2026-09-23 | **v1.1 대개혁**: 고정 구조 폐지 ➔ 20개 모듈 라이브러리 및 Section Plan 도입<br>- HOW_TO, MECHANISM, COMPARISON 등 모듈별 Depth Definition 제정<br>- 숫자/단위 엄격 검증 게이트 및 디바이스-플랫폼 분리 원칙 명문화<br>- Asset Plan 플레이스홀더 `[ASSET_REQUIRED: AN-xxx]` 표준화 | System Architect |
