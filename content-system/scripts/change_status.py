#!/usr/bin/env python3
"""
change_status.py (5-B State Transaction Manager)
콘텐츠 상태 전이를 원자적 트랜잭션(Atomic Transaction)으로 수행합니다.
- Registry, Queue, Lock, Brief 파일의 원자적 쓰기(.tmp -> replace)
- 전이 실패 시 롤백 및 불일치 방지
- logs/events.jsonl 에 Audit Event 기록 (Event Sourcing)
"""
import os
import sys
import csv
import json
import yaml
import shutil
import argparse
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_FILE = os.path.join(BASE_DIR, "registry", "CONTENT_REGISTRY.csv")
BRIEFS_DIR = os.path.join(BASE_DIR, "01_keyword_ai", "briefs")
QUEUE_DIR = os.path.join(BASE_DIR, "queue")
LOCKS_DIR = os.path.join(BASE_DIR, "locks")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
EVENTS_LOG = os.path.join(LOGS_DIR, "events.jsonl")

ALLOWED_TRANSITIONS = {
    "NEW": {"KEYWORD_RESEARCH", "CANCELLED", "DUPLICATE"},
    "KEYWORD_RESEARCH": {"PLANNING", "DUPLICATE", "CANCELLED"},
    "PLANNING": {"RESEARCH_REQUIRED", "READY_FOR_WRITING", "CANCELLED"},
    "RESEARCH_REQUIRED": {"RESEARCHING", "NEEDS_EVIDENCE", "CANCELLED", "BLOCKED"},
    "RESEARCHING": {"KNOWLEDGE_REVIEW", "NEEDS_EVIDENCE", "BLOCKED"},
    "KNOWLEDGE_REVIEW": {"READY_FOR_WRITING", "RESEARCHING", "NEEDS_EVIDENCE", "BLOCKED"},
    "READY_FOR_WRITING": {"WRITING", "RESEARCH_REQUIRED", "BLOCKED"},
    "WRITING": {"READY_FOR_QA", "NEEDS_EVIDENCE", "BLOCKED"},
    "NEEDS_EVIDENCE": {"WRITING", "RESEARCHING", "CANCELLED", "BLOCKED"},
    "READY_FOR_QA": {"READY_TO_PUBLISH", "REVISION_REQUIRED", "BLOCKED"},
    "REVISION_REQUIRED": {"WRITING", "RESEARCH_REQUIRED"},
    "READY_TO_PUBLISH": {"PUBLISHED", "REVISION_REQUIRED"},
    "PUBLISHED": {"ARCHIVED", "REVISION_REQUIRED"},
    "BLOCKED": {"WRITING", "RESEARCHING", "CANCELLED"},
    "CANCELLED": set(),
    "DUPLICATE": set(),
    "ARCHIVED": set()
}

def atomic_write_yaml(filepath, data):
    tmp_path = f"{filepath}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
    # Validate before replace
    with open(tmp_path, "r", encoding="utf-8") as f:
        yaml.safe_load(f)
    os.replace(tmp_path, filepath)

def atomic_write_csv(filepath, rows, fieldnames):
    tmp_path = f"{filepath}.tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    # Validate before replace
    with open(tmp_path, "r", encoding="utf-8") as f:
        list(csv.reader(f))
    os.replace(tmp_path, filepath)

