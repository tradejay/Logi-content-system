import yaml, os, glob, re, json, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

brief_dir = Path('content-system/01_keyword_ai/briefs')
draft_dir = Path('content-system/02_writer_ai/drafts')

files = sorted(brief_dir.glob('CNT-*.brief.yaml'))

for bf in files:
    cid = bf.name.replace('.brief.yaml', '')
    if cid == 'CNT-2026W39-999': continue
    try:
        bdata = yaml.safe_load(bf.read_text(encoding='utf-8'))
    except Exception:
        bdata = {}
    
    # Keyword & product info
    search_info = bdata.get('search', {})
    kw = search_info.get('primary_keyword', '')
    supp_kw = ", ".join(search_info.get('supporting_keywords', [])[:3])
    
    ent = bdata.get('entities', {})
    prods = ent.get('products', [])
    if not prods:
        # scan in knowledge_packs
        kp = bdata.get('knowledge_packs', [])
        prods = [x.split(':')[-1] for x in kp if 'PROD' in x]
    prod_str = ", ".join(prods) if prods else "공통 / 다중 장비"

    df = draft_dir / f'{cid}.draft.md'
    draft_title = ''
    char_count = 0
    assets = []
    has_ocean = False
    
    if df.is_file():
        txt = df.read_text(encoding='utf-8')
        char_count = len(txt)
        assets = re.findall(r'\{\{asset:([^}]+)\}\}', txt)
        has_ocean = '오우션' in txt
        
        m_title = re.search(r'title:\s*"([^"]+)"', txt)
        if m_title:
            draft_title = m_title.group(1)
        else:
            m_h1 = re.search(r'^#\s*(.+)', txt, re.MULTILINE)
            if m_h1: draft_title = m_h1.group(1).strip()

    title = draft_title or bdata.get('topic', '')
    print(f"[{cid}]")
    print(f"  • 주제/제목: {title}")
    print(f"  • 타깃 검색어: {kw} (연관: {supp_kw})")
    print(f"  • 핵심 제품: {prod_str}")
    print(f"  • 작성 분량: 약 {char_count:,}자")
    print(f"  • 시각 자료: 총 {len(assets)}개 슬롯 바인딩")
    print(f"  • 오우션 브랜딩/문의 배너: {'적용 완료' if has_ocean else '미적용'}")
    print("-" * 60)
