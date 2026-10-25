#!/usr/bin/env python3
"""
backup_registry.py (Chapter 7 Maintenance & Recovery)
registry/ 하위의 모든 핵심 CSV 파일(CONTENT, KEYWORD, SOURCE, PRODUCT_TOPIC)을
타임스탬프 기반 백업 디렉토리(registry/backups/YYYYMMDD_HHMMSS/)로 안전하게 복제하고 보존합니다.
"""
import os
import sys
import shutil
import glob
import json
import argparse
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_DIR = os.path.join(BASE_DIR, "registry")
BACKUP_ROOT = os.path.join(REGISTRY_DIR, "backups")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
EVENTS_LOG = os.path.join(LOGS_DIR, "events.jsonl")

def append_event_log(event, details=""):
    os.makedirs(LOGS_DIR, exist_ok=True)
    entry = {
        "time": datetime.now().isoformat(),
        "content_id": "SYSTEM",
        "actor": "BACKUP_MANAGER",
        "event": event,
        "from": "LIVE",
        "to": "BACKED_UP",
        "details": details
    }
    with open(EVENTS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def backup_registry(max_backups=10):
    os.makedirs(BACKUP_ROOT, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_backup_dir = os.path.join(BACKUP_ROOT, timestamp)
    os.makedirs(target_backup_dir, exist_ok=True)

    csv_files = glob.glob(os.path.join(REGISTRY_DIR, "*.csv"))
    if not csv_files:
        print("[WARN] No CSV files found to backup in registry/")
        return None

    copied = []
    for cf in csv_files:
        fname = os.path.basename(cf)
        dest = os.path.join(target_backup_dir, fname)
        shutil.copy2(cf, dest)
        copied.append(fname)

    print(f"[OK] Registry Backup created successfully at:")
    print(f"  -> {target_backup_dir}")
    print(f"  -> Files ({len(copied)}): {copied}")

    append_event_log("REGISTRY_BACKUP_CREATED", f"Backed up {len(copied)} files to {timestamp}")

    # Rotate old backups
    all_backups = sorted([
        os.path.join(BACKUP_ROOT, d) for d in os.listdir(BACKUP_ROOT)
        if os.path.isdir(os.path.join(BACKUP_ROOT, d))
    ])

    if len(all_backups) > max_backups:
        to_delete = all_backups[:-max_backups]
        for old_dir in to_delete:
            try:
                shutil.rmtree(old_dir)
                print(f"  -> [ROTATED] Removed old backup: {os.path.basename(old_dir)}")
            except Exception as e:
                print(f"  -> [WARN] Could not remove old backup {old_dir}: {e}")

    return target_backup_dir

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Create timestamped backup of registry CSVs")
    parser.add_argument("--max-backups", type=int, default=10, help="Number of backups to keep (default: 10)")
    args = parser.parse_args()

    backup_registry(args.max_backups)
