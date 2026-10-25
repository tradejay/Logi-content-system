#!/usr/bin/env python3
"""
scripts/validate_knowledge_pack.py
Validates Knowledge Pack YAML files against schema and required normalized sections.
Checks:
- knowledge_id (must match filename)
- status (VERIFIED, DRAFT, DEPRECATED)
- last_verified (YYYY-MM-DD)
- knowledge_type (feature, product, platform, concept)
- definition / overview / terminology
"""

import os
import sys
import yaml
import argparse
import re

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ALLOWED_TYPES = {"feature", "product", "platform", "concept"}
ALLOWED_STATUSES = {"VERIFIED", "DRAFT", "DEPRECATED"}

def validate_knowledge_pack(filepath):
    errors = []
    if not os.path.exists(filepath):
        return False, [f"File not found: {filepath}"]

    filename = os.path.basename(filepath)
    with open(filepath, "r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f) or {}
        except Exception as e:
            return False, [f"YAML syntax error: {e}"]

    kid = data.get("knowledge_id", "")
    if not kid:
        errors.append("Missing required 'knowledge_id'")
    else:
        if not filename.startswith(kid):
            errors.append(f"knowledge_id '{kid}' does not match filename '{filename}'")

    ktype = data.get("knowledge_type", "")
    if ktype not in ALLOWED_TYPES:
        errors.append(f"Invalid knowledge_type '{ktype}'. Must be one of {sorted(ALLOWED_TYPES)}")

    st = data.get("status", "")
    if st not in ALLOWED_STATUSES:
        errors.append(f"Invalid status '{st}'. Must be one of {sorted(ALLOWED_STATUSES)}")

    lv = str(data.get("last_verified", ""))
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", lv):
        errors.append(f"Invalid last_verified date format: '{lv}' (expected YYYY-MM-DD)")

    if ktype == "feature":
        if "definition" not in data:
            errors.append("Feature knowledge must contain 'definition'")
        if "compatibility" not in data:
            errors.append("Feature knowledge must contain 'compatibility'")
        if "mechanism" not in data:
            errors.append("Feature knowledge must contain 'mechanism'")
        if "operating_conditions" not in data:
            errors.append("Feature knowledge must contain 'operating_conditions'")
        if "limitations" not in data:
            errors.append("Feature knowledge must contain 'limitations'")

    elif ktype == "product":
        if "overview" not in data:
            errors.append("Product knowledge must contain 'overview'")
        if "ports_and_connectivity" not in data:
            errors.append("Product knowledge must contain 'ports_and_connectivity'")

    elif ktype == "platform":
        if "overview" not in data:
            errors.append("Platform knowledge must contain 'overview'")
        if "camera_control_modes" not in data:
            errors.append("Platform knowledge must contain 'camera_control_modes'")

    # Validate atomic Facts if present
    if "facts" in data:
        facts = data.get("facts", [])
        if not isinstance(facts, list):
            errors.append("'facts' section must be a list of Fact objects")
        else:
            for idx, fact in enumerate(facts):
                fid = fact.get("id") or fact.get("fact_id")
                if not fid:
                    errors.append(f"Fact at index {idx} is missing 'id' or 'fact_id'")
                if "canonical_property" not in fact and "property" not in fact:
                    errors.append(f"Fact {fid or idx} is missing 'canonical_property'")
                if "value" not in fact:
                    errors.append(f"Fact {fid or idx} is missing 'value'")

    # Validate Derived Knowledge if present
    if "derived_knowledge" in data:
        dk_list = data.get("derived_knowledge", [])
        if not isinstance(dk_list, list):
            errors.append("'derived_knowledge' section must be a list of objects")
        else:
            for idx, dk in enumerate(dk_list):
                dk_id = dk.get("id")
                if not dk_id:
                    errors.append(f"Derived knowledge at index {idx} missing 'id'")
                if "statement" not in dk:
                    errors.append(f"Derived knowledge {dk_id or idx} missing 'statement'")
                if "derived_from" not in dk or not isinstance(dk.get("derived_from"), list):
                    errors.append(f"Derived knowledge {dk_id or idx} missing 'derived_from' list")

    return len(errors) == 0, errors

def main():
    parser = argparse.ArgumentParser(description="Validate Knowledge Pack YAML")
    parser.add_argument("path", help="Path to Knowledge Pack file")
    args = parser.parse_args()

    ok, errors = validate_knowledge_pack(args.path)
    if ok:
        print(f"[PASS] Knowledge Pack '{os.path.basename(args.path)}' is valid!")
        sys.exit(0)
    else:
        print(f"[FAIL] Knowledge Pack '{os.path.basename(args.path)}' failed with {len(errors)} error(s):")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

if __name__ == "__main__":
    main()
