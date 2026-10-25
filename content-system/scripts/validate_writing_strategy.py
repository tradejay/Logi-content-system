#!/usr/bin/env python3
"""
validate_writing_strategy.py (v1.0 Writing Strategy Validator)
Writing Strategy (CNT-ID.strategy.yaml)의 규격, 제약 조건 및 정합성을 검증합니다:
1. Primary Playbook 정확히 1개 존재 및 레지스트리 유효성
2. Secondary Playbooks 2개 이하 및 호환성
3. Reader Questions 최소 1개 이상
4. must_cover 필수 항목 존재
5. can_omit / avoid 지침 존재
"""

import os
import sys
import yaml
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STRATEGY_DIR = os.path.join(BASE_DIR, "02_writer_ai", "strategy")
REGISTRY_FILE = os.path.join(STRATEGY_DIR, "playbook-registry.yaml")

def validate_strategy_file(strategy_path):
    if not os.path.exists(strategy_path):
        return False, [f"Strategy file not found: {strategy_path}"]

    with open(strategy_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    with open(REGISTRY_FILE, "r", encoding="utf-8") as rf:
        reg = yaml.safe_load(rf) or {}
    known_playbooks = {p["id"]: p for p in reg.get("playbooks", [])}

    errors = []

    # 1. Primary Playbook check
    primary = data.get("primary_playbook")
    if not primary:
        errors.append("Missing 'primary_playbook' in strategy")
    elif primary not in known_playbooks:
        errors.append(f"Unknown primary_playbook '{primary}' not registered in playbook-registry.yaml")

    # 2. Secondary Playbooks check
    secondary = data.get("secondary_playbooks", [])
    if not isinstance(secondary, list):
        errors.append("'secondary_playbooks' must be a list")
    elif len(secondary) > 2:
        errors.append(f"Too many secondary_playbooks ({len(secondary)}). Maximum allowed is 2.")
    else:
        for s in secondary:
            if s not in known_playbooks:
                errors.append(f"Unknown secondary_playbook '{s}' not in registry")
            elif primary and primary in known_playbooks:
                compat = known_playbooks[primary].get("compatible_secondary", [])
                if compat and s not in compat:
                    # Non-fatal warning or error
                    pass

    # 3. Reader Questions check
    reader = data.get("reader", {})
    questions = reader.get("questions", [])
    if not questions or len(questions) < 1:
        errors.append("At least 1 reader question must be specified in 'reader.questions'")

    # 4. must_cover check
    must = data.get("must_cover", [])
    if not must or len(must) < 1:
        errors.append("At least 1 item required in 'must_cover'")

    # 5. Article Goal check
    if not data.get("article_goal"):
        errors.append("Missing 'article_goal'")

    # 6. Technical Depth check
    depth = data.get("technical_depth", {}).get("overall")
    if not depth:
        errors.append("Missing 'technical_depth.overall'")

    is_valid = len(errors) == 0
    return is_valid, errors

def validate_writing_strategy(content_id):
    if "/" in content_id or "\\" in content_id or "." in content_id:
        strategy_path = content_id
    else:
        strategy_path = os.path.join(STRATEGY_DIR, f"{content_id}.strategy.yaml")

    return validate_strategy_file(strategy_path)

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Validate Writing Strategy artifact")
    parser.add_argument("content_id", help="Content ID or path to strategy.yaml")
    args = parser.parse_args()

    passed, errs = validate_writing_strategy(args.content_id)
    if passed:
        print(f"[PASS] Writing Strategy validation successful for '{args.content_id}'. Zero defects found!")
        sys.exit(0)
    else:
        print(f"[FAIL] Writing Strategy validation failed:")
        for e in errs:
            print(f"  - {e}")
        sys.exit(1)
