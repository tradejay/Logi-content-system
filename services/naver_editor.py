"""Bounded prose editing before QA; presentation is rendered separately."""
from copy import deepcopy
import re

RULE_ID='RULE-NAVER-EDITORIAL-V1'
RESPONSE_SCHEMA={'type':'OBJECT','required':['receipt','result'],'properties':{
    'receipt':{'type':'OBJECT','required':['bundle','ids'],'properties':{
        'bundle':{'type':'STRING'},'ids':{'type':'ARRAY','items':{'type':'STRING'}}}},
    'result':{'type':'OBJECT','required':['claims','changes'],'properties':{
        'markdown':{'type':'STRING'},'changes':{'type':'ARRAY','items':{'type':'STRING'}},
        'blocks':{'type':'ARRAY','items':{'type':'OBJECT','required':['id','markdown','claim_ids'],'properties':{
            'id':{'type':'STRING'},'markdown':{'type':'STRING'},'claim_ids':{'type':'ARRAY','items':{'type':'STRING'}}}}},
        'claims':{'type':'ARRAY','items':{'type':'OBJECT','required':['id','text','fact_ids'],'properties':{
            'id':{'type':'STRING'},'text':{'type':'STRING'},'fact_ids':{'type':'ARRAY','items':{'type':'STRING'}}}}}
    }}}}
INSTRUCTION='''네이버 블로그 편집자다. 이번 작업은 새 집필이 아니라 기존 원고의 어투·문단·줄바꿈 다듬기다.
친절한 경어체를 유지하고 이미 설명한 대상의 긴 재지칭·불필요한 수식어를 줄인다. 기술 조건과 예외는 삭제하지 않는다.
긴 한 문단을 의미에 따라 2~3문장의 짧은 문단으로 나누고, 문단 안에서도 절·문장 경계에 실제 줄바꿈을 넣는다.
글자 수를 맞추기 위한 줄바꿈은 하지 않는다. 문장 끝 또는 독립된 의미 단위에서만 끊고, 관형어·수식어와 대상은 붙인다.
예: '별매 옵션인 5.0m 로지텍 액티브 케이블'은 한 덩어리로 유지한다. '별매 옵션인' 뒤에서 줄을 끊지 않는다.
제품명·숫자/단위·링크·강조 구문 중간을 자르지 않는다. 화면 폭에 따른 자연 줄바꿈은 렌더러에 맡긴다.
문단 사이는 빈 줄 1개, 소제목/이미지 전후는 빈 줄 2개를 사용할 수 있다. 중요 결론은 짧은 강조 문단으로 만든다.
디자인 v5.2의 나눔고딕, 본문 fs16, 소제목 fs19/fs24, 제목 fs28, 캡션 fs13, 줄간격 1.8은 HTML 변환기가 적용한다.
HTML/CSS/임의 이미지 URL을 원고에 넣지 않는다. 과장·새 사실·새 추천·새 사례를 만들지 않는다.
제목과 블록 순서, 숫자, URL, 이미지 자리의 ID/순서, Claim ID와 fact_ids는 보존한다. Claim 표현을 바꾸면 claims.text를 새 본문의 정확한 인용으로 갱신한다.
JSON result: blocks(입력에 있으면 같은 id·claim_ids 순서와 편집된 markdown), claims, changes(편집 내역).
blocks가 있으면 전체 markdown은 출력하지 않는다. 시스템이 blocks.markdown을 조립한다. blocks가 없는 입력에서만 markdown을 출력한다.
editable_block_ids가 있으면 해당 블록만 편집하고 다른 블록의 markdown과 관련 Claim text를 그대로 보존한다.
markdown은 blocks.markdown을 빈 줄로 조립한 값이어야 한다. 기존 메타데이터와 미해결 항목은 시스템이 보존한다.'''


def apply_edit(original, edited, editable_block_ids=None):
    if not edited.get('markdown') and isinstance(edited.get('blocks'),list):
        edited={**edited,'markdown':'\n\n'.join(b['markdown'] for b in edited['blocks'])}
    if not isinstance(edited.get('markdown'),str) or not edited['markdown'].strip():
        raise ValueError('네이버 편집 원고 누락')
    before=original['markdown'];after=edited['markdown']
    if re.findall(r'^#\s+.+$',before,re.M)!=re.findall(r'^#\s+.+$',after,re.M):
        raise ValueError('네이버 편집 제목 변경')
    for name,pattern in [('이미지',r'\{\{asset:[^}]+\}\}'),('링크',r'https?://[^\s)<>]+'),
                         ('숫자',r'\d+(?:\.\d+)?')]:
        if re.findall(pattern,before)!=re.findall(pattern,after):
            raise ValueError('네이버 편집에서 '+name+' 정보가 변경됐습니다.')
    old=original.get('claims',[]);new=edited.get('claims')
    if not isinstance(new,list) or [(c['id'],c['fact_ids']) for c in old]!=[(c.get('id'),c.get('fact_ids')) for c in new]:
        raise ValueError('네이버 편집에서 Claim·Fact 연결 변경')
    if any(not isinstance(c.get('text'),str) or not c['text'] or c['text'] not in after for c in new):
        raise ValueError('네이버 편집 Claim 인용과 본문 불일치')
    blocks=original.get('blocks')
    if blocks:
        changed=edited.get('blocks') or []
        if [(b['id'],b.get('claim_ids',[])) for b in blocks]!=[(b.get('id'),b.get('claim_ids',[])) for b in changed]:
            raise ValueError('네이버 편집 블록 구성 변경')
        if after!='\n\n'.join(b['markdown'] for b in changed):
            raise ValueError('네이버 편집 블록 조립 불일치')
        if editable_block_ids:
            for a,b in zip(blocks,changed):
                if a['id'] not in editable_block_ids and a['markdown']!=b['markdown']:
                    raise ValueError('네이버 편집에서 수정 대상 외 블록 변경')
    result=deepcopy(original)
    result.update(markdown=after,claims=new,changes=list(original.get('changes') or [])+list(edited.get('changes') or []))
    if blocks:result['blocks']=[{**a,'markdown':b['markdown']} for a,b in zip(blocks,edited['blocks'])]
    return result
