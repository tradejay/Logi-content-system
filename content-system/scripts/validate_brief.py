#!/usr/bin/env python3
"""
validate_brief.py (5-A Contract & Integrity)
Content Brief YAML 파일이 00_system/schema/content-brief.schema.yaml 및
프로젝트 계약 규칙을 완벽히 준수하는지 엄격하게 검증합니다.
"""
import os
import sys
import re
import yaml
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_FILE = os.path.join(BASE_DIR, "03_sources", "INDEX.yaml")

ALLOWED_STATUSES = {
    "NEW", "KEYWORD_RESEARCH", "PLANNING", "RESEARCH_REQUIRED", "RESEARCHING", "KNOWLEDGE_REVIEW",
    "READY_FOR_WRITING", "WRITING", "READY_FOR_QA", "REVISION_REQUIRED", "READY_TO_PUBLISH",
    "PUBLISHED", "ARCHIVED", "NEEDS_EVIDENCE", "BLOCKED", "CANCELLED", "DUPLICATE"
}

ALLOWED_CTA_BY_FUNNEL = {
    "discovery": {"soft"},
    "evaluation": {"soft", "medium"},
    "decision": {"medium", "hard"}
}

def get_registered_source_ids():
    if not os.path.exists(INDEX_FILE):
        return set()
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    raw = data.get("sources", [])
    if isinstance(raw, dict):
        return set(raw.keys())
    elif isinstance(raw, list):
        return {s["id"] for s in raw if isinstance(s, dict) and "id" in s}
    return set()

