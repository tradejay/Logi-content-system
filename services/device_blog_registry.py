"""
services/device_blog_registry.py
Realtime Device Blog Registry Lookup Service.

Reads live data from:
  1. Primary: c:\\Users\\Choijay\\Desktop\\오우션교육\\Logitech 제품 설계하기\\data\\index.json
  2. Fallback: c:\\Users\\Choijay\\Desktop\\오우션교육\\Logitech 제품 설계하기\\data\\devices\\*\\meta.json
  3. Local: data\\index.json
  4. Master Catalog: content-system\\data\\logitech_master_catalog.json (for high-res CDN images)
  5. Index Assets: content-system\\03_sources\\assets\\INDEX.yaml (for AST-PROD- high-res CDN images)

Never caches stale URLs. Always reads directly from disk to reflect new blog URLs
published via Blog Manager (http://localhost:3000/manager) in real time.
"""

import os
import json
import re
import yaml

PRIMARY_INDEX_PATH = r"c:\Users\Choijay\Desktop\오우션교육\Logitech 제품 설계하기\data\index.json"
PRIMARY_DEVICES_DIR = r"c:\Users\Choijay\Desktop\오우션교육\Logitech 제품 설계하기\data\devices"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_INDEX_PATH = os.path.join(BASE_DIR, "data", "index.json")
MASTER_CATALOG_PATH = os.path.join(BASE_DIR, "content-system", "data", "logitech_master_catalog.json")
INDEX_YAML_PATH = os.path.join(BASE_DIR, "content-system", "03_sources", "assets", "INDEX.yaml")

# Keyword to device ID mapping table for natural text recognition in blog drafts
KEYWORD_TO_DEVICE_ID = {
    "rally bar mini": "logi-rally-bar-mini",
    "랠리 바 미니": "logi-rally-bar-mini",
    "rally bar huddle": "logi-rally-bar-huddle",
    "랠리 바 허들": "logi-rally-bar-huddle",
    "rally bar": "logi-rally-bar",
    "랠리 바": "logi-rally-bar",
    "rally plus": "logi-rally-plus",
    "랠리 플러스": "logi-rally-plus",
    "meetup 2": "logi-meetup-2",
    "밋업 2": "logi-meetup-2",
    "meetup": "logi-meetup",
    "밋업": "logi-meetup",
    "rally mic pod hub": "logi-rally-mic-pod-hub",
    "랠리 마이크 팟 허브": "logi-rally-mic-pod-hub",
    "mic pod hub": "logi-rally-mic-pod-hub",
    "마이크 팟 허브": "logi-rally-mic-pod-hub",
    "rally mic pod": "logi-rally-mic-pod",
    "랠리 마이크 팟": "logi-rally-mic-pod",
    "mic pod": "logi-rally-mic-pod",
    "마이크 팟": "logi-rally-mic-pod",
    "tap scheduler": "logi-tap-scheduler",
    "탭 스케줄러": "logi-tap-scheduler",
    "tap ip": "logi-tap-ip",
    "탭 ip": "logi-tap-ip",
    "tap": "logi-tap",
    "탭": "logi-tap",
    "roommate": "logi-roommate",
    "룸메이트": "logi-roommate",
    "sight": "logi-sight",
    "사이트": "logi-sight",
    "scribe": "logi-scribe",
    "스크라이브": "logi-scribe",
    "swytch": "logi-swytch",
    "스위치": "logi-swytch",
    "rally camera": "logi-rally-camera",
    "랠리 카메라": "logi-rally-camera"
}

def load_device_image_map():
    """
    Loads device hero CDN images from master catalog and INDEX.yaml.
    Returns {device_id: image_cdn_url}
    """
    img_map = {}

    # 1. Master catalog
    if os.path.exists(MASTER_CATALOG_PATH):
        try:
            with open(MASTER_CATALOG_PATH, "r", encoding="utf-8") as f:
                cat = json.load(f)
            devs = cat.get("devices", {})
            for dev_id, d in devs.items():
                cdn_img = d.get("hero_image_cdn")
                if cdn_img:
                    img_map[dev_id] = cdn_img
        except Exception as e:
            print(f"[WARN] Failed to read master catalog for images: {e}")

    # 2. INDEX.yaml (highest priority for AST-PROD- verified assets)
    if os.path.exists(INDEX_YAML_PATH):
        try:
            with open(INDEX_YAML_PATH, "r", encoding="utf-8") as f:
                idx_data = yaml.safe_load(f) or {}
            for a in idx_data.get("assets", []):
                aid = a.get("asset_id", "")
                if aid.startswith("AST-PROD-"):
                    prod = a.get("product", "").strip().lower()
                    if prod and a.get("url"):
                        img_map[prod] = a.get("url")
        except Exception as e:
            print(f"[WARN] Failed to read INDEX.yaml for images: {e}")

    return img_map

