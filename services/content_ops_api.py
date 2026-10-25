"""
services/content_ops_api.py
Chapter 8: Content Operations Console Backend API Blueprint
파일 기반 시스템과 웹 UI 간의 완전한 무결성 제어 플레인(Control Plane)을 제공합니다.
"""

import os
import sys
import re
import csv
import json
import yaml
import glob
import base64
import subprocess
from pathlib import Path
from datetime import datetime, date
from flask import Blueprint, request, jsonify, send_from_directory

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYSTEM_DIR = os.path.join(BASE_DIR, "content-system")
SCRIPTS_DIR = os.path.join(SYSTEM_DIR, "scripts")
REGISTRY_FILE = os.path.join(SYSTEM_DIR, "registry", "CONTENT_REGISTRY.csv")
SOURCE_REGISTRY_FILE = os.path.join(SYSTEM_DIR, "registry", "SOURCE_REGISTRY.csv")
INDEX_FILE = os.path.join(SYSTEM_DIR, "03_sources", "INDEX.yaml")
INBOX_DIR = os.path.join(SYSTEM_DIR, "03_sources", "inbox")
BRIEFS_DIR = os.path.join(SYSTEM_DIR, "01_keyword_ai", "briefs")
DRAFTS_DIR = os.path.join(SYSTEM_DIR, "02_writer_ai", "drafts")
REPORTS_DIR = os.path.join(SYSTEM_DIR, "04_qa_ai", "reports")
VERIFICATION_DIR = os.path.join(SYSTEM_DIR, "04_qa_ai", "verification")
PUBLISH_DIR = os.path.join(SYSTEM_DIR, "05_publish")
ASSETS_ROOT = os.path.join(SYSTEM_DIR, "assets")
EVENTS_LOG = os.path.join(SYSTEM_DIR, "logs", "events.jsonl")
LOCKS_DIR = os.path.join(SYSTEM_DIR, "locks")
WEEKLY_DIR = os.path.join(SYSTEM_DIR, "weekly")

content_ops_bp = Blueprint("content_ops", __name__, url_prefix="/api/content-system")


@content_ops_bp.get('/ide-tasks')
def ide_tasks_api():
    from services.ide_task_monitor import snapshot
    try:
        return jsonify(snapshot(request.args.get('task')))
    except (ValueError, OSError, KeyError) as error:
        return jsonify(error=str(error)), 400


