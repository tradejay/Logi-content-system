"""CLI tool to build, verify, activate, and rollback immutable guide releases."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from services.guide_repository import GuideRepository, GuideRepositoryError


def cmd_build(repo: GuideRepository, args):
    print(f"[*] Building guide release: {args.release_id or '(auto-generated)'}")
    manifest = repo.build_release(
        release_id=args.release_id,
        activate=args.activate,
        eval_report_ref=args.eval_report,
    )
    print(f"✅ Release successfully built: {manifest.release_id}")
    print(f" • Bundle SHA256: {manifest.bundle_sha256}")
    print(f" • Code Revision: {manifest.code_revision}")
    print(f" • Rules: {len(manifest.rules)}, Guides: {len(manifest.guides)}, Prompts: {len(manifest.prompts)}")
    if args.activate:
        print(f" • Status: ACTIVATED as current release.")
    return 0


def cmd_verify(repo: GuideRepository, args):
    target_id = args.release_id or repo.get_active_release_id()
    if not target_id:
        print("❌ No release specified and no active release found.", file=sys.stderr)
        return 1
    print(f"[*] Verifying release integrity: {target_id}")
    manifest = repo.verify_release(target_id)
    print(f"✅ Release {manifest.release_id} is 100% verified and intact.")
    print(f" • Bundle SHA256: {manifest.bundle_sha256}")
    return 0


def cmd_activate(repo: GuideRepository, args):
    print(f"[*] Activating release: {args.release_id}")
    repo.activate_release(args.release_id)
    print(f"✅ Release {args.release_id} is now ACTIVE.")
    return 0


def cmd_rollback(repo: GuideRepository, args):
    print(f"[*] Rolling back to release: {args.release_id}")
    repo.rollback(args.release_id)
    print(f"✅ Active release successfully rolled back to: {args.release_id}")
    return 0


def cmd_status(repo: GuideRepository, args):
    active_id = repo.get_active_release_id()
    print("=== Guide Releases Status ===")
    print(f"Active Release: {active_id or '(None)'}")
    if not repo.releases_dir.exists():
        print("Releases directory does not exist yet.")
        return 0

    releases = sorted([d.name for d in repo.releases_dir.iterdir() if d.is_dir()])
    print(f"Available Releases ({len(releases)}):")
    for r in releases:
        flag = " [ACTIVE]" if r == active_id else ""
        manifest_file = repo.releases_dir / r / "manifest.json"
        created = ""
        if manifest_file.exists():
            try:
                m = json.loads(manifest_file.read_text(encoding="utf-8-sig"))
                created = f" (created: {m.get('created_at', '')[:19]})"
            except Exception:
                pass
        print(f" - {r}{flag}{created}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Manage immutable guide policy releases.")
    parser.add_argument("--root", default=str(ROOT), help="Project workspace root directory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # build
    p_build = subparsers.add_parser("build", help="Build a new immutable guide release")
    p_build.add_argument("--release-id", default=None, help="Identifier for the release")
    p_build.add_argument("--activate", action="store_true", help="Activate immediately upon build")
    p_build.add_argument("--eval-report", default=None, help="Reference to evaluation report")
    p_build.set_defaults(func=cmd_build)

    # verify
    p_verify = subparsers.add_parser("verify", help="Verify release integrity and file hashes")
    p_verify.add_argument("release_id", nargs="?", default=None, help="Release ID to verify")
    p_verify.set_defaults(func=cmd_verify)

    # activate
    p_activate = subparsers.add_parser("activate", help="Activate a verified release")
    p_activate.add_argument("release_id", help="Release ID to activate")
    p_activate.set_defaults(func=cmd_activate)

    # rollback
    p_rollback = subparsers.add_parser("rollback", help="Rollback to a previously verified release")
    p_rollback.add_argument("release_id", help="Target release ID")
    p_rollback.set_defaults(func=cmd_rollback)

    # status
    p_status = subparsers.add_parser("status", help="Show active release and list available releases")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    repo = GuideRepository(workspace_root=args.root)

    try:
        return args.func(repo, args)
    except GuideRepositoryError as e:
        print(f"❌ Operation Failed: {type(e).__name__} - {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Unexpected Error: {type(e).__name__} - {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
