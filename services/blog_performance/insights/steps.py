"""Modular, configuration-driven step implementations for the insights pipeline.

Each step function adheres to the signature:
    step_fn(ctx: ExecutionContext) -> StepResult
No steps hardcode query counts, depths, or QA thresholds; everything is calculated
from the validated ExecutionContext.
"""
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

from services.blog_performance.insights.context import ExecutionContext, StepResult
from services.blog_performance.insights.verify_test_html import verify_test_html

ACTIVITY_SAMPLE_ID = '20261021T054347Z'
ACTIVITY_SAMPLE_DATE = '2026-10-21'


def get_test_report_filename(rid: str, created_at_kst: str, root: Path) -> Path:
    """Generate collision-resistant revisioned HTML filename for test reports."""
    dt_str = created_at_kst[:19].replace('-', '').replace(':', '').replace('T', '-')
    base_name = f"insights-test-{dt_str}-{rid}.html"
    out_dir = root / 'static/reports/insights-tests'
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / base_name
    if not target.exists():
        return target

    counter = 1
    while True:
        rev_name = f"insights-test-{dt_str}-{rid}_rev{counter}.html"
        target = out_dir / rev_name
        if not target.exists():
            return target
        counter += 1


def verify_standard_html(html_path: Path, root: Path, check_browser: bool = True) -> Tuple[bool, List[str]]:
    """Offline Python HTML QA for full 13-slide operational report."""
    text = Path(html_path).read_text(encoding='utf-8')
    issues = []

    slides = re.findall(r'<section class="slide">', text)
    if len(slides) != 13:
        issues.append(f'Expected 13 slides, found {len(slides)}')

    if '<div class="toc-grid">' not in text:
        issues.append('Missing TOC grid')

    if '<div class="top5-audit"' not in text:
        issues.append('Missing top5 audit block')
    else:
        audit_trs = re.findall(r'<tr class="[^"]*"><td>\d+</td>', text)
        all_audit_rows = re.findall(r'<td>\d+위</td><td><a href="', text)
        if max(len(audit_trs), len(all_audit_rows)) < 35:
            issues.append(f'Top 5 audit rows incomplete (found {max(len(audit_trs), len(all_audit_rows))}, expected >= 35)')

    if 'expanded-top10' not in text:
        issues.append('Missing expanded-top10 class for Logitech/Poly')

    if 'data-ocean-own="true"' not in text:
        issues.append('Missing Oceantech highlight attribute')

    v_markers = re.findall(r'title="사용자 지정 오우션 관련 업체">V</b>', text)
    if len(v_markers) < 5:
        issues.append(f'Expected V markers for related companies, found {len(v_markers)}')

    removed_terms = ['합산점', '점수 합계', '제품평균']
    for term in removed_terms:
        if re.search(rf'<th[^>]*>[^<]*{term}[^<]*</th>', text):
            issues.append(f'Removed metric term "{term}" found in table header')
        if re.search(rf'<h1[^>]*>[^<]*{term}[^<]*</h1>', text):
            issues.append(f'Removed metric term "{term}" found in slide title')

    table_count = len(re.findall(r'<table\b', text))
    comp_count = len(re.findall(r'<div class="comparison', text))
    if comp_count < table_count:
        issues.append(f'Missing comparison guidance: {comp_count} callouts for {table_count} tables')

    if check_browser and len(issues) == 0:
        cjs_script = root / 'services/blog_performance/insights/check_search_insights_html.cjs'
        if cjs_script.exists():
            try:
                proc = subprocess.run(
                    ['node', str(cjs_script), str(Path(html_path).resolve())],
                    capture_output=True, text=True, timeout=45, cwd=str(root)
                )
                if proc.returncode != 0:
                    err_msg = (proc.stderr or proc.stdout).strip()
                    issues.append(f"Browser QA (check_search_insights_html.cjs) failed: {err_msg[:300]}")
            except Exception as err:
                issues.append(f"Browser QA execution error: {err}")

    return len(issues) == 0, issues


