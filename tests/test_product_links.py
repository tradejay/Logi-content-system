import json
from pathlib import Path
import tempfile
import unittest

from services.device_blog_registry import resolve_device_id_strictly
from services.pipeline_context import load_context, digest


class TestProductLinks(unittest.TestCase):
    def test_strict_resolution_tap_family(self):
        self.assertEqual(resolve_device_id_strictly('LOGI-TAP-IP'), 'logi-tap-ip')
        self.assertEqual(resolve_device_id_strictly('LOGI-TAP'), 'logi-tap')
        self.assertEqual(resolve_device_id_strictly('Logitech Tap IP'), 'logi-tap-ip')
        self.assertEqual(resolve_device_id_strictly('Logitech Tap'), 'logi-tap')
        self.assertEqual(resolve_device_id_strictly('Tap Scheduler'), 'logi-tap-scheduler')

    def test_strict_resolution_meetup_family(self):
        self.assertEqual(resolve_device_id_strictly('LOGI-MEETUP-2'), 'logi-meetup-2')
        self.assertEqual(resolve_device_id_strictly('LOGI-MEETUP'), 'logi-meetup')
        self.assertEqual(resolve_device_id_strictly('Logitech MeetUp 2'), 'logi-meetup-2')
        self.assertEqual(resolve_device_id_strictly('Logitech MeetUp'), 'logi-meetup')

    def test_context_product_links_for_004(self):
        root = Path(__file__).resolve().parents[1]
        ctx = load_context(root, 'CNT-2026W39-004')
        links = ctx.get('product_links', {})

        self.assertIn('LOGI-TAP', links)
        self.assertIn('LOGI-TAP-IP', links)
        # URL이 서로 완전히 달라야 함
        self.assertNotEqual(links['LOGI-TAP']['blog_url'], links['LOGI-TAP-IP']['blog_url'])
        self.assertIn('224324760360', links['LOGI-TAP']['blog_url'])
        self.assertIn('224324825914', links['LOGI-TAP-IP']['blog_url'])

        # 가상 ref가 input_refs에 포함되어 있는지 확인
        virtual_refs = [r for r in ctx['input_refs'] if r.get('path', '').startswith('virtual:product_links:')]
        self.assertEqual(len(virtual_refs), 1)
        expected_digest = digest(json.dumps(links, sort_keys=True, ensure_ascii=False))
        self.assertEqual(virtual_refs[0]['sha256'], expected_digest)


if __name__ == '__main__':
    unittest.main()
