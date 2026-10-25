#!/usr/bin/env python3
"""
build_writer_context.py (v2.0 Playbook-Driven Context Builder)
Writer AI를 위해 Strategy, Core Constitution, 맞춤 Playbook(Primary 1개 + Secondary 0~2개),
공인 지식 팩(Knowledge), 검증된 소스 스냅샷, 후보 시각 자산(Candidate Assets)을
격리된 작업 폴더(working/{cid}/)로 조립 주입합니다.
"""
import os
import sys
import shutil
import yaml
import argparse
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIEFS_DIR = os.path.join(BASE_DIR, "01_keyword_ai", "briefs")
SOURCES_DIR = os.path.join(BASE_DIR, "03_sources")
INDEX_FILE = os.path.join(SOURCES_DIR, "INDEX.yaml")
KNOWLEDGE_DIR = os.path.join(SOURCES_DIR, "knowledge")
STRATEGY_DIR = os.path.join(BASE_DIR, "02_writer_ai", "strategy")
WORKING_DIR = os.path.join(BASE_DIR, "02_writer_ai", "working")

sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))
from build_writing_strategy import build_writing_strategy
from resolve_playbooks import resolve_playbooks_for_content

def load_source_index():
    if not os.path.exists(INDEX_FILE):
        return {}
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    raw = data.get("sources", [])
    if isinstance(raw, dict):
        res = {}
        for k, v in raw.items():
            if isinstance(v, dict):
                item = dict(v)
                item["id"] = k
                res[k] = item
        return res
    elif isinstance(raw, list):
        return {s["id"]: s for s in raw if isinstance(s, dict) and "id" in s}
    return {}

def find_knowledge_pack_file(knw_id):
    for root, _, files in os.walk(KNOWLEDGE_DIR):
        for f in files:
            if f.endswith(".yaml") or f.endswith(".yml"):
                if os.path.splitext(f)[0] == knw_id:
                    return os.path.join(root, f)
    return None

