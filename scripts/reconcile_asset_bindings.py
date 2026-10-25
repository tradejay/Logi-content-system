#!/usr/bin/env python3
"""
Reconcile inquiry banner bindings for target content IDs.
Preserves admin review status (pending_review), updates candidate to AST-COMPANY-OCEAN-001,
and documents audit trail.
"""
import json
from pathlib import Path
import sys

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TARGET_CIDS = [f'CNT-2026W39-00{i}' for i in range(1, 6)]
BANNER_NEED_IDS = {'oceantech-inquiry-opening', 'oceantech-inquiry-closing',
                   'AST-OCEANTECH-INQUIRY-BANNER', 'oceantech-inquiry-banner'}
COMPANY_BANNER_ID = 'AST-COMPANY-OCEAN-001'


def get_official_banner_asset(root: Path):
    import yaml
    idx_path = root / 'content-system' / '03_sources' / 'assets' / 'INDEX.yaml'
    if idx_path.exists():
        idx_data = yaml.safe_load(idx_path.read_text(encoding='utf-8'))
        for a in idx_data.get('assets', []):
            if a.get('asset_id') == COMPANY_BANNER_ID:
                return a
    return None


def reconcile_bindings(root: Path = PROJECT_ROOT, target_cids=None, dry_run=True):
    root = Path(root).resolve()
    target_cids = target_cids or TARGET_CIDS
    banner_asset = get_official_banner_asset(root)
    if not banner_asset:
        raise ValueError(f"Official banner asset {COMPANY_BANNER_ID} not found in INDEX.yaml")

    report = []

    for cid in target_cids:
        latest_path = root / 'content-system' / 'working' / cid / 'pipeline-latest.json'
        if not latest_path.exists():
            continue
        latest = json.loads(latest_path.read_text(encoding='utf-8'))
        run_id = latest.get('run_id')
        if not run_id:
            continue

        b_path = root / 'content-system' / 'working' / cid / 'runs' / run_id / 'asset-bindings.json'
        if not b_path.exists():
            continue

        b_data = json.loads(b_path.read_text(encoding='utf-8'))
        bindings = b_data.get('bindings', [])
        cid_changes = []

        for b in bindings:
            need = b.get('need', {})
            cand = b.get('candidate')
            need_id = need.get('id', '')
            if need_id in BANNER_NEED_IDS:
                current_cand_id = cand.get('asset_id') if cand else None
                if current_cand_id != COMPANY_BANNER_ID:
                    cid_changes.append({
                        'need_id': need_id,
                        'before_asset_id': current_cand_id,
                        'after_asset_id': COMPANY_BANNER_ID,
                        'reason': '문의 배너 후보를 공식 배너(AST-COMPANY-OCEAN-001)로 정정'
                    })
                    b['candidate'] = banner_asset
                    b['need']['asset_id'] = COMPANY_BANNER_ID
                    b['status'] = 'pending_review'
                    b['reconciliation_note'] = f"Reconciled from {current_cand_id} to {COMPANY_BANNER_ID}"

        if cid_changes:
            report.append({'content_id': cid, 'run_id': run_id, 'changes': cid_changes})
            if not dry_run:
                b_path.write_text(json.dumps(b_data, indent=2, ensure_ascii=False), encoding='utf-8')

    return report


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Reconcile inquiry banner bindings")
    parser.add_argument('--apply', action='store_true', help="Apply modifications (default is dry-run)")
    args = parser.parse_args()

    report = reconcile_bindings(dry_run=not args.apply)
    mode = "APPLIED" if args.apply else "PREVIEW (dry-run)"
    print(f"📋 Banner reconciliation report [{mode}]: {len(report)} content items modified")
    for r in report:
        print(f" • {r['content_id']} (run: {r['run_id']})")
        for ch in r['changes']:
            print(f"    - {ch['need_id']}: {ch['before_asset_id']} -> {ch['after_asset_id']} ({ch['reason']})")


if __name__ == '__main__':
    main()
