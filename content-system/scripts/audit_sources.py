#!/usr/bin/env python3
"""
audit_sources.py (5-E Operations & Audit)
03_sources/INDEX.yaml 및 registry/SOURCE_REGISTRY.csv의 모든 공식 소스에 대해
신선도 기한(freshness_limit_days: 90일/180일) 및 실제 파일 존재 여부를 일괄 감사(Audit)합니다.
"""
import os
import sys
import yaml
from datetime import datetime, date

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_FILE = os.path.join(BASE_DIR, "03_sources", "INDEX.yaml")

# Source Type TTL Policies (in days)
SOURCE_TYPE_TTL_MAP = {
    "cloud_admin": 90,        # Cloud / Admin UI (Short)
    "admin_guide": 90,
    "ui_config": 90,
    "firmware_feature": 180,  # Firmware / Compatibility (Medium)
    "compatibility": 180,
    "support": 180,
    "physical_hardware": 365, # Physical Hardware Specifications (Long)
    "hardware_spec": 365,
    "whitepaper": 365,
    "spec": 365,
}
DEFAULT_TTL = 180

def audit_sources():
    if not os.path.exists(INDEX_FILE):
        print(f"[ERROR] Source index not found: {INDEX_FILE}")
        return False

    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    raw_sources = data.get("sources", [])
    if isinstance(raw_sources, dict):
        sources = []
        for k, v in raw_sources.items():
            if isinstance(v, dict):
                item = dict(v)
                item["id"] = k
                sources.append(item)
    elif isinstance(raw_sources, list):
        sources = raw_sources
    else:
        sources = []
    today = date.today()

    print("=" * 88)
    print(" [SOURCE FRESHNESS AUDIT REPORT - Multi-Tier TTL Policy]")
    print(f" 기준 일자: {today.isoformat()} | 등록 소스 총계: {len(sources)} 건")
    print("=" * 88)
    print(f"{'Source ID':<26} | {'Level':<5} | {'Type':<12} | {'Age(Days)':<9} | {'TTL':<5} | {'Status'}")
    print("-" * 88)

    stale_count = 0
    missing_count = 0
    valid_count = 0

    critical_total = 0
    critical_fresh = 0
    supporting_total = 0
    supporting_fresh = 0
    oldest_critical_days = 0

    for s in sources:
        sid = s.get("id", "UNKNOWN")
        lvl = s.get("evidence_level", "E1")
        stype = str(s.get("type", "spec")).lower()
        v_date_str = str(s.get("last_verified", "2026-01-01"))
        
        # Determine TTL by type or explicit limit
        explicit_limit = s.get("freshness_limit_days")
        if explicit_limit:
            limit_days = int(explicit_limit)
        else:
            limit_days = SOURCE_TYPE_TTL_MAP.get(stype, DEFAULT_TTL)

        rel_path = s.get("path", "")
        abs_path = os.path.join(BASE_DIR, "03_sources", rel_path)
        file_exists = os.path.exists(abs_path)

        try:
            v_date = datetime.strptime(v_date_str, "%Y-%m-%d").date()
            age_days = (today - v_date).days
        except Exception:
            age_days = 9999

        is_critical = lvl in ["E1", "E2"]
        if is_critical:
            critical_total += 1
            if age_days > oldest_critical_days:
                oldest_critical_days = age_days
        else:
            supporting_total += 1

        if not file_exists:
            status = "MISSING_FILE"
            missing_count += 1
        elif age_days > limit_days:
            status = "STALE"
            stale_count += 1
        else:
            status = "VALID"
            valid_count += 1
            if is_critical:
                critical_fresh += 1
            else:
                supporting_fresh += 1

        print(f"{sid:<26} | {lvl:<5} | {stype:<12} | {age_days:<9} | {limit_days:<5} | {status}")

    print("-" * 88)
    print(f"감사 요약: [VALID: {valid_count}] [STALE: {stale_count}] [MISSING: {missing_count}]")
    print(f"  * Critical Sources (E1/E2) : {critical_fresh} / {critical_total} Fresh")
    print(f"  * Supporting Sources       : {supporting_fresh} / {supporting_total} Fresh")
    print(f"  * Oldest Critical Source   : {oldest_critical_days} days\n")

    if missing_count > 0:
        print("[CRITICAL] 누락된 소스 파일이 존재합니다. 즉시 조치하십시오.")
        return False

    if stale_count > 0:
        print("[WARNING] 유효기간이 초과된 STALE 소스가 있습니다. 제조사 신규 업데이트 여부를 재확인하십시오.")

    return True

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    success = audit_sources()
    sys.exit(0 if success else 1)
