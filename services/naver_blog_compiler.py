"""
services/naver_blog_compiler.py
Naver Blog SmartEditor ONE Inline CSS Compiler
Converts Markdown to inline-styled HTML for seamless drag-and-copy into Naver Blog SmartEditor ONE.
Preserves:
- NanumGothic / Apple SD Gothic Neo font stack across all tags
- Full-grid bordered tables (eliminates invisible border bug)
- Clean spacers (eliminates infinite line divider bug)
- 3-tier assertion badges ([FACT], [LIMITATION], [INTERPRETATION])
- Post-it and line-style quotation blocks
- Google Drive CDN high-res thumbnails (sz=w1000)
- ASCII flowcharts and monospace code blocks
- Logitech VC brand color accents (#0078cb)
"""

import os
import re
import html
import yaml

FONT_STACK = "'나눔고딕', NanumGothic, 'Apple SD Gothic Neo', '맑은 고딕', Malgun Gothic, sans-serif"

def mobile_lines(text, width=28):
    """AI owns editorial breaks; renderer preserves them byte-for-byte."""
    return text

def paragraph_layout(source, rendered, index):
    """Report exact hard-break origin; hints are review candidates, not verdicts."""
    authored_offsets={len(re.sub(r'\s','',source[:m.start()])) for m in re.finditer('\n',source)}
    cursor=0;boundaries=[]
    for n,line in enumerate(rendered.split('\n')[:-1],1):
        cursor+=len(re.sub(r'\s','',line))
        origin='source' if cursor in authored_offsets else 'sentence_boundary'
        right=rendered.split('\n')[n]
        hints=[]
        if origin=='source' and not re.search(r'[.!?][”"\']?\s*$',line):
            hints.append('문장 중간 원고 줄바꿈 — 앞뒤 연결 확인')
        if re.search(r'(?:옵션인|길이의|크기의|의|하는|되는)\s*$',line):
            hints.append('수식어와 대상 분리 가능성')
        boundaries.append({'line':n,'origin':origin,
                           'left':line[-70:],'right':right[:70],'hints':hints})
    return {'paragraph':index,'source':source,'rendered':rendered,'boundaries':boundaries}

def _build_default_assets_map(content_id=None):
    from pathlib import Path
    import json
    import yaml

    merged = {
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
        },
        "oceantech-inquiry-banner": {
            "url": "https://drive.google.com/thumbnail?id=1XZ80n6Ufe3w73TTYj2jSVF7_NWr4Pmyg&sz=w1600",
            "alt": "오우션 테크놀러지 로지텍 공식 수입 총판 B2B 문의"
        }
    }

    # 1. Load all assets from global INDEX.yaml
    index_path = Path("content-system/03_sources/assets/INDEX.yaml")
    if index_path.is_file():
        try:
            idata = yaml.safe_load(index_path.read_text(encoding="utf-8")) or {}
            for item in idata.get("assets", []):
                aid = item.get("asset_id")
                if aid and item.get("url"):
                    merged[aid] = item
        except Exception:
            pass

    # 2. If content_id provided, load bindings from latest run
    if content_id:
        work_dir = Path("content-system/working") / content_id
        bindings_files = sorted(list(work_dir.glob("runs/*/asset-bindings.json")), key=lambda p: p.stat().st_mtime, reverse=True)
        if bindings_files:
            try:
                bdata = json.loads(bindings_files[0].read_text(encoding="utf-8"))
                for b in bdata.get("bindings", []):
                    need = b.get("need", {})
                    nid = need.get("id")
                    need_aid = need.get("asset_id")
                    anchor = need.get("anchor")
                    cand = b.get("candidate")
                    if cand and cand.get("url"):
                        if nid: merged[nid] = cand
                        if need_aid: merged[need_aid] = cand
                        if cand.get("asset_id"): merged[cand["asset_id"]] = cand
                        if anchor:
                            clean_anchor = anchor.replace("{{asset:", "").replace("}}", "").strip()
                            merged[clean_anchor] = cand
                            merged[anchor] = cand
            except Exception:
                pass

        # 3. Load per-content asset registry (content-system/assets/{content_id}/assets.yaml)
        content_assets_path = Path("content-system/assets") / content_id / "assets.yaml"
        if content_assets_path.is_file():
            try:
                cdata = yaml.safe_load(content_assets_path.read_text(encoding="utf-8")) or {}
                for item in cdata.get("assets", []):
                    if item.get("review_status") == "rejected":
                        continue
                    aid = item.get("asset_id")
                    nid = item.get("need_id")
                    if item.get("url"):
                        if nid:
                            merged[nid] = item
                        if aid:
                            merged[aid] = item
            except Exception:
                pass

    return merged


