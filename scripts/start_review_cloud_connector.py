"""Start the outbound review connector using local, excluded credentials."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'data/review-webapp/connector-process.json'


def main():
    import psutil
    if STATE.exists():
        saved = json.loads(STATE.read_text(encoding='utf-8'))
        try:
            proc = psutil.Process(saved['pid'])
            if 'services.review_app.connector' in proc.cmdline():
                print('Review connector already running.')
                return
        except (psutil.Error, KeyError):
            pass
    values = json.loads((ROOT / 'config/review-webapp.secrets.json').read_text(encoding='utf-8'))
    env = os.environ.copy()
    env.update({key: values[key] for key in ('CONNECTOR_SECRET', 'REVIEW_SERVER_URL')})
    env['PYTHONPATH'] = os.pathsep.join((str(ROOT / '.pipeline-deps'), str(ROOT)))
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUNBUFFERED'] = '1'
    env['AUTO_REVIEW_ENABLED'] = '1'
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with (STATE.parent / 'connector.log').open('ab') as output:
        proc = subprocess.Popen(
            [sys.executable, '-m', 'services.review_app.connector', '--interval', '5'],
            cwd=ROOT, env=env, stdout=output, stderr=output,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
    STATE.write_text(json.dumps({'pid': proc.pid, 'server': values['REVIEW_SERVER_URL']}), encoding='utf-8')
    print('Review outbound connector started.')


if __name__ == '__main__':
    main()
