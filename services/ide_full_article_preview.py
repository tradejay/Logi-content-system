"""Validate and display isolated whole-article worker output; never apply it."""
from collections import Counter
import html
import re
from .ide_worker_bridge import ROOT, load, save, local


def publish(worker_folder, task_id, state, root=ROOT, force=False):
    if state.get('status')!='collected' or state.get('result_status')!='completed':return None
    worker=root/'worker-workspaces'/worker_folder
    task=load(worker/'inbox'/task_id/'task.json')
    if not task.get('test_only') or task.get('scope')!='full_article' or task.get('stage')!='naver_edit':return None
    source=worker/'inbox'/task_id
    output=worker/'work'/task_id/'naver_edit'
    original=load(source/'original-blocks.json')['blocks']
    edited=load(output/'edited-blocks.json')['blocks']
    markdown=(output/'edited.md').read_text(encoding='utf-8')
    errors=[]
    if [b['id'] for b in original]!=[b['id'] for b in edited]:errors.append('Block IDs or order changed')
    if '\n\n'.join(b['markdown'].strip() for b in edited).strip()!=markdown.strip():errors.append('Markdown and blocks differ')
    for a,b in zip(original,edited):
        if a.get('claim_ids',[])!=b.get('claim_ids',[]):errors.append('Claim assignments changed: '+a['id'])
        for pattern in [r'\d+(?:\.\d+)?(?:m|V|°|mm|cm|倍|배|개|인)',r'\{\{asset:[^}]+\}\}',r'https?://[^\s)]+']:
            if Counter(re.findall(pattern,a['markdown']))!=Counter(re.findall(pattern,b['markdown'])):
                errors.append('Protected values changed: '+a['id'])
    before=load(source/'original-claims.json')['claims'];after=load(output/'claim-map.json')['claims']
    if {c['id']:c.get('fact_ids',[]) for c in before}!={c['id']:c.get('fact_ids',[]) for c in after}:errors.append('Claim/Fact links changed')
    block_by_claim={cid:b['markdown'] for b in edited for cid in b.get('claim_ids',[])}
    for claim in after:
        if not claim.get('text') or claim['text'] not in block_by_claim.get(claim['id'],''):errors.append('Claim quote is not in assigned block: '+claim['id'])
    if '\\n' in markdown or re.search(r'(?:^|\s)/n(?:\s|$)',markdown):errors.append('Literal newline marker in output')
    target=root/'static/experiments/naver-ide-full'/task_id;target.mkdir(parents=True,exist_ok=True)
    if (target/'index.html').exists() and not force:return f'/experiments/naver-ide-full/{task_id}/index.html'
    save(target/'validation.json',{'test_only':True,'passed':not errors,'errors':errors,'blocks':len(edited),'claims':len(after)})
    from .naver_blog_compiler import compile_markdown_to_naver_html
    left_result=compile_markdown_to_naver_html((source/'original.md').read_text(encoding='utf-8'),content_id=task['content_id'])
    right_result=compile_markdown_to_naver_html(markdown,content_id=task['content_id'])
    left=left_result['html']
    right=right_result['html']
    save(target/'layout.json',{'original':left_result['layout_report'],'edited':right_result['layout_report']})
    page=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>블로그 전문 편집 테스트</title><style>body{{font-family:system-ui;background:#f2f5f8;margin:0;padding:24px}}header{{max-width:1100px;margin:0 auto 20px}}.columns{{display:grid;grid-template-columns:1fr 1fr;gap:24px;max-width:1100px;margin:auto}}section{{background:white;padding:28px;border-radius:12px}}@media(max-width:850px){{.columns{{grid-template-columns:1fr}}}}</style><header><h1>블로그 전문 편집 테스트</h1><p>실제 원고·승인·본 파이프라인에 반영하지 않은 테스트 결과입니다.</p><p>{len(edited)}개 블록 · {len(after)}개 Claim · 기계 검증 {'통과' if not errors else '실패'} · 독립 리뷰는 별도 확인</p><p>{html.escape(task_id)}</p><a href="validation.json">기계 검증 상세</a></header><main class="columns"><section><h2>원문 전문</h2>{left}</section><section><h2>AI 편집 전문</h2>{right}</section></main></html>'''
    # Browser checks the small system-generated review result until it arrives.
    status_script='''<script>async function reviewStatus(){try{const r=await fetch('review.json',{cache:'no-store'});if(!r.ok)throw Error();const d=await r.json();document.getElementById('review-status').textContent=d.passed?'독립 리뷰 통과':'독립 리뷰 수정 필요 ('+d.issues.length+'건)';}catch(e){setTimeout(reviewStatus,5000);}}reviewStatus();</script>'''
    page=page.replace('독립 리뷰는 별도 확인','<span id="review-status">독립 리뷰 대기</span>').replace('</html>',status_script+'</html>')
    (target/'index.html').write_text(page,encoding='utf-8')
    (target/'edited.md').write_text(markdown,encoding='utf-8')
    return f'/experiments/naver-ide-full/{task_id}/index.html'
