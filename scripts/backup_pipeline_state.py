#!/usr/bin/env python3
"""
Pipeline State Backup & Restore Tool.
Provides byte-exact snapshots, manifest verification, and safe restoration.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

# Force UTF-8 stdout
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BACKUP_ROOT = PROJECT_ROOT / 'audit' / 'backups'
TARGET_CIDS = [f'CNT-2026W39-00{i}' for i in range(1, 6)]


def compute_bytes_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def create_backup(root: Path = PROJECT_ROOT, target_cids=None, backup_id: str = None, backup_root: Path = None):
    root = Path(root).resolve()
    target_cids = target_cids or TARGET_CIDS
    backup_root = Path(backup_root or (root / 'audit' / 'backups')).resolve()
    
    bid = backup_id or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    dest_dir = backup_root / bid
    dest_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        'backup_id': bid,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'target_cids': target_cids,
        'files': []
    }

    files_to_copy = []

    # 1. Registry CSV
    reg_csv = root / 'content-system' / 'registry' / 'CONTENT_REGISTRY.csv'
    if reg_csv.exists():
        files_to_copy.append((reg_csv, None, None))

    # 2. Knowledge & Asset indexes being touched
    assets_idx = root / 'content-system' / '03_sources' / 'assets' / 'INDEX.yaml'
    if assets_idx.exists():
        files_to_copy.append((assets_idx, None, None))

    for knw_name in ['KNW-PROD-LOGI-TAP.yaml', 'KNW-PROD-LOGI-RALLYPLUS.yaml']:
        kp = root / 'content-system' / '03_sources' / 'knowledge' / 'products' / knw_name
        if kp.exists():
            files_to_copy.append((kp, None, None))

    # 3. For each target CID: draft, pipeline-latest, and latest run dir
    for cid in target_cids:
        draft = root / 'content-system' / '02_writer_ai' / 'drafts' / f'{cid}.draft.md'
        if draft.exists():
            files_to_copy.append((draft, cid, None))

        latest_json = root / 'content-system' / 'working' / cid / 'pipeline-latest.json'
        run_id = None
        if latest_json.exists():
            files_to_copy.append((latest_json, cid, None))
            try:
                data = json.loads(latest_json.read_text(encoding='utf-8'))
                run_id = data.get('run_id')
            except Exception:
                run_id = None

        if run_id:
            run_dir = root / 'content-system' / 'working' / cid / 'runs' / run_id
            if run_dir.is_dir():
                for p in run_dir.rglob('*'):
                    if p.is_file():
                        files_to_copy.append((p, cid, run_id))

    # Perform exact byte copy
    for src_path, cid, run_id in files_to_copy:
        rel_path = src_path.relative_to(root)
        dest_path = dest_dir / 'files' / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initial hash
        sha_before = compute_bytes_sha256(src_path)
        size_before = src_path.stat().st_size
        
        shutil.copy2(src_path, dest_path)
        
        # Verify copied file
        sha_after = compute_bytes_sha256(dest_path)
        if sha_before != sha_after:
            raise RuntimeError(f"Backup instability detected on {rel_path}: sha256 mismatch")

        manifest['files'].append({
            'relative_path': str(rel_path).replace('\\', '/'),
            'size_bytes': size_before,
            'sha256': sha_before,
            'content_id': cid,
            'run_id': run_id,
            'copied': True
        })

    manifest_path = dest_dir / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    return bid, dest_dir, manifest


def verify_backup(backup_dir: Path, root: Path = PROJECT_ROOT):
    backup_dir = Path(backup_dir).resolve()
    manifest_path = backup_dir / 'manifest.json'
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.json not found in {backup_dir}")

    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    results = {'valid': True, 'checked': 0, 'corrupted': []}

    for item in manifest.get('files', []):
        rel = item['relative_path']
        stored = backup_dir / 'files' / rel
        if not stored.exists():
            results['valid'] = False
            results['corrupted'].append({'path': rel, 'error': 'missing_in_backup'})
            continue
        sha = compute_bytes_sha256(stored)
        if sha != item['sha256']:
            results['valid'] = False
            results['corrupted'].append({'path': rel, 'error': 'sha256_mismatch', 'expected': item['sha256'], 'got': sha})
            continue
        results['checked'] += 1

    return results


def restore_backup(backup_dir: Path, root: Path = PROJECT_ROOT, dry_run: bool = True):
    backup_dir = Path(backup_dir).resolve()
    root = Path(root).resolve()
    manifest_path = backup_dir / 'manifest.json'
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.json not found in {backup_dir}")

    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    plan = []

    for item in manifest.get('files', []):
        rel = item['relative_path']
        source = backup_dir / 'files' / rel
        target = root / rel
        
        target_exists = target.exists()
        current_sha = compute_bytes_sha256(target) if target_exists else None
        
        status = 'MATCH' if current_sha == item['sha256'] else ('MODIFIED' if target_exists else 'NEW')
        plan.append({
            'relative_path': rel,
            'source': str(source),
            'target': str(target),
            'status': status,
            'backup_sha256': item['sha256'],
            'current_sha256': current_sha
        })

        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    return plan


def main():
    parser = argparse.ArgumentParser(description="Pipeline state backup and restore utility")
    subparsers = parser.add_subparsers(dest='command', required=True)

    create_p = subparsers.add_parser('create', help="Create a byte-exact backup snapshot")
    create_p.add_argument('--id', default=None, help="Custom backup identifier")

    verify_p = subparsers.add_parser('verify', help="Verify integrity of a backup snapshot")
    verify_p.add_argument('backup_id', help="Backup ID or path")

    restore_p = subparsers.add_parser('restore', help="Preview or apply a restore from backup")
    restore_p.add_argument('backup_id', help="Backup ID or path")
    restore_p.add_argument('--apply', action='store_true', help="Actually restore files (default is dry-run)")

    args = parser.parse_args()

    if args.command == 'create':
        bid, path, manifest = create_backup(backup_id=args.id)
        print(f"✅ Backup created: {bid}")
        print(f" • Destination: {path}")
        print(f" • Total files backed up: {len(manifest['files'])}")

    elif args.command == 'verify':
        bdir = DEFAULT_BACKUP_ROOT / args.backup_id if not Path(args.backup_id).is_dir() else Path(args.backup_id)
        res = verify_backup(bdir)
        if res['valid']:
            print(f"✅ Backup integrity verified: {res['checked']} files match manifest exactly.")
        else:
            print(f"❌ Backup corrupted: {len(res['corrupted'])} items failed.")
            sys.exit(1)

    elif args.command == 'restore':
        bdir = DEFAULT_BACKUP_ROOT / args.backup_id if not Path(args.backup_id).is_dir() else Path(args.backup_id)
        dry = not args.apply
        plan = restore_backup(bdir, dry_run=dry)
        action_word = "PREVIEW (dry-run)" if dry else "RESTORED"
        print(f"📦 Backup restore {action_word}: {len(plan)} files")
        for item in plan[:10]:
            print(f" • [{item['status']:<8}] {item['relative_path']}")
        if len(plan) > 10:
            print(f" ... and {len(plan) - 10} more files.")


if __name__ == '__main__':
    main()
