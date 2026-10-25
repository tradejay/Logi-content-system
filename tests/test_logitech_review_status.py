import unittest
from unittest.mock import Mock
from services.logitech_review_status import inspect_failure, START_COMMAND


class LogitechStatusTests(unittest.TestCase):
    def test_stopped_server_requests_manual_start(self):
        failed = Mock(side_effect=OSError('offline'))
        result = inspect_failure(RuntimeError('failed'), get=failed, connect=failed)
        self.assertEqual(result['status'], 'server_stopped')
        self.assertFalse(result['server_running'])
        self.assertEqual(result['command'], START_COMMAND)

    def test_running_captcha_does_not_request_server_start(self):
        response = Mock(status_code=200)
        response.json.return_value = {'status': 'ready'}
        result = inspect_failure(RuntimeError('human CAPTCHA verification'), get=Mock(return_value=response))
        self.assertEqual(result['status'], 'captcha_required')
        self.assertTrue(result['server_running'])
        self.assertNotIn('command', result)

    def test_listening_server_with_unavailable_health_is_not_offline(self):
        result = inspect_failure(RuntimeError('failed'), get=Mock(side_effect=TimeoutError()), connect=Mock(return_value=Mock()))
        self.assertEqual(result['status'], 'server_not_ready')
        self.assertTrue(result['server_running'])


if __name__ == '__main__':
    unittest.main()
