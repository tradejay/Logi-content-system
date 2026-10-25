#!/usr/bin/env python3
"""
create_evidence_request.py
제품 정보 부족 시 03_sources/inbox/ 에 표준화된 EVREQ-YYYYWww-NNN.yaml 요청을 발행하고
관련 콘텐츠를 NEEDS_EVIDENCE 상태로 안전하게 전이합니다.
"""
import os
import sys
import re
import yaml
import datetime
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INBOX_DIR = os.path.join(BASE_DIR, "03_sources", "inbox")
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")

def get_next_evreq_id():
    now = datetime.date.today()
    iso_year, iso_week, _ = now.isocalendar()
    week_str = f"W{iso_week:02d}"
    prefix = f"EVREQ-{iso_year}{week_str}-"
    
    os.makedirs(INBOX_DIR, exist_ok=True)
    max_num = 0
    pattern = re.compile(rf"^{re.escape(prefix)}(\d{{3}})\.yaml$")

    for fname in os.listdir(INBOX_DIR):
        m = pattern.match(fname)
        if m:
            n = int(m.group(1))
            if n > max_num:
                max_num = n

    next_num = max_num + 1
    return f"{prefix}{next_num:03d}"

def create_evidence_request(content_id, product, missing_type, question, needed_for="", severity="HIGH", acceptable_sources=None):
    if acceptable_sources is None:
        acceptable_sources = ["제조사 공식 데이터시트 (E1)", "공식 관리자 콘솔 가이드 (E2)", "실사 테스트 로그 (E4)"]

    req_id = get_next_evreq_id()
    now_iso = datetime.datetime.now().isoformat()

    evreq_data = {
        "evidence_request_id": req_id,
        "content_id": content_id,
        "product": product,
        "missing_type": missing_type,
        "severity": severity,
        "question": question,
        "needed_for": needed_for or "본문 기술 설명 및 실무 세팅 근거 보강",
        "acceptable_sources": acceptable_sources,
        "status": "OPEN",
        "created_at": now_iso,
        "resolved_at": None,
        "resolved_source_id": None
    }

    req_filepath = os.path.join(INBOX_DIR, f"{req_id}.yaml")
    with open(req_filepath, "w", encoding="utf-8") as f:
        yaml.safe_dump(evreq_data, f, allow_unicode=True, sort_keys=False)

    return req_id, req_filepath

MISSING_TYPES = [
    "MISSING_SPEC",
    "MISSING_FEATURE_DOC",
    "MISSING_COMPATIBILITY",
    "MISSING_CONFIGURATION",
    "MISSING_PLATFORM_REQUIREMENT",
    "MISSING_INSTALLATION_CONDITION",
    "MISSING_VERSION_INFO",
    "MISSING_TEST",
    "CONFLICTING_SOURCE"
]

STATUS_CHOICES = ["OPEN", "IN_RESEARCH", "RESOLVED", "CANCELLED"]

def update_evidence_request_status(evreq_id, new_status, resolved_source_id=None, notes=""):
    if new_status not in STATUS_CHOICES:
        raise ValueError(f"Invalid status '{new_status}'. Allowed: {STATUS_CHOICES}")
    
    req_file = os.path.join(INBOX_DIR, f"{evreq_id}.yaml")
    if not os.path.exists(req_file):
        return False, f"Request file not found: {req_file}"

    with open(req_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    data["status"] = new_status
    if new_status == "RESOLVED":
        data["resolved_at"] = datetime.datetime.now().isoformat()
        if resolved_source_id:
            data["resolved_source_id"] = resolved_source_id
    if notes:
        data["notes"] = notes

    with open(req_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

    return True, f"Status updated to {new_status}"

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Create or update standardized Evidence Request (EVREQ)")
    parser.add_argument("--content-id", help="Target Content ID")
    parser.add_argument("--product", help="Target Product name")
    parser.add_argument("--type", choices=MISSING_TYPES, help="Missing evidence type")
    parser.add_argument("--question", help="Specific technical question to answer")
    parser.add_argument("--needed-for", default="", help="Context/reason for the evidence")
    parser.add_argument("--severity", default="HIGH", choices=["LOW", "MEDIUM", "HIGH"], help="Severity level")
    parser.add_argument("--update-id", help="Evidence Request ID to update status")
    parser.add_argument("--set-status", choices=STATUS_CHOICES, help="New status for --update-id")
    parser.add_argument("--resolved-source", help="Source ID resolving this request")
    args = parser.parse_args()

    if args.update_id and args.set_status:
        ok, msg = update_evidence_request_status(args.update_id, args.set_status, args.resolved_source)
        print(f"[{'OK' if ok else 'ERROR'}] {msg}")
        sys.exit(0 if ok else 1)

    if not args.content_id or not args.product or not args.type or not args.question:
        parser.error("--content-id, --product, --type, and --question are required when creating a request")

    evreq_id, path = create_evidence_request(args.content_id, args.product, args.type, args.question, args.needed_for, args.severity)
    print(f"[OK] Evidence Request '{evreq_id}' generated:")
    print(f"  -> Path: {path}")
