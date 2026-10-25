#!/usr/bin/env python3
"""
impact_analysis.py (v1.1 Knowledge Update Impact Tracker)
특정 Knowledge Pack(KNW-) 또는 Source(SRC-)가 업데이트되거나 개정되었을 때,
해당 지식을 참조하고 있는 모든 기획서(Brief) 및 발행 글을 역추적하여 영향 범위를 보고합니다.
"""

import os
import sys
import yaml
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIEFS_DIR = os.path.join(BASE_DIR, "01_keyword_ai", "briefs")

def analyze_impact(target_id):
    affected = []
    if not os.path.exists(BRIEFS_DIR):
        return affected

    for f in os.listdir(BRIEFS_DIR):
        if f.endswith(".yaml") or f.endswith(".yml"):
            bpath = os.path.join(BRIEFS_DIR, f)
            with open(bpath, "r", encoding="utf-8") as bf:
                try:
                    data = yaml.safe_load(bf) or {}
                except Exception:
                    continue

            cid = data.get("content_id", f)
            status = data.get("status", "UNKNOWN")
            knw_list = data.get("knowledge_packs", [])
            src_list = data.get("required_sources", [])

            matches = []
            if target_id in knw_list:
                matches.append("knowledge_packs")
            if target_id in src_list:
                matches.append("required_sources")

            # Check sections
            sections = data.get("sections", [])
            for sec in sections:
                if isinstance(sec, dict):
                    if target_id in sec.get("required_knowledge", []):
                        matches.append(f"section:{sec.get('id')}")

            if matches:
                affected.append({
                    "content_id": cid,
                    "title": data.get("topic"),
                    "status": status,
                    "matched_in": list(set(matches))
                })

    return affected

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Analyze impact of Knowledge Pack or Source modification")
    parser.add_argument("target_id", help="Knowledge Pack ID (e.g. KNW-FEAT-LOGI-RIGHTSIGHT2) or Source ID (e.g. SRC-LOGI-DOC-RIGHTSENSE)")
    args = parser.parse_args()

    results = analyze_impact(args.target_id)
    print(f"=== Impact Analysis Report for '{args.target_id}' ===")
    if not results:
        print(f"  No contents currently reference '{args.target_id}'.")
    else:
        print(f"  Found {len(results)} affected content item(s):\n")
        for res in results:
            print(f"  * [{res['content_id']}] Status: {res['status']}")
            print(f"    Topic: {res['title']}")
            print(f"    Referenced In: {', '.join(res['matched_in'])}\n")
