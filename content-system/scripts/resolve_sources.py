#!/usr/bin/env python3
"""
resolve_sources.py (v1.1 Source & Knowledge Resolver)
Content Brief의 주제(Topic), 대상 제품(Product), 플랫폼(Platform), 섹션 요구사항을 바탕으로
03_sources/INDEX.yaml의 공식 출처(SRC-) 및 03_sources/knowledge/의 공인 지식 팩(KNW-)을
자동 탐색 및 결정합니다.
"""

import os
import sys
import yaml
import argparse
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_FILE = os.path.join(BASE_DIR, "03_sources", "INDEX.yaml")
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "03_sources", "knowledge")
BRIEFS_DIR = os.path.join(BASE_DIR, "01_keyword_ai", "briefs")

# Provider Registry Integration
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))
try:
    from providers.provider_registry import get_provider_registry
except ImportError:
    get_provider_registry = None

# Topic & Keyword -> Knowledge Pack & Source Mapping Catalog
TOPIC_KNOWLEDGE_MAP = {
    "speaker_tracking": [
        "KNW-FEAT-LOGI-RIGHTSIGHT2",
        "KNW-CONC-SPEAKER-TRACKING"
    ],
    "rightsight": [
        "KNW-FEAT-LOGI-RIGHTSIGHT2"
    ],
    "auto_framing": [
        "KNW-FEAT-LOGI-RIGHTSIGHT2",
        "KNW-CONC-SPEAKER-TRACKING"
    ],
    "zoom": [
        "KNW-PLAT-ZOOM-ROOMS"
    ],
    "teams": [
        "KNW-PLAT-TEAMS-ROOMS"
    ],
    "echo": [
        "KNW-CONC-AUDIO-ECHO-REVERB"
    ],
    "meetup": [
        "KNW-PROD-LOGI-MEETUP2"
    ]
}

PRODUCT_KNOWLEDGE_MAP = {
    "rally_bar": "KNW-PROD-LOGI-RALLYBAR",
    "rally-bar": "KNW-PROD-LOGI-RALLYBAR",
    "rally bar": "KNW-PROD-LOGI-RALLYBAR",
    "logi-rally-bar": "KNW-PROD-LOGI-RALLYBAR",
    "logitech rally bar": "KNW-PROD-LOGI-RALLYBAR",
    "meetup 2": "KNW-PROD-LOGI-MEETUP2",
    "meetup-2": "KNW-PROD-LOGI-MEETUP2",
    "logi-meetup-2": "KNW-PROD-LOGI-MEETUP2",
}

def load_sources_index():
    if not os.path.exists(INDEX_FILE):
        return []
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("sources", [])

