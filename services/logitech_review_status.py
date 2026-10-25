"""Transport diagnostics only; never starts the server or judges article facts."""
import socket

START_COMMAND = 'python services/ask_logitech_ai.py --port 5050'


def inspect_failure(error, get=None, connect=None):
    if get is None:
        import requests
        get = requests.get
    connect = connect or socket.create_connection
    ready = False
    running = False
    try:
        response = get('http://127.0.0.1:5050/health', timeout=3)
        running = True
        ready = response.status_code == 200 and response.json().get('status') == 'ready'
    except Exception:
        try:
            connection = connect(('127.0.0.1', 5050), timeout=1)
            connection.close()
            running = True
        except OSError:
            pass
    if not running:
        return {'status': 'server_stopped', 'server_running': False, 'action_required': '관리자께서 프로젝트 폴더에서 로지텍 AI 서버를 켜 주세요.', 'command': START_COMMAND}
    if 'CAPTCHA' in str(error).upper():
        return {'status': 'captcha_required', 'server_running': True, 'action_required': '로지텍 AI 서버는 켜져 있습니다. 브라우저의 CAPTCHA를 관리자가 직접 해결해 주세요.'}
    return {'status': 'review_failed' if ready else 'server_not_ready', 'server_running': True, 'action_required': '로지텍 AI 서버는 켜져 있습니다. 서버 창의 오류와 브라우저 로그인·연결 상태를 확인해 주세요.'}
