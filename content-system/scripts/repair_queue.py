#!/usr/bin/env python3
"""
repair_queue.py (5-E Operations & Audit)
중앙 레지스트리(CONTENT_REGISTRY.csv)를 단일 진실 공급원(Single Source of Truth)으로 삼아,
불일치하거나 손상된 대기열(writer.queue.yaml, qa.queue.yaml 등)을 자동으로 복구합니다.
--dry-run: 불일치 내역만 출력
--apply: 큐 파일 실제 재구성 복구
"""
import os
import sys
import csv
import yaml
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_FILE = os.path.join(BASE_DIR, "registry", "CONTENT_REGISTRY.csv")
QUEUE_DIR = os.path.join(BASE_DIR, "queue")

def load_queue(qname):
    qpath = os.path.join(QUEUE_DIR, qname)
    if os.path.exists(qpath):
        with open(qpath, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def save_queue(qname, data):
    qpath = os.path.join(QUEUE_DIR, qname)
    tmp_path = f"{qpath}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
    os.replace(tmp_path, qpath)

def repair_queues(apply=False):
    if not os.path.exists(REGISTRY_FILE):
        print("[ERROR] CONTENT_REGISTRY.csv not found.")
        return False

    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        records = list(reader)

    # Reconstruct ideal queue state
    ideal_research_ready = []
    ideal_research_active = None
    ideal_research_completed = []

    ideal_writer_ready = []
    ideal_writer_active = None
    ideal_writer_completed = []

    ideal_qa_ready = []
    ideal_qa_active = None
    ideal_qa_completed = []

    ideal_blocked_items = []

    for r in records:
        cid = r.get("content_id")
        st = r.get("status")

        if st == "RESEARCH_REQUIRED":
            ideal_research_ready.append(cid)
        elif st == "RESEARCHING":
            ideal_research_active = cid
        elif st in ("KNOWLEDGE_REVIEW", "READY_FOR_WRITING", "WRITING", "READY_FOR_QA", "READY_TO_PUBLISH", "PUBLISHED", "ARCHIVED"):
            ideal_research_completed.append(cid)

        if st == "READY_FOR_WRITING" or st == "REVISION_REQUIRED":
            ideal_writer_ready.append(cid)
        elif st == "WRITING":
            ideal_writer_active = cid
        elif st == "READY_FOR_QA":
            ideal_writer_completed.append(cid)
            ideal_qa_ready.append(cid)
        elif st in ("READY_TO_PUBLISH", "PUBLISHED", "ARCHIVED"):
            ideal_writer_completed.append(cid)
            ideal_qa_completed.append(cid)
        elif st in ("NEEDS_EVIDENCE", "BLOCKED"):
            ideal_blocked_items.append({
                "content_id": cid,
                "status": st,
                "reason": "Derived from registry status"
            })

    current_research = load_queue("research.queue.yaml")
    current_writer = load_queue("writer.queue.yaml")
    current_qa = load_queue("qa.queue.yaml")
    current_blocked = load_queue("blocked.queue.yaml")

    discrepancies = []

    if set(current_research.get("ready", [])) != set(ideal_research_ready):
        discrepancies.append(f"research.queue 'ready' mismatch: Current={current_research.get('ready')} vs Ideal={ideal_research_ready}")

    if set(current_writer.get("ready", [])) != set(ideal_writer_ready):
        discrepancies.append(f"writer.queue 'ready' mismatch: Current={current_writer.get('ready')} vs Ideal={ideal_writer_ready}")

    if set(current_qa.get("ready", [])) != set(ideal_qa_ready):
        discrepancies.append(f"qa.queue 'ready' mismatch: Current={current_qa.get('ready')} vs Ideal={ideal_qa_ready}")

    print(f"[REPAIR QUEUE CHECK] Found {len(discrepancies)} discrepancy(ies).")
    for d in discrepancies:
        print(f"  - {d}")

    if apply:
        new_research = {
            "active": ideal_research_active,
            "ready": ideal_research_ready,
            "completed": list(set(ideal_research_completed)),
            "blocked": []
        }
        new_writer = {
            "active": ideal_writer_active,
            "ready": ideal_writer_ready,
            "completed": list(set(ideal_writer_completed)),
            "blocked": []
        }
        new_qa = {
            "active": ideal_qa_active,
            "ready": ideal_qa_ready,
            "completed": list(set(ideal_qa_completed)),
            "blocked": []
        }
        new_blocked = {
            "items": ideal_blocked_items
        }

        save_queue("research.queue.yaml", new_research)
        save_queue("writer.queue.yaml", new_writer)
        save_queue("qa.queue.yaml", new_qa)
        save_queue("blocked.queue.yaml", new_blocked)
        print("[REPAIR APPLIED] All queues successfully reconstructed from CONTENT_REGISTRY.csv!")
    else:
        if discrepancies:
            print("[DRY-RUN] Re-run with '--apply' to automatically fix queue discrepancies.")

    return len(discrepancies) == 0

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Rebuild queue state from Registry as single source of truth")
    parser.add_argument("--apply", action="store_true", help="Apply repaired queue state to files")
    args = parser.parse_args()

    repair_queues(args.apply)
