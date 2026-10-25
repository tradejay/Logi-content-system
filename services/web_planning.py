"""Optional institutional article discovery before strategy; not product Fact approval."""
import hashlib
from services.web_source_policy import allowed_url, POLICY_ID, TRUST_INSTRUCTION

RULE_ID = 'SYS-WEB-PLANNING-004'
INSTRUCTION = """SYS-WEB-PLANNING-004: 기획 참고자료 선별 담당이다.
먼저 주제와 관련된 AVIXA/PSNI 글을 찾고, 관련 글이 있으면 related_articles로 문제 제기·전개·선택 기준·조건·한계·보완/대안을 정리한다.
관련 글이 없으면 fact_fallback으로 개별 사실·설계 원칙만 추린다. 둘 다 없으면 product_facts_only다.
sources의 제목/URL과 segments의 실제 제공 문장만 판단 근거로 쓴다. 원문 전문을 읽었다고 주장하거나 없는 내용을 보충하지 않는다.
유리/불리는 선별 기준이 아니다. 도입 판단에 중요한 불리한 조건이나 빠진 정보도 notes에 적고 확인되지 않은 보완/대안은 조사 과제로 구분한다.
제품 사양 승인·Fact ID 생성은 하지 않는다. 기관 근거의 신뢰성 재승인을 요구하지 않는다.
article_source_ids에는 선택한 points의 segment가 실제 인용하는 출처만 넣는다. 검색 목록에만 있는 글을 참고한 글로 추가하지 않는다.
출력 JSON: {mode: related_articles|fact_fallback|product_facts_only, reason: 문자열,
article_source_ids: [source_id], points: [{segment_id: 입력 ID, use: problem|flow|criteria|conditions|limitations|alternatives|principle, notes: 문자열}]}.
points는 최대 8개. 관련 글 모드는 article_source_ids가 필요하며 사실 대체 모드는 빈 배열이다. 자료 없음은 실패나 집필 중단 사유가 아니다."""
CONTEXT_INSTRUCTION = """SYS-WEB-PLANNING-004: planning_references는 기획 참고자료다. 관련 글의 문제·전개·선택 기준을 주제에 맞게 활용하고, fact_fallback은 개별 사실/설계 원칙만 활용한다.
모든 자료를 본문에 넣을 의무는 없다. 중요한 적용 조건·한계를 지우거나 근거 없는 대안으로 보충하지 않는다.
기관 설계 권고를 로지텍 제품 사양으로 바꾸지 않는다. 제품 사양·호환성은 전달된 제품 Fact와 제조사 검증으로 판단한다.
참고 내용의 source_ids/URL과 적용 조건을 유지하며, grounded_summary를 원문 직접 인용으로 표현하지 않는다."""


def planning_input(brief, research):
    sources = [{k: s.get(k, '') for k in ('document_id', 'title', 'source_location')}
               for s in research.get('results', [])
               if s.get('trust_policy_id') == POLICY_ID and allowed_url(s.get('source_location', ''))][:20]
    ids = {s['document_id'] for s in sources}
    segments = []
    for s in research.get('trusted_segments', []):
        refs = s.get('source_ids', [])
        if refs and set(refs) <= ids and s.get('text'):
            segments.append({'id': 'REF-' + hashlib.sha256((s['text'] + str(refs)).encode()).hexdigest()[:16],
                             'text': s['text'], 'source_ids': refs, 'quote_origin': 'grounded_summary'})
        if len(segments) >= 20:
            break
    return {'topic': brief.get('topic'), 'search': brief.get('search', {}),
            'sources': sources, 'segments': segments,
            'rules': [{'id': RULE_ID, 'body': INSTRUCTION}, {'id': POLICY_ID, 'body': TRUST_INSTRUCTION}]}


def product_only(reason):
    return {'mode': 'product_facts_only', 'reason': reason, 'article_source_ids': [],
            'points': [], 'sources': [], 'rule_id': RULE_ID}


def finalize(result, payload):
    mode = result.get('mode')
    if mode not in ('related_articles', 'fact_fallback', 'product_facts_only'):
        raise ValueError('Invalid planning discovery mode')
    refs = result.get('article_source_ids', [])
    points = result.get('points', [])
    sources = {s['document_id']: s for s in payload['sources']}
    segments = {s['id']: s for s in payload['segments']}
    if not isinstance(refs, list) or any(r not in sources for r in refs):
        raise ValueError('Unknown planning article source')
    if not isinstance(points, list) or len(points) > 8:
        raise ValueError('Invalid planning point list')
    if mode == 'related_articles' and not refs:
        raise ValueError('Related article mode requires article sources')
    if mode != 'related_articles' and refs:
        raise ValueError('Fallback cannot claim related articles')
    if mode == 'product_facts_only' and points:
        raise ValueError('No-reference mode cannot contain reference points')
    if mode != 'product_facts_only' and not points:
        raise ValueError('Reference mode requires supported points')
    normalized = []
    for p in points:
        if p.get('segment_id') not in segments or p.get('use') not in ('problem', 'flow', 'criteria', 'conditions', 'limitations', 'alternatives', 'principle') or not isinstance(p.get('notes'), str):
            raise ValueError('Unsupported planning point')
        segment = segments[p['segment_id']]
        normalized.append({**segment, 'use': p['use'], 'planning_notes': p['notes']})
    supported = {r for p in normalized for r in p['source_ids']}
    excluded = [r for r in refs if r not in supported]
    refs = [r for r in refs if r in supported]
    if mode == 'related_articles' and not refs:
        raise ValueError('Related articles require grounding support')
    used = set(refs) | supported
    return {'mode': mode, 'reason': str(result.get('reason', '')), 'article_source_ids': refs,
            'points': normalized, 'sources': [sources[r] for r in sources if r in used], 'rule_id': RULE_ID,
            'excluded_article_source_ids': excluded}
