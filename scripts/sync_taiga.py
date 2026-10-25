import argparse
import json
from pathlib import Path
import time
from services.taiga_tracking import ROOT, synchronize, tracking_snapshot


def main():
    parser = argparse.ArgumentParser(description='Taiga work tracking sync; no AI calls or publication approval')
    parser.add_argument('--sync', action='store_true')
    parser.add_argument('--watch', action='store_true')
    args = parser.parse_args()
    if not args.sync and not args.watch:
        snapshot = tracking_snapshot()
        destination = ROOT / 'content-system/operations/taiga-sync/preview.json'
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'mode': 'preview', 'counts': snapshot['counts'], 'tasks': len(snapshot['tasks']), 'path': str(destination)}, ensure_ascii=False))
        return
    while True:
        try:
            report = synchronize()
            print(json.dumps({k: report[k] for k in ('created', 'updated', 'unchanged', 'board_url')}, ensure_ascii=False))
        except (ValueError, RuntimeError) as error:
            print(str(error))
            if not args.watch:
                raise SystemExit(1)
        if not args.watch:
            break
        time.sleep(60)


if __name__ == '__main__':
    main()