def load_realtime_device_blog_registry():
    """
    Reads the index.json file dynamically on every call.
    Returns a dict of {device_id: {"id": str, "label": str, "blog_url": str, "image_url": str}}
    """
    registry = {}
    img_map = load_device_image_map()
    
    # 1. Primary index.json
    candidates = [PRIMARY_INDEX_PATH, LOCAL_INDEX_PATH]
    found_primary = False

    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                items = data if isinstance(data, list) else data.get("devices", data.get("items", []))
                for item in items:
                    dev_id = item.get("id")
                    blog_url = item.get("blog_url", "").strip()
                    label = item.get("label") or item.get("name") or dev_id
                    if dev_id:
                        registry[dev_id] = {
                            "id": dev_id,
                            "label": label,
                            "blog_url": blog_url,
                            "image_url": img_map.get(dev_id, "")
                        }
                found_primary = True
                break
            except Exception as e:
                print(f"[WARN] Failed to read {path}: {e}")

    # 2. Check individual devices meta.json if primary missing or for overrides
    if os.path.exists(PRIMARY_DEVICES_DIR):
        try:
            for sub in os.listdir(PRIMARY_DEVICES_DIR):
                meta_path = os.path.join(PRIMARY_DEVICES_DIR, sub, "meta.json")
                if os.path.exists(meta_path):
                    with open(meta_path, "r", encoding="utf-8") as mf:
                        mdata = json.load(mf)
                    b_url = mdata.get("blog_url", "").strip()
                    dev_id = mdata.get("id") or sub
                    label = mdata.get("label") or mdata.get("name") or dev_id
                    img_url = img_map.get(dev_id, "")
                    if b_url and (dev_id not in registry or not registry[dev_id].get("blog_url")):
                        registry[dev_id] = {
                            "id": dev_id,
                            "label": label,
                            "blog_url": b_url,
                            "image_url": img_url
                        }
        except Exception as e:
            print(f"[WARN] Failed to read individual device meta.json: {e}")

    return registry

# Disambiguation Rules for Strict Matching (High-specificity patterns evaluated first)
DISAMBIGUATION_RULES = [
    # 1. MeetUp family (meetup 2 MUST precede meetup)
    (r'(?:meetup[\s_-]*2|밋업[\s_-]*2)', 'logi-meetup-2'),
    (r'(?:meetup|밋업)(?![\s_-]*2)', 'logi-meetup'),
    
    # 2. Mic Pod family (mic pod hub MUST precede pure mic pod)
    (r'(?:mic[\s_-]*pod[\s_-]*hub|마이크[\s_-]*팟[\s_-]*허브)', 'logi-rally-mic-pod-hub'),
    (r'(?:mic[\s_-]*pod[\s_-]*(?:ext|cable)|마이크[\s_-]*팟[\s_-]*연장)', 'logi-rally-mic-pod-ext-cable'),
    (r'(?:mic[\s_-]*pod[\s_-]*cat[\s_-]*coupler|마이크[\s_-]*팟[\s_-]*커플러)', 'logi-rally-mic-pod-cat-coupler'),
    (r'(?:mic[\s_-]*pod|마이크[\s_-]*팟)(?![\s_-]*(?:hub|ext|허브|연장))', 'logi-rally-mic-pod'),
    
    # 3. Rally Bar family (mini, huddle, plus precede standard bar)
    (r'(?:rally[\s_-]*bar[\s_-]*mini|랠리[\s_-]*바[\s_-]*미니)', 'logi-rally-bar-mini'),
    (r'(?:rally[\s_-]*bar[\s_-]*huddle|랠리[\s_-]*바[\s_-]*허들)', 'logi-rally-bar-huddle'),
    (r'(?:rally[\s_-]*plus|랠리[\s_-]*플러스)', 'logi-rally-plus'),
    (r'(?:rally[\s_-]*camera|랠리[\s_-]*카메라)', 'logi-rally-camera'),
    (r'(?:rally[\s_-]*bar|랠리[\s_-]*바)(?![\s_-]*(?:mini|huddle|미니|허들))', 'logi-rally-bar'),
    
    # 4. Tap family (scheduler, ip precede standard tap)
    (r'(?:tap[\s_-]*scheduler|탭[\s_-]*스케줄러)', 'logi-tap-scheduler'),
    (r'(?:tap[\s_-]*ip|탭[\s_-]*ip)', 'logi-tap-ip'),
    (r'(?:tap|탭)(?![\s_-]*(?:ip|scheduler|스케줄러))', 'logi-tap'),
    
    # 5. Standalone compute & peripherals
    (r'(?:roommate|룸메이트)', 'logi-roommate'),
    (r'(?:sight|사이트)', 'logi-sight'),
    (r'(?:scribe|스크라이브)', 'logi-scribe'),
    (r'(?:swytch|스위치)', 'logi-swytch'),
]

