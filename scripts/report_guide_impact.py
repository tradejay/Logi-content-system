"""CLI tool to analyze and report the impact of guide/rule modifications across historical pipeline runs."""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from services.guide_repository import GuideRepository


def analyze_impact(
    workspace_root: Path,
    target_rule_or_guide_id: str,
) -> Dict[str, Any]:
    repo = GuideRepository(workspace_root)
    working_dir = workspace_root / "content-system" / "02_writer_ai" / "working"

    impacted_runs: List[Dict[str, Any]] = []

    if not working_dir.exists():
        return {"target": target_rule_or_guide_id, "impacted_runs": []}

    # Iterate over all content working directories
    for c_dir in sorted(working_dir.iterdir()):
        if not c_dir.is_dir() or not c_dir.name.startswith("CNT-"):
            continue
        cid = c_dir.name
        runs_dir = c_dir / "runs"
        if not runs_dir.exists():
            continue

        for r_dir in sorted(runs_dir.iterdir()):
            if not r_dir.is_dir():
                continue
            run_id = r_dir.name
            manifest_file = r_dir / "guide-manifest.json"
            req_file = r_dir / "requirements.json"
            run_result_file = r_dir / "run-result.json"

            used = False
            version_used = "unknown"
            applied_stages: Set[str] = set()

            # Check guide-manifest
            if manifest_file.is_file():
                try:
                    m = json.loads(manifest_file.read_text(encoding="utf-8"))
                    if target_rule_or_guide_id in m.get("rules", {}):
                        used = True
                        version_used = m["rules"][target_rule_or_guide_id].get("version", "unknown")
                    elif target_rule_or_guide_id in m.get("guides", {}):
                        used = True
                        version_used = m["guides"][target_rule_or_guide_id].get("version", "unknown")
                except Exception:
                    pass

            # Check requirements
            if not used and req_file.is_file():
                try:
                    req_data = json.loads(req_file.read_text(encoding="utf-8"))
                    reqs = req_data.get("requirements", {})
                    if target_rule_or_guide_id in reqs:
                        used = True
                except Exception:
                    pass

            # Check context-selection calls
            selection_dir = r_dir / "context-selection"
            if selection_dir.is_dir():
                for s_file in selection_dir.glob("*.json"):
                    try:
                        s_data = json.loads(s_file.read_text(encoding="utf-8"))
                        selected_rules = {r.get("id") for r in s_data.get("selected_rules", [])}
                        if target_rule_or_guide_id in selected_rules:
                            used = True
                            applied_stages.add(s_data.get("stage", s_file.stem))
                    except Exception:
                        pass

            if used:
                outcome = "UNKNOWN"
                approval = None
                if run_result_file.is_file():
                    try:
                        res_data = json.loads(run_result_file.read_text(encoding="utf-8"))
                        outcome = res_data.get("outcome", "UNKNOWN")
                        approval = res_data.get("approval")
                    except Exception:
                        pass

                impacted_runs.append({
                    "content_id": cid,
                    "run_id": run_id,
                    "version_used": version_used,
                    "applied_stages": sorted(applied_stages),
                    "outcome": outcome,
                    "approved": bool(approval),
                    "review_needed": True,
                })

    return {
        "target_id": target_rule_or_guide_id,
        "total_impacted_runs": len(impacted_runs),
        "impacted_runs": impacted_runs,
    }


def main():
    parser = argparse.ArgumentParser(description="Report impact of a rule or guide on past runs.")
    parser.add_argument("target_id", help="Rule ID or Guide ID to trace (e.g. RULE-NUMERIC-SCOPE)")
    parser.add_argument("--root", default=str(ROOT), help="Project root directory")
    args = parser.parse_args()

    report = analyze_impact(Path(args.root), args.target_id)
    print(f"=== Guide/Rule Impact Analysis: {args.target_id} ===")
    print(f"Total impacted runs found: {report['total_impacted_runs']}")
    if not report['impacted_runs']:
        print("No historical runs found referencing this policy ID.")
        return 0

    print("\nImpacted Content Runs (Review Candidates):")
    for r in report['impacted_runs']:
        appr_flag = " [APPROVED]" if r['approved'] else ""
        stages_str = ", ".join(r['applied_stages']) if r['applied_stages'] else "all"
        print(f" • {r['content_id']} (run: {r['run_id']}) - Outcome: {r['outcome']}{appr_flag} - Stages: [{stages_str}]")

    print("\n⚠️ Note: Approved contents are preserved and not automatically rewritten.")
    print("Use this list to schedule targeted governance reviews for updated policies.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
