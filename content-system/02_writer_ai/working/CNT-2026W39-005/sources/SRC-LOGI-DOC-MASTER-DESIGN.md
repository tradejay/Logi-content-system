# 화상회의 회의실 표준 배선 및 케이블링 종합 설계 가이드 (SRC-LOGI-DOC-MASTER-DESIGN)

- **Source ID**: `SRC-LOGI-DOC-MASTER-DESIGN`
- **Vendor**: Logitech
- **Evidence Level**: E1 (제조사 공식 엔지니어링 백서)
- **최종 검증일**: 2026-09-22
- **유효 기간**: 180일 (상태: VALID)

---

# 📘 로지텍 블로그 리포트 마스터 디자인 가이드 v5.2

이 가이드는 `Logitech Replicator` 시스템을 통해 블로그를 자동으로 작성할 때 사용할 수 있는 디자인 규격 및 인터페이스 사양을 정의합니다.

---

### 1. 폰트 종류 (FontFamily)
`config.fontFamily` 값으로 설정합니다.
*   `nanumgothic` (나눔고딕 - 기본)
*   `nanumbarungothic` (나눔바른고딕)
*   `nanummyeongjo` (나눔명조)
*   `nanumsquare` (나눔스퀘어)
*   `nanumsquareround` (나눔스퀘어라운드)
*   `maruburi` (마루부리)
*   `nanum_again` (다시 시작해)
*   `nanum_hippie` (바른히피)
*   `nanum_daughter` (우리딸손글씨)

> [!IMPORTANT]
> **블로그 복사-붙여넣기 최적화 규격 (중요)**
> 테스트 결과, 네이버 스마트에디터는 다음 형식을 포함해야 폰트를 유지합니다:
> 1. **인라인 스타일 따옴표 없음**: `style="font-family: NanumGothic;"` (공백/따옴표 제거)
> 2. **한글 명칭 포함**: `style="font-family: '나눔고딕', NanumGothic;"`
> 3. **구식 태그**: `<font face="나눔고딕">` (가장 확실하지만 지양)
> **권장 스택**: `font-family: '나눔고딕', NanumGothic, sans-serif;`

### 2. 폰트 크기 (FontSize)
`config.fontSize` 값으로 설정하며 스마트에디터 규격 코드를 따릅니다.
*   `fs11` (아주 작게) / `fs13` (작게)
*   `fs15` (보통 - 기본) / `fs16` (본문2)
*   `fs19` (소제목)
*   `fs24` (중제목)
*   `fs28` (대제목)
*   `fs38` (최대 제목)

### 3. 컬러 팔레트 (Color - 글자색/배경색 공통)
*   **무채색**: `#000000`(블랙), `#141414`(진회색), `#666666`(회색), `#999999`(연회색), `#ffffff`(화이트)
*   **강조**: `#ff0010`(빨강 - 강렬), `#ff9300`(주황), `#ffd300`(노랑), `#00d044`(초록), `#0078cb`(파랑 - 로지텍 브랜드 컬러)
*   **배경색(형광펜/셀)**: `#e2e2e2`(표 헤더 회색), `#fff8b2`(연노랑), `#c2f4db`(연초록), `#b0f1ff`(연하늘)

### 4. 서식 효과 (Text Effects)
*   `bold`: 굵게
*   `italic`: 기울임
*   `underline`: 밑줄
*   `strikethrough`: 취소선

### 5. 레이아웃 및 간격 (Layout)
*   **정렬(Alignment)**: `left`(왼쪽), `center`(중앙), `right`(오른쪽), `full`(양끝)
*   **줄간격(Line Spacing)**: `1.8`(기본)

### 6. 목록 (Lists)
*   `bullet`: 점 목록 (●) - 실제값: `bullet`
*   `number`: 숫자 목록 (1. 2. 3.) - 실제값: `decimal`
*   `checklist`: 체크리스트 (☐)