def compile_markdown_to_naver_html(md_text, content_id=None, assets_map=None):
    """
    Takes a raw markdown string (with or without frontmatter)
    and converts it to inline-styled HTML tailored for Naver SmartEditor ONE.
    """
    base_assets = _build_default_assets_map(content_id=content_id)
    if isinstance(assets_map, dict):
        base_assets.update(assets_map)
    assets_map = base_assets

    # 1. Parse Frontmatter if present
    frontmatter = {}
    body = md_text
    if md_text.startswith("---"):
        parts = md_text.split("---", 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
            except Exception:
                frontmatter = {}
            body = parts[2].strip()

    title = frontmatter.get("title", "")
    target_kw = frontmatter.get("target_keyword", "")

    # 1.5. Extract and format Asset Placeholders (protected from paragraph and inline regex)
    asset_blocks = []
    def replace_asset_placeholder(match):
        aid = match.group(1).strip()
        asset_info = None
        if isinstance(assets_map, dict):
            asset_info = assets_map.get(aid) or assets_map.get(f"{{{{asset:{aid}}}}}")
        
        if not asset_info:
            err_box = f'<div style="background: #fff1f2; border: 1px dashed #f43f5e; color: #be123c; padding: 10px 14px; border-radius: 6px; margin: 14px 0; font-size: 13px; font-family: {FONT_STACK};">⚠️ [ASSET_REQUIRED: {aid}]</div>'
            idx = len(asset_blocks)
            asset_blocks.append(err_box)
            return f"\n\n__ASSET_BLOCK_PLACEHOLDER_{idx}__\n\n"

        if isinstance(asset_info, str):
            url = format_cdn_url(asset_info)
            caption = aid
            alt = aid
        else:
            url = format_cdn_url(asset_info.get('public_url') or asset_info.get("url", ""))
            caption = asset_info.get("caption") or asset_info.get("purpose", aid)
            alt = asset_info.get("alt", caption)

        # 100% clean and escape alt text to prevent HTML attribute injection or syntax breakout
        clean_alt = re.sub(r'<[^>]+>', '', str(alt)).strip()
        clean_alt = html.escape(clean_alt, quote=True)

        # Wrap company intro banner with official inquiry link (https://oceantec.co.kr/board/inquiry)
        is_company_banner = (
            aid == "AST-COMPANY-OCEAN-001" or
            "company_oceantech_intro" in url or
            "1XZ80n6Ufe3w73TTYj2jSVF7_NWr4Pmyg" in url or
            "오우션테크놀러지" in clean_alt or
            "공식 수입 총판" in clean_alt
        )

        if is_company_banner:
            card_html = (
                f'<div style="margin: 24px 0; text-align: center;">'
                f'  <a href="https://oceantec.co.kr/board/inquiry" target="_blank" rel="noreferrer" style="text-decoration: none; display: inline-block;">'
                f'    <img src="{url}" alt="{clean_alt}" style="max-width: 100%; height: auto; display: block; margin: 0 auto; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.06);">'
                f'  </a>'
                f'</div>'
            )
        else:
            card_html = (
                f'<div style="margin: 24px 0; text-align: center;">'
                f'  <img src="{url}" alt="{clean_alt}" style="max-width: 100%; height: auto; display: block; margin: 0 auto; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.06);">'
                f'</div>'
            )
        idx = len(asset_blocks)
        asset_blocks.append(card_html)
        return f"\n\n__ASSET_BLOCK_PLACEHOLDER_{idx}__\n\n"

    body = re.sub(r'\{\{asset:([^\}]+)\}\}', replace_asset_placeholder, body)

    # 2. Extract and format code blocks first (to protect them from tag regex)
    code_blocks = []
    def save_code_block(match):
        code_content = match.group(2)
        idx = len(code_blocks)
        code_blocks.append(code_content)
        return f"__CODE_BLOCK_PLACEHOLDER_{idx}__"

    body = re.sub(r'```([a-zA-Z0-9_-]*)\n([\s\S]*?)```', save_code_block, body)

    # 3. Extract and format Markdown Tables
    table_blocks = []
    def parse_table_match(match):
        table_text = match.group(0).strip()
        lines = [line.strip() for line in table_text.split('\n') if line.strip()]
        if len(lines) < 2:
            return table_text

        header_line = lines[0]
        # skip separator line lines[1]
        data_lines = lines[2:]

        headers = [c.strip() for c in header_line.strip('|').split('|')]
        
        # Build styled table HTML
        th_html = "".join([
            f'<th style="background-color: #f8fafc; color: #1e293b; font-weight: 700; border: 1px solid #cbd5e1; padding: 10px 12px; text-align: center; font-size: 13.5px; font-family: {FONT_STACK};">{render_inlines(h)}</th>'
            for h in headers
        ])

        rows_html = []
        for dl in data_lines:
            cells = [c.strip() for c in dl.strip('|').split('|')]
            # pad or truncate
            while len(cells) < len(headers):
                cells.append("")
            td_html = "".join([
                f'<td style="border: 1px solid #cbd5e1; padding: 9px 12px; font-size: 13.5px; color: #334155; line-height: 1.55; font-family: {FONT_STACK};">{render_inlines(c)}</td>'
                for c in cells[:len(headers)]
            ])
            rows_html.append(f'<tr>{td_html}</tr>')

        table_rendered = (
            f'<div style="margin: 20px 0; overflow-x: auto;">'
            f'<table style="width: 100%; border-collapse: collapse; border: 1px solid #cbd5e1; table-layout: fixed; font-family: {FONT_STACK};">'
            f'<thead><tr>{th_html}</tr></thead>'
            f'<tbody>{"".join(rows_html)}</tbody>'
            f'</table>'
            f'</div>'
        )

        idx = len(table_blocks)
        table_blocks.append(table_rendered)
        return f"\n\n__TABLE_BLOCK_PLACEHOLDER_{idx}__\n\n"

    # Regex to match markdown table: lines beginning and ending with |
    table_regex = re.compile(r'(\|[^\n]+\|\n\|[\s:-|-]+\|\n(?:\|[^\n]+\|\n?)+)')
    body = table_regex.sub(parse_table_match, body)

    # Normalize headings and lists so they are never accidentally merged with lists/paragraphs
    # 1) Ensure headings have blank lines after them
    body = re.sub(r'^(#{1,4}\s+[^\n]+)\n(?!\n)', r'\1\n\n', body, flags=re.MULTILINE)
    # 2) Ensure list starting after a normal text line is separated (without splitting consecutive list items)
    body = re.sub(r'^(?![ \t]*[-*•\d#>])([^\n]+)\n([ \t]*(?:[-*•]|\d+\.))', r'\1\n\n\2', body, flags=re.MULTILINE)

    # 4. Split into block elements by blank lines
    raw_blocks = re.split(r'(\n[ \t]*\n+)',body)
    html_blocks = []
    layout_paragraphs=[]
    seen_blog_urls = set()
    blog_card_count = 0

    for blk in raw_blocks:
        b = blk.strip()
        if not b:
            extra=min(84,max(0,blk.count('\n')-2)*28)
            if extra:
                html_blocks.append(f'<div class="naver-spacer" style="height: {extra}px; clear: both;"></div>')
            continue

        # Restore Code Block
        code_match = re.match(r'^__CODE_BLOCK_PLACEHOLDER_(\d+)__$', b)
        if code_match:
            code_idx = int(code_match.group(1))
            code_content = code_blocks[code_idx]
            escaped_code = html.escape(code_content)
            html_blocks.append(
                f'<div style="background-color: #0f172a; color: #f8fafc; padding: 14px 16px; border-radius: 6px; font-family: Consolas, \'Courier New\', monospace; font-size: 12.5px; line-height: 1.55; margin: 18px 0; overflow-x: auto; white-space: pre; border: 1px solid #334155;">{escaped_code}</div>'
            )
            continue

        # Restore Table Block
        tbl_match = re.match(r'^__TABLE_BLOCK_PLACEHOLDER_(\d+)__$', b)
        if tbl_match:
            tbl_idx = int(tbl_match.group(1))
            html_blocks.append(table_blocks[tbl_idx])
            continue

        # Restore Asset Block
        asset_match = re.match(r'^__ASSET_BLOCK_PLACEHOLDER_(\d+)__$', b)
        if asset_match:
            asset_idx = int(asset_match.group(1))
            html_blocks.append(asset_blocks[asset_idx])
            continue

        # Official Device Blog Link Card with Link Button (RULE-OCEANTECH-BRAND-LINKS)
        blog_link_match = (
            re.match(r'^(?:👉\s*)?\[(?:오우션 공식 블로그|관련 제품 소개)[^\]]*\(([^)]+)\)\]\((https?://blog\.naver\.com/[^)]+)\)$', b) or
            re.match(r'^(?:👉\s*)?\[(?:오우션 공식 블로그|관련 제품 소개)[:\s]+([^\]]+)\]\((https?://blog\.naver\.com/[^)]+)\)$', b)
        )
        if blog_link_match:
            dev_label = blog_link_match.group(1).strip()
            blog_url = blog_link_match.group(2).strip()

            # 중복 URL 노출 차단 (동일 제품 링크는 첫 등장 시 1회만 노출)
            if blog_url in seen_blog_urls:
                continue
            seen_blog_urls.add(blog_url)
            blog_card_count += 1

            # Rendering must never select an unreviewed image implicitly.
            hero_img = None
            if hero_img:
                hero_img = format_cdn_url(hero_img)
                escaped_label = html.escape(dev_label, quote=True)
                html_blocks.append(
                    f'<div style="margin: 24px auto 30px auto; text-align: center; max-width: 520px;">'
                    f'<a href="{blog_url}" target="_blank" rel="noreferrer" style="display: block; text-decoration: none; margin-bottom: 12px;">'
                    f'<img src="{hero_img}" alt="{escaped_label} 제품 사진" style="max-width: 100%; width: 440px; height: auto; border-radius: 8px; display: block; margin: 0 auto; box-shadow: 0 3px 12px rgba(0,0,0,0.07); border: 1px solid #e2e8f0;">'
                    f'</a>'
                    f'<a href="{blog_url}" target="_blank" rel="noreferrer" style="display: inline-block; padding: 9px 24px; background-color: #f0f7fc; color: #0078cb; text-decoration: none; border-radius: 24px; font-size: 14px; font-weight: 700; border: 1.5px solid #bae0fd; font-family: {FONT_STACK}; box-shadow: 0 2px 5px rgba(0,120,203,0.08);">'
                    f'👉 오우션 공식 블로그 ({dev_label})'
                    f'</a>'
                    f'</div>'
                )
            else:
                html_blocks.append(
                    f'<div style="margin: 18px auto 24px auto; text-align: center;">'
                    f'<a href="{blog_url}" target="_blank" rel="noreferrer" style="display: inline-block; padding: 9px 24px; background-color: #f0f7fc; color: #0078cb; text-decoration: none; border-radius: 24px; font-size: 14px; font-weight: 700; border: 1.5px solid #bae0fd; font-family: {FONT_STACK}; box-shadow: 0 2px 5px rgba(0,120,203,0.08);">'
                    f'👉 오우션 공식 블로그 ({dev_label})'
                    f'</a>'
                    f'</div>'
                )
            continue

        # Raw HTML Block (pass through without wrapping in <p> or inline mangling)
        if b.startswith(("<div", "<table", "<p", "<style", "<section")):
            html_blocks.append(b)
            continue

        # Divider / HR (Whitespace Spacer according to master_design_guide.md Section 10)
        # Prevents infinite horizontal divider bug in SmartEditor ONE clipboard paste
        if re.match(r'^(\-{3,}|\*{3,}|_{3,})$', b):
            html_blocks.append(
                '<div style="height: 44px; width: 100%; clear: both; display: block;" class="naver-spacer"></div>'
            )
            continue

        # Headings
        if b.startswith("# "):
            h_text = b[2:].strip()
            if not title:
                title = h_text
            html_blocks.append(
                f'<div style="margin: 28px 0 20px 0; text-align: center;">'
                f'<span style="display: inline-block; padding: 3px 10px; background-color: #0078cb; color: #ffffff; font-size: 12px; font-weight: bold; border-radius: 4px; font-family: {FONT_STACK}; margin-bottom: 12px;">LOGITECH VC TECH BRIEF</span>'
                f'<h1 class="fs28" style="font-family: {FONT_STACK}; font-size: 28px; font-weight: 800; color: #111827; line-height: 1.4; margin: 0; word-break: keep-all; letter-spacing: -0.4px; text-align: center;">{render_inlines(h_text)}</h1>'
                f'</div>'
            )
            continue

        if b.startswith("## "):
            h_text = b[3:].strip()
            html_blocks.append(
                f'<div style="margin: 36px 0 16px 0; text-align: center;">'
                f'<h2 class="fs24" style="font-family: {FONT_STACK}; font-size: 24px; font-weight: 700; color: #111827; margin: 0; line-height: 1.4; word-break: keep-all; letter-spacing: -0.3px; text-align: center; display: inline-block; padding: 0 10px 6px 10px;">{render_inlines(h_text)}</h2>'
                f'</div>'
            )
            continue

        if b.startswith("### "):
            h_text = b[4:].strip()
            html_blocks.append(
                f'<div style="margin: 22px 0 10px 0; text-align: center;">'
                f'<h3 class="fs19" style="font-family: {FONT_STACK}; font-size: 19px; font-weight: 700; color: #1e293b; margin: 0; line-height: 1.4; letter-spacing: -0.2px; text-align: center;">{render_inlines(h_text)}</h3>'
                f'</div>'
            )
            continue

        # Blockquote (4 Styles from master_design_guide.md Section 8)
        # 1) quotation_quote: 따옴표 인용구
        # 2) quotation_postit: 포스트잇 / 요약 박스
        # 3) quotation_talk: 말풍선
        # 4) quotation_line: 상하/중앙 강조 라인
        if b.startswith(">"):
            quote_lines = [re.sub(r'^>\s?', '', l) for l in b.split('\n')]
            quote_content = "\n".join(quote_lines).strip()

            # Check explicit tags: [quote], [postit], [talk], [line]
            is_quote_explicit = bool(re.search(r'^\[(?:quote|따옴표)\]', quote_content, re.IGNORECASE))
            is_postit_explicit = bool(re.search(r'^\[(?:postit|포스트잇)\]', quote_content, re.IGNORECASE))
            is_talk_explicit = bool(re.search(r'^\[(?:talk|말풍선)\]', quote_content, re.IGNORECASE))

            clean_content = re.sub(r'^\[(?:quote|따옴표|postit|포스트잇|talk|말풍선|line)\]\s*', '', quote_content, flags=re.IGNORECASE).strip()

            # Auto-detect 따옴표 스타일: begins and ends with quotation mark or explicit [quote]
            if is_quote_explicit or (clean_content.startswith(('*\"', '\"', '“')) and clean_content.endswith(('\"*', '\"', '”'))):
                q_text = clean_content.strip('*\"“ ”')
                html_blocks.append(
                    f'<div style="text-align: center; margin: 26px auto; padding: 20px 24px; max-width: 92%; font-family: {FONT_STACK}; background-color: #fafbfc; border-radius: 8px;">'
                    f'<div style="font-size: 28px; line-height: 1; color: #0078cb; font-family: Georgia, serif; font-weight: bold; margin-bottom: 8px;">“</div>'
                    f'<div style="font-size: 15px; line-height: 1.7; color: #334155; font-style: italic; word-break: keep-all; padding: 0 10px; text-align: center;">{render_inlines(q_text)}</div>'
                    f'<div style="font-size: 28px; line-height: 1; color: #0078cb; font-family: Georgia, serif; font-weight: bold; margin-top: 8px;">”</div>'
                    f'</div>'
                )
                continue

            # Auto-detect 말풍선 스타일
            if is_talk_explicit:
                html_blocks.append(
                    f'<div style="background-color: #f1f5f9; border-radius: 12px; padding: 14px 20px; margin: 18px auto; font-family: {FONT_STACK}; font-size: 14.5px; line-height: 1.68; color: #1e293b; max-width: 90%; border: 1px solid #e2e8f0; text-align: center;">'
                    f'{render_inlines(clean_content)}'
                    f'</div>'
                )
                continue

            # Auto-detect 포스트잇 / 요약 박스 스타일
            if is_postit_explicit or "빠른 요약" in clean_content or "Quick Answer" in clean_content or "핵심 요약" in clean_content:
                title_match = re.match(r'^\*\*(.*?)\*\*\s*(.*)$', clean_content, re.DOTALL)
                if title_match:
                    box_title = title_match.group(1).strip()
                    box_body = title_match.group(2).strip()
                else:
                    box_title = "📌 3줄 핵심 요약 (Quick Answer)"
                    box_body = clean_content

                html_blocks.append(
                    f'<div style="background-color: #f8fafc; border: 1px solid #cbd5e1; border-top: 3px solid #0078cb; border-radius: 8px; padding: 18px 22px; margin: 22px auto; max-width: 90%; font-family: {FONT_STACK}; box-shadow: 0 1px 3px rgba(0,0,0,0.04); text-align: center;">'
                    f'<div style="font-weight: 700; font-size: 15px; color: #0078cb; margin-bottom: 8px; text-align: center;">'
                    f'{render_inlines(box_title)}'
                    f'</div>'
                    f'<div style="font-size: 14.5px; line-height: 1.68; color: #334155; text-align: center;">{render_inlines(box_body)}</div>'
                    f'</div>'
                )
                continue

            # Default: 라인 스타일 (상하 포인트 보더 & 중앙 정렬)
            lines = clean_content.split('\n')
            first_line = lines[0].strip()
            if first_line.startswith('**') and first_line.endswith('**') and len(lines) > 1:
                line_title = first_line.strip('*')
                line_body = '\n'.join(lines[1:]).strip()
                html_blocks.append(
                    f'<div style="border-top: 2px solid #0078cb; border-bottom: 2px solid #0078cb; padding: 14px 20px; margin: 22px auto; max-width: 90%; font-family: {FONT_STACK}; background-color: #f8fafc; border-radius: 4px; text-align: center;">'
                    f'<div style="font-weight: 700; font-size: 14.5px; color: #0078cb; margin-bottom: 6px; text-align: center;">{render_inlines(line_title)}</div>'
                    f'<div style="font-size: 14px; line-height: 1.68; color: #334155; text-align: center;">{render_inlines(line_body)}</div>'
                    f'</div>'
                )
            else:
                html_blocks.append(
                    f'<div style="border-top: 2px solid #0078cb; border-bottom: 2px solid #0078cb; padding: 12px 18px; margin: 20px auto; max-width: 90%; font-family: {FONT_STACK}; font-size: 14.5px; color: #334155; background-color: #f8fafc; line-height: 1.68; border-radius: 4px; text-align: center;">'
                    f'{render_inlines(clean_content)}'
                    f'</div>'
                )
            continue

        # Image Alone
        img_match = re.match(r'^!\[([^\]]*)\]\((https?://[^)]+|\/api\/[^)]+)\)$', b)
        if img_match:
            cap = img_match.group(1)
            u = img_match.group(2)
            u = format_cdn_url(u)
            clean_cap = html.escape(re.sub(r'<[^>]+>', '', cap), quote=True)
            html_blocks.append(
                f'<div style="text-align: center; margin: 24px 0;">'
                f'<img src="{u}" alt="{clean_cap}" style="max-width: 100%; height: auto; border-radius: 6px; display: inline-block; box-shadow: 0 2px 5px rgba(0,0,0,0.06);">'
                f'<div class="fs13" style="font-size: 13px; color: #64748b; margin-top: 6px; font-family: {FONT_STACK}; text-align: center;">{render_inlines(cap)}</div>'
                f'</div>'
            )
            continue

        # Lists (Ordered or Unordered)
        lines = b.split('\n')
        is_ul = all(l.strip().startswith(('-', '*', '•')) or not l.strip() for l in lines)
        is_ol = all(re.match(r'^\d+\.', l.strip()) or not l.strip() for l in lines)

        if is_ul and len(lines) > 0:
            li_items = []
            is_checklist = any(re.match(r'^[-*•]\s*\[[\sXx]?\]', l.strip()) for l in lines)
            for l in lines:
                l_s = l.strip()
                if not l_s:
                    continue
                item_text = re.sub(r'^[-*•]\s*', '', l_s)
                li_items.append(
                    f'<li style="margin-bottom: 6px; line-height: 1.68; font-family: {FONT_STACK}; font-size: 15px; color: #334155; text-align: center; list-style-position: inside;">{render_inlines(item_text)}</li>'
                )
            list_style = "list-style-type: none; padding: 0;" if is_checklist else "list-style-position: inside; padding: 0;"
            html_blocks.append(
                f'<ul style="font-family: {FONT_STACK}; font-size: 15px; color: #334155; margin: 14px auto 20px auto; text-align: center; {list_style}">'
                f'{"".join(li_items)}'
                f'</ul>'
            )
            continue

        if is_ol and len(lines) > 0:
            li_items = []
            for l in lines:
                l_s = l.strip()
                if not l_s:
                    continue
                item_text = re.sub(r'^\d+\.\s*', '', l_s)
                li_items.append(
                    f'<li style="margin-bottom: 6px; line-height: 1.68; font-family: {FONT_STACK}; font-size: 15px; color: #334155; text-align: center; list-style-position: inside;">{render_inlines(item_text)}</li>'
                )
            html_blocks.append(
                f'<ol style="font-family: {FONT_STACK}; font-size: 15px; color: #334155; margin: 14px auto 20px auto; padding: 0; list-style-position: inside; text-align: center;">'
                f'{"".join(li_items)}'
                f'</ol>'
            )
            continue

        # Normal Paragraph
        wrapped=mobile_lines(b)
        layout_paragraphs.append(paragraph_layout(b,wrapped,len(layout_paragraphs)+1))
        html_blocks.append(
            f'<p class="fs16" data-layout-paragraph="{len(layout_paragraphs)}" style="font-family: {FONT_STACK}; font-size: 16px; line-height: 1.8; color: #222222; margin: 0 auto 32px auto; max-width: 400px; word-break: keep-all; letter-spacing: -0.2px; text-align: center;">'
            f'{render_inlines(wrapped)}'
            f'</p>'
        )

    # Wrap in root container with standard SmartEditor content width (around 700px~720px max)
    full_html = (
        f'<div id="naver-smart-editor-content" style="max-width: 720px; margin: 0 auto; font-family: {FONT_STACK}; color: #222222; background-color: #ffffff; padding: 20px 24px; box-sizing: border-box; text-align: center;">\n'
        + "\n".join(html_blocks)
        + "\n</div>"
    )

    # Fallback cleanup: If any table placeholder was embedded inside a <p>, unwrap it and replace
    for idx, tbl_html in enumerate(table_blocks):
        full_html = re.sub(rf'<p[^>]*>\s*__TABLE_BLOCK_PLACEHOLDER_{idx}__\s*<\/p>', tbl_html, full_html)
        full_html = full_html.replace(f"__TABLE_BLOCK_PLACEHOLDER_{idx}__", tbl_html)

    for idx, code_content in enumerate(code_blocks):
        escaped_code = html.escape(code_content)
        code_box = f'<div style="background-color: #0f172a; color: #f8fafc; padding: 18px 20px; border-radius: 8px; font-family: Consolas, \'Courier New\', monospace; font-size: 13px; line-height: 1.6; margin: 22px 0; overflow-x: auto; white-space: pre; border: 1px solid #334155;">{escaped_code}</div>'
        full_html = re.sub(rf'<p[^>]*>\s*__CODE_BLOCK_PLACEHOLDER_{idx}__\s*<\/p>', code_box, full_html)
        full_html = full_html.replace(f"__CODE_BLOCK_PLACEHOLDER_{idx}__", code_box)

    for idx, asset_html in enumerate(asset_blocks):
        full_html = re.sub(rf'<p[^>]*>\s*__ASSET_BLOCK_PLACEHOLDER_{idx}__\s*<\/p>', asset_html, full_html)
        full_html = full_html.replace(f"__ASSET_BLOCK_PLACEHOLDER_{idx}__", asset_html)

    # Enrich Business Inquiry footer with inline styles for Naver SmartEditor ONE (while preserving classes)
    if 'Business Inquiry' in full_html:
        full_html = re.sub(
            r'<div class="mb-8 pl-5 border-l-4 border-logi-blue bg-white rounded-r-2xl py-4 pr-6 shadow-sm" style="([^"]*?);?"',
            r'<div class="mb-8 pl-5 border-l-4 border-logi-blue bg-white rounded-r-2xl py-4 pr-6 shadow-sm" style="\1; border-top: 2px solid #0078cb; border-bottom: 2px solid #0078cb; border-left: none; padding: 16px 20px; background-color: #ffffff; border-radius: 8px; margin: 0 auto 24px auto; max-width: 90%; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,0.06);"',
            full_html
        )
        full_html = re.sub(
            r'<div class="text-\[10px\] font-black text-logi-blue uppercase tracking-widest mb-2" style="([^"]*?);?"',
            r'<div class="text-[10px] font-black text-logi-blue uppercase tracking-widest mb-2" style="\1; color: #0078cb; font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 6px; text-align: center;"',
            full_html
        )
        full_html = re.sub(
            r'<p class="fs16 text-zinc-600 italic leading-\[1\.9\]" style="([^"]*?);?"',
            r'<p class="fs16 text-zinc-600 italic leading-[1.9]" style="\1; font-size: 15px; color: #52525b; font-style: italic; line-height: 1.8; margin: 0; text-align: center;"',
            full_html
        )

    # v5.2: paragraph/section separation uses whitespace; retain table cell borders.
    full_html=re.sub(r'style="([^"]*)"',lambda m:'style="'+re.sub(r'border-(?:top|bottom):[^;]+;?', '',m.group(1))+'"',full_html)
    return {
        "title": title,
        "content_id": content_id or frontmatter.get("content_id", ""),
        "html": full_html,
        "target_keyword": target_kw
        ,"layout_report":{'version':3,'algorithm':'ai_authored_breaks_only',
            'scope':'강제 줄바꿈 기록. 화면 폭에 따른 브라우저 자동 줄바꿈은 미리보기에서 확인.',
            'paragraphs':layout_paragraphs}
    }

def format_cdn_url(url):
    """Ensure Google Drive thumbnail parameter is high-res (w1000)"""
    if "drive.google.com/thumbnail" in url:
        if "sz=" not in url:
            url += "&sz=w1000"
        else:
            url = re.sub(r'sz=[a-zA-Z0-9]+', 'sz=w1000', url)
    return url

def render_inlines(text):
    """Renders inline markdown tags (bold, italic, badges, images, hardware links)"""
    # Replace inline images
    def replace_inline_img(m):
        raw_cap = m.group(1)
        clean_cap = html.escape(re.sub(r'<[^>]+>', '', raw_cap), quote=True)
        img_url = format_cdn_url(m.group(2))
        return (
            f'<div style="text-align: center; margin: 24px 0;">'
            f'<img src="{img_url}" alt="{clean_cap}" style="max-width: 100%; height: auto; border-radius: 8px;">'
            f'<div style="font-size: 13px; color: #64748b; margin-top: 6px;">{clean_cap}</div>'
            f'</div>'
        )
    text = re.sub(r'!\[([^\]]*)\]\((https?://[^)]+|\/api\/[^)]+)\)', replace_inline_img, text)

    # Markdown Links [text](url)
    def replace_md_link(m):
        link_text = m.group(1)
        link_url = m.group(2)
        return f'<a href="{link_url}" target="_blank" rel="noreferrer" style="color: #0078cb; text-decoration: underline; font-weight: 700; font-family: {FONT_STACK};">{link_text}</a>'
    text = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)', replace_md_link, text)

    # 3-Tier Badges (support both **[TAG]** and [TAG])
    text = re.sub(
        r'(\*\*)?\[FACT\](\*\*)?',
        f'<span style="display: inline-block; background-color: #e0f2fe; color: #0284c7; padding: 2px 7px; border-radius: 4px; font-weight: bold; font-size: 12px; margin-right: 6px; font-family: {FONT_STACK};">[FACT]</span>',
        text
    )
    text = re.sub(
        r'(\*\*)?\[LIMITATION\](\*\*)?',
        f'<span style="display: inline-block; background-color: #fee2e2; color: #dc2626; padding: 2px 7px; border-radius: 4px; font-weight: bold; font-size: 12px; margin-right: 6px; font-family: {FONT_STACK};">[LIMITATION]</span>',
        text
    )
    text = re.sub(
        r'(\*\*)?\[INTERPRETATION\](\*\*)?',
        f'<span style="display: inline-block; background-color: #fef3c7; color: #d97706; padding: 2px 7px; border-radius: 4px; font-weight: bold; font-size: 12px; margin-right: 6px; font-family: {FONT_STACK};">[INTERPRETATION]</span>',
        text
    )

    # Strong Bold
    text = re.sub(
        r'\*\*(.*?)\*\*',
        r'<strong style="color: #0f172a; font-weight: 700;">\1</strong>',
        text
    )

    # Code inlines
    text = re.sub(
        r'`([^`]+)`',
        f'<code style="background-color: #f1f5f9; color: #0f172a; padding: 2px 6px; border-radius: 4px; font-size: 13px; font-family: Consolas, monospace; border: 1px solid #e2e8f0;">\\1</code>',
        text
    )

    # Auto Highlight Core Hardware (Strictly outside existing HTML tags!)
    hardware_patterns = [
        (r'\b(Logitech Rally Bar|로지텍 랠리바|Rally Bar)\b', r'<strong style="color: #0078cb; font-weight: 700;">\1</strong>'),
        (r'\b(RightSight 2|RightSight2)\b', r'<strong style="color: #0078cb; font-weight: 700;">\1</strong>'),
        (r'\b(Rally Mic Pod|랠리 마이크 팟)\b', r'<strong style="color: #0078cb; font-weight: 700;">\1</strong>'),
        (r'\b(Logitech Tap|로지텍 탭)\b', r'<strong style="color: #0078cb; font-weight: 700;">\1</strong>'),
        (r'\b(Logitech MeetUp 2|MeetUp 2|밋업 2)\b', r'<strong style="color: #0078cb; font-weight: 700;">\1</strong>'),
    ]
    parts = re.split(r'(<[^>]+>)', text)
    for i in range(0, len(parts), 2):
        for pattern, repl in hardware_patterns:
            parts[i] = re.sub(pattern, repl, parts[i])
    text = "".join(parts)

    # Clean up redundant nested strong tags
    text = re.sub(r'<strong[^>]*>\s*<strong style="([^"]+)">([^<]+)</strong>\s*</strong>', r'<strong style="\1">\2</strong>', text)

    # Linebreaks inside paragraphs
    text = text.replace("\n", "<br>")

    return text