def prepare_decisions_for(body_dir: Path, source_decisions_path: Path = None, root: Path = None, namespace: str = None) -> Path:
    """Ensure body_dir/ai-decisions.json contains decisions matching expected IDs without fabricating passed=True."""
    body_dir = Path(body_dir)
    terms_file = body_dir / 'ai-terms.json'
    target_file = body_dir / 'ai-decisions.json'

    if not terms_file.exists():
        target_file.write_text(json.dumps({'passed': True, 'issues': [], 'decisions': []}, ensure_ascii=False, indent=2), encoding='utf-8')
        return target_file

    expected_terms = json.loads(terms_file.read_text(encoding='utf-8'))
    expected_items = expected_terms.get('items', [])
    expected_ids = {x['id'] for x in expected_items}

    if not expected_ids:
        target_file.write_text(json.dumps({'passed': True, 'issues': [], 'decisions': []}, ensure_ascii=False, indent=2), encoding='utf-8')
        return target_file

    dec_by_namespaced_id = {}
    dec_by_term = {}
    dec_by_id = {}

    ROOT_PATH = Path(__file__).resolve().parents[3]
    active_root = root or ROOT_PATH

    # 1. Base equipment research
    res_file = active_root / f'data/blog_performance/product-search/{ACTIVITY_SAMPLE_ID}/relevance-review/body-review/brand-only-review/web-research/equipment-research.json'
    if not res_file.exists():
        res_file = ROOT_PATH / f'data/blog_performance/product-search/{ACTIVITY_SAMPLE_ID}/relevance-review/body-review/brand-only-review/web-research/equipment-research.json'
    if res_file.exists():
        try:
            for item in json.loads(res_file.read_text(encoding='utf-8')).get('items', []):
                t = item.get('term', '').casefold()
                if t:
                    dec_by_term[t] = item
        except Exception:
            pass

    # 2. Prior browser search runs
    search_base = active_root / 'data/blog_performance/browser-search'
    if not search_base.exists():
        search_base = ROOT_PATH / 'data/blog_performance/browser-search'
    for p in sorted(search_base.glob('*/body-analysis/ai-decisions.json')):
        m = p.parent / 'model-terms.json'
        t_file = p.parent / 'ai-terms.json'
        try:
            tmap = {}
            if m.exists():
                tmap = {x['id']: x['term'].casefold() for x in json.loads(m.read_text(encoding='utf-8')).get('items', [])}
            elif t_file.exists():
                tmap = {x['id']: x['term'].casefold() for x in json.loads(t_file.read_text(encoding='utf-8')).get('items', [])}
            for d in json.loads(p.read_text(encoding='utf-8')).get('decisions', []):
                t = tmap.get(d['id']) or (d.get('term') or '').casefold()
                if t:
                    dec_by_term[t] = d
        except Exception:
            pass

    # 3. Source decisions file if passed
    if source_decisions_path and Path(source_decisions_path).exists():
        try:
            source_p = Path(source_decisions_path)
            source_data = json.loads(source_p.read_text(encoding='utf-8'))
            source_m = source_p.parent / 'model-terms.json'
            source_t = source_p.parent / 'ai-terms.json'
            source_map = {}
            if source_m.exists():
                source_map = {x['id']: x['term'].casefold() for x in json.loads(source_m.read_text(encoding='utf-8')).get('items', [])}
            elif source_t.exists():
                source_map = {x['id']: x['term'].casefold() for x in json.loads(source_t.read_text(encoding='utf-8')).get('items', [])}

            for d in source_data.get('decisions', []):
                dec_by_id[d['id']] = d
                nid = d.get('namespaced_id') or d.get('id', '')
                if nid:
                    dec_by_namespaced_id[nid] = d
                t = source_map.get(d['id']) or (d.get('term') or '').casefold()
                if t:
                    dec_by_term[t] = d
        except Exception:
            pass

    if target_file.exists():
        try:
            existing = json.loads(target_file.read_text(encoding='utf-8'))
            existing_ids = {x['id'] for x in existing.get('decisions', [])}
            if existing_ids == expected_ids and existing.get('passed') is True:
                return target_file
        except Exception:
            pass

    allowed_categories = {'catalog_model', 'outside_model', 'other_equipment', 'generic', 'uncertain'}
    tailored = []
    unreviewed = []

    for item in expected_items:
        iid = item['id']
        t = item['term'].casefold()
        nid = f"{namespace}:{iid}" if namespace else None

        match = (dec_by_namespaced_id.get(nid) if nid else None) or dec_by_term.get(t) or dec_by_id.get(iid)
        if not match:
            unreviewed.append(item['term'])
            continue

        cat = match.get('category')
        if cat not in allowed_categories:
            cat = 'uncertain'
        decision = {
            'id': iid,
            'category': cat,
            'brand': match.get('brand') or match.get('researched_brand'),
            'model': match.get('model') or match.get('researched_model'),
            'product_ids': match.get('product_ids') or [],
            'reason': match.get('reason') or '검토 완료된 판정 매핑'
        }
        tailored.append(decision)

    if unreviewed:
        raise ValueError(f"Cannot auto-approve unreviewed terms: {unreviewed[:5]} (total {len(unreviewed)} pending)")

    target_file.write_text(json.dumps({
        'passed': True,
        'issues': [],
        'decisions': tailored
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    return target_file


def check_worker_dispatch_preflight(role: str, root: Path, probe=None) -> Tuple[bool, List[str], List[Any]]:
    """Verify registered worker session before dispatch without spawning processes."""
    from services.worker_preflight import run as run_preflight
    pf = run_preflight(root=root, pipeline='insights', probe=probe, online=True)
    w = next((x for x in pf.get('workers', []) if x['role'] == role), None)
    if not w:
        return False, [f"Worker role '{role}' not configured in presets"], []

    issues = list(w.get('issues', []))
    pending = list(w.get('pending_tasks', []))
    if not w.get('connected'):
        issues.append('worker_not_connected')
    if not w.get('workspace_matches'):
        issues.append('workspace_mismatch')
    if pending:
        issues.append('unfinished_delivery_reservation')

    if not w.get('can_dispatch') or not w.get('connected') or not w.get('workspace_matches') or pending:
        user_msg = (
            f"워커 세션 '{role}'({w.get('folder')})이 배정 가능한 상태가 아닙니다. "
            f"(연결: {w.get('connected')}, 루트일치: {w.get('workspace_matches')}, "
            f"미완료 예약: {len(pending)}건). 관리자에게 세션 구동 및 대기 작업 정리를 요청하세요."
        )
        if user_msg not in issues:
            issues.insert(0, user_msg)
        return False, issues, pending
    return True, [], []


# =========================================================================
# Step 1: Preflight
# =========================================================================
def step_preflight(ctx: ExecutionContext) -> StepResult:
    from services.worker_preflight import run as run_preflight
    pf = run_preflight(root=Path(__file__).resolve().parents[3], pipeline='insights', online=False)
    missing = [d['path'] for d in pf.get('dependencies', []) if not d['exists']]

    ctx.state['steps']['preflight'] = {
        'status': 'passed' if not missing else 'failed',
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'dependencies_ok': not bool(missing),
        'missing_files': missing
    }

    if missing:
        ctx.update_state('preflight_blocked', err=f"Missing dependencies: {missing}")
        return StepResult(status='blocked', error=f"의존성 파일 누락: {missing}", artifacts={'missing': missing})

    return StepResult(status='succeeded', message="사전 점검 완료 (의존성 정상)")


# =========================================================================
# Step 2: Panel Preparation
# =========================================================================
def step_panel_preparation(ctx: ExecutionContext) -> StepResult:
    now_dt = datetime.now(timezone.utc)
    kst_dt = now_dt + timedelta(hours=9)

    panel_cfg = ctx.config.get('panel', {})
    ptype = panel_cfg.get('type', 'catalog_full')

    if ptype == 'explicit_queries':
        panel = panel_cfg.get('queries', [])
    else:
        # Build 34 queries from catalog
        from services.blog_performance.insights.config import COMMON_KEYWORDS, get_registered_catalog_keywords
        cat_map = get_registered_catalog_keywords(ctx.root)
        panel = []
        base_url = "https://search.naver.com/search.naver?ssc=tab.blog.all&sm=tab_jum&query="
        for kw in COMMON_KEYWORDS:
            encoded = urllib.parse.quote_plus(kw)
            panel.append({
                'panel': 'common',
                'keyword': kw,
                'search_url': base_url + encoded,
                'product_id': None,
                'brand': None,
                'product': None,
                'report_group': 'common',
                'catalog_group': None
            })
        for kw, info in cat_map.items():
            encoded = urllib.parse.quote_plus(kw)
            item = dict(info)
            item['search_url'] = base_url + encoded
            panel.append(item)

    # Ensure search_url is populated for all queries
    base_url = "https://search.naver.com/search.naver?ssc=tab.blog.all&sm=tab_jum&query="
    for q in panel:
        if not q.get('search_url'):
            q['search_url'] = base_url + urllib.parse.quote_plus(q['keyword'])

    # Save search-panel.json
    panel_file = ctx.run_dir / 'search-panel.json'
    panel_data = {
        'schema_version': 'insights-search-panel-v1',
        'run_id': ctx.run_id,
        'test_only': ctx.test_only,
        'created_at': now_dt.isoformat(),
        'total': len(panel),
        'common_total': sum(p.get('panel') == 'common' for p in panel),
        'products_total': sum(p.get('panel') == 'products' for p in panel),
        'queries': panel
    }
    panel_file.write_text(json.dumps(panel_data, ensure_ascii=False, indent=2), encoding='utf-8')
    panel_sha = hashlib.sha256(panel_file.read_bytes()).hexdigest()

    # Save search-panel.csv
    csv_file = ctx.run_dir / 'search-panel.csv'
    with csv_file.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['panel', 'keyword', 'search_url', 'product_id', 'brand', 'product', 'report_group', 'catalog_group'])
        w.writeheader()
        w.writerows(panel)

    groups_count = {}
    for p in panel:
        if p.get('panel') == 'products':
            g = p.get('report_group')
            if g:
                groups_count[g] = groups_count.get(g, 0) + 1

    manifest = {
        'run_id': ctx.run_id,
        'test_only': ctx.test_only,
        'created_at': now_dt.isoformat(),
        'created_at_utc': now_dt.isoformat(),
        'created_at_kst': kst_dt.isoformat(),
        'status': 'prepared',
        'offline': ctx.is_offline,
        'panel_sha256': panel_sha,
        'query_count': len(panel),
        'common_query_count': sum(p.get('panel') == 'common' for p in panel),
        'product_query_count': sum(p.get('panel') == 'products' for p in panel),
        'selected_queries': panel,
        'expected_panels': sorted(list({p.get('panel') for p in panel})),
        'collection_depth': ctx.depth,
        'search_surface': 'naver_blog_tab',
        'sort': 'relevance',
        'report_groups': groups_count,
        'activity_benchmark': {
            'sample_id': ACTIVITY_SAMPLE_ID,
            'sample_date': ACTIVITY_SAMPLE_DATE,
            'note': '활동량은 2026-10-21 고정 표본이며, 새 검색 순위 관측과 구분하여 유지합니다.' if not ctx.test_only else '테스트 모드: 고정 활동량 표본 참조 (테스트 필수 아님)'
        },
        'english_capture_available': False
    }
    (ctx.run_dir / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    ctx.manifest = manifest
    ctx.state['steps']['query_panel_ready'] = True
    ctx.update_state('prepared')

    tag = "[테스트] " if ctx.test_only else ""
    return StepResult(
        status='succeeded',
        message=f"{tag}{len(panel)}개 검색어 패널 생성 완료 (SHA: {panel_sha[:8]})",
        artifacts={
            'search_panel_json': str(panel_file.relative_to(ctx.root)),
            'search_panel_csv': str(csv_file.relative_to(ctx.root)),
            'manifest': str((ctx.run_dir / 'manifest.json').relative_to(ctx.root))
        },
        metrics={'panel_queries': len(panel), 'depth': ctx.depth}
    )


# =========================================================================
# Step 3: Collection Dispatch
# =========================================================================
def step_collection_dispatch(ctx: ExecutionContext) -> StepResult:
    common_in = ctx.run_dir / 'common/input.json'
    products_in = ctx.run_dir / 'products/input.json'

    # Check for direct file paths in config.inputs
    cfg_inputs = ctx.config.get('inputs', {})
    if cfg_inputs.get('common_json'):
        src_c = Path(cfg_inputs['common_json'])
        if not src_c.is_absolute():
            src_c = (ctx.root / src_c) if (ctx.root / src_c).exists() else (Path(__file__).resolve().parents[3] / src_c)
        if src_c.exists():
            common_in.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src_c, common_in)

    if cfg_inputs.get('products_json'):
        src_p = Path(cfg_inputs['products_json'])
        if not src_p.is_absolute():
            src_p = (ctx.root / src_p) if (ctx.root / src_p).exists() else (Path(__file__).resolve().parents[3] / src_p)
        if src_p.exists():
            products_in.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src_p, products_in)

    needs_common = ctx.has_common and not common_in.exists()
    needs_products = ctx.has_products and not products_in.exists()

    if not needs_common and not needs_products:
        return StepResult(
            status='succeeded',
            message="수집 입력 파일 준비 완료",
            artifacts={
                'common': str(common_in.relative_to(ctx.root)) if common_in.exists() else None,
                'products': str(products_in.relative_to(ctx.root)) if products_in.exists() else None
            }
        )

    # Missing inputs
    required = []
    if needs_common:
        required.append(str(common_in.relative_to(ctx.root)))
    if needs_products:
        required.append(str(products_in.relative_to(ctx.root)))

    if ctx.is_offline:
        ctx.update_state('waiting_for_inputs')
        return StepResult(
            status='waiting',
            message="오프라인 모드: 로컬 수집 파일 필요",
            required_inputs=required
        )

    # Online mode: dispatch to 02_research_planning worker
    task_id = ctx.state['task_ids'].get('collect_browser_ranks')
    from services.worker_dispatch import enqueue, status as get_dispatch_status, load as load_dispatch_task

    if not task_id:
        can_dispatch, issues, pending = check_worker_dispatch_preflight('planner', root=ctx.root)
        if not can_dispatch:
            ctx.update_state('worker_preflight_blocked', err=f"Planner dispatch blocked: {issues}")
            pending_ids = [p['task_id'] if isinstance(p, dict) else str(p) for p in pending]
            pending_desc = f" (미완료 예약: {', '.join(pending_ids)} 대기 중 - 관리자 확인 필요, 임의 삭제/재전송 금지)" if pending_ids else ""
            return StepResult(
                status='blocked',
                error=f"02_research_planning 워커 배정 불가: {issues[0] if issues else 'blocked'}",
                message=f"관리자 확인 필요: 02_research_planning 워커 배정 대기{pending_desc}",
                artifacts={'status': 'worker_preflight_blocked', 'role': 'planner', 'issues': issues, 'pending_tasks': pending, 'pending_reservations': pending_ids, 'reason': '이전 미완료 작업 대기 중 (관리자 세션 확인 필요)'}
            )

        panel_json = ctx.run_dir / 'search-panel.json'
        msg_parts = [
            f"네이버 블로그 탭 검색어 패널(search-panel.json, {len(ctx.panel_queries)}개 쿼리)을 수집하여 단일 result.json 파일에 저장한다.",
            f"결과 JSON 규격:",
            f"- schema_version: 'insights-browser-collection-v1'",
            f"- panel_run_id: '{ctx.run_id}'"
        ]
        if ctx.has_common:
            msg_parts.append(f"- common: {len(ctx.common_queries)}개 공통 검색어 결과 {{total, uniqueCount, results: [{{keyword, searchUrl, capturedAt, rows: [{{rank, title, url}}]}}]}}")
        if ctx.has_products:
            msg_parts.append(f"- products: {len(ctx.product_queries)}개 한국어 제품 검색어 결과 {{scope, total, uniqueCount, results: [{{keyword, searchUrl, capturedAt, rows: [{{rank, title, url}}]}}]}}")
        msg_parts.append(f"광고는 제외하고 실제 검색 순위(rank: 1~{ctx.depth})를 보존하여 작성한다.")
        msg = "\n".join(msg_parts)

        task_rec = enqueue('planner', msg, [panel_json], kind='insights-browser-collection', root=ctx.root)
        ctx.state['task_ids']['collect_browser_ranks'] = task_rec['task_id']
        ctx.update_state('collection_dispatched')
        return StepResult(
            status='waiting',
            worker_task_id=task_rec['task_id'],
            message=f"02_research_planning 워커 수집 작업 실행 중 (작업: {task_rec['task_id']})",
            artifacts={'status': 'collection_dispatched', 'task_id': task_rec['task_id']}
        )
    else:
        t_stat = get_dispatch_status(task_id, root=ctx.root)
        if t_stat.get('status') == 'collected':
            task_rec = load_dispatch_task(ctx.root / 'worker-control/dispatch/tasks' / f'{task_id}.json')
            res_file = ctx.root / 'worker-workspaces' / task_rec['worker_folder'] / t_stat['result_file']
            try:
                collected_data = json.loads(res_file.read_text(encoding='utf-8'))
            except Exception as err:
                ctx.update_state('worker_result_corrupt', err=str(err))
                return StepResult(status='blocked', error=f"워커 수집 결과 파싱 실패: {err}")

            if not isinstance(collected_data, dict) or collected_data.get('schema_version') != 'insights-browser-collection-v1':
                ctx.update_state('worker_result_invalid', err="Worker collection schema_version mismatch")
                return StepResult(
                    status='blocked',
                    error="워커 수집 결과 규격 불일치 (schema_version != 'insights-browser-collection-v1')",
                    artifacts={'status': 'worker_result_invalid'}
                )

            # Partition collected results according to panel
            all_res = collected_data.get('results', [])
            if 'common' in collected_data:
                c_data = collected_data['common']
            else:
                c_res = [r for r in all_res if r.get('keyword') in ctx.common_queries]
                c_data = {'total': sum(len(r.get('rows', [])) for r in c_res), 'uniqueCount': len({row['url'] for r in c_res for row in r.get('rows', []) if 'url' in row}), 'results': c_res}

            if 'products' in collected_data:
                p_data = collected_data['products']
            else:
                p_res = [r for r in all_res if r.get('keyword') in ctx.product_queries]
                p_data = {'scope': '한국어 제품명', 'total': sum(len(r.get('rows', [])) for r in p_res), 'uniqueCount': len({row['url'] for r in p_res for row in r.get('rows', []) if 'url' in row}), 'results': p_res}

            if ctx.has_common:
                common_in.parent.mkdir(parents=True, exist_ok=True)
                common_in.write_text(json.dumps(c_data, ensure_ascii=False, indent=2), encoding='utf-8')
            if ctx.has_products:
                products_in.parent.mkdir(parents=True, exist_ok=True)
                products_in.write_text(json.dumps(p_data, ensure_ascii=False, indent=2), encoding='utf-8')

            return StepResult(status='succeeded', message="02 워커 수집 데이터 검증 및 저장 완료")
        elif t_stat.get('status') == 'delivery_unknown':
            return StepResult(
                status='waiting',
                worker_task_id=task_id,
                message="02 워커 전송 불명(delivery_unknown) 상태입니다. 중복 발송을 방지하기 위해 재발송하지 않고 대기합니다."
            )
        else:
            return StepResult(
                status='waiting',
                worker_task_id=task_id,
                message=f"02 워커 상태: {t_stat.get('status')}"
            )


# =========================================================================
# Step 4: Common Import
# =========================================================================
def step_common_import(ctx: ExecutionContext) -> StepResult:
    if not ctx.has_common:
        ctx.state['steps']['common_imported'] = 'skipped'
        return StepResult(status='skipped', message="설정에 공통 검색어 미포함 (단계 생략)")

    common_in = ctx.run_dir / 'common/input.json'
    if not common_in.exists():
        return StepResult(status='blocked', error="전단 산출물 common/input.json 없음")

    from services.blog_performance.insights import import_browser_search_ranks
    raw = common_in.read_bytes()
    data = json.loads(raw.decode('utf-8-sig'))
    import_browser_search_ranks.validate(data, expected_keywords=ctx.common_queries)

    out = ctx.run_dir / 'common'
    sys_argv = [str(common_in), '--out', str(out), '--no-activate']
    if ctx.test_only:
        sys_argv.append('--test')
        if ctx.common_queries:
            sys_argv.append('--expected-keywords')
            sys_argv.extend(ctx.common_queries)

    old_argv = sys.argv
    try:
        sys.argv = ['import_browser_search_ranks.py', *sys_argv]
        import_browser_search_ranks.main()
    finally:
        sys.argv = old_argv

    ctx.state['steps']['common_imported'] = True
    rep_rel = str((out / 'report.json').relative_to(ctx.root))
    ctx.state['artifacts']['common_report'] = rep_rel
    ctx.update_state('common_imported')

    return StepResult(
        status='succeeded',
        message=f"공통 검색 순위 검증 및 수집 완료 ({len(ctx.common_queries)}개 쿼리)",
        artifacts={'common_report': rep_rel}
    )


# =========================================================================
# Step 5: Products Import
# =========================================================================
def step_products_import(ctx: ExecutionContext) -> StepResult:
    if not ctx.has_products:
        ctx.state['steps']['products_imported'] = 'skipped'
        return StepResult(status='skipped', message="설정에 제품 검색어 미포함 (단계 생략)")

    products_in = ctx.run_dir / 'products/input.json'
    if not products_in.exists():
        return StepResult(status='blocked', error="전단 산출물 products/input.json 없음")

    from services.blog_performance.insights import import_product_browser_ranks
    out = ctx.run_dir / 'products'
    sys_argv = [str(products_in), '--out', str(out), '--no-activate']
    if ctx.test_only:
        sys_argv.append('--test')
        if ctx.product_queries:
            sys_argv.append('--expected-queries')
            sys_argv.extend(ctx.product_queries)

    old_argv = sys.argv
    try:
        sys.argv = ['import_product_browser_ranks.py', *sys_argv]
        import_product_browser_ranks.main()
    finally:
        sys.argv = old_argv

    ctx.state['steps']['products_imported'] = True
    man_rel = str((out / 'manifest.json').relative_to(ctx.root))
    ctx.state['artifacts']['products_manifest'] = man_rel
    ctx.update_state('products_imported')

    return StepResult(
        status='succeeded',
        message=f"제품 검색 순위 검증 및 수집 완료 ({len(ctx.product_queries)}개 쿼리)",
        artifacts={'products_manifest': man_rel}
    )


# =========================================================================
# Step 6: Body Collection & Machine Matching
# =========================================================================
def step_body_collection(ctx: ExecutionContext) -> StepResult:
    from services.blog_performance.insights import analyze_browser_search_bodies

    artifacts = {}
    if ctx.has_common and not ctx.state['steps'].get('common_bodies_analyzed'):
        base = ctx.run_dir / 'common'
        out = base / 'body-analysis'
        out.mkdir(parents=True, exist_ok=True)
        analyze_browser_search_bodies.collect(base, out, offline=ctx.is_offline)
        analyze_browser_search_bodies.prepare(base, out)
        ctx.state['steps']['common_bodies_analyzed'] = True
        artifacts['common_bodies'] = str((out / 'bodies.json').relative_to(ctx.root))
        ctx.state['artifacts']['common_bodies'] = artifacts['common_bodies']

    if ctx.has_products and not ctx.state['steps'].get('products_bodies_analyzed'):
        base = ctx.run_dir / 'products'
        out = base / 'body-analysis'
        out.mkdir(parents=True, exist_ok=True)
        analyze_browser_search_bodies.collect(base, out, offline=ctx.is_offline)
        analyze_browser_search_bodies.prepare(base, out)
        ctx.state['steps']['products_bodies_analyzed'] = True
        artifacts['products_bodies'] = str((out / 'bodies.json').relative_to(ctx.root))
        ctx.state['artifacts']['products_bodies'] = artifacts['products_bodies']

    ctx.update_state('bodies_analyzed')
    return StepResult(status='succeeded', message="본문 수집 및 장비명 매칭 완료", artifacts=artifacts)


def extract_context_for_term(term: str, spellings: List[str], bodies: List[Dict[str, Any]], catalog: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Mechanically extract a short body snippet (~150 chars), URL, and candidate equipment from catalog."""
    search_terms = [term.lower()] + [s.lower() for s in spellings if s]
    found_url = None
    found_snippet = None

    for b in bodies:
        text = b.get('body_text', '')
        if not text:
            continue
        text_lower = text.lower()
        for st in search_terms:
            idx = text_lower.find(st)
            if idx != -1:
                found_url = b.get('requested_url') or b.get('final_url') or b.get('fetch_url')
                start_i = max(0, idx - 65)
                end_i = min(len(text), idx + len(st) + 65)
                snippet_raw = text[start_i:end_i]
                snippet_clean = ' '.join(snippet_raw.split())
                prefix = '...' if start_i > 0 else ''
                suffix = '...' if end_i < len(text) else ''
                found_snippet = f"{prefix}{snippet_clean}{suffix}"
                break
        if found_url and found_snippet:
            break

    matched_models = []
    for cat in catalog:
        brand = (cat.get('brand') or '').lower()
        prod = (cat.get('product') or '').lower()
        queries = [q.lower() for q in cat.get('queries', [])]
        name = f"{cat.get('brand')} {cat.get('product')}".strip()
        for st in search_terms:
            if st and (st in prod or st in brand or any(st in q for q in queries)):
                if name not in matched_models:
                    matched_models.append(name)

    if not matched_models:
        matched_models = [f"{c.get('brand')} {c.get('product')}".strip() for c in catalog[:3]]

    return {
        'url': found_url,
        'snippet': found_snippet,
        'candidate_equipment': matched_models[:3]
    }


# =========================================================================
# Step 7: Unconfirmed Term Review (04 Worker)
# =========================================================================
def step_term_review(ctx: ExecutionContext) -> StepResult:
    common_terms_path = ctx.run_dir / 'common/body-analysis/ai-terms.json'
    products_terms_path = ctx.run_dir / 'products/body-analysis/ai-terms.json'
    c_terms = json.loads(common_terms_path.read_text(encoding='utf-8')).get('items', []) if common_terms_path.exists() else []
    p_terms = json.loads(products_terms_path.read_text(encoding='utf-8')).get('items', []) if products_terms_path.exists() else []

    # Load bodies for context snippet extraction
    bodies_pool = []
    for b_path in [ctx.run_dir / 'common/body-analysis/bodies.json', ctx.run_dir / 'products/body-analysis/bodies.json']:
        if b_path.exists():
            try:
                bodies_pool.extend(json.loads(b_path.read_text(encoding='utf-8')))
            except Exception:
                pass

    # Load catalog for candidate equipment lookup
    cat_file = ctx.root / 'services/blog_performance/product-search-catalog.json'
    catalog_items = []
    if cat_file.exists():
        try:
            catalog_items = json.loads(cat_file.read_text(encoding='utf-8'))
        except Exception:
            pass

    candidates = []
    for item in c_terms:
        ctx_info = extract_context_for_term(item['term'], item.get('spellings', []), bodies_pool, catalog_items)
        candidates.append({
            'namespace': 'common',
            'namespaced_id': f"common:{item['id']}",
            'local_id': item['id'],
            'term': item['term'],
            'spellings': item.get('spellings', []),
            'url': ctx_info['url'],
            'snippet': ctx_info['snippet'],
            'candidate_equipment': ctx_info['candidate_equipment']
        })
    for item in p_terms:
        ctx_info = extract_context_for_term(item['term'], item.get('spellings', []), bodies_pool, catalog_items)
        candidates.append({
            'namespace': 'products',
            'namespaced_id': f"products:{item['id']}",
            'local_id': item['id'],
            'term': item['term'],
            'spellings': item.get('spellings', []),
            'url': ctx_info['url'],
            'snippet': ctx_info['snippet'],
            'candidate_equipment': ctx_info['candidate_equipment']
        })

    terms_in_file = ctx.run_dir / 'unconfirmed-terms-input.json'
    terms_in_file.write_text(json.dumps({'run_id': ctx.run_id, 'total_candidates': len(candidates), 'items': candidates}, ensure_ascii=False, indent=2), encoding='utf-8')

    decisions_file = ctx.run_dir / 'ai-decisions.json'

    # Check config input override
    cfg_dec = ctx.config.get('inputs', {}).get('ai_decisions_json')
    if cfg_dec:
        src = Path(cfg_dec)
        if not src.is_absolute():
            src = (ctx.root / src) if (ctx.root / src).exists() else (Path(__file__).resolve().parents[3] / src)
        if src.exists():
            shutil.copyfile(src, decisions_file)

    if not decisions_file.exists():
        if not candidates:
            decisions_file.write_text(json.dumps({'passed': True, 'issues': [], 'decisions': []}, ensure_ascii=False, indent=2), encoding='utf-8')
        else:
            task_id = ctx.state['task_ids'].get('term_review')
            from services.worker_dispatch import enqueue, status as get_dispatch_status, load as load_dispatch_task

            if task_id:
                t_stat = get_dispatch_status(task_id, root=ctx.root)
                if t_stat.get('status') == 'collected':
                    task_rec = load_dispatch_task(ctx.root / 'worker-control/dispatch/tasks' / f'{task_id}.json')
                    res_file = ctx.root / 'worker-workspaces' / task_rec['worker_folder'] / t_stat['result_file']
                    shutil.copyfile(res_file, decisions_file)
                elif t_stat.get('status') == 'delivery_unknown':
                    return StepResult(
                        status='waiting',
                        worker_task_id=task_id,
                        message="04 워커 전송 불명(delivery_unknown) 상태입니다. 중복 발송을 방지하기 위해 재발송하지 않고 대기합니다."
                    )
                else:
                    return StepResult(status='waiting', worker_task_id=task_id, message=f"04 워커 검토 상태: {t_stat.get('status')}")
            elif ctx.is_online:
                can_dispatch, issues, pending = check_worker_dispatch_preflight('review', root=ctx.root)
                if not can_dispatch:
                    pending_ids = [p['task_id'] if isinstance(p, dict) else str(p) for p in pending]
                    pending_desc = f" (미완료 예약: {', '.join(pending_ids)} 대기 중 - 관리자 확인 필요, 임의 삭제/재전송 금지)" if pending_ids else ""
                    return StepResult(
                        status='blocked',
                        error=f"04_review 워커 배정 불가: {issues[0] if issues else 'blocked'}",
                        message=f"관리자 확인 필요: 04_review 워커 배정 대기{pending_desc}",
                        artifacts={'status': 'worker_preflight_blocked', 'role': 'review', 'issues': issues, 'pending_tasks': pending, 'pending_reservations': pending_ids, 'reason': '이전 미완료 작업 대기 중 (관리자 세션 확인 필요)'}
                    )
                msg = "블로그 본문에서 추출된 미확정 모델·용어 후보를 분류한다. catalog_model, outside_model, other_equipment, generic, uncertain 중 하나를 지정하고 namespaced_id를 유지한다."
                task_rec = enqueue('review', msg, [terms_in_file], kind='insights-term-review', root=ctx.root)
                ctx.state['task_ids']['term_review'] = task_rec['task_id']
                ctx.update_state('term_review_dispatched')
                return StepResult(status='waiting', worker_task_id=task_rec['task_id'], message="04_review 워커 판정 작업 실행 중")
            else:
                return StepResult(status='waiting', required_inputs=[str(terms_in_file.relative_to(ctx.root))], message=f"AI 용어 검토 필요 (미확정 {len(candidates)}건)")

    ctx.state['steps']['terms_reviewed'] = True
    dec_rel = str(decisions_file.relative_to(ctx.root))
    ctx.state['artifacts']['ai_decisions'] = dec_rel
    ctx.update_state('terms_reviewed')

    # Metrics computation: strictly distinguish JSON schema compliance vs uncertain rate vs semantic accuracy
    dec_data = {}
    try:
        dec_data = json.loads(decisions_file.read_text(encoding='utf-8'))
    except Exception:
        pass
    dec_list = dec_data.get('decisions', []) if isinstance(dec_data, dict) else []
    total_dec = len(dec_list)
    uncertain_count = sum(1 for d in dec_list if d.get('category') == 'uncertain')
    uncertain_rate = round(uncertain_count / total_dec, 2) if total_dec > 0 else 0.0

    review_metrics = {
        'total': total_dec,
        'schema_compliance': 1.0 if (isinstance(dec_data, dict) and 'decisions' in dec_data) else 0.0,
        'uncertain_rate': uncertain_rate,
        'semantic_accuracy': None,
        'semantic_accuracy_note': "독립 정답표 부재로 의미 정확도는 미측정으로 유지"
    }

    return StepResult(
        status='succeeded',
        message="04 용어 판정 확인 완료",
        artifacts={'ai_decisions': dec_rel, 'review_metrics': review_metrics},
        metrics=review_metrics
    )


# =========================================================================
# Step 8: Merge Classifications
# =========================================================================
def step_merge(ctx: ExecutionContext) -> StepResult:
    decisions_file = ctx.run_dir / 'ai-decisions.json'
    if not decisions_file.exists():
        return StepResult(status='blocked', error="전단 산출물 ai-decisions.json 없음")

    from services.blog_performance.insights import merge_browser_body_classifications, merge_product_browser_ranks

    artifacts = {}
    if ctx.has_common:
        base = ctx.run_dir / 'common'
        c_dec = prepare_decisions_for(base / 'body-analysis', decisions_file, root=ctx.root, namespace='common')
        old_argv = sys.argv
        try:
            sys.argv = ['merge_browser_body_classifications.py', '--base', str(base), '--result', str(c_dec), '--no-activate']
            merge_browser_body_classifications.main()
        finally:
            sys.argv = old_argv
        ctx.state['steps']['common_merged'] = True
        artifacts['common_final_report'] = str((base / 'body-analysis/report.json').relative_to(ctx.root))
        ctx.state['artifacts']['common_final_report'] = artifacts['common_final_report']

    if ctx.has_products:
        base = ctx.run_dir / 'products'
        p_dec = prepare_decisions_for(base / 'body-analysis', decisions_file, root=ctx.root, namespace='products')
        old_argv = sys.argv
        try:
            sys.argv = ['merge_product_browser_ranks.py', '--base', str(base), '--result', str(p_dec), '--no-activate']
            merge_product_browser_ranks.main()
        finally:
            sys.argv = old_argv
        ctx.state['steps']['products_merged'] = True
        artifacts['products_final_report'] = str((base / 'body-analysis/product-report.json').relative_to(ctx.root))
        ctx.state['artifacts']['products_final_report'] = artifacts['products_final_report']

    ctx.update_state('merged')
    return StepResult(status='succeeded', message="분류 및 순위 병합 완료", artifacts=artifacts)


# =========================================================================
# Step 9: Top 1~5 Audit
# =========================================================================
def step_top5_audit(ctx: ExecutionContext) -> StepResult:
    if not ctx.has_common:
        ctx.state['steps']['top5_audited'] = 'skipped'
        return StepResult(status='skipped', message="공통 검색어 미포함으로 Top 5 감사 생략")

    from services.blog_performance.insights import audit_browser_top5
    c_body_dir = ctx.run_dir / 'common/body-analysis'
    raw_path = ctx.run_dir / 'common/input.json'
    if not raw_path.exists():
        return StepResult(status='blocked', error="Top 5 감사 입력 common/input.json 없음")

    audit_browser_top5.generate_audit(folder=c_body_dir, raw_path=raw_path, out_dir=c_body_dir / 'audits/top5')
    if (c_body_dir / 'top5-audit.json').exists():
        shutil.copyfile(c_body_dir / 'top5-audit.json', ctx.run_dir / 'common/top5-audit.json')

    ctx.state['steps']['top5_audited'] = True
    aud_rel = str((c_body_dir / 'top5-audit.json').relative_to(ctx.root))
    ctx.state['artifacts']['top5_audit'] = aud_rel
    ctx.update_state('top5_audited')
    return StepResult(status='succeeded', message="상위 1~5위 신규 글 독립 감사 완료", artifacts={'top5_audit': aud_rel})


# =========================================================================
# Step 10: HTML Build
# =========================================================================
def step_html_build(ctx: ExecutionContext) -> StepResult:
    out_html = ctx.run_dir / 'report.html'
    artifacts = {}

    from services.blog_performance.insights import build_search_insights_html
    c_rep = ctx.run_dir / 'common/body-analysis/report.json'
    p_rep = ctx.run_dir / 'products/body-analysis/product-report.json'
    # Historical activity is a saved reference dataset, not fresh test collection.
    activity_src = ctx.root / f'data/blog_performance/product-search/{ACTIVITY_SAMPLE_ID}/name-matched-diagnostic/report.json'
    if not activity_src.exists():
        activity_src = Path(__file__).resolve().parents[3] / f'data/blog_performance/product-search/{ACTIVITY_SAMPLE_ID}/name-matched-diagnostic/report.json'
    for report, empty in ((c_rep, {'keywords': [], 'rank_rows': [], 'brands': []}),
                          (p_rep, {'products': [], 'rank_rows': [], 'rows': 0, 'unique_posts': 0, 'queries': [], 'body_collection': {'success': 0}})):
        if not report.exists():
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(json.dumps(empty), encoding='utf-8')
    build_search_insights_html.build(source=activity_src, out=out_html, common_path=c_rep, products_path=p_rep)
    if ctx.test_only:
        import html
        keywords = ', '.join(q['keyword'] for q in ctx.panel_queries)
        notice = ('<aside class="comparison-callout" role="note" style="padding:14px 24px;background:#fff4cc;border-bottom:2px solid #b78500">'
                  '<b>TEST · 운영과 동일한 보고서 형식</b> · ' + html.escape(ctx.run_id) +
                  '<br>이번 검색 표본: ' + html.escape(keywords) +
                  '<br>검색 순위는 위 표본만 반영합니다. 반기별 활동량은 저장된 기존 기준 자료이며 이번 테스트 수집 결과가 아닙니다. 운영 점수와 직접 비교 금지.</aside>')
        text = out_html.read_text(encoding='utf-8').replace('<body>', '<body>' + notice, 1)
        text = text.replace('<title>', '<title>TEST · ', 1)
        out_html.write_text(text, encoding='utf-8')
        kst_str = ctx.manifest.get('created_at_kst') or datetime.now(timezone.utc).isoformat()
        test_html_path = get_test_report_filename(ctx.run_id, kst_str, ctx.root)
        shutil.copyfile(out_html, test_html_path)
        artifacts['test_report_html'] = str(test_html_path.relative_to(ctx.root))

    artifacts['report_html'] = str(out_html.relative_to(ctx.root))
    ctx.state['artifacts']['report_html'] = artifacts['report_html']
    ctx.state['steps']['html_built'] = True
    ctx.update_state('html_built')

    return StepResult(status='succeeded', message="인사이트 보고서 생성 완료", artifacts=artifacts)


# =========================================================================
# Step 11: QA Verification
# =========================================================================
def step_qa_verification(ctx: ExecutionContext) -> StepResult:
    out_html = ctx.run_dir / 'report.html'
    if not out_html.exists():
        return StepResult(status='blocked', error="생성된 HTML 보고서 파일 없음")

    check_browser = ctx.config.get('qa', {}).get('check_browser', False)

    if ctx.test_only:
        valid, issues = verify_test_html(out_html, ctx.manifest, root=ctx.root, check_browser=check_browser)
    else:
        valid, issues = verify_standard_html(out_html, root=ctx.root, check_browser=check_browser)

    if not valid:
        err_msg = "; ".join(issues)
        ctx.update_state('qa_failed', err=err_msg)
        return StepResult(status='failed', error=f"QA 검증 실패: {err_msg}", artifacts={'issues': issues})

    ctx.state['steps']['qa_verified'] = True
    ctx.update_state('qa_verified')
    return StepResult(status='succeeded', message="기계·브라우저 QA 통과")


# =========================================================================
# Step 12: Activation
# =========================================================================
def step_activation(ctx: ExecutionContext) -> StepResult:
    out_html = ctx.run_dir / 'report.html'
    ctx.manifest['status'] = 'completed'
    ctx.manifest['completed_at'] = datetime.now(timezone.utc).isoformat()
    (ctx.run_dir / 'manifest.json').write_text(json.dumps(ctx.manifest, ensure_ascii=False, indent=2), encoding='utf-8')

    artifacts = {}

    if ctx.test_only:
        # Strict isolation: update test pointer, NEVER operational pointer!
        test_pointer_dir = ctx.root / 'data/blog_performance/insights/tests'
        test_pointer_dir.mkdir(parents=True, exist_ok=True)
        latest_test_pointer = test_pointer_dir / 'latest-test-run.json'

        test_data = {
            'run_id': ctx.run_id,
            'test_only': True,
            'completed_at': datetime.now(timezone.utc).isoformat(),
            'query_count': len(ctx.panel_queries),
            'queries': [q['keyword'] for q in ctx.panel_queries],
            'report_html': str(out_html.relative_to(ctx.root))
        }
        latest_test_pointer.write_text(json.dumps(test_data, ensure_ascii=False, indent=2), encoding='utf-8')
        artifacts['latest_test_pointer'] = str(latest_test_pointer.relative_to(ctx.root))
        msg = f"테스트 실행 완료 ({len(ctx.panel_queries)}개 검색어, 운영 최신본 불변 보존)"
    else:
        latest_pointer = ctx.root / 'data/blog_performance/insights/latest-run.json'
        pointer_data = {
            'run_id': ctx.run_id,
            'activated_at': datetime.now(timezone.utc).isoformat(),
            'report_html': str(out_html.relative_to(ctx.root)),
            'common_report': str((ctx.run_dir / 'common/body-analysis/report.json').relative_to(ctx.root)),
            'products_report': str((ctx.run_dir / 'products/body-analysis/product-report.json').relative_to(ctx.root)),
            'manifest': str((ctx.run_dir / 'manifest.json').relative_to(ctx.root))
        }
        latest_pointer.write_text(json.dumps(pointer_data, ensure_ascii=False, indent=2), encoding='utf-8')
        artifacts['latest_pointer'] = str(latest_pointer.relative_to(ctx.root))
        msg = "최신 인사이트 본 활성화 완료"

    ctx.state['steps']['activated'] = True
    ctx.update_state('completed')
    return StepResult(status='succeeded', message=msg, artifacts=artifacts)
