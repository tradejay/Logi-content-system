#!/usr/bin/env python3
"""
archive_week.py
지정된 주간 배치(weekly/YYYY-Www/)의 작업을 마감하고 매니페스트 상태를 ARCHIVED로 전환합니다.
"""
import os
import sys
import yaml
import datetime
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEEKLY_DIR = os.path.join(BASE_DIR, "weekly")

def archive_week(week_str):
    wpath = os.path.join(WEEKLY_DIR, week_str)
    if not os.path.exists(wpath):
        raise FileNotFoundError(f"Weekly folder not found: {wpath}")

    manifest_path = os.path.join(wpath, "manifest.yaml")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"manifest.yaml not found in {wpath}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    now_str = datetime.date.today().strftime("%Y-%m-%d")
    data["status"] = "ARCHIVED"
    data["closed_at"] = now_str

    with open(manifest_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

    changelog_path = os.path.join(wpath, "changelog.md")
    if os.path.exists(changelog_path):
        with open(changelog_path, "a", encoding="utf-8") as f:
            f.write(f"- {now_str}: 주간 배치 마감 완료 (`status: ARCHIVED`).\n")

    return manifest_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Archive completed weekly batch")
    parser.add_argument("week", help="Weekly folder name (e.g. 2026-W39)")
    args = parser.parse_args()

    try:
        mpath = archive_week(args.week)
        print(f"SUCCESS: Weekly batch '{args.week}' successfully archived.")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
