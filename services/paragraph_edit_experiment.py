"""Isolated paragraph editing experiment. Never writes production draft or approval."""
from collections import Counter
from datetime import datetime,timezone
import hashlib
import html
import json
from pathlib import Path
import re
import uuid

from services.content_pipeline import atomic
from services.pipeline_provider import ModelProvider,parse_object
from services.policy_call_audit import prepare_call,verify_receipt
from services.naver_editor import RESPONSE_SCHEMA
from services.naver_blog_compiler import compile_markdown_to_naver_html

ROOT=Path(__file__).resolve().parents[1]
GUIDE=ROOT/'experiments/naver-paragraph/GUIDE.md'
ISSUE_SCHEMA={'type':'OBJECT','required':['before','after','detail','requested_change'],'properties':{k:{'type':'STRING'} for k in ['before','after','detail','requested_change']}}
REVIEW_BLOCK={'type':'OBJECT','required':['id','passed','reason','issues'],'properties':{'id':{'type':'STRING'},'passed':{'type':'BOOLEAN'},'reason':{'type':'STRING'},'issues':{'type':'ARRAY','items':ISSUE_SCHEMA}}}
REVIEW_SCHEMA={'type':'OBJECT','required':['receipt','result'],'properties':{'receipt':RESPONSE_SCHEMA['properties']['receipt'],'result':{'type':'OBJECT','required':['blocks'],'properties':{'blocks':{'type':'ARRAY','items':REVIEW_BLOCK}}}}}


class TestProvider(ModelProvider):
    def generation_config(self,stage,model):
        return {'responseMimeType':'application/json','maxOutputTokens':8192,
                'responseSchema':REVIEW_SCHEMA if stage=='paragraph_test_review' else RESPONSE_SCHEMA}


def extract(markdown):
    paragraphs=re.split(r'\n\s*\n',markdown)
    fov=next(p for p in paragraphs if p.startswith('로지텍 MeetUp 2는 카메라 사양 기준으로'))
    start=markdown.index('둘째, MeetUp 2는')
    cable=markdown[start:markdown.index('\n## ',start)].strip()
    checklist=next(p for p in paragraphs if p.startswith('1. **카메라와 착석자 거리 확인**'))
    return [{'id':'TEST-FOV','label':'화각 사양 문단','markdown':fov,'claim_ids':[]},
            {'id':'TEST-CABLE','label':'운영 방식·기본 구성·별매 케이블 문단','markdown':cable,'claim_ids':[]},
            {'id':'TEST-CHECKLIST','label':'도입 점검 체크리스트','markdown':checklist,'claim_ids':[]}]


def inventory(text,pattern):
    return Counter(re.findall(pattern,text))


def validate(original,edited,claims):
    errors=[];blocks=edited.get('blocks') or []
    if [b['id'] for b in original]!=[b.get('id') for b in blocks]:return ['블록 ID/순서 변경']
    for a,b in zip(original,blocks):
        if not isinstance(b.get('markdown'),str) or not b['markdown'].strip():errors.append(a['id']+': 빈 출력');continue
        if a['claim_ids']!=b.get('claim_ids'):errors.append(a['id']+': Claim 배정 변경')
        # Presentation list numbers are not product values. Order may change within one block.
        def prose(s):
            s=re.sub(r'^\s*\d+[.)]\s*','',s,flags=re.M)
            return re.sub(r'(?i)MeetUp\s*2','MeetUp',s)
        for name,pattern in [('수치',r'\d+(?:\.\d+)?'),('URL',r'https?://[^\s)<>]+'),('이미지',r'\{\{asset:[^}]+\}\}')]:
            before=inventory(prose(a['markdown']),pattern);after=inventory(prose(b['markdown']),pattern)
            # Repeated descriptions may merge. Semantic quantities/conditions are checked by review AI.
            if (set(before)!=set(after) if name=='수치' else before!=after):errors.append(a['id']+': '+name+' 변경')
    new=edited.get('claims') or []
    if {c['id']:c['fact_ids'] for c in claims}!={c.get('id'):c.get('fact_ids') for c in new}:errors.append('Claim/Fact 연결 변경')
    for b in blocks:
        for cid in b.get('claim_ids',[]):
            claim=next((c for c in new if c.get('id')==cid),None)
            if not claim or not claim.get('text') or claim['text'] not in b['markdown']:errors.append(b['id']+': Claim 인용 불일치 '+cid)
    return errors


