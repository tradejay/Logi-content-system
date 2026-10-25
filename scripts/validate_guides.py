"""CLI tool to validate guides, rules, registries, contracts, dependencies, and file integrity."""
import argparse
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from services.guide_repository import GuideRepository, GuideRepositoryError


def main():
    parser = argparse.ArgumentParser(description="Validate guide registries, contracts, and dependencies.")
    parser.add_argument("--root", default=str(ROOT), help="Project workspace root directory")
    args = parser.parse_args()

    repo = GuideRepository(workspace_root=args.root)
    print(f"[*] Validating guides and rules at: {repo.authoring_dir}")

    try:
        res = repo.validate_all()
        print(f"✅ All guides and rules are VALID!")
        print(f" • Rules checked: {res['rules_count']}")
        print(f" • Guides checked: {res['guides_count']}")
        print(f" • Prompts checked: {res['prompts_count']}")
        return 0
    except GuideRepositoryError as e:
        print(f"❌ Guide Validation FAILED: {type(e).__name__} - {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Unexpected Error: {type(e).__name__} - {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