### 7. 표 자동 생성 및 데이터 주입 (Table)
*   **격자 구조 (Full Grid Style)**: 블로그 복사 시 표의 겉 테두리와 내부 구분선이 누락되는 것을 방지하기 위해, **반드시 `table`과 모든 `td`, `th` 태그에 직접 `border`를 적용**하십시오.
*   **외곽 스타일**: 표를 감싸는 부모 `div`에 테두리를 주는 대신, `table` 태그에 `border-collapse: collapse`를 적용하고 1px 실선을 부여하십시오.
*   **헤더 스타일**: 첫 번째 행(`<thead>` 또는 `th`)은 반드시 배경색 **`#e2e2e2`** 또는 **`#f8f9fa`**와 **굵게(Bold)**를 적용하십시오.
*   **내부 스타일**: 모든 칸 사이에는 중간 줄(세로선)과 행 구분선(가로선)이 존재해야 하며, 텍스트는 인라인 폰트 스타일이 적용된 상태여야 합니다.
*   **규격**: 기본 3x3 외에 가변형 크기를 지원하며 시스템이 자동으로 규격을 맞춤니다.

### 8. 강조 박스 및 인용구 (Quotation)
인용구는 제목과 본문이 구분된 멀티 블록 구조를 권장합니다.
*   **구조**: 반드시 상단 `div`(제목)와 하단 `div`(본문)로 분리하십시오.
*   `quotation_line`: 대괄호 라인 스타일
*   `quotation_postit`: 배경색이 있는 포스트잇 스타일
*   `quotation_talk`: 말풍선 스타일
*   `quotation_quote`: 따옴표 강조 스타일

### 9. 이미지 배치 가이드 (Images)
*   **표기**: 사진 위치에 명시적으로 **`(사진)`** 키워드 배치. 

### 10. 구분선 (Section Separator)
*   **디자인 원칙**: 블로그 복사 시 "끝없는 가로줄"이 생기는 것을 방지하기 위해, 실선 대신 **수직 여백(Vertical Whitespace)**으로 섹션을 구분합니다.
*   **타입(type)**: 
    *   `line1`: 큰 여백 (`h-20` / 약 80px) - 주 섹션 구분용
    *   `line2`: 중간 여백 (`h-16` / 약 64px) - 챕터 내부 구분용
    *   `line3`: 좁은 여백 (`h-12` / 약 48px) - 세부 항목 구분용
*   **주의**: 제목(`h1~h3`) 아래에는 가급적 테두리(`border-bottom`)를 쓰지 않고 하단 여백(`margin-bottom`)으로만 처리합니다.

> [!WARNING]
> **무한 가로줄(Infinite Divider) 방지**
> 섹션 컨테이너나 헤더에 `border-top`, `border-bottom`과 같은 물리적 실선을 사용할 경우, 네이버 블로그 에디터로 복사 시 CSS 상속 문제로 인해 **"화면 끝까지 이어지는 긴 구분선"**이 중복 생성되는 현상이 발생합니다. 
> 이를 해결하기 위해 모든 디자인 분할은 **물리적 선 대신 여백(Whitespace)**을 사용하는 것을 원칙으로 합니다.

### 11. 부분 스타일링 (Mixed Inline Styling)
*   **원칙**: 한 문장 내에서 스타일이 바뀌는 경우(예: 특정 단어만 빨간색), 해당 영역을 `<span>` 태그로 감싸고 인라인 스타일을 부여하십시오.
*   **작동**: 시스템은 이를 감지하여 문장을 쪼개서 각각의 스타일로 주입한 뒤 문장 끝에서만 줄바꿈을 수행합니다.

### 12. 에디터 기술 매커니즘 (Technical Mechanics) - **중요**

*   **승리의 줄바꿈 로직 (Winner's Line Break)**:
    *   에디터의 텍스트 복제 버그를 방지하기 위해 다음 시퀀스를 따릅니다.
    1.  텍스트 주입 후 끝에 강제로 공백(` `) 하나 추가.
    2.  `KeyboardEvent(keydown 13)`을 통해 에디터에 엔터 신호를 먼저 보냄.
    3.  이후 `execCommand("insertParagraph")`로 물리적 줄바꿈 확정.
    4.  안정적인 처리를 위해 **800ms**의 대기 시간을 가짐.

*   **Iframe 컨텍스트 관리**:
    *   에디터 본문은 Iframe 내부에 있으므로, 모든 명령 실행 전에 `getDeepestContext`를 통해 현재 활성화된 document를 재확인해야 합니다.

---
*최종 업데이트: 2026-05-06*
*시스템 버전: Logitech Replicator v5.3 (격자형 표 테두리 및 여백 기반 레이아웃 반영)*
