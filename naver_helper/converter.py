import os
import re
import sys

# Styling Mappings
FONT_STACK = "'나눔고딕', NanumGothic, 'Apple SD Gothic Neo', sans-serif"

SIZE_MAP = {
    "fs11": "font-size: 11px;",
    "fs13": "font-size: 13px;",
    "fs15": "font-size: 15px;",
    "fs16": "font-size: 16px;",
    "fs19": "font-size: 19px; font-weight: bold;",
    "fs24": "font-size: 24px; font-weight: 800;",
    "fs28": "font-size: 28px; font-weight: 900;",
    "fs38": "font-size: 38px; font-weight: 900;",
    "fs48": "font-size: 48px; font-weight: 900;",
}

COLOR_MAP = {
    "text-logi-blue": "color: #0078cb;",
    "bg-table-header": "background-color: #e2e2e2;",
}

def inline_html_styles(html_content):
    # 1. Inject overall body/font styles
    # Match any elements with fsXX classes or text tags and inject font-family
    html_content = re.sub(
        r'(<p|<span|<div|<h1|<h2|<h3|<h4|<td|<th|<article)([^>]*?)class="([^"]*?)(fs\d+)([^"]*?)"',
        lambda m: f'{m.group(1)}{m.group(2)}class="{m.group(3)}{m.group(4)}{m.group(5)}" style="font-family: {FONT_STACK}; {SIZE_MAP.get(m.group(4), "")}"',
        html_content
    )

    # 2. Convert other typography tags (if style not already present)
    html_content = re.sub(
        r'(<p|<span|<div|<h1|<h2|<h3|<h4|<td|<th)([^>]*?)(?!style=)([^>]*?)>',
        lambda m: f'{m.group(1)}{m.group(2)} style="font-family: {FONT_STACK};" {m.group(3)}>' if 'style=' not in m.group(2) and 'style=' not in m.group(3) else m.group(0),
        html_content
    )

    # 3. Add explicit border and collapse to tables, td, th (Full Grid Table Rule)
    # Add border and border-collapse to tables
    html_content = re.sub(
        r'<table([^>]*?)style="([^"]*?)"',
        r'<table\1style="border-collapse: collapse; border: 1px solid #d4d4d8; \2"',
        html_content
    )
    # Add border directly to th and td elements
    html_content = re.sub(
        r'<td([^>]*?)style="([^"]*?)"',
        r'<td\1style="border: 1px solid #d4d4d8; \2"',
        html_content
    )
    html_content = re.sub(
        r'<th([^>]*?)style="([^"]*?)"',
        r'<th\1style="border: 1px solid #d4d4d8; \2"',
        html_content
    )
    
    # 4. Handle section dividers (replace line1, line2, line3 with spacing divs)
    # Replace line1 with a height-80px whitespace div
    html_content = re.sub(
        r'<div([^>]*?)class="line1([^"]*?)"([^>]*?)>.*?</div>',
        r'<div style="height: 80px; width: 100%; clear: both; display: block; margin: 0; padding: 0;"></div>',
        html_content
    )
    # Replace line2 with a height-64px whitespace div
    html_content = re.sub(
        r'<div([^>]*?)class="line2([^"]*?)"([^>]*?)>.*?</div>',
        r'<div style="height: 64px; width: 100%; clear: both; display: block; margin: 0; padding: 0;"></div>',
        html_content
    )
    
    # 5. Handle Quotation blocks
    # Line style quote
    html_content = re.sub(
        r'class="quotation_line" style="([^"]*?)"',
        r'style="border-left: 4px solid #0078cb; padding-left: 20px; margin: 25px 0; \1"',
        html_content
    )
    # Post-it style quote
    html_content = re.sub(
        r'class="quotation_postit" style="([^"]*?)"',
        r'style="background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 16px; padding: 24px; margin: 25px 0; \1"',
        html_content
    )

    # 6. Apply mapped colors and backgrounds
    for cls, inline_style in COLOR_MAP.items():
        html_content = html_content.replace(f'class="{cls}"', f'style="{inline_style}"')
        html_content = html_content.replace(f'class=\'{cls}\'', f'style="{inline_style}"')

    # Remove script tags that aren't useful in Naver Editor
    html_content = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', html_content)

    return html_content

def convert_file(input_path, output_path):
    if not os.path.exists(input_path):
        print(f"[Error] Input file not found: {input_path}")
        return False
    
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        inlined_content = inline_html_styles(content)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(inlined_content)
        
        print(f"[Success] Converted: {os.path.basename(input_path)} -> {os.path.basename(output_path)}")
        return True
    except Exception as e:
        print(f"[Error] Failed to convert file: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("[Usage] python converter.py <input_html_file> [output_html_file]")
        print("[Example] python converter.py ../blogs/wd-001.html converted_wd-001.html")
        return

    input_file = sys.argv[1]
    if len(sys.argv) >= 3:
        output_file = sys.argv[2]
    else:
        # Default output filename
        dir_name = os.path.dirname(input_file)
        base_name = os.path.basename(input_file)
        output_file = os.path.join(dir_name, "naver_inlined_" + base_name)

    convert_file(input_file, output_file)

if __name__ == "__main__":
    main()
