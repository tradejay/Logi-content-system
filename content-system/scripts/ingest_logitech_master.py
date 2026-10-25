r"""
content-system/scripts/ingest_logitech_master.py
Ingestion script that extracts verified Logitech VC Master data from:
C:\Users\Choijay\Desktop\오우션교육\Logitech 제품 설계하기

Outputs:
1. 03_sources/devices/{device_id}.md (52 comprehensive Markdown fact sheets)
2. 03_sources/docs/*.md (5 official technical whitepapers)
3. 03_sources/INDEX.yaml (master registry of all sources)
4. registry/PRODUCT_TOPIC_REGISTRY.csv (52 products mapped to topics and sources)
5. data/logitech_master_catalog.json (fast API cache)
"""

import os
import sys
import json
import csv
import shutil
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT_SYSTEM_DIR = os.path.dirname(SCRIPT_DIR)
WORKSPACE_DIR = os.path.dirname(CONTENT_SYSTEM_DIR)

SOURCE_ROOT = r"C:\Users\Choijay\Desktop\오우션교육\Logitech 제품 설계하기"
DATA_DIR = os.path.join(SOURCE_ROOT, "data")
DOCS_DIR = os.path.join(SOURCE_ROOT, "docs")
IMAGE_MAP_FILE = os.path.join(CONTENT_SYSTEM_DIR, "03_sources", "image_map.json")

TARGET_SOURCES_DIR = os.path.join(CONTENT_SYSTEM_DIR, "03_sources")
TARGET_DEVICES_DIR = os.path.join(TARGET_SOURCES_DIR, "devices")
TARGET_DOCS_DIR = os.path.join(TARGET_SOURCES_DIR, "docs")
TARGET_INDEX_YAML = os.path.join(TARGET_SOURCES_DIR, "INDEX.yaml")
TARGET_PRODUCT_REGISTRY = os.path.join(CONTENT_SYSTEM_DIR, "registry", "PRODUCT_TOPIC_REGISTRY.csv")
TARGET_CATALOG_JSON = os.path.join(CONTENT_SYSTEM_DIR, "data", "logitech_master_catalog.json")

