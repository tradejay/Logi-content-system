"""Unit tests for the integrated insights pipeline (main.py, preflight, fixtures)."""
import json
import os
import shutil
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.blog_performance.insights import main as insights_main
from services import worker_preflight

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_COMMON = ROOT / 'data/blog_performance/browser-search/20261022-common-ea7fdc3e9b/input.json'
FIXTURE_PRODUCTS = ROOT / 'data/blog_performance/browser-search/20261022-products-ko-419ff665f1/input.json'
FIXTURE_AI_DECISIONS = ROOT / 'data/blog_performance/browser-search/20261022-common-ea7fdc3e9b/body-analysis/ai-decisions.json'


class NetworkBlockedError(RuntimeError):
    pass


def fail_on_network(*args, **kwargs):
    raise NetworkBlockedError("Live network request forbidden in offline mode")


class TestInsightsPipeline(unittest.TestCase):
    def test_search_panel_structure(self):
        panel = insights_main.build_search_panel()
        self.assertEqual(len(panel), 34)

        common_items = [p for p in panel if p['panel'] == 'common']
        self.assertEqual(len(common_items), 7)
        self.assertEqual([p['keyword'] for p in common_items], insights_main.COMMON_KEYWORDS)

        prod_items = [p for p in panel if p['panel'] == 'products']
        self.assertEqual(len(prod_items), 27)

        # Check report grouping: Large 4, Medium 5, Small 9, Modular 9
        groups = {}
        for p in prod_items:
            g = p['report_group']
            groups[g] = groups.get(g, 0) + 1

        self.assertEqual(groups, {'bar': 4, 'medium': 5, 'small': 9, 'modular': 9})

        # Check PanaCast 50 is classified into small
        panacast = [p for p in prod_items if p['product_id'] in {'VC-016', 'VC-017'}]
        self.assertEqual(len(panacast), 2)
        for p in panacast:
            self.assertEqual(p['report_group'], 'small')

        # Check URL formatting
        for p in panel:
            self.assertTrue(p['search_url'].startswith('https://search.naver.com/search.naver?ssc=tab.blog.all&sm=tab_jum&query='))

    def test_preflight_and_run_id_validation(self):
        result = worker_preflight.run(root=ROOT, pipeline='insights', online=False)
        self.assertEqual(result['pipeline'], 'insights')
        missing = [d['path'] for d in result['dependencies'] if not d['exists']]
        self.assertEqual(missing, [], f"Missing dependencies: {missing}")

        # Path traversal checks
        with self.assertRaises(ValueError):
            insights_main.validate_run_id("INSIGHTS-../../etc", root=ROOT)
        with self.assertRaises(ValueError):
            insights_main.validate_run_id("INVALID_PREFIX", root=ROOT)
        with self.assertRaises(ValueError):
            insights_main.validate_run_id("", root=ROOT)

    def test_html_verification_rules(self):
        # Mutated HTML with wrong slide count
        bad_html = "<html><body><section class='slide'></section></body></html>"
        with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(bad_html)
            bad_path = Path(f.name)
        try:
            valid, issues = insights_main.verify_html(bad_path, root=ROOT, check_browser=False)
            self.assertFalse(valid)
            self.assertTrue(any('Expected 13 slides' in s for s in issues))
        finally:
            bad_path.unlink(missing_ok=True)

        # Mutated HTML with removed metric term in header
        with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write("<section class='slide'><th>제품평균</th></section>")
            bad_path2 = Path(f.name)
        try:
            valid, issues = insights_main.verify_html(bad_path2, root=ROOT, check_browser=False)
            self.assertFalse(valid)
            self.assertTrue(any('제품평균' in s for s in issues))
        finally:
            bad_path2.unlink(missing_ok=True)

    def test_fixture_pipeline_execution_and_invariants(self):
        if not FIXTURE_COMMON.exists() or not FIXTURE_PRODUCTS.exists():
            self.skipTest("Sample fixtures not found on disk")

        # Create isolated test root so actual project data/latest-run.json is untouched
        temp_dir = tempfile.mkdtemp(prefix='insights-isolated-root-')
        test_root = Path(temp_dir).resolve()

        # Setup minimal isolated tree
        (test_root / 'data/blog_performance/insights').mkdir(parents=True, exist_ok=True)
        (test_root / 'data/blog_performance').mkdir(parents=True, exist_ok=True)
        (test_root / 'services/blog_performance/insights').mkdir(parents=True, exist_ok=True)
        (test_root / 'worker-control/dispatch/tasks').mkdir(parents=True, exist_ok=True)

        # Copy essential reference data files
        shutil.copyfile(ROOT / 'services/blog_performance/product-search-catalog.json',
                        test_root / 'services/blog_performance/product-search-catalog.json')
        shutil.copyfile(ROOT / 'data/blog_performance/blog-directory.json',
                        test_root / 'data/blog_performance/blog-directory.json')
        if (ROOT / 'worker-control/dispatch-presets.json').exists():
            shutil.copyfile(ROOT / 'worker-control/dispatch-presets.json',
                            test_root / 'worker-control/dispatch-presets.json')

        # Copy prior browser search fixtures to isolated root for local term cache reuse
        fixture_dir = ROOT / 'data/blog_performance/browser-search/20261022-common-ea7fdc3e9b'
        if fixture_dir.exists():
            shutil.copytree(fixture_dir, test_root / 'data/blog_performance/browser-search/20261022-common-ea7fdc3e9b')

        prod_fixture_dir = ROOT / 'data/blog_performance/browser-search/20261022-products-ko-419ff665f1'
        if prod_fixture_dir.exists():
            shutil.copytree(prod_fixture_dir, test_root / 'data/blog_performance/browser-search/20261022-products-ko-419ff665f1')

        sample_eq = ROOT / f'data/blog_performance/product-search/{insights_main.ACTIVITY_SAMPLE_ID}/relevance-review/body-review/brand-only-review/web-research/equipment-research.json'
        if sample_eq.exists():
            dest = test_root / f'data/blog_performance/product-search/{insights_main.ACTIVITY_SAMPLE_ID}/relevance-review/body-review/brand-only-review/web-research/equipment-research.json'
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(sample_eq, dest)

        test_rid = "INSIGHTS-UNITTEST-ISOLATED"
        run_dir = test_root / 'data/blog_performance/insights' / test_rid

        real_latest_pointer = ROOT / 'data/blog_performance/insights/latest-run.json'
        real_ptr_before = real_latest_pointer.read_bytes() if real_latest_pointer.exists() else None

        try:
            # Network guard: verify zero outbound HTTP calls in offline mode
            with patch('urllib.request.urlopen', side_effect=fail_on_network):

                # 1. Prepare run (idempotent check)
                prep1 = insights_main.prepare_run(test_rid, root=test_root)
                self.assertEqual(prep1['status'], 'prepared')
                self.assertEqual(prep1['panel_queries'], 34)

                # Calling prepare again on existing run must NOT overwrite state
                prep2 = insights_main.prepare_run(test_rid, root=test_root)
                self.assertTrue(prep2.get('resumed'))
                self.assertEqual(prep2['status'], 'prepared')

                # 2. Status check
                stat = insights_main.get_status(test_rid, root=test_root)
                self.assertEqual(stat['stage'], 'prepared')
                self.assertEqual(stat['steps']['query_panel_ready'], True)
                self.assertEqual(stat['steps']['preflight']['status'], 'passed')

                # 3. Execution lock check
                lock_file = run_dir / '.execution.lock'
                insights_main.save_json(lock_file, {'pid': 99999, 'locked_at': '2099-01-01T00:00:00+00:00'})
                lock_res = insights_main.run_pipeline(run_id=test_rid, offline=True, root=test_root)
                self.assertEqual(lock_res['status'], 'locked')
                lock_file.unlink(missing_ok=True)

                # 4. Run pipeline end-to-end with fixtures
                res = insights_main.run_pipeline(
                    run_id=test_rid,
                    common_json=FIXTURE_COMMON,
                    products_json=FIXTURE_PRODUCTS,
                    ai_decisions=FIXTURE_AI_DECISIONS if FIXTURE_AI_DECISIONS.exists() else None,
                    offline=True,
                    root=test_root
                )
                self.assertEqual(res['status'], 'completed')
                self.assertTrue(res['activated'])
                self.assertTrue((run_dir / 'report.html').exists())
                self.assertTrue((run_dir / 'common/top5-audit.json').exists())

                # 5. Check isolated latest-run pointer vs real root pointer
                isolated_pointer = test_root / 'data/blog_performance/insights/latest-run.json'
                self.assertTrue(isolated_pointer.exists())
                ptr_data = insights_main.read_json(isolated_pointer)
                self.assertEqual(ptr_data['run_id'], test_rid)

                # REAL project root pointer MUST remain untouched!
                real_ptr_after = real_latest_pointer.read_bytes() if real_latest_pointer.exists() else None
                self.assertEqual(real_ptr_before, real_ptr_after, "Real project latest-run.json was modified!")

                # 6. QA failure safety invariant: verification failure leaves pointer unchanged
                isolated_ptr_saved = isolated_pointer.read_bytes()
                mutated_html = run_dir / 'bad_report.html'
                mutated_html.write_text("<html><body>bad</body></html>", encoding='utf-8')
                valid, issues = insights_main.verify_html(mutated_html, root=test_root, check_browser=False)
                self.assertFalse(valid)
                # Pointer remains unchanged
                self.assertEqual(isolated_pointer.read_bytes(), isolated_ptr_saved)

                # 7. Resuming completed run is idempotent
                res2 = insights_main.run_pipeline(run_id=test_rid, offline=True, root=test_root)
                self.assertEqual(res2['status'], 'completed')

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
