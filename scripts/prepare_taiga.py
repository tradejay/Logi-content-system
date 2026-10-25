"""Prepare official Taiga stable Compose for a loopback-only local installation."""
import json
from pathlib import Path
import secrets
import shutil
import yaml

ROOT = Path(__file__).resolve().parents[1]


def prepare(root=ROOT):
    deployment = Path(root) / 'deployments/taiga'
    upstream, runtime = deployment / 'upstream', deployment / 'runtime'
    runtime.mkdir(parents=True, exist_ok=True)
    for name in ('docker-compose.yml', 'docker-compose-inits.yml'):
        compose = yaml.safe_load((upstream / name).read_text(encoding='utf-8'))
        compose.pop('version', None)
        limits_path = deployment / 'resource-limits.json'
        limits = json.loads(limits_path.read_text(encoding='utf-8')) if limits_path.exists() else {}
        for service, values in limits.items():
            if service in compose.get('services', {}):
                compose['services'][service].update(values)
        if 'taiga-gateway' in compose['services']:
            compose['services']['taiga-gateway']['ports'] = ['127.0.0.1:9000:80']
        if 'taiga-front' in compose['services'] and (runtime/'front-overlay/index.html').exists():
            compose['services']['taiga-front']['image'] = 'naver-content-taiga-front:local'
            compose['services']['taiga-front']['build'] = {'context': './front-overlay'}
        if 'taiga-front' in compose['services']:
            compose['services']['taiga-front'].setdefault('environment', {})['DEFAULT_LANGUAGE'] = 'ko'
        (runtime / name).write_text(yaml.safe_dump(compose, sort_keys=False), encoding='utf-8')
    shutil.copytree(upstream / 'taiga-gateway', runtime / 'taiga-gateway', dirs_exist_ok=True)
    env = runtime / '.env'
    if not env.exists():
        values = {'TAIGA_SCHEME': 'http', 'TAIGA_DOMAIN': '127.0.0.1:9000', 'SUBPATH': '', 'WEBSOCKETS_SCHEME': 'ws',
                  'SECRET_KEY': secrets.token_hex(32), 'POSTGRES_USER': 'taiga', 'POSTGRES_PASSWORD': secrets.token_hex(24),
                  'EMAIL_BACKEND': 'console', 'EMAIL_HOST': '', 'EMAIL_PORT': '587', 'EMAIL_HOST_USER': '',
                  'EMAIL_HOST_PASSWORD': '', 'EMAIL_DEFAULT_FROM': 'local@example.invalid', 'EMAIL_USE_TLS': 'False',
                  'EMAIL_USE_SSL': 'False', 'RABBITMQ_USER': 'taiga', 'RABBITMQ_PASS': secrets.token_hex(24),
                  'RABBITMQ_VHOST': 'taiga', 'RABBITMQ_ERLANG_COOKIE': secrets.token_hex(24),
                  'ATTACHMENTS_MAX_AGE': '360', 'ENABLE_TELEMETRY': 'False'}
        env.write_text('\n'.join(k + '=' + v for k, v in values.items()) + '\n', encoding='utf-8')
    manifest = {'source': 'https://github.com/taigaio/taiga-docker', 'branch': 'stable',
                'commit': (upstream / '.git/refs/heads/stable').read_text().strip(),
                'version': (upstream / 'VERSION.md').read_text().strip(), 'license': 'MPL-2.0',
                'url': 'http://127.0.0.1:9000', 'docker_required': True,
                'images': 'official stable deployment image tags; pull happens on Start'}
    (deployment / 'source-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return {'prepared': True, 'runtime': str(runtime), 'url': manifest['url'], 'upstream_version': manifest['version']}


if __name__ == '__main__':
    print(json.dumps(prepare(), ensure_ascii=False))
