#!/usr/bin/env python3
"""
scripts/check_knowledge_coverage.py
Knowledge Coverage Gate: Checks if Research Requirements for a content ID
are resolved with verified knowledge packs before approving transition to READY_FOR_WRITING.
If ANY 'critical' requirement is unresolved, the gate fails immediately.
"""

import os
import sys
import yaml
import argparse

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RR_DIR = os.path.join(BASE_DIR, "01_keyword_ai", "research_requirements")
KNW_DIR = os.path.join(BASE_DIR, "03_sources", "knowledge")

def find_knowledge_file(kid):
    for root, _, files in os.walk(KNW_DIR):
        for f in files:
            if f.startswith(kid) and (f.endswith(".yaml") or f.endswith(".yml")):
                return os.path.join(root, f)
    return None

def check_coverage(content_id):
    rr_file = os.path.join(RR_DIR, f"RR-{content_id}.yaml")
    if not os.path.exists(rr_file):
        # Fallback: check brief for embedded research_requirements
        brief_file = os.path.join(BASE_DIR, "01_keyword_ai", "briefs", f"{content_id}.brief.yaml")
        if os.path.exists(brief_file):
            with open(brief_file, "r", encoding="utf-8") as bf:
                bdata = yaml.safe_load(bf) or {}
            reqs = bdata.get("research_requirements", [])
        else:
            return False, [f"No Research Requirements found for '{content_id}'"], {}
    else:
        with open(rr_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        reqs = data.get("must_resolve", [])

    if not reqs:
        return False, ["Research Requirements list is empty"], {}

    critical_unresolved = []
    high_unresolved = []
    coverage_map = {}

    for r in reqs:
        rid = r.get("id", "UNKNOWN")
        cat = r.get("category", "general")
        priority = r.get("priority", "medium")
        kid = r.get("resolved_by")
        status = r.get("status", "UNRESOLVED")

        # Verify that kid exists and is VERIFIED
        is_verified = False
        if kid:
            kf = find_knowledge_file(kid)
            if kf and os.path.exists(kf):
                with open(kf, "r", encoding="utf-8") as f:
                    kdata = yaml.safe_load(f) or {}
                if kdata.get("status") == "VERIFIED":
                    is_verified = True

        if not is_verified or status != "RESOLVED":
            coverage_map[cat] = "MISSING"
            if priority == "critical":
                critical_unresolved.append(f"{rid} [{cat}]: {r.get('question')}")
            elif priority == "high":
                high_unresolved.append(f"{rid} [{cat}]: {r.get('question')}")
        else:
            coverage_map[cat] = "PASS"

    errors = []
    if critical_unresolved:
        errors.append(f"Critical Research Requirements unresolved ({len(critical_unresolved)}):")
        for u in critical_unresolved:
            errors.append(f"  - CRITICAL: {u}")

    passed = len(critical_unresolved) == 0
    return passed, errors, coverage_map

def main():
    parser = argparse.ArgumentParser(description="Check Knowledge Coverage for Content ID")
    parser.add_argument("content_id", help="Content ID (e.g. CNT-2026W39-001)")
    args = parser.parse_args()

    passed, errors, cov = check_coverage(args.content_id)
    print("=" * 70)
    print(f" [KNOWLEDGE COVERAGE GATE REPORT: {args.content_id}]")
    print("=" * 70)
    for cat, status in cov.items():
        print(f"  - {cat:<22}: {status}")
    print("-" * 70)
    if passed:
        print("[PASS] All critical research requirements verified! Ready for writing.")
        sys.exit(0)
    else:
        print(f"[FAIL] Knowledge Coverage Gate FAILED:")
        for err in errors:
            print(f"  {err}")
        sys.exit(1)

if __name__ == "__main__":
    main()
