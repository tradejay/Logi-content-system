"""Create the local Taiga administrator without exposing its password in argv/logs."""
import json
from pathlib import Path
import secrets
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    private = ROOT / 'config/taiga.secrets.json'
    if private.exists():
        credentials = json.loads(private.read_text(encoding='utf-8'))
    else:
        credentials = {'username': 'contentops', 'password': secrets.token_urlsafe(24), 'auth_token': ''}
        private.write_text(json.dumps(credentials, indent=2) + '\n', encoding='utf-8')
    if not credentials.get('username') or not credentials.get('password'):
        raise SystemExit('Local username/password required; existing credentials were preserved.')
    runtime = ROOT / 'deployments/taiga/runtime'
    command = ['docker', 'compose', '--project-name', 'naver-content-taiga',
               '--project-directory', str(runtime), '--env-file', str(runtime / '.env'),
               '-f', str(runtime / 'docker-compose.yml'), 'exec', '-T', 'taiga-back',
               'python', 'manage.py', 'shell']
    code = '\n'.join([
        'import json', 'from django.contrib.auth import get_user_model',
        'credentials = json.loads(' + repr(json.dumps(credentials)) + ')',
        'User = get_user_model()',
        "user = User.objects.filter(username=credentials['username']).first()",
        'if user is None:',
        "    user = User.objects.create_superuser(username=credentials['username'], email='contentops@localhost.test', password=credentials['password'])",
        "    user.full_name = 'Content Operations'; user.save()",
        "print('Local administrator ready')", '',
    ])
    result = subprocess.run(command, input=code, text=True, capture_output=True, cwd=ROOT)
    if result.returncode:
        raise SystemExit('Taiga account setup failed; credentials preserved. Check container readiness.')
    from services.taiga_tracking import TaigaClient
    client = TaigaClient('http://127.0.0.1:9000', credentials=credentials)
    client.login()
    config_path = ROOT / 'config/taiga.json'
    config = json.loads(config_path.read_text(encoding='utf-8'))
    config['enabled'] = True
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'administrator': credentials['username'], 'credentials_file': str(private), 'authenticated': True}))


if __name__ == '__main__':
    main()