def run(cid,provider=None,block_ids=None,full_article=False):
    from services.content_pipeline import ContentPipeline
    pipeline=ContentPipeline(ROOT);source=pipeline.draft_path(cid)
    raw=source.read_bytes();markdown=source.read_text(encoding='utf-8')
    sha=hashlib.sha256(raw).hexdigest();latest=pipeline.latest(cid)
    claimfile=Path(latest['run_directory'])/'revisions'/('r'+str(latest['draft_revision'])+'.claim-map.json')
    allclaims=json.loads(claimfile.read_text(encoding='utf-8'))['claims']
    if full_article:
        meta=json.loads(claimfile.with_name(claimfile.name.replace('.claim-map.json','.writer-metadata.json')).read_text(encoding='utf-8'))
        blocks=[{'id':b['id'],'label':b['id'],'markdown':b['markdown'],'claim_ids':b.get('claim_ids',[])} for b in meta['blocks']]
        if '\n\n'.join(b['markdown'] for b in blocks)!=markdown:raise ValueError('Current article/block snapshot mismatch')
    else:blocks=extract(markdown)
    if block_ids:
        if not set(block_ids)<={b['id'] for b in blocks}:raise ValueError('Unknown test block')
        blocks=[b for b in blocks if b['id'] in block_ids]
    claims=[]
    if full_article:
        assigned={cid for b in blocks for cid in b['claim_ids']}
        claims=[c for c in allclaims if c['id'] in assigned]
    else:
        for c in allclaims:
            for b in blocks:
                if c['text'] in b['markdown']:
                    b['claim_ids'].append(c['id'])
                    if c['id'] not in {x['id'] for x in claims}:claims.append(c)
    protected=[b['id'] for b in blocks if b['markdown'].startswith('# ') or re.fullmatch(r'\{\{asset:[^}]+\}\}',b['markdown']) or ('https://' in b['markdown'] and '\n' not in b['markdown'])]
    runid=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]
    directory=ROOT/'static/experiments/naver-paragraph'/runid
    atomic(directory/'source.md',markdown)
    guide=GUIDE.read_text(encoding='utf-8');model=provider or TestProvider(ROOT)
    calls=[]
    def call(stage,instruction,payload,label=None):
        label=label or stage
        instruction,payload,ledger=prepare_call(stage,instruction,{**payload,'rules':[{'id':'RULE-NAVER-PARAGRAPH-TEST-001','body':guide}]},
            runid+'-'+label,'paragraph-experiment-v1',str(GUIDE.relative_to(ROOT)),hashlib.sha256(guide.encode()).hexdigest())
        atomic(directory/(label+'.prompt.json'),{'instruction':instruction,'context':payload})
        try:
            count=model.count_tokens(stage,instruction,payload)
            if count>50000:raise ValueError('Test input token budget exceeded')
            raw_response=model.complete(stage,instruction,payload)
            atomic(directory/(label+'.response.json'),{'raw':raw_response})
            parsed=parse_object(raw_response);ledger.update(verify_receipt(parsed,ledger))
            if ledger['receipt_status']!='verified':raise ValueError('Test rule receipt mismatch')
            return parsed['result']
        finally:
            atomic(directory/(label+'.audit.json'),ledger)
            calls.append({'stage':stage,'label':label,'input_tokens':locals().get('count'),'metadata':model.last_metadata})
            atomic(directory/'calls.json',calls)
    atomic(directory/'input.json',{'content_id':cid,'source_sha256':sha,'full_article':full_article,'blocks':blocks,'claims':claims,'protected_block_ids':protected})
    instruction='한국어 네이버 블로그 문단 구성 편집 테스트다. 제공 가이드를 적용해 입력 블록 내부의 문단 분리·통합·순서 조정·나열/목록화를 수행한다. 단순 줄바꿈 추가로 끝내지 않는다. 원문 조건과 사실은 보존한다. 결과는 blocks(id,markdown,claim_ids), claims(id,text,fact_ids), changes(변경 이유 배열) JSON이다. 전체 markdown은 중복 반환하지 않는다.'
    try:
        instruction+=' protected_block_ids는 제목·이미지·제품 링크 블록이며 markdown을 그대로 반환한다. 그 외 블록 내부만 편집한다.'
        if full_article:
            edited={'blocks':[],'claims':[],'changes':[]}
            batches=[blocks[i:i+5] for i in range(0,len(blocks),5)]
            for n,batch in enumerate(batches,1):
                ids={b['id'] for b in batch}; assigned={cid for b in batch for cid in b['claim_ids']}
                partial=call('paragraph_test_edit',instruction,{'blocks':batch,'claims':[c for c in claims if c['id'] in assigned],
                    'protected_block_ids':[bid for bid in protected if bid in ids],
                    'article_outline':[{'id':b['id'],'first_line':b['markdown'].split('\n')[0][:120]} for b in blocks]},label='paragraph_test_edit-'+str(n))
                for key in edited:edited[key].extend(partial.get(key) or [])
                atomic(directory/'edited.partial.json',edited)
        else:
            edited=call('paragraph_test_edit',instruction,{'blocks':blocks,'claims':claims,'protected_block_ids':protected})
        errors=validate(blocks,edited,claims)
        for a,b in zip(blocks,edited.get('blocks') or []):
            if a['id'] in protected and a['markdown']!=b.get('markdown'):errors.append(a['id']+': 보호 블록 변경')
        atomic(directory/'edited.json',edited)
        review=None
        if not errors:
            review_instruction='원문과 편집본을 가이드에 따라 독립 리뷰한다. 조건/대상 귀속·예외·내용 누락과 중복·문단 역할/순서·줄바꿈 문맥을 의미로 대조한다. 단어 존재만으로 통과하지 않는다. blocks별 id,passed,reason,issues(before,after,detail,requested_change)를 JSON으로 반환한다.'
            if full_article:
                review={'blocks':[]}
                for n,batch in enumerate(batches,1):
                    ids={b['id'] for b in batch}
                    partial=call('paragraph_test_review',review_instruction,{'original':batch,'edited':{
                        'blocks':[b for b in edited['blocks'] if b['id'] in ids]},
                        'article_outline':[{'id':b['id'],'first_line':b['markdown'].split('\n')[0][:120]} for b in blocks]},label='paragraph_test_review-'+str(n))
                    review['blocks'].extend(partial.get('blocks') or [])
                    atomic(directory/'review.partial.json',review)
            else:review=call('paragraph_test_review',review_instruction,{'original':blocks,'edited':edited})
            atomic(directory/'review.json',review)
        reviewed=(review or {}).get('blocks',[])
        review_valid=[b.get('id') for b in reviewed]==[b['id'] for b in blocks] and all(isinstance(b.get('passed'),bool) and isinstance(b.get('issues'),list) for b in reviewed)
        passed=not errors and review_valid and all(b['passed'] and not b['issues'] for b in reviewed)
        report={'test_only':True,'content_id':cid,'run_id':runid,'full_article':full_article,'passed':passed,'mechanical_errors':errors,
                'source_unchanged':source.read_bytes()==raw,'calls':calls,'preview_url':'http://127.0.0.1:5014/experiments/naver-paragraph/'+runid+'/index.html'}
        if not report['source_unchanged']:raise ValueError('Production source changed concurrently; test result is stale')
        atomic(directory/'result.json',report)
        panels=[]
        for a,b in zip(blocks,edited.get('blocks') or []):
            before=compile_markdown_to_naver_html(a['markdown'],content_id=cid)['html'];after=compile_markdown_to_naver_html(b['markdown'],content_id=cid)['html']
            row=next((r for r in reviewed if r.get('id')==a['id']),{})
            panels.append('<section><h2>'+html.escape(a['label'])+'</h2><div class="compare"><div><h3>원문</h3>'+before+'</div><div><h3>AI 편집</h3>'+after+'</div></div><details><summary>리뷰·수정 이유</summary><pre>'+html.escape(json.dumps(row,ensure_ascii=False,indent=2))+'</pre></details></section>')
        page='<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>문단 구성 편집 테스트</title><style>body{font:15px/1.7 system-ui;background:#f3f6f5;margin:24px}section{background:white;padding:20px;margin:20px 0}.compare{display:grid;grid-template-columns:1fr 1fr;gap:20px}pre{white-space:pre-wrap}@media(max-width:800px){.compare{grid-template-columns:1fr}}</style><h1>문단 구성 편집 · 테스트 전용</h1><p>실제 원고·승인·본 파이프라인은 변경하지 않았습니다. 테스트 리뷰: '+('통과' if passed else '보완 필요')+'</p><pre>'+html.escape(json.dumps({'errors':errors,'changes':edited.get('changes')},ensure_ascii=False,indent=2))+'</pre>'+''.join(panels)
        atomic(directory/'index.html',page)
        if full_article and edited.get('blocks'):
            article='\n\n'.join(b['markdown'] for b in edited['blocks'])
            atomic(directory/'full-article.md',article)
            atomic(directory/'full-article.html','<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><p>전문 편집 테스트 — 운영 원고가 아닙니다. <a href="index.html">비교·리뷰 보기</a></p>'+compile_markdown_to_naver_html(article,content_id=cid)['html'])
        return report
    except Exception as e:
        atomic(directory/'failure.json',{'type':type(e).__name__,'source_unchanged':source.read_bytes()==raw})
        raise
