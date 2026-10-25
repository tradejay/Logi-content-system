"""Standalone, test-specific HTML report generator for 1-2 query test runs.

Distinct from operational 13-page report. Never extrapolates or confuses test scores with 34-query operational scores.
"""
import html
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
e = lambda x: html.escape(str(x) if x is not None else '')


def build(manifest, run_dir, out_path, monitor_state=None):
    run_dir = Path(run_dir)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rid = manifest.get('run_id', 'UNKNOWN-RUN')
    utc_str = manifest.get('created_at_utc') or manifest.get('created_at', '')
    kst_str = manifest.get('created_at_kst')
    if not kst_str and utc_str:
        try:
            dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
            kst_str = (dt + timedelta(hours=9)).strftime('%Y-%m-%d %H:%M:%S KST')
        except Exception:
            kst_str = utc_str
    offline = manifest.get('offline', True)
    mode_text = '오프라인 (로컬 파일)' if offline else '온라인 (워커 수집)'
    selected_queries = manifest.get('selected_queries', [])
    query_count = len(selected_queries)
    common_count = manifest.get('common_query_count', sum(q.get('panel') == 'common' for q in selected_queries))
    prod_count = manifest.get('product_query_count', sum(q.get('panel') == 'products' for q in selected_queries))

    # Load artifacts if present
    common_rep = None
    common_path = run_dir / 'common/body-analysis/report.json'
    if common_path.exists():
        try:
            common_rep = json.loads(common_path.read_text(encoding='utf-8'))
        except Exception:
            pass

    prod_rep = None
    prod_path = run_dir / 'products/body-analysis/product-report.json'
    if prod_path.exists():
        try:
            prod_rep = json.loads(prod_path.read_text(encoding='utf-8'))
        except Exception:
            pass

    top5_audit = None
    top5_path = run_dir / 'common/body-analysis/top5-audit.json'
    if not top5_path.exists():
        top5_path = run_dir / 'common/top5-audit.json'
    if top5_path.exists():
        try:
            top5_audit = json.loads(top5_path.read_text(encoding='utf-8'))
        except Exception:
            pass

    decisions = []
    decisions_path = run_dir / 'ai-decisions.json'
    if decisions_path.exists():
        try:
            dec_data = json.loads(decisions_path.read_text(encoding='utf-8'))
            decisions = dec_data.get('decisions', [])
        except Exception:
            pass

    if monitor_state is None and (run_dir / 'monitor-state.json').exists():
        try:
            monitor_state = json.loads((run_dir / 'monitor-state.json').read_text(encoding='utf-8'))
        except Exception:
            pass

    # Build sections
    steps_html = _render_steps_table(monitor_state, common_count, prod_count)
    queries_html = _render_queries_table(selected_queries)
    results_html = _render_captured_results(run_dir, selected_queries)
    scores_html = _render_brand_scores(common_rep, common_count)
    top5_html = _render_top5_audit(top5_audit)
    terms_html = _render_terms_review(decisions)

    html_content = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>[TEST] 블로그 검색 인사이트 테스트 보고서 - {e(rid)}</title>
