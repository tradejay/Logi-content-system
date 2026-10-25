"""Unit test suite for the configuration-driven insights pipeline.

Verifies:
1. Config schema validation, bounded ranges, whitelisting, and safety checks.
2. 1-query preset execution (mock/offline, single common query, skipped products steps).
3. 2-query preset execution (1 common + 1 product query, test report).
4. Depth variation preset execution (depth=10).
5. Saved data replay execution.
6. Tamper-evident resume blocking on config hash mismatch.
7. Operational asset invariance guarantee (real pointers untouched).
"""
import copy
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.blog_performance.insights import (
    config as insights_config,
    main as insights_main,
    tracker as insights_tracker
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_COMMON = ROOT / 'data/blog_performance/browser-search/20261022-common-ea7fdc3e9b/input.json'
FIXTURE_PRODUCTS = ROOT / 'data/blog_performance/browser-search/20261022-products-ko-419ff665f1/input.json'
FIXTURE_AI_DECISIONS = ROOT / 'data/blog_performance/browser-search/20261022-common-ea7fdc3e9b/body-analysis/ai-decisions.json'


class TestInsightsConfigPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix='test-config-pipeline-')
        self.test_root = Path(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_config_schema_validation_and_rejections(self):
        """Test 1: Validate schema_version, whitelisting, bounded ranges, and safety checks."""
        # 1. All standard presets must load and validate cleanly
        for preset_name in ['operational-full', 'test-single-common', 'test-mini-two-query', 'test-depth-10', 'replay-saved-data']:
            cfg = insights_config.load_preset(preset_name, root=ROOT)
            self.assertEqual(cfg['schema_version'], insights_config.SCHEMA_VERSION)

        base_valid = insights_config.load_preset('test-single-common', root=ROOT)

        # 2. Rejection of invalid schema_version
        bad_version = copy.deepcopy(base_valid)
        bad_version['schema_version'] = 'insights-pipeline-config-v999'
        valid, _, issues = insights_config.validate_config(bad_version, root=ROOT)
        self.assertFalse(valid)
        self.assertTrue(any('schema_version' in i for i in issues))

        # 3. Rejection of disallowed top keys
        bad_key = copy.deepcopy(base_valid)
        bad_key['malicious_script'] = 'rm -rf /'
        valid, _, issues = insights_config.validate_config(bad_key, root=ROOT)
        self.assertFalse(valid)
        self.assertTrue(any('Disallowed top-level' in i for i in issues))

        # 4. Rejection of invalid depth
        bad_depth = copy.deepcopy(base_valid)
        bad_depth['execution']['depth'] = 999
        valid, _, issues = insights_config.validate_config(bad_depth, root=ROOT)
        self.assertFalse(valid)
        self.assertTrue(any('depth' in i for i in issues))

        # 5. Rejection of unregistered queries
        bad_query = copy.deepcopy(base_valid)
        bad_query['panel']['queries'] = ['미등록_임의_키워드_123']
        valid, _, issues = insights_config.validate_config(bad_query, root=ROOT)
        self.assertFalse(valid)
        self.assertTrue(any('not a registered panel query' in i for i in issues))

        # 6. Rejection of duplicate queries
        dup_query = copy.deepcopy(base_valid)
        dup_query['panel']['limit'] = 2
        dup_query['panel']['queries'] = ['화상회의', '화상회의']
        valid, _, issues = insights_config.validate_config(dup_query, root=ROOT)
        self.assertFalse(valid)
        self.assertTrue(any('Duplicate query keyword' in i for i in issues))

        # 7. Rejection of unsafe path traversals
        bad_path = copy.deepcopy(base_valid)
        bad_path['inputs']['common_json'] = '../../etc/shadow'
        valid, _, issues = insights_config.validate_config(bad_path, root=ROOT)
        self.assertFalse(valid)
        self.assertTrue(any('unsafe path' in i for i in issues))

    def test_single_query_preset_execution(self):
        """Test 2: Single common query preset execution without touching operational files."""
        cfg = insights_config.load_preset('test-single-common', root=ROOT)
        cfg['execution']['mode'] = 'offline'

        rid = "INSIGHTS-TEST-SINGLE-COMMON"
        prep = insights_main.prepare_run(run_id=rid, config=cfg, root=self.test_root)
        self.assertEqual(prep['status'], 'prepared')
        self.assertEqual(prep['panel_queries'], 1)
        self.assertTrue(prep['test_only'])

        run_dir = self.test_root / 'data/blog_performance/insights/tests' / rid
        self.assertTrue(run_dir.exists())

        # Seed mock common input
        common_input = run_dir / 'common/input.json'
        common_input.parent.mkdir(parents=True, exist_ok=True)
        raw_fixture = json.loads(FIXTURE_COMMON.read_text(encoding='utf-8'))
        # Filter fixture to only 화상회의
        single_res = [r for r in raw_fixture['results'] if r['keyword'] == '화상회의']
        filtered_common = {
            'total': len(single_res[0]['rows']),
            'uniqueCount': len(set(h['url'] for h in single_res[0]['rows'])),
            'results': single_res
        }
        common_input.write_text(json.dumps(filtered_common, ensure_ascii=False), encoding='utf-8')

        # Run pipeline
        res = insights_main.run_pipeline(run_id=rid, ai_decisions=FIXTURE_AI_DECISIONS, root=self.test_root)
        self.assertEqual(res['status'], 'completed')
        self.assertTrue(res['test_only'])

        # Verify products steps were skipped
        state = json.loads((run_dir / 'state.json').read_text(encoding='utf-8'))
        self.assertEqual(state['steps']['products_imported'], 'skipped')

        # Verify test HTML exists
        self.assertTrue((run_dir / 'report.html').exists())
        html_text = (run_dir / 'report.html').read_text(encoding='utf-8')
        self.assertIn("TEST", html_text)
        self.assertIn("화상회의", html_text)

        # Verify isolated test pointer was updated
        test_ptr = self.test_root / 'data/blog_performance/insights/tests/latest-test-run.json'
        self.assertTrue(test_ptr.exists())
        ptr_data = json.loads(test_ptr.read_text(encoding='utf-8'))
        self.assertEqual(ptr_data['run_id'], rid)

        # Operational pointer must NOT exist in isolated test directory
        self.assertFalse((self.test_root / 'data/blog_performance/insights/latest-run.json').exists())

    def test_two_query_preset_execution(self):
        """Test 3: 1 common + 1 product query preset execution."""
        cfg = insights_config.load_preset('test-mini-two-query', root=ROOT)
        cfg['execution']['mode'] = 'offline'

        rid = "INSIGHTS-TEST-TWO-QUERIES"
        prep = insights_main.prepare_run(run_id=rid, config=cfg, root=self.test_root)
        self.assertEqual(prep['status'], 'prepared')
        self.assertEqual(prep['panel_queries'], 2)

        run_dir = self.test_root / 'data/blog_performance/insights/tests' / rid

        # Seed mock common input
        common_input = run_dir / 'common/input.json'
        common_input.parent.mkdir(parents=True, exist_ok=True)
        raw_common = json.loads(FIXTURE_COMMON.read_text(encoding='utf-8'))
        single_common = [r for r in raw_common['results'] if r['keyword'] == '화상회의']
        common_input.write_text(json.dumps({
            'total': len(single_common[0]['rows']),
            'uniqueCount': len(set(h['url'] for h in single_common[0]['rows'])),
            'results': single_common
        }, ensure_ascii=False), encoding='utf-8')

        # Seed mock products input
        prod_input = run_dir / 'products/input.json'
        prod_input.parent.mkdir(parents=True, exist_ok=True)
        raw_prod = json.loads(FIXTURE_PRODUCTS.read_text(encoding='utf-8'))
        single_prod = [r for r in raw_prod['results'] if r['keyword'] == '로지텍 랠리바 미니']
        prod_input.write_text(json.dumps({
            'scope': '한국어 제품명',
            'total': len(single_prod[0]['rows']),
            'uniqueCount': len(set(h['url'] for h in single_prod[0]['rows'])),
            'results': single_prod
        }, ensure_ascii=False), encoding='utf-8')

        res = insights_main.run_pipeline(run_id=rid, ai_decisions=FIXTURE_AI_DECISIONS, root=self.test_root)
        self.assertEqual(res['status'], 'completed')

        state = json.loads((run_dir / 'state.json').read_text(encoding='utf-8'))
        self.assertTrue(state['steps']['common_imported'])
        self.assertTrue(state['steps']['products_imported'])
        # Test data must exercise the production slide renderer, not a separate mock UI.
        report = (run_dir / 'report.html').read_text(encoding='utf-8')
        self.assertIn('class="slide"', report)
        self.assertIn('class="toolbar"', report)
        self.assertIn('common-brand-matrix', report)
        self.assertIn('brand-line', report)
        self.assertIn('TEST · 운영과 동일한 보고서 형식', report)

    def test_depth_variation_preset_execution(self):
        """Test 4: Depth variation preset execution (depth=10)."""
        cfg = insights_config.load_preset('test-depth-10', root=ROOT)
        self.assertEqual(cfg['execution']['depth'], 10)

        rid = "INSIGHTS-TEST-DEPTH-10"
        prep = insights_main.prepare_run(run_id=rid, config=cfg, root=self.test_root)
        self.assertEqual(prep['status'], 'prepared')

        run_dir = self.test_root / 'data/blog_performance/insights/tests' / rid
        manifest = json.loads((run_dir / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['collection_depth'], 10)

    def test_config_hash_mismatch_blocks_resume(self):
        """Test 6: Tamper-evident resume: modifying config on resume is blocked."""
        cfg = insights_config.load_preset('test-single-common', root=ROOT)
        rid = "INSIGHTS-TEST-HASH-INTEGRITY"

        insights_main.prepare_run(run_id=rid, config=cfg, root=self.test_root)
        run_dir = self.test_root / 'data/blog_performance/insights/tests' / rid

        # Tamper with the saved config.json
        cfg_saved = json.loads((run_dir / 'config.json').read_text(encoding='utf-8'))
        cfg_saved['execution']['depth'] = 50
        (run_dir / 'config.json').write_text(json.dumps(cfg_saved, ensure_ascii=False), encoding='utf-8')

        # Resume must detect tamper/mismatch
        res = insights_main.run_pipeline(run_id=rid, config=cfg, root=self.test_root)
        self.assertEqual(res['status'], 'config_hash_mismatch')
        self.assertIn('Cannot resume run with modified configuration', res['error'])

    def test_operational_assets_invariance_guarantee(self):
        """Test 7: Operational asset invariance: test runs must NEVER alter production assets."""
        real_ptr = ROOT / 'data/blog_performance/insights/latest-run.json'
        real_common_ptr = ROOT / 'data/blog_performance/browser-search/latest-common.json'
        real_prod_ptr = ROOT / 'data/blog_performance/browser-search/latest-products-ko.json'

        ptr_before = real_ptr.read_bytes() if real_ptr.exists() else None
        common_before = real_common_ptr.read_bytes() if real_common_ptr.exists() else None
        prod_before = real_prod_ptr.read_bytes() if real_prod_ptr.exists() else None

        # Execute test run with preset
        cfg = insights_config.load_preset('test-single-common', root=ROOT)
        rid = "INSIGHTS-TEST-INVARIANCE"
        prep = insights_main.prepare_run(run_id=rid, config=cfg, root=self.test_root)
        run_dir = self.test_root / 'data/blog_performance/insights/tests' / rid

        common_input = run_dir / 'common/input.json'
        common_input.parent.mkdir(parents=True, exist_ok=True)
        raw_fixture = json.loads(FIXTURE_COMMON.read_text(encoding='utf-8'))
        single_res = [r for r in raw_fixture['results'] if r['keyword'] == '화상회의']
        common_input.write_text(json.dumps({
            'total': len(single_res[0]['rows']),
            'uniqueCount': len(set(h['url'] for h in single_res[0]['rows'])),
            'results': single_res
        }, ensure_ascii=False), encoding='utf-8')

        insights_main.run_pipeline(run_id=rid, root=self.test_root)

        ptr_after = real_ptr.read_bytes() if real_ptr.exists() else None
        common_after = real_common_ptr.read_bytes() if real_common_ptr.exists() else None
        prod_after = real_prod_ptr.read_bytes() if real_prod_ptr.exists() else None

        self.assertEqual(ptr_before, ptr_after, "Operational latest-run.json was tampered!")
        self.assertEqual(common_before, common_after, "Operational latest-common.json was tampered!")
        self.assertEqual(prod_before, prod_after, "Operational latest-products-ko.json was tampered!")


if __name__ == '__main__':
    unittest.main()
