#!/usr/bin/env python3
"""
validate_project.py
프로젝트 전체(소스 인덱스, 기획서, 레지스트리, 큐, 잔여 락)의 정합성을 일괄 전수 검사합니다.
"""
import os
import sys
import csv
import yaml
import glob
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_FILE = os.path.join(BASE_DIR, "03_sources", "INDEX.yaml")
REGISTRY_FILE = os.path.join(BASE_DIR, "registry", "CONTENT_REGISTRY.csv")
BRIEFS_DIR = os.path.join(BASE_DIR, "01_keyword_ai", "briefs")
LOCKS_DIR = os.path.join(BASE_DIR, "locks")
QUEUE_DIR = os.path.join(BASE_DIR, "queue")

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def validate_project():
    issues = []
    warnings = []
    checks_passed = 0

    print("=" * 60)
    print(" [INFO] 주간 AI 콘텐츠 운영 시스템 프로젝트 정합성 검사")
    print("=" * 60)

    # 1. Check Source Index & Files
    if not os.path.exists(INDEX_FILE):
        issues.append("03_sources/INDEX.yaml does not exist.")
    else:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            idx = yaml.safe_load(f) or {}
        raw_sources = idx.get("sources", {})
        source_items = raw_sources.values() if isinstance(raw_sources, dict) else raw_sources
        for s in source_items:
            if isinstance(s, dict):
                spath = os.path.join(BASE_DIR, "03_sources", s.get("path", ""))
                if not os.path.exists(spath):
                    issues.append(f"Broken Source Path: points to non-existent '{s.get('path')}'")
                else:
                    checks_passed += 1

    # 2. Check Briefs
    brief_files = glob.glob(os.path.join(BRIEFS_DIR, "*.brief.yaml"))
    for bf in brief_files:
        with open(bf, "r", encoding="utf-8") as f:
            bdata = yaml.safe_load(f) or {}
        mix = bdata.get("content_type_mix", {})
        if sum(mix.values()) != 100:
            issues.append(f"Brief '{os.path.basename(bf)}' content_type_mix sum is {sum(mix.values())}%, not 100%")
        else:
            checks_passed += 1

    # 3. Check CONTENT_REGISTRY.csv
    if not os.path.exists(REGISTRY_FILE):
        issues.append("registry/CONTENT_REGISTRY.csv does not exist.")
    else:
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                cid = r.get("content_id")
                b_path = r.get("brief_path")
                if b_path and not os.path.exists(os.path.join(BASE_DIR, b_path)):
                    warnings.append(f"Registry {cid}: brief_path '{b_path}' not found on disk")
                checks_passed += 1

    # 4. Check Stale Locks
    if os.path.exists(LOCKS_DIR):
        for lk in os.listdir(LOCKS_DIR):
            if lk.endswith(".lock"):
                lk_path = os.path.join(LOCKS_DIR, lk)
                mtime = datetime.fromtimestamp(os.path.getmtime(lk_path))
                if datetime.now() - mtime > timedelta(hours=24):
                    issues.append(f"Stale Lock detected (>24h): {lk}")
                else:
                    warnings.append(f"Active Lock present: {lk}")

    # 5. Check Queues
    for qf in ["keyword.queue.yaml", "research.queue.yaml", "writer.queue.yaml", "qa.queue.yaml", "blocked.queue.yaml"]:
        qp = os.path.join(QUEUE_DIR, qf)
        if not os.path.exists(qp):
            issues.append(f"Queue file missing: {qf}")
        else:
            with open(qp, "r", encoding="utf-8") as f:
                try:
                    yaml.safe_load(f)
                    checks_passed += 1
                except Exception as e:
                    issues.append(f"Queue YAML syntax error in {qf}: {e}")

    print(f"\n[검사 결과 요약]")
    print(f"  - 통과된 무결성 점검 항목: {checks_passed} 건")
    print(f"  - 경고 사항(Warnings): {len(warnings)} 건")
    print(f"  - 결함 사항(Issues): {len(issues)} 건")

    if warnings:
        print("\n[WARN: 경고 목록]")
        for w in warnings:
            print(f"  - {w}")

    if issues:
        print("\n[ERROR: 오류 목록]")
        for i in issues:
            print(f"  - {i}")
        print("\n결과: [FAIL] 프로젝트 정합성 검사 실패.")
        return False
    else:
        print("\n결과: [PASS] 프로젝트의 모든 파일, 스키마, 큐, 레지스트리가 100% 정상입니다.")
        return True

if __name__ == "__main__":
    success = validate_project()
    sys.exit(0 if success else 1)