def resolve_device_id_strictly(query):
    """
    Resolves canonical device ID using strict disambiguation rules.
    Eliminates false substring hits (e.g. meetup matching meetup 2, or mic pod matching mic pod hub).
    """
    if not query:
        return None
    q_norm = re.sub(r'^(?:로지텍|logitech|logi)[\s_-]*', '', query.strip().lower())
    for pattern, dev_id in DISAMBIGUATION_RULES:
        if re.search(pattern, q_norm):
            return dev_id
    return None

def get_device_blog_info(query):
    """
    Finds device blog information by device ID or product name/keyword.
    Returns {"id": ..., "label": ..., "blog_url": ..., "image_url": ...} or None if not found/no blog URL.
    """
    if not query:
        return None

    registry = load_realtime_device_blog_registry()
    q_lower = query.strip().lower()

    # 1. Exact device ID match
    if q_lower in registry and registry[q_lower].get("blog_url"):
        return registry[q_lower]

    # 2. Strict Disambiguation match (high precision)
    resolved_id = resolve_device_id_strictly(query)
    if resolved_id and resolved_id in registry and registry[resolved_id].get("blog_url"):
        return registry[resolved_id]

    # 3. Fallback exact label match only (NO substring fallbacks that cause false positives)
    clean_q = re.sub(r'^(?:로지텍|logitech|logi)\s*', '', q_lower).strip()
    for dev_id, info in registry.items():
        if not info.get("blog_url"):
            continue
        label_clean = re.sub(r'^(?:로지텍|logitech|logi)\s*', '', info.get("label", "").lower()).strip()
        if clean_q == label_clean:
            return info

    return None

def get_device_main_image(query):
    """
    Returns the high-res CDN image URL for a given device ID or label/keyword.
    """
    info = get_device_blog_info(query)
    if info and info.get("image_url"):
        return info["image_url"]
    
    resolved_id = resolve_device_id_strictly(query)
    if resolved_id:
        img_map = load_device_image_map()
        if resolved_id in img_map:
            return img_map[resolved_id]

    return ""

def format_official_blog_markdown_link(query, custom_label=None):
    """
    Returns markdown formatted link:
    👉 [오우션 공식 블로그 ({label})]({blog_url})
    or None if device has no published blog URL yet.
    """
    info = get_device_blog_info(query)
    if not info or not info.get("blog_url"):
        return None

    display_label = custom_label or info.get("label", query)
    # Strip parenthesized duplicates if present, e.g. "Rally Bar (랠리 바)" -> "로지텍 랠리 바"
    display_label = re.sub(r'^[Ll]ogi(?:tech)?\s*', '로지텍 ', display_label)
    if not display_label.startswith("로지텍 "):
        # If english name only, prefix with 로지텍
        display_label = f"로지텍 {display_label}"

    clean_label = display_label.strip()
    return f"👉 [오우션 공식 블로그 ({clean_label})]({info['blog_url']})"

