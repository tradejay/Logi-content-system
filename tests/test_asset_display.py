import importlib.util
import tempfile
import unittest
from pathlib import Path

MOD_PATH = Path(__file__).resolve().parent.parent / 'services' / 'asset_display.py'
spec = importlib.util.spec_from_file_location('work_asset_display', MOD_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
describe = mod.describe

from services.ide_worker_bridge import save


class AssetDisplayTests(unittest.TestCase):
    def test_instruction_is_not_presented_as_actual_generation_prompt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            save(root / 'worker-workspaces/05_assets/inbox/TASK-1/input-1.json', {'requests': [{'content_id': 'CNT-TEST', 'need_id': 'N1', 'purpose': '회의실 장면'}]})
            binding = {'need': {'id': 'N1', 'purpose': '설명용'}, 'candidate': {'origin_type': 'generated', 'source_ref': {'task_id': 'TASK-1'}}}
            result = describe(root, 'CNT-TEST', binding)
            self.assertEqual(result['production_instruction'], '회의실 장면')
            self.assertIsNone(result['generation_prompt'])
            self.assertIn('미기록', result['prompt_note'])

    def test_generation_prompt_preserved_when_present(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            save(root / 'worker-workspaces/05_assets/inbox/TASK-2/input-1.json', {'requests': [{'content_id': 'CNT-TEST', 'need_id': 'N2', 'purpose': '회의실 전경'}]})
            binding = {'need': {'id': 'N2', 'purpose': '회의실 전경'}, 'candidate': {'origin_type': 'generated', 'generation_prompt': 'A high-end conference room with dual cameras', 'source_ref': {'task_id': 'TASK-2'}}}
            result = describe(root, 'CNT-TEST', binding)
            self.assertEqual(result['production_instruction'], '회의실 전경')
            self.assertEqual(result['generation_prompt'], 'A high-end conference room with dual cameras')
            self.assertNotIn('prompt_note', result)

    def test_unregistered_candidate_display(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            binding = {'need': {'id': 'N3', 'purpose': '제품 사진'}}
            result = describe(root, 'CNT-TEST', binding)
            self.assertEqual(result['review'], '제작·확보 필요')
            self.assertEqual(result['type'], '제작·확보 필요')
            self.assertIsNone(result['generation_prompt'])
            self.assertNotIn('prompt_note', result)

    def test_string_binding_or_string_fields_do_not_throw_attribute_error(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            # Binding as raw string
            res1 = describe(root, 'CNT-TEST', 'NEED-RAW-STRING')
            self.assertIsInstance(res1, dict)
            self.assertEqual(res1['review'], '제작·확보 필요')

            # Need and candidate as strings
            res2 = describe(root, 'CNT-TEST', {'need': 'NEED-1', 'candidate': 'AST-1'})
            self.assertIsInstance(res2, dict)
            self.assertEqual(res2['review'], '검토·승인 대기')


if __name__ == '__main__':
    unittest.main()
