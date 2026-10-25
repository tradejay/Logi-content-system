"""User-selected authoritative sources; identity checked before automatic trust."""
from urllib.parse import urlparse, urljoin

POLICY_ID = 'SYS-WEB-SOURCE-TRUST-003'
DOMAINS = ('avixa.org', 'psni.org')
TRUST_INSTRUCTION = 'SYS-WEB-SOURCE-TRUST-003: 웹 근거는 avixa.org/psni.org 기관 자료만 사용한다. 실제 도메인이 확인된 기관 근거의 신뢰 점수는 1.0(100%)이며 수동 출처 승인 없이 채택한다. 제품별 공식 사양과 기관 권고의 적용 범위는 구분한다.'


def allowed_url(url):
    parsed = urlparse(url)
    host = (parsed.hostname or '').lower().rstrip('.')
    return parsed.scheme in ('https', 'http') and not parsed.username and not parsed.password and parsed.port in (None, 80, 443) and any(host == d or host.endswith('.' + d) for d in DOMAINS)


def original_url(url, session):
    # Resolve Google citation links, never follow a redirect to a third-party site.
    for _ in range(5):
        if allowed_url(url):
            return url
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname != 'vertexaisearch.cloud.google.com' or not parsed.path.startswith('/grounding-api-redirect/'):
            return None
        response = session.get(url, allow_redirects=False, timeout=15, stream=True)
        try:
            if response.status_code not in (301, 302, 303, 307, 308):
                return None
            url = urljoin(url, response.headers.get('Location', ''))
        finally:
            response.close()
    return None


def apply_policy(research, session):
    accepted, rejected, indices = [], [], {}
    for source in research.get('results', []):
        try:
            resolved = original_url(source['source_location'], session)
        except Exception:
            resolved = None
        if not resolved:
            rejected.append({'document_id': source['document_id'], 'reason': 'outside_allowlist_or_unresolved'})
            continue
        item = {**source, 'original_source_location': source['source_location'], 'source_location': resolved,
                'source_classification': 'institution', 'status': 'trusted', 'trust_score': 1.0,
                'trust_policy_id': POLICY_ID}
        accepted.append(item)
        for index in source.get('grounding_chunk_indices', []):
            indices[index] = item['document_id']
    segments, used = [], set()
    summary = research.get('raw_summary', research.get('summary', ''))
    for support in research.get('grounding_metadata', {}).get('groundingSupports', []):
        refs = support.get('groundingChunkIndices', [])
        segment = support.get('segment', {})
        text = segment.get('text')
        if not text:
            start, end = segment.get('startIndex', 0), segment.get('endIndex', 0)
            if type(start) is int and type(end) is int and 0 <= start < end <= len(summary):
                text = summary[start:end]
        if not refs or any(i not in indices for i in refs) or not isinstance(text, str) or not text.strip():
            continue
        signature = (text, tuple(refs))
        if signature in used:
            continue
        used.add(signature)
        segments.append({'text': text, 'source_ids': list(dict.fromkeys(indices[i] for i in refs))})
    return {**research, 'results': accepted, 'rejected_sources': rejected, 'raw_summary': summary,
            'summary': '\n'.join('[' + ','.join(s['source_ids']) + '] ' + s['text'] for s in segments),
            'trusted_segments': segments, 'source_policy': {'id': POLICY_ID, 'allowed_domains': list(DOMAINS), 'trust_score': 1.0},
            'status': 'trusted' if accepted and segments else 'ungrounded',
            'approved_for_writing': bool(accepted and segments)}
