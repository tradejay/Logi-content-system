#!/usr/bin/env python3
"""
recover_locks.py (Chapter 7 Maintenance & Recovery)
방치되거나 비정상 종료로 남겨진 고아 락(Stale Lock, 기본 24시간 초과)을 안전하게 감지하고 해제합니다.
"""
import os
import sys
import json
import yaml
import argparse
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCKS_DIR = os.path.join(BASE_DIR, "locks")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
EVENTS_LOG = os.path.join(LOGS_DIR, "events.jsonl")

def append_event_log(content_id, event, details=""):
    os.makedirs(LOGS_DIR, exist_ok=True)
    entry = {
        "time": datetime.now().isoformat(),
        "content_id": content_id,
        "actor": "RECOVERY_MANAGER",
        "event": event,
        "from": "LOCKED",
        "to": "UNLOCKED",
        "details": details
    }
    with open(EVENTS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def recover_locks(max_hours=24, clean=False):
    if not os.path.exists(LOCKS_DIR):
        print("[INFO] locks/ directory does not exist.")
        return 0

    lock_files = [f for f in os.listdir(LOCKS_DIR) if f.endswith(".lock")]
    if not lock_files:
        print("[INFO] 활성화된 Lock 파일이 없습니다. (정상 상태)")
        return 0

    now = datetime.now()
    threshold = timedelta(hours=max_hours)
    stale_locks = []

    print("=" * 70)
    print(f" [LOCK AUDIT] 현재 활성 Lock 총계: {len(lock_files)} 건 (기준 초과 기한: {max_hours}시간)")
    print("=" * 70)

    for lf in lock_files:
        lpath = os.path.join(LOCKS_DIR, lf)
        mtime = datetime.fromtimestamp(os.path.getmtime(lpath))
        age = now - mtime

        lock_data = {}
        try:
            with open(lpath, "r", encoding="utf-8") as f:
                lock_data = yaml.safe_load(f) or {}
        except Exception:
            pass

        cid = lock_data.get("content_id", lf.replace(".lock", ""))
        role = lock_data.get("role", "UNKNOWN")

        is_stale = age > threshold
        status_str = "STALE (고아 락)" if is_stale else "ACTIVE (정상 작업 중)"

        print(f"  - File: {lf:<24} | Role: {role:<10} | 경과: {age.total_seconds()/3600:.1f}시간 | 상태: {status_str}")

        if is_stale:
            stale_locks.append((lf, lpath, cid, role, age))

    if stale_locks:
        print(f"\n[ALERT] 총 {len(stale_locks)} 건의 고아 락이 감지되었습니다.")
        if clean:
            for lf, lpath, cid, role, age in stale_locks:
                try:
                    os.remove(lpath)
                    append_event_log(cid, "STALE_LOCK_RECOVERED", f"Lock released after {age.total_seconds()/3600:.1f}h of inactivity (Role: {role})")
                    print(f"  -> [CLEANED] '{lf}' 강제 해제 완료 (Audit Event 기록됨).")
                except Exception as e:
                    print(f"  -> [ERROR] '{lf}' 삭제 실패: {e}")
        else:
            print("[DRY-RUN] 고아 락을 강제 해제하려면 '--clean' 플래그를 붙여 다시 실행하십시오.")

    return len(stale_locks)

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Audit and recover stale concurrency locks")
    parser.add_argument("--max-hours", type=float, default=24.0, help="Max inactivity threshold in hours (default: 24)")
    parser.add_argument("--clean", action="store_true", help="Automatically delete stale lock files")
    args = parser.parse_args()

    recover_locks(args.max_hours, args.clean)