@content_ops_bp.get('/ide-tasks/<task_id>/file')
def ide_task_file_api(task_id):
    from services.ide_task_monitor import task_view
    try:
        view = task_view(task_id)
        item = next((f for f in view['files'] if f['path'] == request.args.get('path')), None)
        if not item:
            return jsonify(error='이 작업의 허용된 파일이 아닙니다.'), 404
        path = Path(BASE_DIR) / 'worker-workspaces' / view['worker_folder'] / item['path']
        response = send_from_directory(path.parent, path.name, mimetype=None if path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'} else 'text/plain; charset=utf-8')
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response
    except (ValueError, OSError, KeyError) as error:
        return jsonify(error=str(error)), 400


@content_ops_bp.get('/worker-flow')
def worker_flow_api():
    from services.worker_flow import monitor
    try:
        return jsonify(monitor(request.args.get('content'), run_id=request.args.get('run_id')))
    except (ValueError, OSError) as error:
        return jsonify(error=str(error)), 400


@content_ops_bp.get('/contents/<content_id>/work-artifacts')
def work_artifacts_api(content_id):
    from services.console_work import artifacts
    try:
        return jsonify(items=artifacts(content_id, request.args.get('run_id')))
    except (ValueError, OSError) as error:
        return jsonify(error=str(error)), 400


@content_ops_bp.get('/contents/<content_id>/work-artifacts/<identity>')
def work_artifact_file_api(content_id, identity):
    from services.console_work import artifacts
    try:
        item = next((a for a in artifacts(content_id, request.args.get('run_id')) if a['id'] == identity), None)
        if not item:
            return jsonify(error='이 글의 산출물이 아닙니다.'), 404
        path = Path(BASE_DIR) / item['path']
        response = send_from_directory(path.parent, path.name, mimetype='text/plain; charset=utf-8')
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response
    except (ValueError, OSError) as error:
        return jsonify(error=str(error)), 400


@content_ops_bp.route('/contents/<content_id>/work-actions', methods=['GET', 'POST'])
def work_actions_api(content_id):
    from services.console_work import start, current, read
    try:
        current(content_id)
        if request.method == 'GET':
            jobs = [read(p) for p in (Path(BASE_DIR) / 'worker-control/console-actions').glob('*/job.json')]
            return jsonify(jobs=sorted([j for j in jobs if j.get('content_id') == content_id], key=lambda j: j.get('created_at', ''), reverse=True))
        if request.headers.get('Origin') and request.headers['Origin'].rstrip('/') != request.host_url.rstrip('/'):
            return jsonify(error='동일한 로컬 관리 화면에서 요청하세요.'), 403
        return jsonify(job=start(content_id, request.get_json(silent=True) or {})), 202
    except (ValueError, KeyError, OSError) as error:
        return jsonify(error=str(error)), 409

def run_script(script_name, args):
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    cmd = [sys.executable, script_path] + args
    res = subprocess.run(cmd, cwd=SYSTEM_DIR, capture_output=True, text=True, encoding="utf-8")
    return res.returncode, res.stdout, res.stderr

# 1. Dashboard Summary
@content_ops_bp.route("/dashboard", methods=["GET"])
def get_dashboard():
    from services.pipeline_status import get_aggregated_status_counts
    # Shared durable status counts
    status_counts = get_aggregated_status_counts(BASE_DIR)
    contents_list = []
    if os.path.exists(REGISTRY_FILE):
        with open(REGISTRY_FILE, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for r in reader:
                contents_list.append(r)

    # Attention Items
    attention_items = []

    # 1) Open EVREQ
    if os.path.exists(INBOX_DIR):
        for fname in os.listdir(INBOX_DIR):
            if fname.endswith(".yaml") or fname.endswith(".yml"):
                try:
                    with open(os.path.join(INBOX_DIR, fname), "r", encoding="utf-8") as yf:
                        ev = yaml.safe_load(yf) or {}
                    if ev.get("status") == "OPEN":
                        attention_items.append({
                            "type": "MISSING_EVIDENCE",
                            "id": ev.get("evidence_request_id", fname),
                            "content_id": ev.get("content_id"),
                            "title": f"{ev.get('product')}: {ev.get('missing_type')}",
                            "severity": ev.get("severity", "HIGH"),
                            "question": ev.get("question")
                        })
                except Exception:
                    pass

    # 2) Stale Sources
    if os.path.exists(INDEX_FILE):
        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as yf:
                idx = yaml.safe_load(yf) or {}
            today = date.today()
            for s in idx.get("sources", []):
                v_str = s.get("last_verified", "2000-01-01")
                limit = int(s.get("freshness_limit_days", 90))
                try:
                    v_date = datetime.strptime(v_str, "%Y-%m-%d").date()
                    age = (today - v_date).days
                    if age > limit:
                        attention_items.append({
                            "type": "STALE_SOURCE",
                            "id": s.get("id"),
                            "title": s.get("title"),
                            "severity": "MEDIUM",
                            "details": f"최종 검증 후 {age}일 경과 (기한: {limit}일)"
                        })
                except Exception:
                    pass
        except Exception:
            pass

    # 3) Active Locks
    if os.path.exists(LOCKS_DIR):
        for lk in os.listdir(LOCKS_DIR):
            if lk.endswith(".lock"):
                cid = lk.replace(".lock", "")
                attention_items.append({
                    "type": "LOCKED",
                    "id": lk,
                    "content_id": cid,
                    "title": f"현재 작업 중 (Lock 걸림)",
                    "severity": "LOW"
                })

    # Recent Events
    recent_events = []
    if os.path.exists(EVENTS_LOG):
        try:
            with open(EVENTS_LOG, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
                for l in reversed(lines[-20:]):
                    recent_events.append(json.loads(l))
        except Exception:
            pass

    return jsonify({
        "status": "ok",
        "system_version": "1.0.0",
        "counts": status_counts,
        "total_contents": len(contents_list),
        "attention_items": attention_items,
        "recent_events": recent_events
    })

# 2. All Contents List
@content_ops_bp.route("/contents", methods=["GET"])
def get_contents():
    from services.pipeline_status import calculate_effective_status
    rows = []
    if os.path.exists(REGISTRY_FILE):
        with open(REGISTRY_FILE, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for r in reader:
                cid = r.get("content_id")
                # Look for QA score
                qa_score = None
                qa_file = os.path.join(REPORTS_DIR, f"{cid}.qa.yaml")
                if os.path.exists(qa_file):
                    try:
                        with open(qa_file, "r", encoding="utf-8") as qf:
                            qdata = yaml.safe_load(qf) or {}
                            qa_score = qdata.get("overall_score")
                    except Exception:
                        pass
                r["qa_score"] = qa_score
                # Calculate shared effective status
                st_info = calculate_effective_status(BASE_DIR, cid, registry_row=r)
                r["registry_status"] = r.get("status", "PLANNING")
                r["effective_status"] = st_info["effective_status"]
                r["pipeline_outcome"] = st_info["pipeline_outcome"]
                r["pipeline_reason"] = st_info["reason"]
                r["publish_ready"] = st_info["publish_ready"]
                r["qa_passed"] = st_info["qa_passed"]
                r["run_id"] = st_info["run_id"]
                r["is_interrupted"] = st_info["is_interrupted"]
                r["status"] = st_info["effective_status"]
                rows.append(r)
    return jsonify({"contents": rows})

# 3. Single Content Detail (Brief, Draft, QA, Sources, Assets)
@content_ops_bp.route("/contents/<content_id>", methods=["GET"])
def get_content_detail(content_id):
    brief_data = None
    brief_file = os.path.join(BRIEFS_DIR, f"{content_id}.brief.yaml")
    if os.path.exists(brief_file):
        with open(brief_file, "r", encoding="utf-8") as f:
            brief_data = yaml.safe_load(f)

    draft_text = ""
    draft_file = os.path.join(DRAFTS_DIR, f"{content_id}.draft.md")
    if os.path.exists(draft_file):
        with open(draft_file, "r", encoding="utf-8") as f:
            draft_text = f.read()
    else:
        # Check if final exists
        final_file = os.path.join(PUBLISH_DIR, "ready", f"{content_id}.final.md")
        if os.path.exists(final_file):
            with open(final_file, "r", encoding="utf-8") as f:
                draft_text = f.read()

    qa_data = None
    qa_file = os.path.join(REPORTS_DIR, f"{content_id}.qa.yaml")
    if os.path.exists(qa_file):
        with open(qa_file, "r", encoding="utf-8") as f:
            qa_data = yaml.safe_load(f)

    # Resolve Sources
    sources_info = []
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            idx = yaml.safe_load(f) or {}
        raw_sources = idx.get("sources", {})
        index_map = {}
        if isinstance(raw_sources, dict):
            for sid, sval in raw_sources.items():
                if isinstance(sval, dict):
                    sd = dict(sval)
                    sd["id"] = sid
                    index_map[sid] = sd
        elif isinstance(raw_sources, list):
            for s in raw_sources:
                if isinstance(s, dict) and "id" in s:
                    index_map[s["id"]] = s

        req_sources = (brief_data or {}).get("required_sources", [])
        for sid in req_sources:
            if sid in index_map:
                s_meta = dict(index_map[sid])
                # Read content snippet
                s_path = os.path.join(SYSTEM_DIR, "03_sources", s_meta.get("path", ""))
                if os.path.exists(s_path):
                    with open(s_path, "r", encoding="utf-8") as sf:
                        s_meta["body"] = sf.read()
                sources_info.append(s_meta)

    # Assets (Master Asset Index + Working Context + Local Uploads)
    content_assets = []
    assets_seen = set()

    # 1. Master Asset Registry (03_sources/assets/INDEX.yaml)
    master_asset_file = os.path.join(SYSTEM_DIR, "03_sources", "assets", "INDEX.yaml")
    if os.path.exists(master_asset_file):
        try:
            with open(master_asset_file, "r", encoding="utf-8") as mf:
                mdata = yaml.safe_load(mf) or {}
            for a in mdata.get("assets", []):
                aid = a.get("asset_id")
                if aid and aid not in assets_seen:
                    assets_seen.add(aid)
                    a_copy = dict(a)
                    a_copy["is_used"] = f"{{{{asset:{aid}}}}}" in draft_text
                    content_assets.append(a_copy)
        except Exception:
            pass

    # 2. Working Context (02_writer_ai/working/{content_id}/assets/asset-index.yaml)
    working_asset_file = os.path.join(SYSTEM_DIR, "02_writer_ai", "working", content_id, "assets", "asset-index.yaml")
    if os.path.exists(working_asset_file):
        try:
            with open(working_asset_file, "r", encoding="utf-8") as wf:
                wdata = yaml.safe_load(wf) or {}
            for a in wdata.get("available_assets", []):
                aid = a.get("asset_id")
                if aid and aid not in assets_seen:
                    assets_seen.add(aid)
                    a_copy = dict(a)
                    a_copy["is_used"] = f"{{{{asset:{aid}}}}}" in draft_text
                    content_assets.append(a_copy)
        except Exception:
            pass

    # 3. Local Uploaded Assets
    asset_dir = os.path.join(ASSETS_ROOT, content_id)
    if os.path.exists(asset_dir):
        assets_meta_file = os.path.join(asset_dir, "assets.yaml")
        if os.path.exists(assets_meta_file):
            with open(assets_meta_file, "r", encoding="utf-8") as af:
                adata = yaml.safe_load(af) or {}
                for a in adata.get("assets", []):
                    aid = a.get("asset_id")
                    if aid and aid not in assets_seen:
                        assets_seen.add(aid)
                        a_copy = dict(a)
                        a_copy["is_used"] = f"{{{{asset:{aid}}}}}" in draft_text or a.get("filename", "") in draft_text
                        content_assets.append(a_copy)
        else:
            for fn in os.listdir(asset_dir):
                if fn.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                    aid = fn.split(".")[0]
                    if aid not in assets_seen:
                        assets_seen.add(aid)
                        content_assets.append({
                            "asset_id": aid,
                            "filename": fn,
                            "url": f"/api/content-system/assets/{content_id}/{fn}",
                            "is_used": aid in draft_text or fn in draft_text
                        })

    # Lock status
    lock_file = os.path.join(LOCKS_DIR, f"{content_id}.lock")
    is_locked = os.path.exists(lock_file)
    lock_info = None
    if is_locked:
        try:
            with open(lock_file, "r", encoding="utf-8") as lf:
                lock_info = yaml.safe_load(lf)
        except Exception:
            pass

    # Knowledge Packs
    knw_packs = []
    if brief_data:
        req_knw = brief_data.get("knowledge_packs", [])
        for kid in req_knw:
            for root, _, files in os.walk(os.path.join(SYSTEM_DIR, "03_sources", "knowledge")):
                for f in files:
                    if f.endswith(f"{kid}.yaml") or f.endswith(f"{kid}.yml"):
                        kpath = os.path.join(root, f)
                        try:
                            with open(kpath, "r", encoding="utf-8") as kf:
                                knw_packs.append(yaml.safe_load(kf))
                        except Exception:
                            pass

    # Research Requirements
    rr_data = None
    rr_file = os.path.join(SYSTEM_DIR, "01_keyword_ai", "research_requirements", f"RR-{content_id}.yaml")
    if os.path.exists(rr_file):
        try:
            with open(rr_file, "r", encoding="utf-8") as rf:
                rr_data = yaml.safe_load(rf)
        except Exception:
            pass

    # Claim Evidence Check & Section Depth Check
    claim_qa = None
    section_depth = None
    try:
        if SCRIPTS_DIR not in sys.path:
            sys.path.insert(0, SCRIPTS_DIR)
        from validate_claim_evidence import validate_claims
        from check_section_depth import evaluate_section_depth
        passed, errs, rep = validate_claims(content_id)
        claim_qa = rep
        depth_passed, depth_warns, depth_rep = evaluate_section_depth(content_id)
        section_depth = depth_rep
    except Exception as e:
        pass

    # Verification (Tier 1 Logitech AI + Tier 2 Admin Review Queue)
    verif_data = None
    verif_file = os.path.join(VERIFICATION_DIR, f"{content_id}.verification.yaml")
    if os.path.exists(verif_file):
        try:
            with open(verif_file, "r", encoding="utf-8") as vf:
                verif_data = yaml.safe_load(vf)
        except Exception:
            pass

    from services.content_pipeline import ContentPipeline
    from services.pipeline_status import calculate_effective_status
    pipeline_result = ContentPipeline().latest(content_id)
    status_info = calculate_effective_status(BASE_DIR, content_id, latest_run=pipeline_result, draft_text=draft_text)
    return jsonify({
        "content_id": content_id,
        "pipeline": pipeline_result,
        "status_info": status_info,
        "effective_status": status_info["effective_status"],
        "publish_ready": status_info["publish_ready"],
        "qa_passed": status_info["qa_passed"],
        "pipeline_outcome": status_info["pipeline_outcome"],
        "pipeline_reason": status_info["reason"],
        "brief": brief_data,
        "draft": draft_text,
        "qa": qa_data,
        "verification": verif_data,
        "sources": sources_info,
        "knowledge_packs": knw_packs,
        "research_requirements": rr_data,
        "claim_qa": claim_qa,
        "section_depth": section_depth,
        "assets": content_assets,
        "is_locked": is_locked or status_info["is_locked"],
        "lock_info": lock_info or status_info["lock_info"]
    })

# 3.1 Verification Management (Tier 2 Admin Factcheck)
@content_ops_bp.route("/contents/<content_id>/verify-item", methods=["POST"])
def verify_item_api(content_id):
    data = request.get_json(silent=True) or {}
    item_id = data.get("item_id")
    new_status = data.get("status", "APPROVED")
    reviewer = data.get("reviewer", "ADMIN")
    note = data.get("note", "")

    verif_file = os.path.join(VERIFICATION_DIR, f"{content_id}.verification.yaml")
    if not os.path.exists(verif_file):
        return jsonify({"status": "error", "message": "Verification file not found"}), 404

    try:
        with open(verif_file, "r", encoding="utf-8") as vf:
            vdata = yaml.safe_load(vf) or {}

        items = (vdata.get("tier2_admin_review_queue") or {}).get("items", [])
        updated = False
        for item in items:
            if item.get("item_id") == item_id:
                item["status"] = new_status
                item["reviewer"] = reviewer
                item["reviewed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if note:
                    item["admin_note"] = note
                updated = True
                break

        if updated:
            vdata["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(verif_file, "w", encoding="utf-8") as vf:
                yaml.dump(vdata, vf, allow_unicode=True, sort_keys=False)
            return jsonify({"status": "ok", "verification": vdata})
        else:
            return jsonify({"status": "error", "message": f"Item {item_id} not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@content_ops_bp.route("/contents/<content_id>/verify-all-admin", methods=["POST"])
def verify_all_admin_api(content_id):
    data = request.get_json(silent=True) or {}
    reviewer = data.get("reviewer", "ADMIN")

    verif_file = os.path.join(VERIFICATION_DIR, f"{content_id}.verification.yaml")
    if not os.path.exists(verif_file):
        return jsonify({"status": "error", "message": "Verification file not found"}), 404

    try:
        with open(verif_file, "r", encoding="utf-8") as vf:
            vdata = yaml.safe_load(vf) or {}

        items = (vdata.get("tier2_admin_review_queue") or {}).get("items", [])
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for item in items:
            item["status"] = "APPROVED"
            item["reviewer"] = reviewer
            item["reviewed_at"] = now_str

        vdata["updated_at"] = now_str
        with open(verif_file, "w", encoding="utf-8") as vf:
            yaml.dump(vdata, vf, allow_unicode=True, sort_keys=False)
        return jsonify({"status": "ok", "verification": vdata})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 4. Status Transition Transaction (via change_status.py)
@content_ops_bp.route("/contents/<content_id>/status", methods=["POST"])
def change_status_api(content_id):
    data = request.get_json(silent=True) or {}
    new_status = data.get("new_status")
    actor = data.get("actor", "WEB_CONSOLE")
    details = data.get("details", "Triggered via Web Workbench")
    force = bool(data.get("force", False))

    if not new_status:
        return jsonify({"error": "new_status is required"}), 400

    if new_status in ["READY_TO_PUBLISH", "PUBLISHED"]:
        from services.content_pipeline import ContentPipeline
        try:
            ContentPipeline().assert_publishable(content_id)
        except ValueError as error:
            return jsonify({"success": False, "error": str(error)}), 409

    args = [content_id, new_status, "--actor", actor, "--details", details]
    if force:
        args.append("--force")

    code, out, err = run_script("change_status.py", args)
    if code == 0:
        return jsonify({"success": True, "message": out.strip()})
    else:
        return jsonify({"success": False, "error": (err or out).strip()}), 400

# 5. Save Draft Content with Automatic Post-Edit Claim Re-validation
@content_ops_bp.route("/contents/<content_id>/save-draft", methods=["POST"])
def save_draft_api(content_id):
    data = request.get_json(silent=True) or {}
    draft_content = data.get("draft_content", "")

    if not draft_content:
        return jsonify({"error": "draft_content cannot be empty"}), 400

    from services.content_pipeline import ContentPipeline
    try:
        result = ContentPipeline().save_edit(content_id, draft_content)
        return jsonify({"success": True, "pipeline": result, "qa_passed": False,
                        "message": "Saved; review must be repeated for the edited revision"})
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 409

# Shared pipeline endpoints
@content_ops_bp.route("/pipeline/console-contents", methods=["GET"])
def pipeline_console_contents_api():
    from services.pipeline_monitor import monitor_contents
    return jsonify({"contents": monitor_contents(BASE_DIR)})


@content_ops_bp.route("/contents/<content_id>/pipeline/monitor", methods=["GET"])
def pipeline_monitor_api(content_id):
    from services.pipeline_monitor import read_monitor
    try:
        return jsonify(read_monitor(BASE_DIR, content_id, request.args.get('run_id')))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except FileNotFoundError as error:
        return jsonify({"error": str(error)}), 404


@content_ops_bp.route("/contents/<content_id>/pipeline/publish-check", methods=["POST"])
def inspect_publish_api(content_id):
    from services.pipeline_monitor import read_monitor
    from services.article_publish_checks import inspect_article
    from services.content_pipeline import atomic
    data = request.get_json(silent=True) or {}
    try:
        latest = read_monitor(BASE_DIR, content_id)
        run_id = data.get('run_id')
        draft_sha256 = data.get('draft_sha256')
        if not run_id or run_id != latest.get('run_id'):
            return jsonify({'error': '과거 실행이거나 유효하지 않은 실행입니다. 최신 실행에서만 검사를 수행할 수 있습니다.'}), 409
        if not draft_sha256 or draft_sha256 != latest.get('draft_sha256'):
            return jsonify({'error': '원고 해시가 일치하지 않거나 누락되었습니다. 최신 실행을 확인하세요.'}), 409
        selected = latest
        if not selected.get('markdown'):
            return jsonify({'error': '선택한 실행에 작성된 원고가 없습니다.'}), 409
        report = inspect_article(selected['markdown'], {'search': selected.get('search') or {}}, selected['asset_bindings'])
        destination = Path(BASE_DIR) / 'content-system/working' / content_id / 'inspections' / (selected['run_id'] + '-publish-checks.json')
        atomic(destination, report)
        return jsonify(report)
    except ValueError as error:
        return jsonify({'error': str(error)}), 400
    except FileNotFoundError as error:
        return jsonify({'error': str(error)}), 404


@content_ops_bp.route("/contents/<content_id>/pipeline/trace", methods=["GET"])
def pipeline_trace_api(content_id):
    from services.pipeline_trace import read_trace
    try:
        return jsonify(read_trace(content_id, since=request.args.get('since')))
    except (ValueError, FileNotFoundError) as error:
        return jsonify({"error": str(error)}), 400

@content_ops_bp.route("/pipeline/dispatch", methods=["POST"])
def dispatch_pipeline_api():
    from services.pipeline_dispatcher import dispatcher
    try:
        data = request.get_json(silent=True) or {}
        content_id = data.get("content_id")
        start_stage = data.get("start_stage")
        user_feedback = data.get("user_feedback", "")
        force = data.get("force", bool(content_id))
        job, created = dispatcher.start(content_id=content_id, start_stage=start_stage,
                                        user_feedback=user_feedback, force=force)
        return jsonify({"success": True, "created": created, "job": job}), 202
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 409


@content_ops_bp.route('/tracking', methods=['GET'])
def tracking_dashboard_api():
    from services.taiga_tracking import tracking_snapshot
    try:
        return jsonify(tracking_snapshot(Path(BASE_DIR)))
    except Exception as exc:
        return jsonify(error=f"Tracking dashboard error: {exc}"), 500


@content_ops_bp.route('/tracking/sync', methods=['POST'])
def tracking_sync_api():
    from services.taiga_tracking import synchronize
    try:
        return jsonify(synchronize(Path(BASE_DIR)))
    except ValueError as error:
        return jsonify(error=str(error)), 409
    except RuntimeError as error:
        return jsonify(error=str(error)), 502


@content_ops_bp.route("/pipeline/operations", methods=["GET"])
def pipeline_operations_api():
    from services.pipeline_dispatcher import dispatcher
    job = dispatcher.read_job()
    return jsonify({"context_profile": "stage-specific-v1", "job": job, "snapshot": dispatcher.inspect() if not job or job['status'] not in ['CHECKING', 'RUNNING'] else None})


@content_ops_bp.route("/contents/<content_id>/generate-draft", methods=["POST"])
def generate_draft_api(content_id):
    from services.content_pipeline import ContentPipeline
    try:
        data = request.get_json(silent=True) or {}
        start_stage = data.get("start_stage")
        result = ContentPipeline().run(content_id, user_feedback=data.get("feedback", ""), start_stage=start_stage)
        outcome = result.get("outcome", "FAILED")
        qa_passed = bool(result.get("qa", {}).get("passed", False))
        publish_ready = bool(result.get("publish_ready", False))
        return jsonify({
            "success": True,
            "outcome": outcome,
            "qa_passed": qa_passed,
            "publish_ready": publish_ready,
            "pipeline": result,
            "error": result.get("error") if outcome in ["FAILED", "ERROR"] else None
        })
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 409


@content_ops_bp.route("/contents/<content_id>/pipeline", methods=["GET"])
def pipeline_result_api(content_id):
    from services.content_pipeline import ContentPipeline
    try:
        return jsonify({"pipeline": ContentPipeline().latest(content_id)})
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@content_ops_bp.route("/guide-status", methods=["GET"])
def guide_status_api():
    from services.guide_repository import GuideRepository
    try:
        repo = GuideRepository()
        active_id = repo.get_active_release_id()
        manifest = repo.verify_release(active_id) if active_id else None
        releases = sorted([d.name for d in repo.releases_dir.iterdir() if d.is_dir()]) if repo.releases_dir.exists() else []
        return jsonify({
            "active_release_id": active_id,
            "bundle_sha256": manifest.bundle_sha256 if manifest else None,
            "rules_count": len(manifest.rules) if manifest else 0,
            "guides_count": len(manifest.guides) if manifest else 0,
            "prompts_count": len(manifest.prompts) if manifest else 0,
            "releases": releases
        })
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@content_ops_bp.route("/contents/<content_id>/governance", methods=["GET"])
def content_governance_api(content_id):
    from services.content_pipeline import ContentPipeline
    pipeline = ContentPipeline()
    latest = pipeline.latest(content_id)
    if not latest or not latest.get("run_directory"):
        return jsonify({"error": "No run directory found for this content"}), 404

    run_dir = Path(latest["run_directory"])
    res = {
        "content_id": content_id,
        "run_id": latest.get("run_id"),
        "guide_manifest": None,
        "requirements": None,
        "review_report": None,
        "review_report_md": None,
        "coverage": None,
    }

    manifest_file = run_dir / "guide-manifest.json"
    if manifest_file.exists():
        try:
            res["guide_manifest"] = json.loads(manifest_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    req_file = run_dir / "requirements.json"
    if req_file.exists():
        try:
            res["requirements"] = json.loads(req_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    rep_file = run_dir / "review-report.json"
    if rep_file.exists():
        try:
            res["review_report"] = json.loads(rep_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    rep_md_file = run_dir / "review-report.md"
    if rep_md_file.exists():
        try:
            res["review_report_md"] = rep_md_file.read_text(encoding="utf-8")
        except Exception:
            pass

    # Find latest coverage
    cov_files = sorted(run_dir.glob("coverage/*.json"), reverse=True)
    if cov_files:
        try:
            res["coverage"] = json.loads(cov_files[0].read_text(encoding="utf-8"))
        except Exception:
            pass

    return jsonify(res)



@content_ops_bp.route("/contents/<content_id>/pipeline/approve", methods=["POST"])
def pipeline_approve_api(content_id):
    from services.content_pipeline import ContentPipeline
    data = request.get_json(silent=True) or {}
    try:
        result = ContentPipeline().approve(content_id, data.get("run_id"), data.get("draft_sha256"),
            data.get("reviewer", ""), data.get("bindings", {}), data.get("resolutions", []))
        return jsonify({"success": True, "pipeline": result})
    except (ValueError, TypeError) as error:
        return jsonify({"success": False, "error": str(error)}), 409


@content_ops_bp.route('/contents/<content_id>/approval', methods=['GET'])
def approval_snapshot_api(content_id):
    from services.article_approval import ArticleApproval
    try:
        return jsonify(ArticleApproval(BASE_DIR).snapshot(content_id))
    except (ValueError, FileNotFoundError) as error:
        return jsonify(error=str(error)), 409


@content_ops_bp.route('/contents/<content_id>/approval/<action>', methods=['POST'])
def approval_action_api(content_id, action):
    from services.article_approval import ArticleApproval
    data=request.get_json(silent=True) or {}
    try:
        service=ArticleApproval(BASE_DIR)
        if action=='images': result=service.images(content_id,data)
        elif action=='final': result=service.finalize(content_id,data)
        elif action=='publish': result=service.publish(content_id,data)
        else: return jsonify(error='Unknown approval action'),404
        return jsonify(success=True,snapshot=result)
    except (ValueError, FileNotFoundError, KeyError) as error:
        return jsonify(error=str(error)),409
    except Exception:
        return jsonify(error='승인 처리에 실패했습니다. 현재 상태를 새로고침하고 서버 설정을 확인하세요.'),502

@content_ops_bp.route('/contents/<content_id>/publish', methods=['POST'])
def publish_url_api(content_id):
    from services.article_approval import ArticleApproval
    data = request.get_json(silent=True) or {}
    try:
        service = ArticleApproval(BASE_DIR)
        result = service.publish(content_id, data)
        return jsonify(success=True, snapshot=result)
    except (ValueError, FileNotFoundError, KeyError) as error:
        return jsonify(error=str(error)), 409
    except Exception as e:
        return jsonify(error='발행 URL 등록 실패: ' + str(e)), 502



# 6. Upload / Paste Asset (Image / GIF)
@content_ops_bp.route("/contents/<content_id>/asset", methods=["POST"])
def upload_asset_api(content_id):
    from services.content_pipeline import ContentPipeline
    from services.pipeline_monitor import read_monitor
    try:
        ContentPipeline().work(content_id)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    data = request.get_json(silent=True) or {}
    try:
        latest = read_monitor(BASE_DIR, content_id)
        run_id = data.get("run_id")
        draft_sha256 = data.get("draft_sha256")
        if not run_id or run_id != latest.get("run_id"):
            return jsonify({"error": "과거 실행이거나 유효하지 않은 실행입니다. 최신 실행에서만 자산을 등록할 수 있습니다."}), 409
        if not draft_sha256 or draft_sha256 != latest.get("draft_sha256"):
            return jsonify({"error": "원고 해시가 일치하지 않거나 누락되었습니다. 최신 실행을 확인하세요."}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    image_b64 = data.get("image_base64")
    ext = data.get("ext", "png").lower().replace(".", "")
    caption = data.get("caption", "")
    purpose = data.get("purpose", "회의실 구축 실사 이미지")

    if not image_b64:
        # Check files in form-data
        if "file" in request.files:
            file_obj = request.files["file"]
            fn = file_obj.filename
            ext = fn.split(".")[-1].lower() if "." in fn else "png"
            raw_bytes = file_obj.read()
        else:
            return jsonify({"error": "image_base64 or file upload is required"}), 400
    else:
        # Base64 decode
        if "," in image_b64:
            image_b64 = image_b64.split(",")[1]
        try:
            raw_bytes = base64.b64decode(image_b64)
        except Exception as e:
            return jsonify({"error": f"Invalid base64: {e}"}), 400

    if ext not in {'png', 'jpg', 'jpeg', 'gif', 'webp'}:
        return jsonify({"error": "지원하지 않는 이미지 확장자입니다."}), 400
    asset_dir = os.path.join(ASSETS_ROOT, content_id)
    os.makedirs(asset_dir, exist_ok=True)

    # Generate sequence ID
    cid_short = content_id.replace("CNT-", "").replace("-", "")
    existing = glob.glob(os.path.join(asset_dir, f"AST-{cid_short}-*.*"))
    seq = len(existing) + 1
    asset_id = f"AST-{cid_short}-{seq:03d}"
    filename = f"{asset_id}.{ext}"
    target_path = os.path.join(asset_dir, filename)

    with open(target_path, "wb") as f:
        f.write(raw_bytes)

    # Update assets.yaml
    assets_yaml_file = os.path.join(asset_dir, "assets.yaml")
    current_assets_data = {"assets": []}
    if os.path.exists(assets_yaml_file):
        try:
            with open(assets_yaml_file, "r", encoding="utf-8") as yf:
                current_assets_data = yaml.safe_load(yf) or {"assets": []}
        except Exception:
            pass

    asset_entry = {
        "asset_id": asset_id,
        "content_id": content_id,
        "type": ext,
        "filename": filename,
        "url": f"/api/content-system/assets/{content_id}/{filename}",
        "caption": caption,
        "purpose": purpose,
        "created_at": datetime.now().isoformat()
    }
    # Upload success is a candidate, never automatic approval.
    import hashlib
    import io
    try:
        from PIL import Image
        with Image.open(io.BytesIO(raw_bytes)) as uploaded_image:
            dimensions = {"width": uploaded_image.width, "height": uploaded_image.height}
            detected_mime = Image.MIME.get(uploaded_image.format)
            uploaded_image.verify()
    except Exception:
        Path(target_path).unlink(missing_ok=True)
        return jsonify({"error": "올바른 이미지 파일을 등록해 주세요."}), 400
    asset_entry.update(revision=1, origin_type="owned", source_ref={"type": "admin_upload"},
                       need_id=data.get("need_id"), rights_status="needs_review", entity_ids=[], fact_ids=[],
                       local_path=str(Path(target_path).relative_to(BASE_DIR)).replace('\\', '/'),
                       public_url=None, mime_type=detected_mime, dimensions=dimensions,
                       sha256=hashlib.sha256(raw_bytes).hexdigest(), alt=caption or purpose,
                       review_status="candidate", lifecycle_status="candidate", reviewer=None, reviewed_at=None)

    # Cloud Sync with Google Drive
    drive_url = None
    try:
        from services.gdrive_sync import gdrive_sync
        drive_url = gdrive_sync.upload_file(target_path, filename=filename, subfolder_name=content_id)
        if not drive_url:
            drive_url = gdrive_sync.resolve_cdn_url(filename)
    except Exception as ge:
        print(f"[WARN] GDrive sync notice: {ge}")

    if drive_url:
        asset_entry["drive_url"] = drive_url

    current_assets_data.setdefault("assets", []).append(asset_entry)

    with open(assets_yaml_file, "w", encoding="utf-8") as yf:
        yaml.safe_dump(current_assets_data, yf, allow_unicode=True, sort_keys=False)

    effective_img_url = drive_url if drive_url else asset_entry["url"]
    return jsonify({
        "success": True,
        "asset_id": asset_id,
        "url": asset_entry["url"],
        "drive_url": drive_url,
        "markdown_tag": f"![{caption or purpose}]({effective_img_url})",
        "placeholder_tag": f"{{{{asset:{asset_id}}}}}"
    })

# Serve Asset files directly
@content_ops_bp.route("/assets/<content_id>/<path:filename>", methods=["GET"])
def serve_asset_file(content_id, filename):
    if not re.fullmatch(r'CNT-[A-Za-z0-9-]+', content_id):
        return jsonify({'error': 'Invalid content ID'}), 404
    asset_dir = os.path.join(ASSETS_ROOT, content_id)
    if not (Path(asset_dir) / filename).resolve().is_relative_to(Path(asset_dir).resolve()):
        return jsonify({'error': 'Invalid asset path'}), 404
    return send_from_directory(asset_dir, filename)


@content_ops_bp.route('/contents/<content_id>/image-revisions', methods=['GET', 'POST'])
def image_revision_api(content_id):
    from services.asset_revision import snapshot, submit, add_slot, ensure_processor
    try:
        if request.method == 'GET':
            return jsonify(snapshot(content_id))
        if request.headers.get('Origin') and request.headers['Origin'].rstrip('/') != request.host_url.rstrip('/'):
            return jsonify(error='동일한 로컬 관리 화면에서 요청하세요.'), 403
        data = request.get_json(silent=True) or {}
        job = add_slot(content_id, data) if data.get('mode') == 'add_slot' else submit(content_id, data)
        ensure_processor()
        return jsonify(job), 202
    except (ValueError, KeyError, FileNotFoundError) as error:
        return jsonify(error=str(error)), 400


@content_ops_bp.route('/image-revisions/<request_id>', methods=['GET'])
def image_revision_status_api(request_id):
    import uuid
    from services.ide_worker_bridge import load
    try:
        identity = str(uuid.UUID(request_id))
        from services.asset_revision import processor_status, ensure_processor
        job = load(Path(BASE_DIR) / 'worker-control/asset-revisions' / identity / 'job.json')
        if not processor_status()['alive']:
            ensure_processor()
        return jsonify({**job, 'processor': processor_status()})
    except (ValueError, FileNotFoundError):
        return jsonify(error='재제작 요청을 찾을 수 없습니다.'), 404

# 7. Create Evidence Request (EVREQ)
@content_ops_bp.route("/contents/<content_id>/evidence-request", methods=["POST"])
def create_evreq_api(content_id):
    data = request.get_json(silent=True) or {}
    product = data.get("product", "Logitech Device")
    missing_type = data.get("missing_type", "MISSING_SPEC")
    question = data.get("question", "")
    severity = data.get("severity", "HIGH")
    needed_for = data.get("needed_for", "본문 기술 설명 근거 보강")

    if not question:
        return jsonify({"error": "question is required"}), 400

    args = [
        "--content-id", content_id,
        "--product", product,
        "--type", missing_type,
        "--question", question,
        "--severity", severity,
        "--needed-for", needed_for
    ]

    code, out, err = run_script("create_evidence_request.py", args)
    if code == 0:
        # Move content to NEEDS_EVIDENCE
        run_script("change_status.py", [content_id, "NEEDS_EVIDENCE", "--actor", "EVIDENCE_GAP_BOT", "--details", f"EVREQ issued: {question}"])
        return jsonify({"success": True, "message": out.strip()})
    else:
        return jsonify({"success": False, "error": (err or out).strip()}), 400

# 8. List Evidence Requests
@content_ops_bp.route("/evidence-requests", methods=["GET"])
def list_evreqs():
    requests_list = []
    if os.path.exists(INBOX_DIR):
        for fn in sorted(os.listdir(INBOX_DIR), reverse=True):
            if fn.endswith(".yaml") or fn.endswith(".yml"):
                try:
                    with open(os.path.join(INBOX_DIR, fn), "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                        requests_list.append(data)
                except Exception:
                    pass
    return jsonify({"requests": requests_list})

# 9. List Sources and Freshness
@content_ops_bp.route("/sources", methods=["GET"])
def list_sources():
    sources_list = []
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            idx = yaml.safe_load(f) or {}
        today = date.today()
        raw_sources = idx.get("sources", {})
        items = []
        if isinstance(raw_sources, dict):
            for sid, sval in raw_sources.items():
                if isinstance(sval, dict):
                    sd = dict(sval)
                    sd["id"] = sid
                    items.append(sd)
        elif isinstance(raw_sources, list):
            items = raw_sources

        for s in items:
            s_dict = dict(s)
            v_str = s.get("last_verified", "2000-01-01")
            limit = int(s.get("freshness_limit_days", 90))
            try:
                v_date = datetime.strptime(v_str, "%Y-%m-%d").date()
                age = (today - v_date).days
                s_dict["age_days"] = age
                s_dict["is_stale"] = age > limit
            except Exception:
                s_dict["age_days"] = 9999
                s_dict["is_stale"] = True
            sources_list.append(s_dict)
    return jsonify({"sources": sources_list})

# 10. List Events
@content_ops_bp.route("/events", methods=["GET"])
def list_events():
    events = []
    if os.path.exists(EVENTS_LOG):
        with open(EVENTS_LOG, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        events.append(json.loads(line.strip()))
                    except Exception:
                        pass
    return jsonify({"events": list(reversed(events))})

# 11. Repair Queue API
@content_ops_bp.route("/repair-queue", methods=["POST"])
def repair_queue_api():
    code, out, err = run_script("repair_queue.py", ["--apply"])
    return jsonify({"success": code == 0, "message": (out or err).strip()})

# 12. Logitech Products Catalog API
@content_ops_bp.route("/products", methods=["GET"])
def list_products_api():
    catalog_file = os.path.join(SYSTEM_DIR, "data", "logitech_master_catalog.json")
    if not os.path.exists(catalog_file):
        return jsonify({"products": [], "total": 0})

    try:
        with open(catalog_file, "r", encoding="utf-8") as f:
            catalog = json.load(f)
        devices_dict = catalog.get("devices", {})
        category_filter = request.args.get("category", "").lower().strip()
        search_query = request.args.get("search", "").lower().strip()

        result = []
        for dev_id, dev_data in devices_dict.items():
            if category_filter and dev_data.get("category", "").lower() != category_filter:
                continue
            if search_query:
                tags_str = " ".join(dev_data.get("tags", [])).lower()
                label_str = dev_data.get("label", "").lower()
                if search_query not in dev_id.lower() and search_query not in label_str and search_query not in tags_str:
                    continue
            result.append(dev_data)

        return jsonify({"products": result, "total": len(result)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@content_ops_bp.route("/products/<product_id>", methods=["GET"])
def get_product_detail_api(product_id):
    catalog_file = os.path.join(SYSTEM_DIR, "data", "logitech_master_catalog.json")
    dev_data = {}
    if os.path.exists(catalog_file):
        try:
            with open(catalog_file, "r", encoding="utf-8") as f:
                catalog = json.load(f)
            dev_data = catalog.get("devices", {}).get(product_id, {})
        except Exception:
            pass

    # Read markdown fact sheet
    md_file = os.path.join(SYSTEM_DIR, "03_sources", "devices", f"{product_id}.md")
    md_content = ""
    images = []
    if os.path.exists(md_file):
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                md_content = f.read()
            # Extract markdown images
            import re
            img_matches = re.findall(r'!\[([^\]]*)\]\((https?://[^)]+)\)', md_content)
            for caption, url in img_matches:
                images.append({"caption": caption, "url": url})
        except Exception:
            pass

    return jsonify({
        "product_id": product_id,
        "summary": dev_data,
        "fact_sheet_md": md_content,
        "images": images
    })

# 13. Naver Blog Publication Export & SmartEditor ONE Compiler
@content_ops_bp.route("/blog-export/<content_id>", methods=["GET"])
def export_blog_post(content_id):
    from services.content_pipeline import ContentPipeline
    try:
        result = ContentPipeline().export(content_id, expected_run_id=request.args.get('run_id'),
                                          expected_sha256=request.args.get('draft_sha256'))
        return jsonify({"success": True, **result,
            "preview_url": f"/api/content-system/blog-preview/{content_id}"})
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 409


@content_ops_bp.route("/blog-preview/<content_id>", methods=["GET"])
def preview_blog_post(content_id):
    from services.content_pipeline import ContentPipeline
    from services.naver_blog_compiler import compile_markdown_to_naver_html
    from pathlib import Path
    import html
    import json
    try:
        pipeline = ContentPipeline()
        result = pipeline.latest(content_id) or {}
        from services.taiga_tracking import article_details
        details = article_details(Path(BASE_DIR), content_id, result)
        draft = details.get('markdown') or ''
        if not draft:
            if result.get('run_id'):
                raise FileNotFoundError('This run has no draft yet')
            draft = pipeline.draft_path(content_id).read_text(encoding='utf-8')
        assets = {
            "oceantech-inquiry-opening": {
                "url": "https://drive.google.com/thumbnail?id=1XZ80n6Ufe3w73TTYj2jSVF7_NWr4Pmyg&sz=w1600",
                "alt": "오우션 테크놀러지 로지텍 공식 수입 총판 B2B 문의"
            },
            "oceantech-inquiry-closing": {
                "url": "https://drive.google.com/thumbnail?id=1XZ80n6Ufe3w73TTYj2jSVF7_NWr4Pmyg&sz=w1600",
                "alt": "오우션 테크놀러지 로지텍 공식 수입 총판 B2B 문의"
            },
            "AST-OCEANTECH-INQUIRY-BANNER": {
                "url": "https://drive.google.com/thumbnail?id=1XZ80n6Ufe3w73TTYj2jSVF7_NWr4Pmyg&sz=w1600",
                "alt": "오우션 테크놀러지 로지텍 공식 수입 총판 B2B 문의"
            }
        }
        if result.get("approved_assets"):
            assets.update(result["approved_assets"])
        
        run_id = result.get("run_id")
        if run_id:
            bpath = pipeline.work(content_id) / 'runs' / run_id / 'asset-bindings.json'
            if bpath.is_file():
                try:
                    bdata = json.loads(bpath.read_text(encoding="utf-8"))
                    for b in bdata.get("bindings", []):
                        nid = b.get("need", {}).get("id")
                        cand = b.get("candidate")
                        if nid and cand and cand.get("url"):
                            assets[nid] = cand
                except Exception:
                    pass

        for binding in details.get('asset_bindings',[]):
            need=binding.get('need',{}).get('id');candidate=binding.get('candidate') or {}
            if need and candidate and need not in result.get('approved_assets',{}):
                assets[need]=candidate
        rendered = compile_markdown_to_naver_html(draft, content_id=content_id, assets_map=assets)
        label = html.escape(result.get("outcome", "UNREVIEWED_DRAFT"))
        if request.args.get('format')=='layout-json':
            from services.pipeline_context import digest
            return jsonify(content_id=content_id,run_id=result.get('run_id'),draft_sha256=digest(draft),
                           report=rendered['layout_report'])
        monitor='/naver-layout-monitor.html?content='+content_id
        return f'<meta name="viewport" content="width=device-width,initial-scale=1"><p>현재 초안 미리보기 · {label} · <a href="{html.escape(monitor,quote=True)}">줄바꿈 모니터 열기</a></p>' + rendered["html"]
    except (ValueError, FileNotFoundError) as error:
        return html.escape(str(error)), 404


@content_ops_bp.route('/performance/summary', methods=['GET'])
def performance_summary_api():
    try:
        from services.performance_db import summary
        return jsonify(summary())
    except Exception:
        return jsonify({
            'status': 'prepared',
            'message': '성과 집계 기능이 준비 상태입니다.',
            'items': []
        })


@content_ops_bp.route('/contents/<content_id>/performance', methods=['GET'])
def content_performance_api(content_id):
    try:
        from services.performance_db import content_performance
        return jsonify(content_performance(content_id))
    except Exception:
        return jsonify({
            'content_id': content_id,
            'status': 'prepared',
            'message': '원고 성과 추적 기능이 준비 상태입니다.',
            'metrics': {}
        })
