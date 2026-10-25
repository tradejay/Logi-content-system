"""Process explicit UI image requests, without automatic API fallback."""
import os
import time
from services.ide_worker_bridge import ROOT, load, save
from services.asset_revision import step


def cycle(root=ROOT, synchronize=None):
    """One real watcher cycle; retry remote sync without losing local completion."""
    health = {'pid': os.getpid(), 'heartbeat': time.time(), 'status': 'running'}
    try:
        step(root)
    except Exception as error:
        health.update(status='error', error=type(error).__name__ + ': ' + str(error)[:200])
    pending = []
    for path in (root / 'worker-control/asset-revisions').glob('*/job.json'):
        try:
            job = load(path)
            if job['status'] == 'completed' and not job.get('taiga_synced') and job.get('sync_retry_at', 0) <= time.time():
                pending.append((path, job))
        except (ValueError, OSError, KeyError):
            continue
    if pending:
        try:
            if synchronize is None:
                from services.taiga_tracking import synchronize
            synchronize()
            for path, expected in pending:
                job = load(path)
                if job.get('asset_id') == expected.get('asset_id'):
                    job.update(taiga_synced=True, phase='synced')
                    job.pop('taiga_sync_error', None)
                    job.pop('sync_retry_at', None)
                    save(path, job)
        except Exception as error:
            for path, _ in pending:
                job = load(path)
                job.update(phase='taiga_sync_pending', taiga_sync_error=str(error)[:200], sync_retry_at=time.time()+15)
                save(path, job)
            health['sync_error'] = type(error).__name__
    health['heartbeat'] = time.time()
    save(root / 'worker-control/asset-revisions/health.json', health)
    return health


def main():
    lock = ROOT / 'worker-control/asset-revisions/watcher.lock'
    lock.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(descriptor, str(os.getpid()).encode())
    os.close(descriptor)
    try:
        while True:
            try:
                cycle()
            except Exception as error:
                print(type(error).__name__, str(error)[:200], flush=True)
            time.sleep(5)
    finally:
        lock.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
