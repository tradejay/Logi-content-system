import unittest
from unittest.mock import patch
from flask import Flask
from services.policy_api import policy_bp
from tests import test_policy_manager as fixtures


class PolicyApiTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.PolicyManagerTests()
        self.fixture.setUp()
        app = Flask(__name__)
        app.register_blueprint(policy_bp)
        self.client = app.test_client()
        self.manager_patch = patch('services.policy_api.manager', return_value=self.fixture.manager)
        self.manager_patch.start()
        self.headers = {'X-Policy-Editor': '1'}

    def tearDown(self):
        self.manager_patch.stop()
        self.fixture.tearDown()

    def test_page_and_list_and_edit(self):
        with self.client.get('/content-ops/policies') as response:
            self.assertEqual(response.status_code, 200)
        result = self.client.get('/api/content-system/policies')
        self.assertEqual(result.status_code, 200)
        pid = self.fixture.atom()['id']
        data = {'expected_revision': 1, 'policy': {'text': '수정', 'review_note': '검토'}}
        response = self.client.put('/api/content-system/policies/' + pid, json=data, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        response = self.client.put('/api/content-system/policies/' + pid, json=data, headers=self.headers)
        self.assertEqual(response.status_code, 409)

    def test_cross_origin_and_form_rejected(self):
        data = {'expected_revision': 1, 'policy': {}}
        response = self.client.post('/api/content-system/policies', json=data,
                                   headers={**self.headers, 'Origin': 'https://outside.example'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.post('/api/content-system/policies', data='x').status_code, 400)
        self.assertEqual(self.client.post('/api/content-system/policies', json=[] ,headers=self.headers).status_code, 400)

    def test_preview_build_activate_end_to_end(self):
        preview = self.client.get('/api/content-system/policy-preview')
        self.assertTrue(preview.json['validation']['valid'])
        built = self.client.post('/api/content-system/policy-candidates', headers=self.headers,
                                 json={'expected_revision': 1, 'reviewer': 'owner', 'review_note': '검토'})
        self.assertEqual(built.status_code, 200)
        activated = self.client.post('/api/content-system/policy-activate', headers=self.headers,
                                     json={'release_id': built.json['release_id'], 'expected_active': None})
        self.assertEqual(activated.status_code, 200)
        self.assertEqual(self.client.get('/api/content-system/policies').json['active_release'], built.json['release_id'])


if __name__ == '__main__':
    unittest.main()