def validate_brief_file(filepath):
    errors = []
    warnings = []

    if not os.path.exists(filepath):
        return False, [f"File not found: {filepath}"], []

    filename = os.path.basename(filepath)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            brief = yaml.safe_load(f)
    except Exception as e:
        return False, [f"YAML parsing error: {e}"], []

    if not isinstance(brief, dict):
        return False, ["Brief root must be a YAML dictionary mapping"], []

    # 1. Required fields check
    required_fields = [
        "content_id", "batch_id", "status", "created_at", "topic",
        "canonical_topic", "one_line_purpose", "funnel_stage", "audience",
        "search", "intent", "content_type_mix", "title_candidates",
        "questions", "flow", "required_sources", "product_bridge", "cta"
    ]
    for rf in required_fields:
        if rf not in brief or brief[rf] is None:
            errors.append(f"Missing required field: '{rf}'")

    # 2. Content ID & Filename Consistency
    cid = str(brief.get("content_id", ""))
    if not re.match(r"^CNT-\d{4}W\d{2}-\d{3}$", cid):
        errors.append(f"Invalid content_id format: '{cid}' (expected ^CNT-YYYYWww-NNN$)")
    else:
        # Check if filename starts with content_id
        if not filename.startswith(cid):
            errors.append(f"Content ID '{cid}' does NOT match filename '{filename}'")

    # 3. Batch ID regex
    bid = str(brief.get("batch_id", ""))
    if not re.match(r"^BATCH-\d{4}W\d{2}$", bid):
        errors.append(f"Invalid batch_id format: '{bid}' (expected ^BATCH-YYYYWww$)")

    # 4. Status check
    st = brief.get("status", "")
    if st not in ALLOWED_STATUSES:
        errors.append(f"Invalid status: '{st}'. Must be one of {sorted(ALLOWED_STATUSES)}")

    # 5. Non-empty essential string fields
    canonical_topic = str(brief.get("canonical_topic", "")).strip()
    if not canonical_topic:
        errors.append("canonical_topic cannot be empty")

    purpose = str(brief.get("one_line_purpose", "")).strip()
    if not purpose:
        errors.append("one_line_purpose cannot be empty")

    search_block = brief.get("search", {})
    if isinstance(search_block, dict):
        primary_kw = str(search_block.get("primary_keyword", "")).strip()
        if not primary_kw:
            errors.append("search.primary_keyword cannot be empty")
    else:
        errors.append("search block must be a dict")

    # 6. Content type mix sum == 100
    mix = brief.get("content_type_mix", {})
    if isinstance(mix, dict):
        required_mix_keys = ["problem", "mechanism", "howto", "comparison", "review"]
        for mk in required_mix_keys:
            if mk not in mix:
                errors.append(f"content_type_mix missing component: '{mk}'")
        total_pct = sum(v for v in mix.values() if isinstance(v, (int, float)))
        if total_pct != 100:
            errors.append(f"content_type_mix total sum must be exactly 100%, got {total_pct}%")
    else:
        errors.append("content_type_mix must be an object/dict")

    # 7. Minimum items count
    titles = brief.get("title_candidates", [])
    if not isinstance(titles, list) or len(titles) < 3:
        errors.append(f"title_candidates must have at least 3 items, got {len(titles) if isinstance(titles, list) else 0}")

    questions = brief.get("questions", [])
    if not isinstance(questions, list) or len(questions) < 3:
        errors.append(f"questions must have at least 3 items, got {len(questions) if isinstance(questions, list) else 0}")

    flow = brief.get("flow", [])
    if not isinstance(flow, list) or len(flow) < 5:
        errors.append(f"flow must have at least 5 stages, got {len(flow) if isinstance(flow, list) else 0}")

    # 8. Funnel Stage and CTA Compatibility Check
    funnel = brief.get("funnel_stage")
    cta = brief.get("cta", {})
    if funnel in ALLOWED_CTA_BY_FUNNEL and isinstance(cta, dict):
        cta_level = cta.get("level")
        allowed_cta = ALLOWED_CTA_BY_FUNNEL[funnel]
        if cta_level not in allowed_cta:
            errors.append(f"Incompatible CTA level '{cta_level}' for funnel stage '{funnel}'. Allowed: {sorted(allowed_cta)}")

    # 9. Required Sources in INDEX.yaml
    valid_sources = get_registered_source_ids()
    req_sources = brief.get("required_sources", [])
    if not req_sources:
        errors.append("required_sources cannot be empty")
    else:
        for sid in req_sources:
            if not sid.startswith("SRC-"):
                errors.append(f"Invalid source ID format: '{sid}' (must start with 'SRC-')")
            elif sid not in valid_sources:
                errors.append(f"Source ID '{sid}' not found in 03_sources/INDEX.yaml")

    # 10. v1.1 Section Plan & Knowledge Pack Check (Optional for v1.0, validated if present)
    VALID_MODULE_TYPES = {
        "hook", "quick_answer", "problem", "diagnosis", "terminology", "concept",
        "mechanism", "feature", "compatibility", "operating_conditions", "how_to", "howto",
        "platform", "platform_integration", "comparison", "field_test", "limitations", "limitation",
        "troubleshooting", "product_implementation", "product_bridge", "faq", "cta"
    }

    if "sections" in brief:
        sections = brief["sections"]
        if not isinstance(sections, list) or len(sections) == 0:
            errors.append("'sections' must be a non-empty list of section objects")
        else:
            for s_idx, sec in enumerate(sections):
                if not isinstance(sec, dict):
                    errors.append(f"sections[{s_idx}] must be a dict")
                    continue
                s_id = sec.get("id")
                s_type = str(sec.get("type", "")).lower()
                s_obj = sec.get("objective")
                if not s_id or not str(s_id).startswith("SEC-"):
                    errors.append(f"sections[{s_idx}] invalid id '{s_id}' (must start with 'SEC-')")
                if not s_obj:
                    errors.append(f"sections[{s_idx}] missing 'objective'")
                if s_type not in VALID_MODULE_TYPES:
                    errors.append(f"sections[{s_idx}] invalid module type '{s_type}'. Allowed: {sorted(VALID_MODULE_TYPES)}")

    if "knowledge_packs" in brief:
        k_packs = brief["knowledge_packs"]
        if not isinstance(k_packs, list):
            errors.append("'knowledge_packs' must be a list of KNW- IDs")
        else:
            knw_root = os.path.join(BASE_DIR, "03_sources", "knowledge")
            for kid in k_packs:
                if not str(kid).startswith("KNW-"):
                    errors.append(f"Invalid knowledge_pack ID '{kid}' (must start with 'KNW-')")
                else:
                    found = False
                    for root, _, files in os.walk(knw_root):
                        if f"{kid}.yaml" in files or f"{kid}.yml" in files:
                            found = True
                            break
                    if not found:
                        errors.append(f"Referenced knowledge_pack '{kid}' not found under 03_sources/knowledge/")

    is_valid = len(errors) == 0
    return is_valid, errors, warnings

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Validate Content Brief YAML against schema and contracts")
    parser.add_argument("path_or_id", help="Path to brief file or content_id (e.g. CNT-2026W39-001)")
    args = parser.parse_args()

    target = args.path_or_id
    if not target.endswith(".yaml") and not target.endswith(".yml"):
        target = os.path.join(BASE_DIR, "01_keyword_ai", "briefs", f"{target}.brief.yaml")

    valid, errs, warns = validate_brief_file(target)
    if valid:
        print(f"[PASS] Brief '{os.path.basename(target)}' passed all schema and contract rules!")
        sys.exit(0)
    else:
        print(f"[FAIL] Brief '{os.path.basename(target)}' failed validation with {len(errs)} error(s):")
        for e in errs:
            print(f"  - ERROR: {e}")
        sys.exit(1)