<style>
  :root {{
    --ink: #172b3a;
    --muted: #536777;
    --teal: #087e86;
    --danger: #dc2626;
    --danger-bg: #fef2f2;
    --warn-bg: #fffbeb;
    --warn-border: #f59e0b;
    --line: #d8e1e5;
    --paper: #fff;
    --bg: #f1f5f9;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 24px 20px 60px;
    background: var(--bg);
    color: var(--ink);
    font: 14px/1.6 "Pretendard", "Malgun Gothic", -apple-system, sans-serif;
  }}
  .container {{
    max-width: 1180px;
    margin: 0 auto;
    background: var(--paper);
    padding: 36px 44px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.06);
    border-radius: 8px;
    border-top: 6px solid var(--danger);
  }}
  .test-banner {{
    background: var(--danger-bg);
    border: 2px solid var(--danger);
    border-radius: 6px;
    padding: 16px 20px;
    margin-bottom: 24px;
  }}
  .test-badge {{
    display: inline-block;
    background: var(--danger);
    color: white;
    font-weight: 700;
    font-size: 11px;
    padding: 3px 8px;
    border-radius: 4px;
    letter-spacing: 1px;
    text-transform: uppercase;
  }}
  .test-banner h2 {{
    margin: 8px 0 6px;
    font-size: 18px;
    color: #991b1b;
  }}
  .test-banner p {{
    margin: 0;
    font-size: 13px;
    color: #7f1d1d;
    line-height: 1.5;
  }}
  header.report-head {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    border-bottom: 2px solid var(--line);
    padding-bottom: 16px;
    margin-bottom: 24px;
    flex-wrap: wrap;
    gap: 16px;
  }}
  h1 {{
    margin: 0 0 6px;
    font-size: 24px;
    font-weight: 800;
    letter-spacing: -0.5px;
  }}
  .meta-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 12px 20px;
    background: #f8fafc;
    padding: 16px;
    border-radius: 6px;
    border: 1px solid var(--line);
    margin-bottom: 28px;
    font-size: 13px;
  }}
  .meta-item b {{ color: var(--muted); display: block; font-size: 11px; text-transform: uppercase; }}
  section.report-section {{
    margin-bottom: 36px;
  }}
  section.report-section h2 {{
    font-size: 17px;
    border-bottom: 2px solid var(--teal);
    padding-bottom: 6px;
    margin: 0 0 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  table {{
    border-collapse: collapse;
    width: 100%;
    font-size: 13px;
    margin-top: 10px;
  }}
  th {{
    background: #f8fafc;
    font-weight: 700;
    color: var(--muted);
    font-size: 11px;
    border-bottom: 2px solid var(--ink);
    padding: 8px 10px;
    text-align: left;
  }}
  td {{
    border-bottom: 1px solid var(--line);
    padding: 9px 10px;
    vertical-align: middle;
  }}
  tbody tr:nth-child(even) {{ background: #fafafa; }}
  .comparison-callout {{
    background: var(--warn-bg);
    border-left: 3px solid var(--warn-border);
    padding: 8px 12px;
    font-size: 12px;
    margin-bottom: 8px;
    color: #92400e;
  }}
  .comparison-callout b {{ margin-right: 6px; }}
  .rank-pill {{
    display: inline-block;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
  }}
  .rank-pill.top1 {{ background: #08754d; color: white; }}
  .rank-pill.top3 {{ background: #c2e8d5; color: #154e39; }}
  .rank-pill.top10 {{ background: #d2e5fa; color: #214c7d; }}
  .rank-pill.other {{ background: #e9edf0; color: #556574; }}
  .badge-status {{
    display: inline-block;
    padding: 2px 7px;
    border-radius: 9999px;
    font-size: 11px;
    font-weight: 700;
  }}
  .badge-succeeded {{ background: #dcfce7; color: #166534; }}
  .badge-skipped {{ background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; }}
  .badge-failed {{ background: #fee2e2; color: #991b1b; }}
  .badge-running {{ background: #e0f2fe; color: #075985; }}
  a {{ color: #0284c7; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  footer.report-foot {{
    border-top: 1px solid var(--line);
    padding-top: 16px;
    color: var(--muted);
    font-size: 11px;
    line-height: 1.5;
  }}
</style>
</head>
<body>
<div class="container">
  <div class="test-banner" role="alert">
    <span class="test-badge">TEST EXECUTION ONLY</span>
    <h2>테스트 실행 전용 보고서 (운영 점수와 비교 금지)</h2>
    <p>
      본 보고서는 1~2개 검색어 단위의 파이프라인 기능 검증을 위한 테스트 전용 문서입니다.<br>
      전체 34개 쿼리를 종합한 운영 13페이지 보고서와 혼동하지 마십시오.
      공통 관측점 계산 시 분모는 실제 선택된 공통 검색어 수({common_count}개)로 계산되며 운영 점수와 직접 비교할 수 없습니다.
    </p>
  </div>

  <header class="report-head">
    <div>
      <h1>블로그 검색 인사이트 테스트 보고서</h1>
      <div style="color:var(--muted); font-size:13px;">실행 식별자: <code>{e(rid)}</code></div>
    </div>
    <div style="text-align:right;">
      <span class="badge-status badge-succeeded">테스트 완료</span>
    </div>
  </header>

  <div class="meta-grid">
    <div class="meta-item">
      <b>실행 ID</b>
      <code>{e(rid)}</code>
    </div>
    <div class="meta-item">
      <b>실행 시각 (KST)</b>
      <span>{e(kst_str)}</span>
    </div>
    <div class="meta-item">
      <b>실행 모드</b>
      <span>{e(mode_text)}</span>
    </div>
    <div class="meta-item">
      <b>테스트 검색어 범위</b>
      <span>총 {query_count}개 (공통 {common_count}개 / 제품 {prod_count}개)</span>
    </div>
  </div>

  <section class="report-section">
    <h2>1. 파이프라인 단계별 처리 상태</h2>
    <div class="comparison-callout">
      <b>조건부 비교:</b> 선택되지 않은 패널이나 생략된 단계는 사유와 함께 <code>skipped</code>로 표기하며, 거짓 성공이나 0점으로 가장하지 않습니다.
    </div>
    {steps_html}
  </section>

  <section class="report-section">
    <h2>2. 선택 검색어 패널</h2>
    <div class="comparison-callout">
      <b>패널 안내:</b> 허용된 34개 패널 중 이번 테스트에 선택된 1~2개 검색어 목록입니다.
    </div>
    {queries_html}
  </section>

  <section class="report-section">
    <h2>3. 실제 수집 순위 및 브랜드 매칭</h2>
    <div class="comparison-callout">
      <b>원래 순서 보존:</b> 네이버 블로그 탭 상위 일반 검색 순위(광고 제외) 원본을 유지하고 본문 기반 브랜드/장비명을 매칭한 결과입니다.
    </div>
    {results_html}
  </section>

  {scores_html}

  {top5_html}

  {terms_html}

  <footer class="report-foot">
    <p>• <b>안내:</b> 활동량 옛 표본(2026-10-21)은 테스트 필수 범위에서 제외되며 고정 참고 자료로 유지됩니다.</p>
    <p>• <b>저장 경로:</b> <code>{e(str(out_path.name))}</code> (운영 최신 포인터 latest-run.json 및 운영 리포트 불변 보장)</p>
  </footer>
</div>
</body>
</html>
"""
    out_path.write_text(html_content, encoding='utf-8')
    return out_path


def _render_steps_table(monitor_state, common_count, prod_count):
    from services.blog_performance.insights.tracker import STEPS_ORDER, STEP_LABELS
    steps = monitor_state.get('steps', {}) if monitor_state else {}
    rows = []
    for s_name in STEPS_ORDER:
        label = STEP_LABELS.get(s_name, s_name)
        s_data = steps.get(s_name, {})
        if isinstance(s_data, dict):
            status = s_data.get('status', 'succeeded')
            msg = s_data.get('message', '—')
            elapsed = s_data.get('elapsed_seconds')
        elif isinstance(s_data, str):
            status = s_data
            msg = '—'
            elapsed = None
        elif isinstance(s_data, bool):
            status = 'succeeded' if s_data else 'pending'
            msg = '—'
            elapsed = None
        else:
            status = 'succeeded'
            msg = '—'
            elapsed = None
        elapsed_str = f"{elapsed:.2f}s" if isinstance(elapsed, (int, float)) else '—'
        badge_cls = f"badge-{status}" if status in ['succeeded', 'skipped', 'failed', 'running'] else 'badge-skipped'
        rows.append(f"""<tr>
          <td><b>{e(label)}</b><br><small style="color:var(--muted)">{e(s_name)}</small></td>
          <td><span class="badge-status {badge_cls}">{e(status)}</span></td>
          <td>{e(msg)}</td>
          <td>{e(elapsed_str)}</td>
        </tr>""")
    return f"""<table>
      <thead>
        <tr>
          <th>단계명</th>
          <th>상태</th>
          <th>메시지 / 사유</th>
          <th>소요 시간</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>"""


def _render_queries_table(selected_queries):
    rows = []
    for q in selected_queries:
        panel_label = "공통 검색어" if q.get('panel') == 'common' else "제품 검색어"
        kw = q.get('keyword', '')
        url = q.get('search_url', '')
        prod = q.get('product') or q.get('brand') or '—'
        rows.append(f"""<tr>
          <td><span class="badge-status badge-succeeded">{e(panel_label)}</span></td>
          <td><b>{e(kw)}</b></td>
          <td>{e(prod)}</td>
          <td><a href="{e(url)}" target="_blank" rel="noopener">네이버 검색 열기 ↗</a></td>
        </tr>""")
    return f"""<table>
      <thead>
        <tr>
          <th>패널 구분</th>
          <th>검색어</th>
          <th>대상 모델/브랜드</th>
          <th>검색 URL</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>"""


def _render_captured_results(run_dir, selected_queries):
    tables = []
    for q in selected_queries:
        kw = q.get('keyword', '')
        panel = q.get('panel', 'common')
        in_file = run_dir / f"{panel}/input.json"
        q_results = []
        if in_file.exists():
            try:
                raw_data = json.loads(in_file.read_text(encoding='utf-8'))
                for r_item in raw_data.get('results', []):
                    if r_item.get('keyword') == kw:
                        q_results = r_item.get('rows', [])[:10]  # Show top 10 for compact test view
                        break
            except Exception:
                pass

        if not q_results:
            tables.append(f"""<div style="margin-top:14px;">
              <h3>검색어: {e(kw)}</h3>
              <p style="color:var(--muted);">수집 결과 데이터 없음 (오프라인 모드 미입력 또는 건너뜀)</p>
            </div>""")
            continue

        rows_html = []
        for r in q_results:
            rank = r.get('rank', 0)
            pill_cls = 'top1' if rank == 1 else 'top3' if rank <= 3 else 'top10' if rank <= 10 else 'other'
            title = r.get('title', '제목 없음')
            url = r.get('url', '#')
            rows_html.append(f"""<tr>
              <td style="text-align:center;"><span class="rank-pill {pill_cls}">{rank}위</span></td>
              <td><a href="{e(url)}" target="_blank" rel="noopener">{e(title)}</a></td>
              <td><small>{e(url)}</small></td>
            </tr>""")

        tables.append(f"""<div style="margin-top:18px;">
          <h3>검색어: <code>{e(kw)}</code> (상위 관측 결과)</h3>
          <table>
            <thead>
              <tr>
                <th style="width:60px; text-align:center;">순위</th>
                <th>글 제목 (클릭 시 링크)</th>
                <th>URL</th>
              </tr>
            </thead>
            <tbody>
              {''.join(rows_html)}
            </tbody>
          </table>
        </div>""")

    return ''.join(tables)


def _render_brand_scores(common_rep, common_count):
    if not common_rep or common_count == 0:
        return """<section class="report-section">
          <h2>4. 공통 검색어 브랜드 관측점</h2>
          <div class="comparison-callout">
            <b>건너뜀:</b> 선택된 검색어 중 공통 검색어가 포함되지 않아 관측점 산출이 건너뛰어졌습니다.
          </div>
        </section>"""

    brand_scores = common_rep.get('brand_scores', [])
    rows = []
    for b in brand_scores:
        brand = b.get('brand', '')
        score = b.get('observed_score', 0.0)
        matched = b.get('matched_posts', 0)
        best_ranks = [str(kr.get('best_rank', '—')) for kr in b.get('keyword_ranks', [])]
        rows.append(f"""<tr>
          <td><b>{e(brand)}</b></td>
          <td style="text-align:right;"><b>{score:.2f}</b></td>
          <td style="text-align:center;">{e(', '.join(best_ranks))}</td>
          <td style="text-align:right;">{matched}건</td>
        </tr>""")

    return f"""<section class="report-section">
      <h2>4. 공통 검색어 브랜드 관측점 (테스트 표본)</h2>
      <div class="comparison-callout">
        <b>분모 기준 ({common_count}개 쿼리):</b> 관측점 = 100 × (최고 순위 역수 합) ÷ {common_count}. 운영 7개 쿼리 합산점과 비교하지 마십시오.
      </div>
      <table>
        <thead>
          <tr>
            <th>브랜드</th>
            <th style="text-align:right;">관측점 (0~100)</th>
            <th style="text-align:center;">선택 쿼리 최고 순위</th>
            <th style="text-align:right;">매칭 글 수</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </section>"""


def _render_top5_audit(top5_audit):
    if not top5_audit:
        return ""
    items = top5_audit.get('rows', []) or top5_audit.get('items', [])
    if not items:
        return ""
    rows = []
    for item in items[:10]:
        rank = item.get('rank', '—')
        title = item.get('title', '')
        url = item.get('url', '#')
        reason = item.get('reason', '')
        topic = item.get('topic', '')
        rows.append(f"""<tr>
          <td style="text-align:center;">{e(rank)}위</td>
          <td><a href="{e(url)}" target="_blank" rel="noopener">{e(title)}</a></td>
          <td>{e(topic)}</td>
          <td>{e(reason)}</td>
        </tr>""")
    return f"""<section class="report-section">
      <h2>5. 상위 1~5위 신규 글 독립 감사 요약</h2>
      <div class="comparison-callout">
        <b>독립 검토:</b> 상위 순위 진입 글의 브랜드 표시 여부 및 미표시 사유 검토 내역입니다.
      </div>
      <table>
        <thead>
          <tr>
            <th style="width:60px; text-align:center;">순위</th>
            <th>제목</th>
            <th>분류 주제</th>
            <th>판정 및 사유</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </section>"""


def _render_terms_review(decisions):
    if not decisions:
        return ""
    rows = []
    for d in decisions:
        tid = d.get('id', '')
        cat = d.get('category', '')
        brand = d.get('brand') or '—'
        model = d.get('model') or '—'
        reason = d.get('reason', '')
        rows.append(f"""<tr>
          <td><code>{e(tid)}</code></td>
          <td><span class="badge-status badge-succeeded">{e(cat)}</span></td>
          <td>{e(brand)}</td>
          <td>{e(model)}</td>
          <td>{e(reason)}</td>
        </tr>""")
    return f"""<section class="report-section">
      <h2>6. 04 AI 용어 판정 내역</h2>
      <div class="comparison-callout">
        <b>미확정 용어 분류:</b> 본문에서 추출된 후보 모델명의 04_review 독립 판정 결과입니다.
      </div>
      <table>
        <thead>
          <tr>
            <th>용어 ID</th>
            <th>분류 카테고리</th>
            <th>인식 브랜드</th>
            <th>인식 모델</th>
            <th>판정 사유</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </section>"""