def build_writer_context(content_id):
    brief_file = os.path.join(BRIEFS_DIR, f"{content_id}.brief.yaml")
    if not os.path.exists(brief_file):
        raise FileNotFoundError(f"Brief file not found: {brief_file}")

    with open(brief_file, "r", encoding="utf-8") as f:
        brief = yaml.safe_load(f)

    target_dir = os.path.join(WORKING_DIR, content_id)
    sources_target_dir = os.path.join(target_dir, "sources")
    knw_target_dir = os.path.join(target_dir, "knowledge")
    os.makedirs(sources_target_dir, exist_ok=True)
    os.makedirs(knw_target_dir, exist_ok=True)

    # 1. Ensure Writing Strategy exists
    strategy_file = os.path.join(STRATEGY_DIR, f"{content_id}.strategy.yaml")
    if not os.path.exists(strategy_file):
        _, strat_data = build_writing_strategy(content_id)
    else:
        with open(strategy_file, "r", encoding="utf-8") as sf:
            strat_data = yaml.safe_load(sf) or {}

    # Copy strategy.yaml to working directory
    shutil.copy2(strategy_file, os.path.join(target_dir, "strategy.yaml"))

    # 2. Resolve and shard Playbooks & Core
    guides_dir, copied_guides = resolve_playbooks_for_content(content_id)

    # 3. Copy brief.yaml
    shutil.copy2(brief_file, os.path.join(target_dir, "brief.yaml"))

    # 4. Bundle Knowledge Packs
    bundled_knw_meta = []
    knw_ids = brief.get("knowledge_packs", [])
    for kid in knw_ids:
        k_path = find_knowledge_pack_file(kid)
        if k_path and os.path.exists(k_path):
            dest_file = f"{kid}.yaml"
            shutil.copy2(k_path, os.path.join(knw_target_dir, dest_file))
            with open(k_path, "r", encoding="utf-8") as kf:
                k_data = yaml.safe_load(kf) or {}
            bundled_knw_meta.append({
                "id": kid,
                "name": k_data.get("name"),
                "knowledge_type": k_data.get("knowledge_type"),
                "vendor": k_data.get("vendor"),
                "status": k_data.get("status"),
                "local_path": f"knowledge/{dest_file}"
            })

    with open(os.path.join(target_dir, "knowledge-index.yaml"), "w", encoding="utf-8") as f:
        yaml.safe_dump({"knowledge_packs": bundled_knw_meta}, f, allow_unicode=True, sort_keys=False)

    # 5. Lookup and copy required sources as read-only snapshot
    source_index = load_source_index()
    bundled_sources_meta = []
    missing_sources = []

    for sid in brief.get("required_sources", []):
        if sid in source_index:
            s_meta = source_index[sid]
            src_rel_path = s_meta.get("path", "")
            src_abs_path = os.path.join(SOURCES_DIR, src_rel_path)
            if os.path.exists(src_abs_path):
                dest_filename = f"{sid}.md"
                dest_path = os.path.join(sources_target_dir, dest_filename)
                shutil.copy2(src_abs_path, dest_path)
                bundled_sources_meta.append({
                    "id": sid,
                    "title": s_meta.get("title"),
                    "vendor": s_meta.get("vendor"),
                    "evidence_level": s_meta.get("evidence_level"),
                    "last_verified": s_meta.get("last_verified"),
                    "local_path": f"sources/{dest_filename}"
                })
            else:
                missing_sources.append(sid)
        else:
            missing_sources.append(sid)

    if missing_sources:
        raise ValueError(f"Cannot build context pack: Missing required sources on disk: {missing_sources}")

    with open(os.path.join(target_dir, "source-index.yaml"), "w", encoding="utf-8") as f:
        yaml.safe_dump({"sources": bundled_sources_meta}, f, allow_unicode=True, sort_keys=False)

    # 6. Resolve Candidate Assets
    from resolve_assets import resolve_assets_for_content
    available_assets, asset_bindings, unresolved_assets = resolve_assets_for_content(content_id)

    # 7. Generate Streamlined Reader-First TASK.md
    reader_questions = strat_data.get("reader", {}).get("questions", [])
    questions_text = "\n".join([f"- **Q{i+1}**: {q}" for i, q in enumerate(reader_questions)])
    
    suggested_flow = strat_data.get("suggested_flow", [])
    flow_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(suggested_flow)])

    must_cover = strat_data.get("must_cover", [])
    must_text = "\n".join([f"- {m}" for m in must_cover])

    can_omit = strat_data.get("can_omit", [])
    omit_text = "\n".join([f"- {o}" for o in can_omit])

    avoid = strat_data.get("avoid", [])
    avoid_text = "\n".join([f"- {a}" for a in avoid])

    assets_text = ""
    for a in available_assets:
        roles_str = a.get("asset_type", "").upper()
        assets_text += f"- `{{{{asset:{a['asset_id']}}}}}` : [{roles_str}] {a['feature']} - {a.get('caption', '')}\n"
        if a.get("customer_message"):
            assets_text += f"  - 추천 활용 맥락: \"{a['customer_message']}\"\n"

    task_content = f"""# Writing Task: {content_id} (Playbook-Driven vNext)

- **Content ID**: `{content_id}`
- **Batch ID**: `{brief.get('batch_id')}`
- **Primary Keyword**: `{brief.get('search', {}).get('primary_keyword')}`
- **Layman Search Terms**: {', '.join(brief.get('search', {}).get('layman_terms', []))}
- **Canonical Topic**: `{brief.get('canonical_topic')}`
- **Article Goal**: {strat_data.get('article_goal')}

---

## 📚 Writing Modes (Playbooks)
- **PRIMARY PLAYBOOK**: `{strat_data.get('primary_playbook')}` (`guides/primary.md`)
- **SECONDARY PLAYBOOKS**: {', '.join(strat_data.get('secondary_playbooks', []))} (`guides/secondary-*.md`)
- **CORE CONSTITUTION**: `guides/WRITING_CORE.md`, `guides/STYLE_CORE.md`, `guides/SAFETY_CORE.md`

---

## 🙋 핵심 독자 질문 (Reader Questions - 이 순서로 궁금증을 해결하십시오)
{questions_text}

---

## 💡 권장 흐름 (Suggested Flow - 필요 시 자연스럽게 조정 가능)
{flow_text}

---

## ⚖️ 지식 및 스펙 제어 지침
### ✅ 반드시 포함할 핵심 (Must Cover):
{must_text}

### 🚫 생략할 스펙 (Can Omit - 독자의 의사결정에 방해되는 전기/나사/포트 세부 스펙):
{omit_text}

### ⚠️ 절대 피할 형식 (Avoid - 기계적 템플릿 금지):
{avoid_text}

---

## 🖼️ 활용 가능한 시각 자산 (Candidate Assets)
*독자가 눈으로 확인하고 싶은 가장 자연스러운 순간에 `{{{{asset:AST-ID}}}}` 문법으로 배치하십시오.*
{assets_text}

---

## 🔓 Writer AI 편집 자유도 선언 (Editorial Freedom)
1. **높은 편집 자유도 (HIGH)**: 고정된 목차 체크리스트는 없습니다. 독자의 질문 흐름에 맞춰 소제목을 자유롭고 매력적으로 구성하십시오.
2. **낮은 사실 자유도 (LOW)**: 공식 수치나 스펙 범위를 임의 날조해서는 안 됩니다. 기술 수치는 `knowledge/*`를 엄격히 준수하십시오.
3. **자연스러운 스토리텔링**: `FACT:`나 `WHAT IT MEANS:` 같은 기계적 레이블을 본문에 출력하지 마십시오.

작성 완료 후 초안은 다음 경로에 저장하십시오:
`../../drafts/{content_id}.draft.md`
"""

    with open(os.path.join(target_dir, "TASK.md"), "w", encoding="utf-8") as f:
        f.write(task_content)

    return target_dir, bundled_sources_meta, bundled_knw_meta

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Build Writer Context Pack with Strategy, Playbooks, Knowledge Packs and isolated sources")
    parser.add_argument("content_id", help="Content ID (e.g. CNT-2026W39-001)")
    args = parser.parse_args()

    try:
        out_dir, srcs, knws = build_writer_context(args.content_id)
        print(f"[OK] Context Pack built for '{args.content_id}':")
        print(f"  -> Path: {out_dir}")
        print(f"  -> TASK.md & strategy.yaml & guides/ & knowledge/ & assets.yaml & source-index.yaml generated")
        print(f"  -> Bundled Knowledge Packs ({len(knws)}): {[k['id'] for k in knws]}")
        print(f"  -> Bundled Sources ({len(srcs)}): {[s['id'] for s in srcs]}")
    except Exception as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        sys.exit(1)
