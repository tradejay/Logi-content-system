#!/usr/bin/env python3
"""
extract_claims.py (v1.1.2 Comprehensive Claim Extractor)
Draft 마크다운 파일의 본문, 마크다운 표(Table), 캡션(Caption), 콜아웃(Callout),
이미지 Alt 텍스트, FAQ 등 모든 콘텐츠 영역에서 기술적 사실 주장(Claim) 및 수치 단위를 자동 추출합니다.
"""

import os
import sys
import re
import yaml
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFTS_DIR = os.path.join(BASE_DIR, "02_writer_ai", "drafts")

# Number and unit patterns
# %, 초, ms, m, mm, cm, 명, 배, GHz, Mbps, °, W, V, A, dB, kg 등
# Korean particle compatibility: (?![a-zA-Z0-9]) instead of \b to match 4.5m까지, 70mm로, 130° 등
NUMERICAL_PATTERN = re.compile(
    r'\b\d+(?:\.\d+)?\s*(?:%|퍼센트|초|ms|mm|cm|m|명|배|GHz|MHz|Mbps|Kbps|°|도|W|와트|V|볼트|A|암페어|dB|kg|g|픽셀|fps)(?![a-zA-Z0-9])',
    re.IGNORECASE
)

# Technical assertion keywords
TECHNICAL_ASSERTION_KEYWORDS = [
    "지원", "미지원", "탑재", "제공", "설정", "호환", "최대", "최소", "권장", "반경", "거리", "센서", "알고리즘", "인터페이스", "단자", "포트"
]

def extract_claims_from_text(text):
    claims = []
    lines = text.split("\n")
    
    current_section = "INTRO"
    claim_counter = 1

    in_code_block = False
    in_frontmatter = False

    for line_idx, line in enumerate(lines, 1):
        stripped = line.strip()

        # Handle frontmatter
        if line_idx == 1 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue

        # Handle code blocks
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        # Track section headers
        if stripped.startswith("#"):
            current_section = stripped.lstrip("#").strip()
            continue

        # Skip only internal missing evidence warnings
        if stripped.startswith("> [!WARNING]") and "MISSING_EVIDENCE" in stripped:
            continue

        # Extract Image Alt text: ![Alt Text](url)
        img_matches = re.findall(r'!\[(.*?)\]\(.*?\)', stripped)
        for alt_text in img_matches:
            alt_clean = alt_text.strip()
            if alt_clean and len(alt_clean) >= 5:
                num_matches = NUMERICAL_PATTERN.findall(alt_clean)
                is_num = len(num_matches) > 0
                is_tech = any(kw in alt_clean for kw in TECHNICAL_ASSERTION_KEYWORDS)
                if is_num or is_tech:
                    claims.append({
                        "claim_id": f"CLM-{claim_counter:03d}",
                        "line_number": line_idx,
                        "section": current_section,
                        "origin": "IMAGE_ALT",
                        "text": alt_clean,
                        "type": "NUMERICAL" if is_num else "TECHNICAL_FACT",
                        "extracted_units": num_matches,
                        "status": "UNVERIFIED"
                    })
                    claim_counter += 1

        # Strip blockquote markers but KEEP the content (for Captions & Callouts)
        clean_line = re.sub(r'^>\s*', '', stripped)

        # Handle Table Rows (| Col1 | Col2 | Col3 |)
        if clean_line.startswith("|") and clean_line.endswith("|"):
            # Skip separator line (| :--- | :--- |)
            if re.match(r'^\|[\s\-:]+\|$', clean_line):
                continue
            cells = [c.strip() for c in clean_line.split("|")[1:-1]]
            for cell in cells:
                if len(cell) >= 3:
                    num_matches = NUMERICAL_PATTERN.findall(cell)
                    is_num = len(num_matches) > 0
                    is_tech = any(kw in cell for kw in TECHNICAL_ASSERTION_KEYWORDS)
                    if is_num or (is_tech and len(cell) >= 8):
                        claims.append({
                            "claim_id": f"CLM-{claim_counter:03d}",
                            "line_number": line_idx,
                            "section": current_section,
                            "origin": "TABLE_CELL",
                            "text": cell,
                            "type": "NUMERICAL" if is_num else "TECHNICAL_FACT",
                            "extracted_units": num_matches,
                            "status": "UNVERIFIED"
                        })
                        claim_counter += 1
            continue

        # Skip raw HTML footer/banner markup
        if clean_line.startswith("<") or "<div" in clean_line or "<table" in clean_line:
            continue

        # Clean markdown formatting for sentence extraction
        clean_text = re.sub(r'[*_`]', '', clean_line)

        # Split sentences roughly by period or bullet points
        sentences = re.split(r'(?<=[.?!])\s+|(?<=\n)\s*-\s*', clean_text)
        for sent in sentences:
            sent_clean = sent.strip()
            if not sent_clean or len(sent_clean) < 8:
                continue

            num_matches = NUMERICAL_PATTERN.findall(sent_clean)
            is_num_claim = len(num_matches) > 0
            is_tech_claim = any(kw in sent_clean for kw in TECHNICAL_ASSERTION_KEYWORDS)

            if is_num_claim or (is_tech_claim and len(sent_clean) > 12):
                origin = "CALLOUT" if stripped.startswith(">") else "BODY_TEXT"
                claims.append({
                    "claim_id": f"CLM-{claim_counter:03d}",
                    "line_number": line_idx,
                    "section": current_section,
                    "origin": origin,
                    "text": sent_clean,
                    "type": "NUMERICAL" if is_num_claim else "TECHNICAL_FACT",
                    "extracted_units": num_matches,
                    "status": "UNVERIFIED"
                })
                claim_counter += 1

    return claims

def extract_claims_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    return extract_claims_from_text(content)

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Extract technical and numerical claims from draft")
    parser.add_argument("target", help="Content ID (e.g. CNT-2026W39-001) or markdown filepath")
    parser.add_argument("--out", help="Optional output yaml filepath")
    args = parser.parse_args()

    target_path = args.target
    if not os.path.exists(target_path):
        target_path = os.path.join(DRAFTS_DIR, f"{args.target}.draft.md")

    if not os.path.exists(target_path):
        print(f"[ERROR] Target file not found: {target_path}", file=sys.stderr)
        sys.exit(1)

    claims = extract_claims_file(target_path)
    print(f"=== Extracted {len(claims)} Claims from {os.path.basename(target_path)} ===")
    num_count = sum(1 for c in claims if c['type'] == 'NUMERICAL')
    tech_count = len(claims) - num_count
    origins = {}
    for c in claims:
        orig = c.get("origin", "BODY_TEXT")
        origins[orig] = origins.get(orig, 0) + 1

    print(f"  - Numerical Claims: {num_count}")
    print(f"  - Technical Assertions: {tech_count}")
    print(f"  - Origins Breakdown: {origins}\n")

    for c in claims[:10]:
        print(f"[{c['claim_id']}] ({c.get('origin')} | Line {c['line_number']} | {c['type']}) {c['text']}")

    if len(claims) > 10:
        print(f"  ... and {len(claims) - 10} more claims.")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            yaml.dump({"claims": claims}, f, allow_unicode=True, sort_keys=False)
        print(f"\n[SAVED] Claims saved to {args.out}")