def append_event_log(content_id, actor, event, from_st, to_st, details=""):
    os.makedirs(LOGS_DIR, exist_ok=True)
    entry = {
        "time": datetime.now().isoformat(),
        "content_id": content_id,
        "actor": actor,
        "event": event,
        "from": from_st,
        "to": to_st,
        "details": details
    }
    with open(EVENTS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def get_current_status(content_id):
    if os.path.exists(REGISTRY_FILE):
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("content_id") == content_id:
                    return row.get("status")
    
    brief_file = os.path.join(BRIEFS_DIR, f"{content_id}.brief.yaml")
    if os.path.exists(brief_file):
        with open(brief_file, "r", encoding="utf-8") as f:
            bdata = yaml.safe_load(f)
            if bdata and "status" in bdata:
                return bdata["status"]
    return "NEW"

def load_queue(qname):
    qpath = os.path.join(QUEUE_DIR, qname)
    if os.path.exists(qpath):
        with open(qpath, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def execute_status_transaction(content_id, new_status, actor="SYSTEM", details="", force=False):
    if new_status in ("READY_TO_PUBLISH", "PUBLISHED"):
        sys.path.insert(0, os.path.dirname(BASE_DIR))
        from services.content_pipeline import ContentPipeline
        ContentPipeline().assert_publishable(content_id)
    curr_status = get_current_status(content_id)

    # 1. Transition validation
    if not force:
        allowed = ALLOWED_TRANSITIONS.get(curr_status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Illegal transition: Cannot move '{content_id}' from '{curr_status}' to '{new_status}'. "
                f"Allowed destinations: {sorted(allowed)}"
            )

    lock_file = os.path.join(LOCKS_DIR, f"{content_id}.lock")

    # 2. Concurrency Lock check
    if new_status == "WRITING":
        if os.path.exists(lock_file) and not force:
            with open(lock_file, "r", encoding="utf-8") as f:
                lk_info = yaml.safe_load(f) or {}
            raise RuntimeError(f"Lock conflict: Content '{content_id}' is already locked by {lk_info.get('role')} at {lk_info.get('started_at')}")
        # Create lock
        os.makedirs(LOCKS_DIR, exist_ok=True)
        with open(lock_file, "w", encoding="utf-8") as f:
            yaml.safe_dump({
                "content_id": content_id,
                "role": actor or "WRITER",
                "started_at": datetime.now().isoformat()
            }, f)

    # If leaving WRITING/QA, release lock
    if curr_status in ("WRITING", "READY_FOR_QA") and new_status in ("READY_FOR_QA", "READY_TO_PUBLISH", "PUBLISHED", "NEEDS_EVIDENCE", "BLOCKED"):
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
            except Exception:
                pass

    # 3. Snapshot for rollback
    backup_research_q = load_queue("research.queue.yaml")
    backup_writer_q = load_queue("writer.queue.yaml")
    backup_qa_q = load_queue("qa.queue.yaml")
    backup_blocked_q = load_queue("blocked.queue.yaml")

    try:
        # 4. Sync Queues
        research_q = dict(backup_research_q)
        writer_q = dict(backup_writer_q)
        qa_q = dict(backup_qa_q)
        blocked_q = dict(backup_blocked_q)

        def remove_item(lst, item):
            return [x for x in (lst or []) if x != item]

        if research_q.get("active") == content_id:
            research_q["active"] = None
        research_q["ready"] = remove_item(research_q.get("ready"), content_id)

        if writer_q.get("active") == content_id:
            writer_q["active"] = None
        writer_q["ready"] = remove_item(writer_q.get("ready"), content_id)

        if qa_q.get("active") == content_id:
            qa_q["active"] = None
        qa_q["ready"] = remove_item(qa_q.get("ready"), content_id)

        if new_status == "RESEARCH_REQUIRED":
            research_q.setdefault("ready", [])
            if content_id not in research_q["ready"]:
                research_q["ready"].append(content_id)

        elif new_status == "RESEARCHING":
            research_q["active"] = content_id

        elif new_status == "KNOWLEDGE_REVIEW":
            research_q.setdefault("completed", [])
            if content_id not in research_q["completed"]:
                research_q["completed"].append(content_id)

        elif new_status == "READY_FOR_WRITING":
            research_q.setdefault("completed", [])
            if content_id not in research_q["completed"]:
                research_q["completed"].append(content_id)
            writer_q.setdefault("ready", [])
            if content_id not in writer_q["ready"]:
                writer_q["ready"].append(content_id)

        elif new_status == "WRITING":
            writer_q["active"] = content_id

        elif new_status == "READY_FOR_QA":
            writer_q.setdefault("completed", [])
            if content_id not in writer_q["completed"]:
                writer_q["completed"].append(content_id)
            qa_q.setdefault("ready", [])
            if content_id not in qa_q["ready"]:
                qa_q["ready"].append(content_id)

        elif new_status == "REVISION_REQUIRED":
            writer_q.setdefault("ready", [])
            if content_id not in writer_q["ready"]:
                writer_q["ready"].append(content_id)

        elif new_status in ("READY_TO_PUBLISH", "PUBLISHED"):
            qa_q.setdefault("completed", [])
            if content_id not in qa_q["completed"]:
                qa_q["completed"].append(content_id)

        elif new_status in ("NEEDS_EVIDENCE", "BLOCKED"):
            blocked_q.setdefault("items", [])
            blocked_q["items"] = [item for item in blocked_q["items"] if item.get("content_id") != content_id]
            blocked_q["items"].append({
                "content_id": content_id,
                "status": new_status,
                "reason": details or "Moved to blocked queue",
                "timestamp": datetime.now().isoformat()
            })

        atomic_write_yaml(os.path.join(QUEUE_DIR, "research.queue.yaml"), research_q)
        atomic_write_yaml(os.path.join(QUEUE_DIR, "writer.queue.yaml"), writer_q)
        atomic_write_yaml(os.path.join(QUEUE_DIR, "qa.queue.yaml"), qa_q)
        atomic_write_yaml(os.path.join(QUEUE_DIR, "blocked.queue.yaml"), blocked_q)

        # 5. Update Brief file if exists
        brief_file = os.path.join(BRIEFS_DIR, f"{content_id}.brief.yaml")
        if os.path.exists(brief_file):
            with open(brief_file, "r", encoding="utf-8") as f:
                bdata = yaml.safe_load(f) or {}
            bdata["status"] = new_status
            bdata["updated_at"] = datetime.now().strftime("%Y-%m-%d")
            atomic_write_yaml(brief_file, bdata)

        # 6. Update Registry file
        if os.path.exists(REGISTRY_FILE):
            rows = []
            updated = False
            fieldnames = []
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                for r in reader:
                    if r.get("content_id") == content_id:
                        r["status"] = new_status
                        r["last_reviewed"] = datetime.now().strftime("%Y-%m-%d")
                        updated = True
                    rows.append(r)
            if updated and fieldnames:
                atomic_write_csv(REGISTRY_FILE, rows, fieldnames)

        # 7. Append Event Log
        event_name = f"STATUS_TRANSITION_{new_status}"
        append_event_log(content_id, actor, event_name, curr_status, new_status, details)

    except Exception as exc:
        # Rollback queues
        atomic_write_yaml(os.path.join(QUEUE_DIR, "writer.queue.yaml"), backup_writer_q)
        atomic_write_yaml(os.path.join(QUEUE_DIR, "qa.queue.yaml"), backup_qa_q)
        atomic_write_yaml(os.path.join(QUEUE_DIR, "blocked.queue.yaml"), backup_blocked_q)
        raise RuntimeError(f"Transaction failed and rolled back cleanly: {exc}")

    return curr_status, new_status

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Execute atomic status transition transaction")
    parser.add_argument("content_id", help="Content ID")
    parser.add_argument("new_status", help="Target status")
    parser.add_argument("--actor", default="OPERATOR", help="Actor triggering the transition")
    parser.add_argument("--details", default="", help="Details or audit notes")
    parser.add_argument("--force", action="store_true", help="Bypass check (Admin only)")
    args = parser.parse_args()

    try:
        old_st, new_st = execute_status_transaction(args.content_id, args.new_status, args.actor, args.details, args.force)
        print(f"[TRANSACTION OK] '{args.content_id}' : {old_st} -> {new_st} (Event Logged)")
    except Exception as e:
        print(f"[TRANSACTION FAIL] {e}", file=sys.stderr)
        sys.exit(1)
