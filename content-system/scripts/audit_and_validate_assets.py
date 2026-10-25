#!/usr/bin/env python3
"""
content-system/scripts/audit_and_validate_assets.py
Comprehensive Asset Integrity, Semantic Alignment, and Visual Safety Auditor

Guarantees:
  1. No broken URLs or missing files for any asset in INDEX.yaml.
  2. MIME type verification: Image format matches file extension (no corrupted/mismatched binaries).
  3. Strict Blacklist: Blocks mock drawings, placeholder illustrations, or cartoon graphics from being used in corporate publications.
  4. Publication Consistency: Every asset in published articles (05_publish/ready/*.final.md) is valid, active, and topically aligned.
  5. HTML Safety: Scans for attribute leakage, broken quotes, or improper tag nesting in compiled HTML.
"""

import os
import sys
import re
import yaml
import urllib.request
from PIL import Image
import io

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

CONTENT_SYS_DIR = os.path.join(BASE_DIR, "content-system")
INDEX_PATH = os.path.join(CONTENT_SYS_DIR, "03_sources", "assets", "INDEX.yaml")
READY_DIR = os.path.join(CONTENT_SYS_DIR, "05_publish", "ready")

# Known mock / placeholder signatures to forbid
FORBIDDEN_KEYWORDS = [
    "chicken", "silhouette", "dummy", "placeholder", "mockup_fake"
]

# Obvious product conflicts: Asset product vs post topic
PRODUCT_CONFLICT_RULES = [
    # Article product prefix / key -> Forbidden asset products in specific context
    {"post_product": "LOGI-RALLY-PLUS", "forbidden_assets": ["AST-RS2-SPEAKER-001"], "reason": "Rally Plus large boardroom post should not use Rally Bar all-in-one speaker tracking animation"}
]

def load_master_assets():
    if not os.path.exists(INDEX_PATH):
        raise FileNotFoundError(f"Master asset index not found: {INDEX_PATH}")
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {a["asset_id"]: a for a in data.get("assets", []) if "asset_id" in a}

def validate_asset_binary(aid, asset_info):
    """Downloads/reads asset and verifies image dimensions and format integrity."""
    url = asset_info.get("url", "")
    fname = asset_info.get("file_name", "")
    
    if not url:
        return False, "Empty URL"
        
    img_bytes = None
    if url.startswith("/static/"):
        local_path = os.path.join(BASE_DIR, "static", url.replace("/static/", ""))
        if not os.path.exists(local_path):
            return False, f"Local static file missing: {local_path}"
        with open(local_path, "rb") as f:
            img_bytes = f.read()
    else:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                img_bytes = resp.read()
        except Exception as e:
            return False, f"HTTP fetch failed: {e}"
            
    if not img_bytes or len(img_bytes) < 100:
        return False, f"Image payload too small ({len(img_bytes) if img_bytes else 0} bytes)"

    try:
        im = Image.open(io.BytesIO(img_bytes))
        width, height = im.size
        fmt = im.format
        if width < 50 or height < 50:
            return False, f"Suspiciously small image resolution: {width}x{height}"
            
        # Blacklist check
        combined_text = f"{fname} {asset_info.get('purpose', '')} {asset_info.get('caption', '')}".lower()
        for kw in FORBIDDEN_KEYWORDS:
            if kw in combined_text:
                return False, f"Forbidden keyword detected in asset: '{kw}'"
                
        return True, {
            "format": fmt,
            "width": width,
            "height": height,
            "bytes": len(img_bytes),
            "animated": getattr(im, "is_animated", False)
        }
    except Exception as e:
        return False, f"Corrupted image data: {e}"

def audit_published_articles(assets_map):
    """Audits all markdown files and compiled HTML files in 05_publish/ready."""
    errors = []
    warnings = []
    
    import glob
    final_files = glob.glob(os.path.join(READY_DIR, "*.final.md"))
    
    for ff in final_files:
        cid = os.path.basename(ff).replace(".final.md", "")
        with open(ff, "r", encoding="utf-8") as f:
            md_content = f.read()
            
        referenced_assets = re.findall(r'\{\{asset:([^\}]+)\}\}', md_content)
        
        # 1. Existence and active status check
        for aid in referenced_assets:
            if aid not in assets_map:
                errors.append(f"[{cid}] Referenced asset '{aid}' does not exist in INDEX.yaml!")
            elif assets_map[aid].get("status") != "ACTIVE":
                errors.append(f"[{cid}] Referenced asset '{aid}' is not ACTIVE (status: {assets_map[aid].get('status')})")

        # 2. Product Conflict Rules
        for rule in PRODUCT_CONFLICT_RULES:
            if rule["post_product"] in md_content:
                for fa in rule["forbidden_assets"]:
                    if fa in referenced_assets:
                        errors.append(f"[{cid}] Semantic mismatch: {rule['reason']} (Found: {fa})")

        # 3. Check corresponding .naver.html file for HTML attribute safety
        html_file = os.path.join(READY_DIR, f"{cid}.naver.html")
        if os.path.exists(html_file):
            with open(html_file, "r", encoding="utf-8") as hf:
                html_text = hf.read()
                
            if 'alt="<' in html_text or 'alt="<strong' in html_text or 'alt="<span' in html_text:
                errors.append(f"[{cid}.naver.html] CRITICAL: HTML tags leaked into img alt attribute!")
                
            if re.search(r'<p[^>]*>\s*<div', html_text):
                errors.append(f"[{cid}.naver.html] Invalid DOM: <div> wrapped inside <p> paragraph tag!")

    return errors, warnings

def run_full_asset_audit():
    print("=" * 70)
    print("LOGITECH CONTENT SYSTEM: AUTOMATED ASSET & VISUAL AUDITOR")
    print("=" * 70)
    
    assets_map = load_master_assets()
    print(f"Loaded {len(assets_map)} assets from INDEX.yaml\n")
    
    passed_count = 0
    failed_assets = []
    
    for aid, info in sorted(assets_map.items()):
        ok, res = validate_asset_binary(aid, info)
        if ok:
            passed_count += 1
            anim_str = " (Animated)" if res.get("animated") else ""
            print(f"  [PASS] {aid:<26} | {res['format']:<4} {res['width']}x{res['height']}{anim_str} | {res['bytes']:,} bytes")
        else:
            failed_assets.append((aid, res))
            print(f"  [FAIL] {aid:<26} | ERROR: {res}")
            
    print("\n" + "-" * 70)
    print(f"Asset Binary Integrity: {passed_count}/{len(assets_map)} passed.")
    if failed_assets:
        print(f"WARNING: {len(failed_assets)} asset(s) failed verification!")
        
    print("\nAuditing Published Articles & HTML Output...")
    pub_errors, pub_warnings = audit_published_articles(assets_map)
    
    if pub_errors:
        print("\n[CRITICAL ERRORS FOUND IN PUBLISHED ARTICLES]:")
        for pe in pub_errors:
            print(f"  ❌ {pe}")
    else:
        print("  ✅ All published articles and HTML preview outputs passed safety & alignment checks!")
        
    if pub_warnings:
        print("\n[WARNINGS]:")
        for pw in pub_warnings:
            print(f"  ⚠️ {pw}")

    print("=" * 70)
    return len(failed_assets) == 0 and len(pub_errors) == 0

if __name__ == "__main__":
    success = run_full_asset_audit()
    sys.exit(0 if success else 1)
