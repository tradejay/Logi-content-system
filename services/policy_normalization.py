"""Lossless document decomposition with explicit, conservative scope classification."""
import re
from services.policy_manager import stamp

DOMAINS = {'OCEANTECH': 'brand', 'EVIDENCE': 'evidence', 'NUMERIC': 'evidence',
           'COMPONENT': 'evidence', 'PLATFORM': 'evidence', 'CONFIGURATION': 'evidence',
           'EXPERIENCE': 'business', 'ASSET': 'images', 'READER': 'editorial',
           '01-TOPIC': 'planning', '02-FACTS': 'evidence', '03-STRUCTURE': 'editorial',
           '04-IMAGES': 'images', '05-FEEDBACK': 'review', '06-COMPLETION': 'operations',
           '07-CONTRACTS': 'implementation', '08-RUNTIME': 'implementation'}

def pieces(body):
    """Keep whitespace, markdown tables and complete fenced blocks byte-for-byte."""
    fence = None
    for line in body.splitlines(keepends=True):
        mark = re.match(r'^\s*(`{3,}|~{3,})', line)
        if fence or mark:
            yield line, 'reference' if line.strip() else 'literal'
            if mark:
                if fence == mark[1][0]: fence = None
                elif fence is None: fence = mark[1][0]
            continue
        if not line.strip():
            yield line, 'literal'
        elif re.match(r'^\s*#', line):
            yield line, 'heading'
        elif re.match(r'^\s*(Version:|문서 버전:|추가일:|\||>)', line) or re.search(r'\*[^*]*예시[^*]*\*', line):
            yield line, 'reference'
        else:
            for part in re.split(r'(?<=다\.)(\s+)', line):
                if part:
                    yield part, 'literal' if not part.strip() else 'directive'

def classification(doc_id, section, text, inherited):
    domain = next((v for k, v in DOMAINS.items() if k in doc_id), 'content')
    level = 'L1' if 'CORE-' in doc_id else 'L2' if doc_id.startswith('RULE-') else 'L3'
    stages = list(inherited)
    if doc_id.startswith('PROMPT-'):
        stages = [doc_id.split('-')[1].lower()]
        domain = 'response-contract'
    elif domain == 'implementation':
        stages = []
    elif doc_id == 'GUIDE-05-FEEDBACK':
        stages = ['official'] if section == '로지텍 AI에 검토 요청' else ['feedback', 'official'] if section in (
            '틀린 내용 → 지식 업데이트 대기열', '판단 불가 → 관리자 검토 대기열', '재검토와 종료') else ['feedback']
    elif '독자 관점의 편집 검토' in section:
        stages = ['feedback']
    elif text.lstrip().startswith('검토 출력:') or section == '검토 체크':
        stages = ['feedback', 'official'] if domain != 'editorial' else ['feedback']
    elif domain == 'brand':
        stages = ['write', 'feedback']
        if '계획' in text or '작성 입력' in text: stages.insert(0, 'strategy')
    elif '기획 AI' in section or re.match(r'^\s*\d+\. 기획에서', text):
        stages = ['strategy']
    elif '집필' in section or '마감' in section or '초반' in section or '블로그 문체' in section:
        stages = [s for s in ['write', 'feedback'] if s in inherited]
    if not stages:
        kind = 'reference'
    elif re.search(r'않는다|말 것|금지|허용하지|안 된다|없이는', text):
        kind = 'prohibit'
    elif re.search(r'할 수 있다(?:\.|$)|가능하다(?:\.|$)|허용한다|생략 가능', text):
        kind = 'permit'
    elif re.search(r'권장|목표로|참고|예시|기본은', text):
        kind = 'recommend'
    else:
        kind = 'require'
    return domain, level, stages, kind

def normalize(manager, expected):
    manager.ensure()
    with manager.lock():
        state = manager.load()
        manager.check_revision(state, expected)
        if state.get('normalization_version') == 2:
            return state
        before = manager.assemble(state)
        originals = {a['id']: a for a in state['atoms']}
        new_atoms = []
        for doc_id, doc in state['documents'].items():
            # Reuse every current slot, including user edits. Retire rather than delete old IDs.
            body = ''.join(slot.get('literal', '') if 'literal' in slot else
                           (originals[slot['policy_id']]['text'] if originals[slot['policy_id']]['enabled'] else '')
                           for slot in doc['slots'])
            inherited = next(a['stages'] for a in originals.values() if a['target'] == doc_id)
            section, line, slots = '', 1, []
            for index, (part, role) in enumerate(pieces(body)):
                if role == 'literal':
                    slots.append({'literal': part})
                else:
                    if role == 'heading': section = part.strip().lstrip('#').strip()
                    domain, level, stages, kind = classification(doc_id, section, part, inherited)
                    is_reference = role != 'directive' or domain == 'implementation' or bool(re.search(
                        r'규칙이다\.$|기준이다\.$|^[\s\d.*-]*\*\*[^\n]+\*\*:\s*$|^\s*- (문의 페이지|배너 이미지|이미지 alt|문의 문구):|^\s*\d{4}-\d{2}-\d{2}', part.strip()))
                    pid = f'{doc_id}-V2N{index:04d}'
                    source_atom = next((a for a in originals.values() if a['target'] == doc_id
                                        and a['source'].get('line', 0) <= line
                                        and line <= a['source'].get('line', 0) + a['text'].count('\n')), None)
                    atom = dict(id=pid, revision=1, title=part.strip().splitlines()[0][:100], text=part,
                                domain=domain, level=level, kind='reference' if is_reference else kind,
                                stages=[] if is_reference else stages, tags=[], subject='', action='', object='',
                                evaluator='guidance', severity=source_atom['severity'] if source_atom else 'review',
                                enabled=True, review_note='',
                                target=doc_id, source={'path':doc['path'], 'line':line, 'sha256':doc['sha256']},
                                section=section, entry_type='source' if is_reference else 'policy',
                                granularity='sentence', classification_status='needs_semantic_review',
                                classification_basis='document/section scope; sentence wording',
                                updated_at=stamp())
                    atom['review_note'] = '제목·버전·코드와 지시를 분리하고 문맥·적용 단계를 정리함. 복합 지시와 의미 분류는 추가 검토 대상.'
                    if source_atom: atom['split_from'] = source_atom['id']
                    new_atoms.append(atom)
                    slots.append({'policy_id':pid})
                line += part.count('\n')
            doc['slots'] = slots
        for old in state['atoms']:
            if old['target'] != 'GENERATED':
                old.update(enabled=False, retired_by='normalization-v1')
        state['atoms'].extend(new_atoms)
        state['normalization_version'] = 2
        if manager.assemble(state) != before:
            raise ValueError('정책 분리 중 문서 본문이 변경되었습니다.')
        manager.commit(state, {'policy_id':'NORMALIZATION-V1', 'before':None,
                              'after':{'review_note':'무손실 문장 분리·출처 분리·단계 범위 검토'},
                              'new_ids':[a['id'] for a in new_atoms]})
    return state