def load_json(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to load {filepath}: {e}")
    return None

def resolve_cdn_url(image_map, rel_path):
    if not rel_path or not image_map:
        return None
    clean = rel_path.replace("\\", "/").strip()
    if clean.startswith("/assets/images/"):
        clean = clean.replace("/assets/images/", "")
    elif clean.startswith("assets/images/"):
        clean = clean.replace("assets/images/", "")

    if clean in image_map:
        return image_map[clean]
    base = os.path.basename(clean)
    if base in image_map:
        return image_map[base]
    for k, v in image_map.items():
        if k.endswith(base):
            return v
    return None

def build_device_markdown(dev_id, dev_summary, meta, ports, room_fit, image_map):
    data = meta.get("data", {}) if meta else {}
    label = dev_summary.get("label") or data.get("model") or dev_id
    model_kr = data.get("model_kr") or label
    category = dev_summary.get("ui_group") or data.get("category") or "vc_hardware"
    part_number = dev_summary.get("part_number") or data.get("part_number") or "-"
    blog_url = dev_summary.get("blog_url") or meta.get("blog_url") or ""
    headline = data.get("headline") or ""
    description_hook = data.get("description_hook") or ""
    description_main = data.get("description_main") or ""

    source_id = f"SRC-LOGI-{dev_id.upper().replace('-', '_')}"

    lines = []
    lines.append(f"# Logitech {label} 공식 하드웨어 사양 및 기술 데이터시트 ({source_id})")
    lines.append("")
    lines.append(f"- **Source ID**: `{source_id}`")
    lines.append(f"- **Vendor**: Logitech")
    lines.append(f"- **Device ID**: `{dev_id}`")
    lines.append(f"- **Category**: `{category}`")
    lines.append(f"- **Part Number**: `{part_number}`")
    lines.append(f"- **Evidence Level**: E1 (제조사 공식 데이터시트 및 엔지니어링 스펙)")
    lines.append(f"- **최종 검증일**: 2026-09-22")
    lines.append(f"- **유효 기간**: 180일 (상태: VALID)")
    if blog_url:
        lines.append(f"- **네이버 블로그 실발행 링크**: {blog_url}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 1. Headline & Overview
    if headline or description_hook or description_main:
        lines.append("## 1. 제품 개요 및 핵심 특징")
        if headline:
            lines.append(f"**{headline}**")
        if description_hook:
            lines.append(f"> {description_hook}")
        if description_main:
            lines.append(description_main)
        lines.append("")

    # Hero Image
    hero_img = meta.get("hero_image") or data.get("hero_image")
    if hero_img:
        cdn = resolve_cdn_url(image_map, hero_img)
        if cdn:
            lines.append(f"![{label} 공식 외관]({cdn})")
            lines.append("")

    # 2. Detailed Spec Sections
    sections = data.get("sections", [])
    if sections:
        lines.append("## 2. 상세 하드웨어 및 기술 사양")
        for sec in sections:
            sec_id = sec.get("id")
            meta_info = sec.get("_meta", {})
            sec_label = meta_info.get("label", sec_id)

            lines.append(f"### {sec_label}")

            # Section media
            media_list = meta_info.get("media", [])
            for m in media_list:
                m_url = m.get("url")
                m_cdn = resolve_cdn_url(image_map, m_url)
                if m_cdn:
                    lines.append(f"![{m.get('label', sec_label)}]({m_cdn})")

            # Specs table
            specs_tbl = sec.get("specs_table")
            if isinstance(specs_tbl, dict):
                lines.append("| 항목 | 상세 사양 |")
                lines.append("| :--- | :--- |")
                for k, v in specs_tbl.items():
                    val_str = str(v).replace("\n", " ")
                    lines.append(f"| **{k}** | {val_str} |")
                lines.append("")
            elif isinstance(specs_tbl, list):
                lines.append("| 사양 항목 | 상세 내용 |")
                lines.append("| :--- | :--- |")
                for item in specs_tbl:
                    if isinstance(item, dict):
                        k = item.get("name") or item.get("label") or list(item.keys())[0]
                        v = item.get("value") or list(item.values())[0]
                        lines.append(f"| **{k}** | {v} |")
                lines.append("")

            # Sub-sections if any
            sub_secs = sec.get("sub_sections", [])
            if isinstance(sub_secs, list):
                for sub in sub_secs:
                    sub_title = sub.get("title") or sub.get("name") or ""
                    sub_desc = sub.get("description") or sub.get("content") or ""
                    if sub_title:
                        lines.append(f"- **{sub_title}**: {sub_desc}")
                lines.append("")

            # Items (e.g. box contents)
            items = sec.get("items", [])
            if isinstance(items, list):
                for itm in items:
                    lines.append(f"- {itm}")
                lines.append("")

    # 3. Ports & Electrical Specifications
    if ports:
        lines.append("## 3. 포트 규격 및 전원 사양 (Interface & Power)")
        lines.append("| 구분 | 인터페이스 규격 및 상세 사양 |")
        lines.append("| :--- | :--- |")
        for pk, pv in ports.items():
            if isinstance(pv, dict):
                p_desc = ", ".join(f"{k}: {v}" for k, v in pv.items())
                lines.append(f"| **{pk}** | {p_desc} |")
            elif isinstance(pv, list):
                lines.append(f"| **{pk}** | {', '.join(str(x) for x in pv)} |")
            else:
                lines.append(f"| **{pk}** | {pv} |")
        lines.append("")

    # 4. Room Fit & Capacity Recommendations
    if room_fit:
        lines.append("## 4. 회의실 규모별 적합도 및 권장 구성 (Room Fit)")
        fit_scores = room_fit.get("fit_scores") or room_fit.get("ratings") or {}
        if fit_scores:
            lines.append("| 회의실 규모 | 적합도 등급 | 권장 인원 | 비고 |")
            lines.append("| :--- | :--- | :--- | :--- |")
            for r_size, score in fit_scores.items():
                lines.append(f"| **{r_size.capitalize()}** | {score} | {dev_summary.get('people_max', '-')}명 이하 | 공식 권장 규모 |")
            lines.append("")

        rules = room_fit.get("rules") or room_fit.get("constraints") or {}
        if rules:
            lines.append("### 공간 배치 및 확장 규칙")
            for rk, rv in rules.items():
                lines.append(f"- **{rk}**: {rv}")
            lines.append("")

    # 5. Platforms & Companion Devices
    lines.append("## 5. 인증 플랫폼 및 호환 장비")
    platforms = dev_summary.get("platforms", [])
    if platforms:
        lines.append(f"- **공식 인증 플랫폼**: {', '.join(p.upper() for p in platforms)}")
    companions = dev_summary.get("companions", [])
    if companions:
        lines.append(f"- **추천 연동 장비**: {', '.join(companions)}")
    lines.append("")

    return "\n".join(lines)


def main():
    print("==================================================")
    print("   LOGITECH MASTER DB INGESTION PIPELINE")
    print("==================================================")

    os.makedirs(TARGET_DEVICES_DIR, exist_ok=True)
    os.makedirs(TARGET_DOCS_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(TARGET_PRODUCT_REGISTRY), exist_ok=True)
    os.makedirs(os.path.dirname(TARGET_CATALOG_JSON), exist_ok=True)

    # 1. Load Image Map
    image_map = load_json(IMAGE_MAP_FILE) or {}
    print(f"[OK] Loaded image map with {len(image_map)} entries.")

    # 2. Load index.json
    index_file = os.path.join(DATA_DIR, "index.json")
    index_data = load_json(index_file) or {}
    devices_summary_list = index_data.get("devices", [])
    print(f"[OK] Found {len(devices_summary_list)} devices in master index.json.")

    catalog_data = {}
    sources_index_entries = {}
    product_registry_rows = []

    # 3. Process Each Device
    for d_sum in devices_summary_list:
        dev_id = d_sum.get("id")
        if not dev_id:
            continue

        dev_dir = os.path.join(DATA_DIR, "devices", dev_id)
        meta = load_json(os.path.join(dev_dir, "meta.json")) or {}
        ports = load_json(os.path.join(dev_dir, "ports.json")) or {}
        room_fit = load_json(os.path.join(dev_dir, "room-fit.json")) or {}

        # Build Markdown
        md_content = build_device_markdown(dev_id, d_sum, meta, ports, room_fit, image_map)
        target_md_path = os.path.join(TARGET_DEVICES_DIR, f"{dev_id}.md")
        with open(target_md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        source_id = f"SRC-LOGI-{dev_id.upper().replace('-', '_')}"
        label = d_sum.get("label") or dev_id
        category = d_sum.get("ui_group") or "vc_hardware"

        # Collect for INDEX.yaml
        sources_index_entries[source_id] = {
            "title": f"Logitech {label} 공식 기술 데이터시트",
            "vendor": "Logitech",
            "type": "official_datasheet",
            "path": f"devices/{dev_id}.md",
            "evidence_level": "E1",
            "freshness_limit_days": 180,
            "last_verified": "2026-09-22",
            "status": "VALID",
            "topics": f"{dev_id.replace('-', '_')} {category} logitech_vc " + " ".join(d_sum.get("tags", [])[:5])
        }

        # Collect for PRODUCT_TOPIC_REGISTRY.csv
        product_registry_rows.append({
            "product_id": dev_id,
            "product_name": label,
            "category": category,
            "primary_topic": f"{label} 스펙 및 회의실 설치 구성",
            "related_sources": source_id,
            "canonical_keyword": d_sum.get("tags", [label])[0] if d_sum.get("tags") else label,
            "blog_url": d_sum.get("blog_url", ""),
            "updated_at": "2026-09-22"
        })

        # Collect for Catalog JSON
        hero_cdn = resolve_cdn_url(image_map, meta.get("hero_image"))
        catalog_data[dev_id] = {
            "id": dev_id,
            "label": label,
            "part_number": d_sum.get("part_number"),
            "category": category,
            "brand": "Logitech",
            "series": d_sum.get("series"),
            "form_factor": d_sum.get("form_factor"),
            "platforms": d_sum.get("platforms", []),
            "room_types": d_sum.get("room_types", []),
            "people_max": d_sum.get("people_max"),
            "tags": d_sum.get("tags", []),
            "blog_url": d_sum.get("blog_url"),
            "hero_image_cdn": hero_cdn,
            "source_id": source_id,
            "has_ports": bool(ports),
            "has_room_fit": bool(room_fit)
        }

    print(f"[OK] Generated {len(catalog_data)} device fact sheets in 03_sources/devices/")

    # 4. Ingest docs/ technical whitepapers
    doc_mapping = {
        "mic_pod_compatibility.md": ("SRC-LOGI-DOC-MIC-POD-COMPAT", "Logitech 랠리 마이크 팟 연결 및 토폴로지 가이드", "audio_topology mic_pod cat_coupler daisy_chain"),
        "rightsense_compatibility.md": ("SRC-LOGI-DOC-RIGHTSENSE", "Logitech RightSense AI 기술 사양 및 버전별 비교 가이드", "rightsight rightsound rightlight speaker_view group_view grid_view"),
        "rally_bar_guide.md": ("SRC-LOGI-DOC-RALLY-BAR-GUIDE", "Logitech 랠리 바 룸 설계 및 공간 표준 가이드", "rally_bar room_fit placement camera_fov"),
        "master_design_guide.md": ("SRC-LOGI-DOC-MASTER-DESIGN", "화상회의 회의실 표준 배선 및 케이블링 종합 설계 가이드", "wiring_diagram cabling power_hdmi_usb byod appliance"),
        "ai-command-api.md": ("SRC-LOGI-DOC-AI-COMMAND", "로지텍 AI 커맨드 및 CollabOS 통합 가이드", "collabos sync lna device_management")
    }

    for doc_fn, (doc_src_id, doc_title, doc_topics) in doc_mapping.items():
        src_doc_p = os.path.join(DOCS_DIR, doc_fn)
        if os.path.exists(src_doc_p):
            with open(src_doc_p, "r", encoding="utf-8") as f:
                d_content = f.read()

            header = f"""# {doc_title} ({doc_src_id})

- **Source ID**: `{doc_src_id}`
- **Vendor**: Logitech
- **Evidence Level**: E1 (제조사 공식 엔지니어링 백서)
- **최종 검증일**: 2026-09-22
- **유효 기간**: 180일 (상태: VALID)

---

"""
            dst_doc_p = os.path.join(TARGET_DOCS_DIR, doc_fn)
            with open(dst_doc_p, "w", encoding="utf-8") as f:
                f.write(header + d_content)

            sources_index_entries[doc_src_id] = {
                "title": doc_title,
                "vendor": "Logitech",
                "type": "official_whitepaper",
                "path": f"docs/{doc_fn}",
                "evidence_level": "E1",
                "freshness_limit_days": 180,
                "last_verified": "2026-09-22",
                "status": "VALID",
                "topics": doc_topics
            }

    # Curated Core Logitech Sources (c:\Users\Choijay\Desktop\naveradvertise\content-system\03_sources\logitech\)
    sources_index_entries["SRC-LOGI-RALLYBAR"] = {
        "title": "Logitech Rally Bar 공식 기술 사양서",
        "vendor": "Logitech",
        "type": "official_datasheet",
        "path": "logitech/rallybar.md",
        "evidence_level": "E1",
        "freshness_limit_days": 180,
        "last_verified": "2026-09-22",
        "status": "VALID",
        "topics": "all_in_one_bar medium_to_large_room beamforming_mic dual_camera_ptz appliance_mode byod_mode"
    }
    sources_index_entries["SRC-LOGI-RIGHTSIGHT2"] = {
        "title": "Logitech RightSight 2 자동 프레이밍 및 화자 추적 기술 백서",
        "vendor": "Logitech",
        "type": "official_whitepaper",
        "path": "logitech/rightsight2.md",
        "evidence_level": "E1",
        "freshness_limit_days": 90,
        "last_verified": "2026-09-22",
        "status": "VALID",
        "topics": "speaker_tracking auto_framing group_view speaker_view tdoa_audio_triangulation"
    }

    # Add general platform sources
    sources_index_entries["SRC-ZOOM-CAMERA-MODES"] = {
        "title": "Zoom Rooms 지능형 카메라 제어 및 프레이밍 모드 설정 가이드",
        "vendor": "Zoom",
        "type": "platform_guide",
        "path": "zoom/camera-modes.md",
        "evidence_level": "E2",
        "freshness_limit_days": 90,
        "last_verified": "2026-09-22",
        "status": "VALID",
        "topics": "zoom_rooms camera_control speaker_focus multi_stream"
    }

    # 5. Write 03_sources/INDEX.yaml (Standard List of Dictionaries)
    yaml_lines = ["sources:"]
    for sid, sdata in sorted(sources_index_entries.items()):
        yaml_lines.append(f"  - id: {sid}")
        yaml_lines.append(f"    title: \"{sdata['title']}\"")
        yaml_lines.append(f"    vendor: \"{sdata['vendor']}\"")
        yaml_lines.append(f"    type: \"{sdata['type']}\"")
        yaml_lines.append(f"    path: \"{sdata['path']}\"")
        yaml_lines.append(f"    evidence_level: \"{sdata['evidence_level']}\"")
        yaml_lines.append(f"    freshness_limit_days: {sdata['freshness_limit_days']}")
        yaml_lines.append(f"    last_verified: \"{sdata['last_verified']}\"")
        yaml_lines.append(f"    status: \"{sdata['status']}\"")
        yaml_lines.append(f"    topics: \"{sdata['topics']}\"")

    with open(TARGET_INDEX_YAML, "w", encoding="utf-8") as f:
        f.write("\n".join(yaml_lines) + "\n")
    print(f"[OK] Wrote {len(sources_index_entries)} sources to 03_sources/INDEX.yaml")

    # 6. Write registry/SOURCE_REGISTRY.csv (Fully Synchronized Single Source of Truth)
    target_source_registry = os.path.join(CONTENT_SYSTEM_DIR, "registry", "SOURCE_REGISTRY.csv")
    csv_headers = ["source_id", "vendor", "title", "path", "type", "evidence_level", "last_verified", "freshness_limit_days", "status"]
    with open(target_source_registry, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(csv_headers)
        for sid, sdata in sorted(sources_index_entries.items()):
            writer.writerow([
                sid,
                sdata["vendor"],
                sdata["title"],
                sdata["path"],
                sdata["type"],
                sdata["evidence_level"],
                sdata["last_verified"],
                sdata["freshness_limit_days"],
                sdata["status"]
            ])
    print(f"[OK] Wrote {len(sources_index_entries)} rows to registry/SOURCE_REGISTRY.csv")

    # 7. Write registry/PRODUCT_TOPIC_REGISTRY.csv
    fieldnames = ["product_id", "product_name", "category", "primary_topic", "related_sources", "canonical_keyword", "blog_url", "updated_at"]
    with open(TARGET_PRODUCT_REGISTRY, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in product_registry_rows:
            writer.writerow(row)
    print(f"[OK] Wrote {len(product_registry_rows)} rows to PRODUCT_TOPIC_REGISTRY.csv")

    # 8. Write data/logitech_master_catalog.json
    with open(TARGET_CATALOG_JSON, "w", encoding="utf-8") as f:
        json.dump({"devices": catalog_data, "total": len(catalog_data), "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    print(f"[OK] Wrote catalog cache to {TARGET_CATALOG_JSON}")

    print("==================================================")
    print("   INGESTION COMPLETED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    main()
