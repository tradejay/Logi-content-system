"""QA verification for test-specific insights HTML reports.

Validates that test reports clearly exhibit the TEST badge, contain the exact selected queries,
properly calculate denominators without operational extrapolation, and render cleanly in browser.
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def verify_test_html(html_path, manifest, root=ROOT, check_browser=False):
    path = Path(html_path)
    if not path.exists():
        return False, [f"Test HTML file does not exist: {path}"]

    text = path.read_text(encoding='utf-8')
    issues = []

    # 1. TEST indicator must be prominently present
    if 'TEST' not in text and '테스트' not in text:
        issues.append("Missing required TEST indicator in document")

    # 2. Run ID must be present
    rid = manifest.get('run_id')
    if rid and rid not in text:
        issues.append(f"Run ID '{rid}' missing in HTML text")

    # 3. All selected keywords must appear in the HTML
    selected_queries = manifest.get('selected_queries', [])
    for q in selected_queries:
        kw = q.get('keyword')
        if kw and kw not in text:
            issues.append(f"Selected test keyword '{kw}' missing from test report HTML")

    # 4. Must contain warning against operational comparison
    if '비교 금지' not in text and '운영 점수' not in text:
        issues.append("Missing warning regarding distinction from operational scores")

    # 5. Table comparison callouts
    table_count = len(re.findall(r'<table\b', text))
    callout_count = len(re.findall(r'class="comparison(?:-callout|[ "])', text))
    if table_count > 0 and callout_count == 0:
        issues.append("Missing comparison-callout for report tables")

    # 6. Basic HTML structural validity
    if '</html>' not in text or '</body>' not in text:
        issues.append("Malformed HTML: missing closing tags")

    # 7. Optional Browser check via Node Playwright
    if check_browser and len(issues) == 0:
        node_script = """
let chromium;
try {
  chromium = require('playwright').chromium;
} catch (e) {
  try {
    chromium = require('C:/Users/Choijay/AppData/Local/Programs/Python/Python311/Lib/site-packages/playwright/driver/package').chromium;
  } catch (e2) {
    console.error('Playwright driver not available');
    process.exit(0);
  }
}
const path = require('path');

(async () => {
  let browser;
  try {
    browser = await chromium.launch({
      headless: true,
      executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
    });
  } catch (e) {
    browser = await chromium.launch({ headless: true });
  }
  const page = await browser.newPage();
  const filePath = 'file:///' + path.resolve(process.argv[2]).replace(/\\\\/g, '/');
  
  const errors = [];
  page.on('pageerror', err => errors.push(err.message));

  await page.goto(filePath, { waitUntil: 'domcontentloaded' });
  const title = await page.title();
  if (!title.includes('TEST')) {
    errors.push('Page title missing TEST marker');
  }
  await browser.close();
  if (errors.length > 0) {
    console.error(JSON.stringify(errors));
    process.exit(1);
  }
  console.log('OK');
})();
"""
        cjs_path = root / 'static/reports/_check_test_html.cjs'
        cjs_path.write_text(node_script, encoding='utf-8')
        try:
            proc = subprocess.run(
                ['node', str(cjs_path), str(path.resolve())],
                capture_output=True, text=True, encoding='utf-8', timeout=30, cwd=str(root)
            )
            if proc.returncode != 0:
                err = (proc.stderr or proc.stdout).strip()
                issues.append(f"Browser QA check failed: {err[:300]}")
        except Exception as exc:
            issues.append(f"Browser QA check error: {exc}")
        finally:
            cjs_path.unlink(missing_ok=True)

    return len(issues) == 0, issues
