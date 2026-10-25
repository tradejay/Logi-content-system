#!/usr/bin/env python3
"""
resolve_playbooks.py (v1.0 Playbook Context Sharding Engine)
Writing Strategy (strategy.yaml)를 읽어, 이번 콘텐츠에 배정된
Core 헌법과 Primary Playbook 1개 및 Secondary Playbook(0~2개)만을 선별하여
Writer 작업 폴더(working/{cid}/guides/)로 주입(Sharding)합니다.
"""

import os
import sys
import shutil
import yaml
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WRITER_DIR = os.path.join(BASE_DIR, "02_writer_ai")
CORE_DIR = os.path.join(WRITER_DIR, "core")
STRATEGY_DIR = os.path.join(WRITER_DIR, "strategy")
WORKING_DIR = os.path.join(WRITER_DIR, "working")
REGISTRY_FILE = os.path.join(STRATEGY_DIR, "playbook-registry.yaml")

def resolve_playbooks_for_content(content_id):
    strategy_file = os.path.join(STRATEGY_DIR, f"{content_id}.strategy.yaml")
    if not os.path.exists(strategy_file):
        # Fallback to working directory if strategy was placed there
        strategy_file = os.path.join(WORKING_DIR, content_id, "strategy.yaml")

    if not os.path.exists(strategy_file):
        raise FileNotFoundError(f"Strategy file not found for {content_id}: {strategy_file}")

    with open(strategy_file, "r", encoding="utf-8") as sf:
        strat = yaml.safe_load(sf) or {}

    with open(REGISTRY_FILE, "r", encoding="utf-8") as rf:
        reg = yaml.safe_load(rf) or {}
    playbook_map = {p["id"]: p for p in reg.get("playbooks", [])}

    target_guides_dir = os.path.join(WORKING_DIR, content_id, "guides")
    os.makedirs(target_guides_dir, exist_ok=True)

    copied_guides = []

    # 1. Copy Core Constitution files
    for core_f in ["WRITING_CORE.md", "STYLE_CORE.md", "SAFETY_CORE.md"]:
        src = os.path.join(CORE_DIR, core_f)
        if os.path.exists(src):
            dst = os.path.join(target_guides_dir, core_f)
            shutil.copy2(src, dst)
            copied_guides.append(core_f)

    # 2. Copy Primary Playbook
    primary_id = strat.get("primary_playbook")
    if primary_id and primary_id in playbook_map:
        p_rel = playbook_map[primary_id].get("path", "")
        p_abs = os.path.join(WRITER_DIR, p_rel)
        if os.path.exists(p_abs):
            dst = os.path.join(target_guides_dir, "primary.md")
            shutil.copy2(p_abs, dst)
            copied_guides.append(f"primary.md ({primary_id})")

    # 3. Copy Secondary Playbooks (up to 2)
    secondary_ids = strat.get("secondary_playbooks", [])
    for idx, sec_id in enumerate(secondary_ids[:2]):
        if sec_id in playbook_map:
            s_rel = playbook_map[sec_id].get("path", "")
            s_abs = os.path.join(WRITER_DIR, s_rel)
            if os.path.exists(s_abs):
                dst_name = f"secondary-0{idx+1}.md"
                dst = os.path.join(target_guides_dir, dst_name)
                shutil.copy2(s_abs, dst)
                copied_guides.append(f"{dst_name} ({sec_id})")

    # Copy strategy to working directory
    working_strat_dst = os.path.join(WORKING_DIR, content_id, "strategy.yaml")
    if os.path.abspath(strategy_file) != os.path.abspath(working_strat_dst):
        shutil.copy2(strategy_file, working_strat_dst)

    return target_guides_dir, copied_guides

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Resolve and inject Playbooks into working folder")
    parser.add_argument("content_id", help="Content ID (e.g. CNT-2026W39-001)")
    args = parser.parse_args()

    try:
        gdir, cfiles = resolve_playbooks_for_content(args.content_id)
        print(f"[OK] Playbooks resolved for '{args.content_id}':")
        print(f"  -> Target Directory: {gdir}")
        for cf in cfiles:
            print(f"     - {cf}")
    except Exception as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        sys.exit(1)
