"""Offline inventory/checks only; never dispatch, collect, or change active pointers."""
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from scripts.search_report_room_groups import grouped_report

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    out = ROOT / 'audit/blog-insights-pipeline-20261023'
    out.mkdir(parents=True, exist_ok=True)
    checks, panels, sources = [], [], {}

    def check(name, passed, detail):
        checks.append({'check': name, 'passed': bool(passed), 'detail': detail})

    catalog = read(ROOT / 'services/blog_performance/product-search-catalog.json')
    historical = ROOT / 'data/blog_performance/product-search/20261021T054347Z'
    check('catalog_consistency', catalog == read(historical / 'catalog.json'), 'Current catalog versus saved catalog used by matching')
    groups = {p['product_id']: p['group'] for p in grouped_report({'products': catalog})['products']}
    for mode, pointer_name in [('common', 'latest-common.json'), ('products', 'latest-products-ko.json')]:
        pointer = read(ROOT / 'data/blog_performance/browser-search' / pointer_name)
        report_path = ROOT / pointer['report']
        base = report_path.parent.parent
        raw_path = base / 'input.json'
        raw, report = read(raw_path), read(report_path)
        sha = hashlib.sha256(raw_path.read_bytes()).hexdigest()
        check(mode + '_raw_hash', sha == pointer['raw_sha256'], str(raw_path.relative_to(ROOT)))
        check(mode + '_surface', report['search_surface'] == 'naver_blog_tab', report['search_surface'])
        flat = [h for q in raw['results'] for h in q['rows']]
        check(mode + '_row_count', len(flat) == raw['total'], len(flat))
        check(mode + '_unique_urls', len({h['url'] for h in flat}) == raw['uniqueCount'], raw['uniqueCount'])
        check(mode + '_rank_sequence', all([h['rank'] for h in q['rows']] == list(range(1, len(q['rows'])+1)) for q in raw['results']), 'Original sequence; no reranking')
        bodies = read(base / 'body-analysis/bodies.json')
        check(mode + '_body_coverage', len(bodies) == raw['uniqueCount'], len(bodies))
        check(mode + '_body_files', all((ROOT / b['body_file']).is_file() or (historical / 'relevance-review' / b['body_file']).is_file() for b in bodies if b['status'] == 'success'), 'Resolve current workspace paths and historical body-review-relative paths')
        sources[mode] = {'report': str(report_path.relative_to(ROOT)), 'queries': len(raw['results']), 'rows': len(flat), 'unique_posts': raw['uniqueCount'], 'capture_times': [q['capturedAt'] for q in raw['results']], 'body_success': sum(b['status'] == 'success' for b in bodies), 'body_failed': sum(b['status'] != 'success' for b in bodies)}
        for q in raw['results']:
            product = next((p for p in catalog if q['keyword'] in p['queries']), None)
            panels.append({'panel': mode, 'keyword': q['keyword'], 'search_url': 'https://search.naver.com/search.naver?' + urlencode({'ssc': 'tab.blog.all', 'sm': 'tab_jum', 'query': q['keyword']}), 'captured_search_url': q['searchUrl'], 'product_id': product['product_id'] if product else '', 'report_group': groups[product['product_id']] if product else 'common', 'captured_rows': len(q['rows']), 'captured_at': q['capturedAt']})
    check('query_panel_size', len(panels) == 34 and len({p['keyword'] for p in panels}) == 34, '7 common + 27 Korean product queries')
    check('company_directory', len(read(ROOT / 'data/blog_performance/blog-directory.json')['blogs']) == 36, 'User-provided labels; IDs stay separate')
    expected_html = ROOT / 'static/reports/blog-search-insights-20261022.html'
    check('configured_html_exists', expected_html.is_file(), str(expected_html.relative_to(ROOT)))
    html_path = expected_html if expected_html.exists() else ROOT / 'static/reports/blog-search-insights-3차.html'
    html = html_path.read_text(encoding='utf-8')
    sources['html'] = str(html_path.relative_to(ROOT))
    check('html_page_count', html.count('<section class="slide">') == 13, html.count('<section class="slide">'))
    qa = read(ROOT / 'static/reports/_qa/blog-insights-check.json')
    check('last_browser_qa', qa['pages'] == 13 and not qa['errors'], 'Stored QA; not a new browser or live rank check')
    result = {'checked_at': datetime.now(timezone.utc).isoformat(), 'mode': 'offline_read_only_audit', 'live_collection': False, 'sources': sources, 'checks': checks, 'all_snapshot_checks_passed': all(c['passed'] for c in checks), 'search_panel': panels}
    (out / 'inventory.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    with (out / 'search-panel.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(panels[0])); writer.writeheader(); writer.writerows(panels)
    print(json.dumps({'checks': len(checks), 'failed': [c for c in checks if not c['passed']], 'queries': len(panels), 'sources': sources, 'output': str(out.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == '__main__':
    main()
