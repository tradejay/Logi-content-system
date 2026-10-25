# Sources & Knowledge Engineering Guide (SOURCE_GUIDE.md)

- **Version**: 2.0 (vNext)
- **Scope**: 공인 소스 수집, 로컬 CLI 어댑터 연동, 사실(Fact) 추출 및 지식 팩(Knowledge Pack) 구축 규격

---

## 1. 공식 리소스 연동 체계 (Provider Integration)

본 시스템은 로지텍 공식 매뉴얼 1,471개 HTML 코퍼스에 직접 연결되어 있습니다.

- **CLI 실행 경로**: `python "C:\Users\Choijay\Desktop\오우션교육\Logitech Quick Manual-2\manual_cli.py"`
- **파이썬 어댑터**: `content-system/scripts/providers/logitech_provider.py`
- **조회 명령 예시**:
  ```bash
  # 1. 후보 문서 검색
  python "...\manual_cli.py" --query "Speaker View" --product "Rally Bar" --limit 5 --output json

  # 2. 문서 전문 상세 확인 (필수)
  python "...\manual_cli.py" --detail LOGI-000123 --output json
  ```

---

## 2. 팩트(Fact) 추출 4대 원칙

1. **원문 문맥 보존 (Context Integrity)**:
   - "Speaker View는 카메라 픽업 범위인 4.5m(15ft) 내에서 활성 발언자를 감지한다"는 문장에서 4.5m만 떼어내어 "마이크 픽업 범위가 4.5m"라고 왜곡하거나 다른 장비에 대입해서는 안 됩니다.
2. **네거티브 바운더리(does_not_imply) 명시**:
   - 팩트를 추출할 때, 다운스트림 AI가 흔히 범하기 쉬운 오해를 반드시 `does_not_imply`에 등록합니다:
     - 예: `does_not_imply: "Rally Mic Pod 증설이 RightSight 2 카메라 화자 추적 위치 정보를 제공함"`
     - 예: `does_not_imply: "Smart Switching이 단일 랠리바 내부의 프레이밍 전환을 의미함"`
3. **단위 및 수치의 원형 유지**:
   - 단위(`m`, `°`, `mm`, `kg`, `W`, `dB`)와 수치는 원문 그대로 `value`와 `unit`에 분리 저장합니다.
4. **출처 로케이터(Locator) 기록**:
   - 팩트마다 반드시 `source_id`(예: `SRC-LOGI-RALLYBAR`)와 해당 문서의 `locator`(섹션 제목, 단락)를 명기합니다.

---

## 3. 지식 팩(Knowledge Pack) 구조

- **제품 지식 (`knowledge/products/`)**: 하드웨어 고유 스펙, 치수, 포트, 정격, 호환 기기 목록
- **기능 지식 (`knowledge/features/`)**: 온디바이스 AI, 알고리즘, 동작 원리, 운영 조건, 물리적 한계
- **플랫폼 지식 (`knowledge/platforms/`)**: Zoom Rooms, Teams Rooms 등 클라우드 연동 및 UI 메뉴 경로
- **개념 지식 (`knowledge/concepts/`)**: TDoA, AEC, 빔포밍 등 업계 표준 공학 원리

모든 지식 팩은 `validate_knowledge_pack.py`를 통해 스키마 무결성을 검증받아야 합니다.
