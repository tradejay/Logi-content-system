"""Generate structured review package (base commit, diff, changed files, test summary).

Adheres to ROOT-GIT-RUFF-20261023:
- Never includes secrets, tokens, or credential files
- Provides git diff and test verification summary
- Emits clean JSON package for review AI consumption
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.sqlite3', '.db', '.pdf', '.exe', '.dll', '.zip'}
SENSITIVE_PATTERNS = {'token', 'csrf', 'key', 'secret', 'password', 'credential', '.env'}


def run_git(args):
    res = subprocess.run(['git'] + args, cwd=str(ROOT), capture_output=True, text=True, encoding='utf-8')
    if res.returncode != 0:
        return None
    return res.stdout.strip()


def get_diff(base_ref=None):
    if base_ref:
        files_text = run_git(['diff', '--name-only', f'{base_ref}..HEAD'])
    else:
        files_text = run_git(['diff', '--name-only', 'HEAD'])

    files = [f.strip() for f in (files_text or '').splitlines() if f.strip()]
    safe_files = []
    skipped = []

    for f in files:
        f_lower = f.lower()
        if any(p in f_lower for p in SENSITIVE_PATTERNS):
            skipped.append({'file': f, 'reason': 'sensitive_keyword'})
            continue
        if any(f_lower.endswith(ext) for ext in EXCLUDE_EXTS):
            skipped.append({'file': f, 'reason': 'binary_or_asset'})
            continue
        safe_files.append(f)

    # Only collect eligible file patches; omitted paths must not leak in the diff.
    diff_args = ['diff', f'{base_ref}..HEAD'] if base_ref else ['diff', 'HEAD']
    diff_text = run_git(diff_args + ['--', *safe_files]) if safe_files else ''
    # Sanitize diff text
    lines = (diff_text or '').splitlines()
    safe_diff_lines = []
    for line in lines:
        if any(p in line.lower() for p in ['token', 'csrf', 'secret', 'password', 'bearer']):
            safe_diff_lines.append("[REDACTED SENSITIVE LINE]")
        else:
            safe_diff_lines.append(line)

    return '\n'.join(safe_diff_lines), safe_files, skipped


def get_test_status():
    summary_file = ROOT / 'static/reports/insights-allure-report/summary.json'
    if summary_file.exists():
        try:
            return json.loads(summary_file.read_text(encoding='utf-8')).get('stats', {})
        except Exception:
            pass
    return {'status': 'not_available'}


def main():
    parser = argparse.ArgumentParser(description="Generate Review Diff Package")
    parser.add_argument('--base', help="Base commit hash or reference")
    parser.add_argument('--out', help="Output JSON file path")
    args = parser.parse_args()

    head_commit = run_git(['rev-parse', 'HEAD'])
    base_commit = args.base or run_git(['rev-parse', 'HEAD~1']) or head_commit

    diff_ref = args.base or (base_commit if base_commit != head_commit else None)
    diff_content, changed_files, skipped = get_diff(diff_ref)
    test_summary = get_test_status()

    package = {
        'schema_version': 'review-diff-package-v1',
        'head_commit': head_commit,
        'base_commit': base_commit,
        'changed_files': changed_files,
        'skipped_files': skipped,
        'test_stats': test_summary,
        'diff': diff_content
    }

    output_json = json.dumps(package, ensure_ascii=False, indent=2)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_json, encoding='utf-8')
        print(f"Review package written to {out_path}")
    else:
        print(output_json)


if __name__ == '__main__':
    main()
