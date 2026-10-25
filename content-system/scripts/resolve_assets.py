#!/usr/bin/env python3
"""
content-system/scripts/resolve_assets.py
Asset Resolver & Auto-Binding Engine
Resolves required assets from 03_sources/assets/INDEX.yaml for a given Content Brief,
preventing placeholder generation when matching official media exists.
"""

import os
import sys
import yaml
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_INDEX_FILE = os.path.join(BASE_DIR, "03_sources", "assets", "INDEX.yaml")
BRIEFS_DIR = os.path.join(BASE_DIR, "01_keyword_ai", "briefs")
WORKING_DIR = os.path.join(BASE_DIR, "02_writer_ai", "working")

def load_master_assets():
    if not os.path.exists(ASSETS_INDEX_FILE):
        return []
    with open(ASSETS_INDEX_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("assets", [])

def resolve_assets_for_content(content_id):
    brief_file = os.path.join(BRIEFS_DIR, f"{content_id}.brief.yaml")
    if not os.path.exists(brief_file):
        raise FileNotFoundError(f"Brief file not found: {brief_file}")

    with open(brief_file, "r", encoding="utf-8") as f:
        brief = yaml.safe_load(f) or {}

    master_assets = load_master_assets()
    target_working_dir = os.path.join(WORKING_DIR, content_id)
    assets_out_dir = os.path.join(target_working_dir, "assets")
    os.makedirs(assets_out_dir, exist_ok=True)

    # Gather required concepts from brief
    primary_kw = brief.get("search", {}).get("primary_keyword", "")
    target_product = (
        brief.get("product", "") 
        or brief.get("target_device", "") 
        or brief.get("product_bridge", {}).get("product", "")
    )
    sections = brief.get("sections", [])
    asset_plans = brief.get("asset_plan", [])

    # Filter applicable assets from master
    available_assets = []
    bindings = []
    unresolved_requirements = []

    # Map sections to assets
    for s in sections:
        sid = s.get("id")
        stype = s.get("type", "").lower()
        sobj = s.get("objective", "")
        must_cover = [m.lower() for m in s.get("must_cover", [])]
        sec_text = (sobj + " " + " ".join(must_cover) + " " + " ".join(s.get("questions", []))).lower()

        for asset in master_assets:
            aid = asset.get("asset_id", "")
            feat = asset.get("feature", "").lower()
            view_mode = asset.get("view_mode", "").lower()
            prod = asset.get("product", "").lower()

            matched = False

            # SEC-01 / SEC-02: Speaker Tracking Visual Hook
            if sid in ["SEC-01", "SEC-02"]:
                if aid == "AST-RS2-SPEAKER-001":
                    matched = True

            # SEC-03: RightSight 2 Modes & Comparison
            elif sid == "SEC-03":
                if aid in ["AST-RS2-COMPARE-001", "AST-RS2-GROUP-001", "AST-RS2-SPEAKER-001", "AST-RS2-GRID-001"]:
                    matched = True

            # SEC-04: Hardware Sensor Fusion / AI Viewfinder
            elif sid == "SEC-04":
                if aid == "AST-RS2-HARDWARE-001":
                    matched = True

            # Product Hardware Guide (Dynamic Product Matching)
            elif aid.startswith("AST-PROD-"):
                tp_norm = (target_product or "").lower().replace(" ", "").replace("-", "").replace("logitech", "")
                p_norm = prod.lower().replace(" ", "").replace("-", "").replace("logi", "")
                if "meetup" in tp_norm and "meetup" in p_norm:
                    matched = True
                elif ("mic" in tp_norm or "pod" in tp_norm) and "mic" in p_norm:
                    matched = True
                elif "tap" in tp_norm and "tap" in p_norm:
                    matched = True
                elif "plus" in tp_norm and "plus" in p_norm:
                    matched = True
                elif ("rally" in tp_norm or "bar" in tp_norm) and "rallybar" in p_norm:
                    matched = True

            # General semantic fallback
            elif any(k in sec_text for k in ["speaker view", "화자 추적", "스마트 전환"]) and "speaker" in feat:
                matched = True
            elif any(k in sec_text for k in ["group view", "그룹 뷰"]) and "group" in feat:
                matched = True
            elif any(k in sec_text for k in ["grid view", "그리드 뷰"]) and "grid" in feat:
                matched = True

            if matched:
                if asset not in available_assets:
                    available_assets.append(asset)
                binding_entry = {
                    "section_id": sid,
                    "asset_id": aid,
                    "asset_type": asset["asset_type"],
                    "placement": "after_lead",
                    "caption": asset.get("caption"),
                    "customer_message": asset.get("customer_message")
                }
                if binding_entry not in bindings:
                    bindings.append(binding_entry)

    # Check unresolved requirements
    bound_sections = {b["section_id"] for b in bindings}
    for ap in asset_plans:
        sec = ap.get("section")
        need_id = ap.get("asset_need_id")
        desc = ap.get("purpose", "")
        if sec not in bound_sections:
            unresolved_requirements.append({
                "need_id": need_id,
                "section": sec,
                "description": desc
            })

    # Save asset-index.yaml into working/assets/
    asset_index_path = os.path.join(assets_out_dir, "asset-index.yaml")
    with open(asset_index_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"available_assets": available_assets}, f, allow_unicode=True, sort_keys=False)

    # Save asset-bindings.yaml into working/
    bindings_path = os.path.join(target_working_dir, "asset-bindings.yaml")
    with open(bindings_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({
            "content_id": content_id,
            "bindings": bindings,
            "unresolved_requirements": unresolved_requirements
        }, f, allow_unicode=True, sort_keys=False)

    return available_assets, bindings, unresolved_requirements

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Resolve assets for a given content ID")
    parser.add_argument("content_id", help="Content ID (e.g. CNT-2026W39-001)")
    args = parser.parse_args()

    assets, binds, unres = resolve_assets_for_content(args.content_id)
    print(f"[OK] Assets resolved for {args.content_id}:")
    print(f"  -> Available assets: {len(assets)}")
    for a in assets:
        print(f"     - [{a['asset_id']}] ({a['asset_type']}) {a['feature']} : {a['file_name']}")
    print(f"  -> Section bindings: {len(binds)}")
    for b in binds:
        print(f"     - {b['section_id']} => {b['asset_id']}")
    print(f"  -> Unresolved placeholders: {len(unres)}")
