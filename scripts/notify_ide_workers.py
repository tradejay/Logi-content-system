"""Notify explicit opt-in inbox tasks; collect verified outputs without live application."""
import argparse
import json
import time
from services.ide_worker_bridge import ROOT, process, load, save, file_activity
from services.ide_test_review import handoff
from services.ide_full_article_preview import publish
from services.ide_review_status import sync


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--worker')
    p.add_argument('--task')
    p.add_argument('--watch', action='store_true')
    p.add_argument('--interval', type=float, default=5)
    p.add_argument('--timeout', type=float, default=600)
    args = p.parse_args()
    if bool(args.worker) != bool(args.task):
        p.error('--worker and --task must be specified together')
    started = time.monotonic()
    previous_log = None
    while True:
        targets = [(args.worker, args.task)] if args.worker else [
            (path.parents[2].name, path.parent.name)
            for path in (ROOT / 'worker-workspaces').glob('*/inbox/*/task.json')
            if load(path).get('notification', {}).get('enabled')]
        results = []
        for worker, task in targets:
            try:
                state = process(worker, task)
                review_task = handoff(worker, task, state)
                preview = publish(worker, task, state)
                sync(worker,task,state)
                results.append({'worker':worker,'task':task,'status':state['status'],
                                'result_status':state.get('result_status'),'review_task':review_task,'preview':preview,
                                'activity':file_activity(ROOT/'worker-workspaces'/worker)})
            except Exception as exc:
                results.append({'worker':worker,'task':task,'error':str(exc)})
        save(ROOT / 'worker-control/bridge-status.json', {'updated_at':time.time(),'tasks':results})
        # Age changes every tick; log only actual status/file-activity changes.
        signature = json.dumps([{**r,'activity':{k:v for k,v in r.get('activity',{}).items()
                             if k != 'seconds_since_change'}} for r in results],sort_keys=True)
        if signature != previous_log:
            print(json.dumps(results, ensure_ascii=False), flush=True)
            previous_log = signature
        if not args.watch or (args.task and results and results[0].get('status') == 'collected'):
            return
        if time.monotonic() - started >= args.timeout:
            return
        time.sleep(max(1, args.interval))


if __name__ == '__main__':
    main()