def resolve_for_brief(brief_path):
    with open(brief_path, "r", encoding="utf-8") as f:
        brief = yaml.safe_load(f) or {}

    cid = brief.get("content_id", "UNKNOWN")
    canonical_topic = str(brief.get("canonical_topic", "")).lower()
    product_bridge = brief.get("product_bridge", {})
    product_name = str(product_bridge.get("product", "")).lower() if isinstance(product_bridge, dict) else ""
    
    search_obj = brief.get("search", {})
    kw_list = []
    if isinstance(search_obj, dict):
        kw_list.append(str(search_obj.get("primary_keyword", "")).lower())
        for sk in search_obj.get("supporting_keywords", []):
            kw_list.append(str(sk).lower())
        for tt in search_obj.get("technical_terms", []):
            kw_list.append(str(tt).lower())

    text_corpus = f"{canonical_topic} {product_name} {' '.join(kw_list)}".lower()

    # 1. Resolve Knowledge Packs
    resolved_knw = set()
    for key, knw_ids in TOPIC_KNOWLEDGE_MAP.items():
        if key in text_corpus:
            for kid in knw_ids:
                resolved_knw.add(kid)

    for p_key, kid in PRODUCT_KNOWLEDGE_MAP.items():
        if p_key in product_name or p_key in text_corpus:
            resolved_knw.add(kid)

    # Check explicit sections in brief
    sections = brief.get("sections", [])
    if isinstance(sections, list):
        for sec in sections:
            if isinstance(sec, dict):
                sec_type = str(sec.get("type", "")).lower()
                if "zoom" in sec_type or "zoom" in str(sec.get("objective", "")).lower():
                    resolved_knw.add("KNW-PLAT-ZOOM-ROOMS")
                for rk in sec.get("required_knowledge", []):
                    resolved_knw.add(rk)

    # Verify Knowledge Pack Files Exist
    existing_knw = {}
    for root, _, files in os.walk(KNOWLEDGE_DIR):
        for f in files:
            if f.endswith(".yaml") or f.endswith(".yml"):
                kid = os.path.splitext(f)[0]
                existing_knw[kid] = os.path.join(root, f)

    valid_knw = [k for k in sorted(resolved_knw) if k in existing_knw]
    missing_knw = [k for k in sorted(resolved_knw) if k not in existing_knw]

    # 2. Resolve Sources from INDEX.yaml and Providers
    sources = load_sources_index()
    resolved_sources = set(brief.get("required_sources", []))

    for s in sources:
        sid = s.get("id", "")
        topics = str(s.get("topics", "")).lower()
        title = str(s.get("title", "")).lower()
        path = str(s.get("path", "")).lower()

        # Keyword matching
        if "speaker" in text_corpus or "rightsight" in text_corpus:
            if sid in ["SRC-LOGI-DOC-RIGHTSENSE", "SRC-LOGI-DOC-RALLY-BAR-GUIDE"]:
                resolved_sources.add(sid)
        if "rally_bar" in text_corpus or "rally bar" in text_corpus:
            if "rally-bar" in path or "rally_bar" in topics:
                resolved_sources.add(sid)

    # 3. Process Explicit source_requirements (Provider-Ready)
    source_reqs = brief.get("source_requirements", [])
    provider_results = []
    candidate_evidence_requests = []
    
    if get_provider_registry:
        registry = get_provider_registry()
        for sreq in source_reqs:
            rid = sreq.get("requirement_id", "SR-UNKNOWN")
            subj = sreq.get("subject", "")
            qtype = sreq.get("query_type", "FEATURE")
            vendor = sreq.get("vendor", "")
            priority = sreq.get("priority", "medium")
            
            q_str = f"{vendor} {subj} {qtype}".strip()
            p_res = registry.search(q_str)
            matched = p_res.get("results", [])
            
            if matched:
                provider_results.append({
                    "requirement_id": rid,
                    "query": q_str,
                    "matched_count": len(matched),
                    "top_doc": matched[0]["title"],
                    "location": matched[0]["source_location"]
                })
                # Add document id if it maps to a source
                for doc in matched:
                    if doc["document_id"].startswith("SRC-"):
                        resolved_sources.add(doc["document_id"])
            else:
                candidate_evidence_requests.append({
                    "request_id": f"EVR-{cid}-{rid}",
                    "missing_type": f"MISSING_{qtype.upper()}",
                    "subject": f"{vendor} {subj}".strip(),
                    "priority": priority,
                    "status": "OPEN",
                    "reason": f"No provider results found for source requirement {rid} ({q_str})"
                })

    return {
        "content_id": cid,
        "resolved_knowledge_packs": valid_knw,
        "missing_knowledge_packs": missing_knw,
        "resolved_sources": sorted(list(resolved_sources)),
        "provider_results": provider_results,
        "candidate_evidence_requests": candidate_evidence_requests
    }

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Resolve sources and knowledge packs for a content brief")
    parser.add_argument("target", help="Content ID (e.g. CNT-2026W39-001) or brief yaml path")
    parser.add_argument("--update-brief", action="store_true", help="Automatically inject resolved knowledge packs into brief")
    args = parser.parse_args()

    target_path = args.target
    if not os.path.exists(target_path):
        target_path = os.path.join(BRIEFS_DIR, f"{args.target}.brief.yaml")

    if not os.path.exists(target_path):
        print(f"[ERROR] Target brief not found: {target_path}")
        sys.exit(1)

    result = resolve_for_brief(target_path)
    print(f"=== Source & Knowledge Resolver Result for {result['content_id']} ===")
    print("\n[Resolved Knowledge Packs]:")
    for kp in result["resolved_knowledge_packs"]:
        print(f"  + {kp}")
    if result["missing_knowledge_packs"]:
        print("\n[Missing/Unbuilt Knowledge Packs]:")
        for mkp in result["missing_knowledge_packs"]:
            print(f"  ! {mkp} (needs creation under 03_sources/knowledge/)")

    print("\n[Resolved Sources]:")
    for s in result["resolved_sources"]:
        print(f"  * {s}")

    if args.update_brief:
        with open(target_path, "r", encoding="utf-8") as f:
            brief_data = yaml.safe_load(f) or {}
        brief_data["knowledge_packs"] = result["resolved_knowledge_packs"]
        brief_data["required_sources"] = result["resolved_sources"]
        with open(target_path, "w", encoding="utf-8") as f:
            yaml.dump(brief_data, f, allow_unicode=True, sort_keys=False)
        print(f"\n[UPDATED] Injected knowledge_packs and required_sources into {os.path.basename(target_path)}")
