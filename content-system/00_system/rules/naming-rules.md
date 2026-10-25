# 식별자 및 파일 명명 규칙 (naming-rules.md)

1년 이상 수백 건의 콘텐츠가 누적되어도 파일이 충돌하거나 유실되지 않도록 표준 명명 체계를 강제합니다.

---

## 1. Content ID 명명 규격 (불변)

```text
형식: CNT-YYYYWww-NNN
예시: CNT-2026W39-001
```

- `CNT`: Content Prefix (고정)
- `YYYY`: 생성 연도 4자리 (예: `2026`)
- `Www`: 생성 주차 (`W01` ~ `W53`, ISO 주차 기준)
- `NNN`: 해당 주차 내 3자리 일련번호 (`001`, `002`, ...)
- **주의**: 기획 도중 또는 게시 후 제목이 수정되어도 `content_id`는 **절대 변경되지 않습니다.**

---

## 2. 파일명 규격 (Artifact Filenames)

모든 산출물은 반드시 Content ID를 기반으로 명명되며, 파일명에 글 제목 전문을 넣지 않습니다.

- **Content Brief (기획서)**: `01_keyword_ai/briefs/CNT-2026W39-001.brief.yaml`
- **Draft (초안)**: `02_writer_ai/drafts/CNT-2026W39-001.draft.md`
- **QA Report (검수서)**: `04_qa_ai/reports/CNT-2026W39-001.qa.yaml`
- **Final Content (최종본)**: `05_publish/ready/CNT-2026W39-001.final.md`

*(선택사항) IDE 탐색기 가독성을 위해 짧은 영문 슬러그를 덧붙이는 것은 허용되나 식별자는 오직 앞부분의 ID입니다:*
`CNT-2026W39-001__speaker-tracking.draft.md`

---

## 3. 주간 Batch ID 규격

```text
형식: BATCH-YYYYWww
예시: BATCH-2026W39
폴더: weekly/2026-W39/
```

- 매주 월요일 생성되며, 주간 목표와 처리된 Content ID 목록을 관리합니다.

---

## 4. Source & Asset ID 규격

- **Source ID**: `SRC-{VENDOR}-{PRODUCT/FEATURE}`
  - 예시: `SRC-LOGI-RALLYBAR`, `SRC-LOGI-RIGHTSIGHT2`, `SRC-ZOOM-CAMERA-MODES`
- **Asset ID**: `ASSET-{VENDOR}-{TYPE}-{SLUG}`
  - 예시: `ASSET-LOGI-GIF-RIGHTSIGHT2`, `ASSET-LOGI-PHOTO-REAR-PORTS`

---

## 5. 버전 번호(Version) 관리 규정
- 동일 ID 내에서 내용 갱신 시 버전을 올립니다:
  - 단순 오탈자 및 문장 수정: `v1.0` → `v1.1`
  - 제품 UI 전면 개편 또는 스펙 변경에 따른 대대적 재작성: `v1.1` → `v2.0`
- **버전이 올라가도 Content ID는 그대로 유지됩니다.**
