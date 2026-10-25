#!/usr/bin/env python3
"""
create_week.py
새로운 주간 배치 디렉토리(weekly/YYYY-Www/)와 manifest.yaml, summary.md, changelog.md를 생성합니다.
"""
import os
import sys
import re
import datetime
import yaml
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEEKLY_DIR = os.path.join(BASE_DIR, "weekly")

def create_week(year=None, week=None, keyword_target=8, draft_target=4):
    now = datetime.date.today()
    if not year or not week:
        iso_year, iso_week, _ = now.isocalendar()
        year = year or iso_year
        week = week or f"W{iso_week:02d}"

    if isinstance(week, int):
        week_str = f"W{week:02d}"
        week_num = week
    else:
        week_num = int(re.sub(r"[^\d]", "", str(week)))
        week_str = f"W{week_num:02d}"

    folder_name = f"{year}-{week_str}"
    batch_id = f"BATCH-{year}{week_str}"
    target_path = os.path.join(WEEKLY_DIR, folder_name)
    os.makedirs(target_path, exist_ok=True)

    # 1. manifest.yaml
    manifest_data = {
        "batch_id": batch_id,
        "week": {
            "year": year,
            "number": week_num
        },
        "status": "ACTIVE",
        "targets": {
            "keyword_briefs": keyword_target,
            "drafts": draft_target,
            "publish": draft_target
        },
        "keyword_input": {
            "source": "keyword_graph.db",
            "selection_rule": "product_affinity_and_opportunity",
            "candidate_pool": "high_affinity_nodes"
        },
        "contents": [],
        "started_at": now.strftime("%Y-%m-%d"),
        "closed_at": None
    }
    manifest_path = os.path.join(target_path, "manifest.yaml")
    with open(manifest_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(manifest_data, f, allow_unicode=True, sort_keys=False)

    # 2. summary.md
    summary_content = f"""# {year}-{week_str} 주간 운영 요약 보고서

- **Batch ID**: `{batch_id}`
- **시작일**: {now.strftime("%Y-%m-%d")}
- **상태**: `ACTIVE`

## 주간 생산 현황
- 신규 키워드 기획(Brief): 0 / {keyword_target}
- 초안 작성 완료(Draft): 0 / {draft_target}
- 검수 통과(QA Pass): 0 / {draft_target}
- 최종 배포(Published): 0 / {draft_target}

## 이슈 및 블로커
- 결측 증거(Missing Evidence): 0건
- 차단(Blocked): 0건
"""
    with open(os.path.join(target_path, "summary.md"), "w", encoding="utf-8") as f:
        f.write(summary_content)

    # 3. changelog.md
    changelog_content = f"""# {year}-{week_str} 변경 이력 (Changelog)

- {now.strftime("%Y-%m-%d")}: `{batch_id}` 주간 배치 디렉토리 및 매니페스트 초기화 완료.
"""
    with open(os.path.join(target_path, "changelog.md"), "w", encoding="utf-8") as f:
        f.write(changelog_content)

    return target_path, batch_id

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create new Weekly Operation Batch")
    parser.add_argument("--year", type=int, help="Year (e.g. 2026)")
    parser.add_argument("--week", type=str, help="Week (e.g. W39 or 39)")
    parser.add_argument("--briefs", type=int, default=8, help="Target briefs count")
    parser.add_argument("--drafts", type=int, default=4, help="Target drafts count")
    args = parser.parse_args()

    wpath, bid = create_week(args.year, args.week, args.briefs, args.drafts)
    print(f"SUCCESS: Weekly batch '{bid}' initialized at:")
    print(f"  -> {wpath}")
