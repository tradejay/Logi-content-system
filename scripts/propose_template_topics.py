"""Run Keyword AI for template-design candidates; never enqueue drafts."""
import csv
import json
from pathlib import Path
import sqlite3
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from services.pipeline_provider import ModelProvider, parse_object

OUT=ROOT/'audit/2026-10-06-template-topic-candidates'
OUT.mkdir(parents=True,exist_ok=True)

def save(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

conn=sqlite3.connect('file:'+str(ROOT/'data/keyword_graph.db')+'?mode=ro',uri=True)
conn.row_factory=sqlite3.Row
observations=[dict(r) for r in conn.execute('SELECT query,monthly_total,intent,target_products,product_affinity,explored_at,updated_at FROM query_nodes ORDER BY product_affinity DESC,monthly_total DESC LIMIT 180')]
conn.close()
catalog=json.loads((ROOT/'data/product_taxonomy.json').read_text(encoding='utf-8-sig'))
products=[{'id':k,'name':v.get('name_ko',k),'synonyms':v.get('synonyms',[])} for k,v in catalog.get('products',{}).items()]
existing=[]
for filename in ('CONTENT_REGISTRY.csv','KEYWORD_REGISTRY.csv'):
    with (ROOT/'content-system/registry'/filename).open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
        existing.append({'registry':filename,'rows':[{k:v for k,v in row.items() if any(t in k.lower() for t in ('title','keyword','topic','intent','purpose','content_id','status'))} for row in rows]})
instruction='''당신은 화상회의 장비 네이버 블로그의 Keyword AI다. 본문은 쓰지 않는다.
목적은 글 템플릿을 설계할 수 있도록 서로 다른 독자 질문·키워드·글 주제를 20개(부족하면 10~19개) 제안하는 것이다.
제품 소개, 제품 비교, 회의실 구성, 기능 설명, 문제 해결 5가지 템플릿의 다양성을 확보한다.
제공된 제품 ID만 사용한다. 제품별 지원·성능·호환성은 명칭이나 분류 데이터로 확정하지 않는다.
일상적인 독자 표현을 대표 키워드와 연결한다. 기존 글/키워드와 중복 위험을 대조하며 기존 주제면 보완 또는 비교 목적을 제안한다.
검색 관측은 저장된 자료다. 없는 검색량, 최신 검색 순위, 수요를 만들지 않는다. 관측 키워드가 아니면 AI 제안이라고 구분한다.
현재 v3 가이드가 과거 Keyword 가이드보다 우선한다. 고정 구성 비율, 정보 70%, 고정 질문 개수, 실증 강제를 적용하지 않는다.
각 글은 중심 결정 하나를 돕는다. 단순 표현만 바꾼 중복 주제를 20개로 부풀리지 않는다.
JSON 객체만 반환: candidates(array).
각 항목 필드: id, primary_keyword, supporting_keywords(array), layman_terms(array), topic, reader_question, template_type(제품 소개/제품 비교/회의실 구성/기능 설명/문제 해결), product_ids(array), canonical_topic, intent, central_decision, existing_content_ids(array), duplicate_assessment, evidence_needed(array), suggested_visuals(array).
suggested_visuals는 확보 확인이 아니라 필요한 자료 유형 제안이다. evidence_needed는 제품 주장을 확정하기 전에 필요한 공식 자료를 기록한다.'''
guide=(ROOT/'content-system/02_writer_ai/authoring/01-topic-and-keywords.md').read_text(encoding='utf-8-sig')
context={'task':'template_design_topic_proposals','maximum':20,'keyword_observations':observations,'product_names_only':products,'existing_registries':existing,'current_v3_keyword_guide':guide}
(OUT/'instruction.md').write_text(instruction,encoding='utf-8')
save('input.json',context)
if '--prepare-only' in sys.argv:
    print(json.dumps({'observations':len(observations),'products':len(products),'existing_rows':sum(len(r['rows']) for r in existing),'input':str(OUT/'input.json')},ensure_ascii=True))
    sys.exit(0)
provider=ModelProvider(ROOT)
try:
    raw=provider.complete('keyword-topic-proposals',instruction,context)
    (OUT/'model-response.txt').write_text(raw,encoding='utf-8')
    data=parse_object(raw)
    items=data.get('candidates')
    if not isinstance(items,list) or not 10<=len(items)<=20: raise ValueError('AI candidate count must be 10–20')
    ids=set(); keywords=set(); known={p['id'] for p in products}; observed={r['query']:r for r in observations}
    required={'id','primary_keyword','supporting_keywords','layman_terms','topic','reader_question','template_type','product_ids','canonical_topic','intent','central_decision','existing_content_ids','duplicate_assessment','evidence_needed','suggested_visuals'}
    for item in items:
        if not isinstance(item,dict) or required-set(item): raise ValueError('AI candidate missing fields')
        if item['id'] in ids or item['primary_keyword'].replace(' ','') in keywords: raise ValueError('AI duplicate candidate')
        if not isinstance(item['product_ids'],list) or set(item['product_ids'])-known: raise ValueError('Unknown product ID')
        ids.add(item['id']);keywords.add(item['primary_keyword'].replace(' ',''))
        observation=observed.get(item['primary_keyword'])
        item['keyword_origin']='stored_observation' if observation else 'ai_proposed'
        item['observation']=observation
    data.update(created_at=datetime.now(timezone.utc).isoformat(),status='PROPOSALS_FOR_TEMPLATE_DESIGN',model=provider.last_metadata,observation_scope='stored top 180 rows; no live Naver collection')
    save('candidates.json',data)
    lines=['# 템플릿 설계용 키워드·글 주제 후보','', '실제 Keyword AI 호출 결과. 저장된 관측 기반이며 신규 실시간 검색 수집은 수행하지 않았다. 제품 사실·검색 수요 확정 및 발행 승인이 아니다.','', '| 번호 | 키워드 | 글 주제 | 템플릿 유형 | 키워드 출처 |','|---|---|---|---|---|']
    for i,item in enumerate(items,1):
        vals=[str(i),item['primary_keyword'],item['topic'],item['template_type'], '저장 관측' if item['observation'] else 'AI 제안']
        lines.append('| '+' | '.join(v.replace('|','/').replace('\n',' ') for v in vals)+' |')
    (OUT/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'count':len(items),'report':str(OUT/'report.md'),'model':provider.last_metadata.get('model_version')},ensure_ascii=True))
except Exception as error:
    # Transport errors deliberately omit credential-bearing HTTP response bodies.
    save('failure.json',{'type':type(error).__name__,'message':str(error) if not isinstance(error, OSError) else 'Network or filesystem access failed'})
    print('Keyword AI failed: '+type(error).__name__)
    sys.exit(1)
