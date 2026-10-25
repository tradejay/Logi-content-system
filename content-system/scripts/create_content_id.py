#!/usr/bin/env python3
"""
create_content_id.py
원자적으로 중복 없는 다음 Content ID(CNT-YYYYWww-NNN)를 발급합니다.
"""
import os
import sys
import re
import csv
import datetime
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_FILE = os.path.join(BASE_DIR, "registry", "CONTENT_REGISTRY.csv")
BRIEFS_DIR = os.path.join(BASE_DIR, "01_keyword_ai", "briefs")

def get_current_year_week():
    now = datetime.date.today()
    iso_year, iso_week, _ = now.isocalendar()
    return iso_year, f"W{iso_week:02d}"

def generate_content_id(year=None, week=None):
    if not year or not week:
        curr_y, curr_w = get_current_year_week()
        year = year or curr_y
        week = week or curr_w
    
    if isinstance(week, int):
        week = f"W{week:02d}"
    elif not week.startswith("W"):
        week = f"W{int(week):02d}"

    pattern = re.compile(rf"^CNT-{year}{week}-(\d{{3}})")
    max_seq = 0

    # 1. Check CONTENT_REGISTRY.csv
    if os.path.exists(REGISTRY_FILE):
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = row.get("content_id", "")
                m = pattern.match(cid)
                if m:
                    seq = int(m.group(1))
                    if seq > max_seq:
                        max_seq = seq

    # 2. Check 01_keyword_ai/briefs
    if os.path.exists(BRIEFS_DIR):
        for fname in os.listdir(BRIEFS_DIR):
            m = pattern.match(fname)
            if m:
                seq = int(m.group(1))
                if seq > max_seq:
                    max_seq = seq

    next_seq = max_seq + 1
    new_id = f"CNT-{year}{week}-{next_seq:03d}"
    return new_id

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate next unique Content ID")
    parser.add_argument("--year", type=int, help="Target Year (e.g. 2026)")
    parser.add_argument("--week", type=str, help="Target Week (e.g. W39 or 39)")
    args = parser.parse_args()

    content_id = generate_content_id(args.year, args.week)
    print(content_id)
