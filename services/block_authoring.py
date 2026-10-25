"""Explicit per-block writing contracts inside a single article call."""
import hashlib
import json
from pathlib import Path

BLOCK_INSTRUCTION = '''
[블록별 집필 계약]
block_plan의 순서와 ID에 맞게 blocks 배열을 반환한다. 각 항목은 id, markdown, claim_ids 배열이다.
각 블록의 목적·근거·가이드·rule_ids를 적용한다. 해당 블록 밖의 Fact를 근거로 쓰지 않는다.
guide_roles는 공통 block_guides의 역할별 가이드를 참조한다. 각 역할의 원문 가이드는 한 번만 전달된다.
전체 markdown은 blocks의 markdown을 순서대로 두 줄바꿈으로 합친 문자열과 정확히 같아야 한다.
기존 claims/changes/used_asset_need_ids/unresolved_items 출력 계약도 유지한다.
claim_ids는 해당 블록에 그대로 인용된 claims의 ID이며, 모든 Claim은 정확히 한 블록에 배정한다.
본문을 완성한 다음 claims.text를 해당 블록 markdown에서 문자 그대로 복사한다. 굵게 표시(**), 구두점, 띄어쓰기를 제거하거나 요약하지 않는다.
이미지 자리표시자만 있는 블록의 claim_ids는 빈 배열이다. 생성 예정 그림의 설명을 이미 본문에 있는 Claim으로 등록하지 않는다.
일반 개념 정의를 제품의 수치 Fact 하나로 입증하지 않는다. 제품 사양 Claim은 실제 제품 수치·조건이 적힌 본문 문장과 대응시킨다.
블록 ID·규칙 ID·검토 질문 같은 내부 메타데이터를 독자용 markdown에 출력하지 않는다.
블록별 검증이 실패한 경우에도 누락 블록을 임의로 생략하지 않는다.
'''.strip()


def planner_instruction(root):
    path = Path(root) / 'content-system/00_system/templates/articles/content-block-guides.json'
    catalog = json.loads(path.read_text(encoding='utf-8-sig'))
    roles = ', '.join(b['block_id'] for b in catalog['blocks'])
    return ('기존 전략 출력에 content_blocks 배열을 추가한다.' +
            '\n각 항목: id(이번 글의 고유 블록 ID), roles(역할 ID 배열), purpose, fact_ids(입력 근거 ID 배열). '
            '승인된 사용자 블록 계획이 있으면 그대로 보존한다. 모든 역할을 무조건 넣지 말고 주제에 맞는 역할과 순서를 선택한다. '
            '인사·기업 안내·본문·마감 등 필요한 구성의 누락을 검토한다. 역할 목록은 고정 배치 순서가 아니다. '
            '사용 가능한 역할: ' + roles)


def repair_targets(previous, feedback):
    """Localize only when every reported issue has an unambiguous block location."""
    blocks = previous.get('blocks', []) if isinstance(previous, dict) else []
    issues = feedback.get('issues', []) if isinstance(feedback, dict) else []
    if not blocks or not issues or feedback.get('contract_errors') or feedback.get('missing_claims'):
        return []
    valid = {b['id'] for b in blocks}
    claims = {cid: b['id'] for b in blocks for cid in b.get('claim_ids', [])}
    targets = set()
    for issue in issues:
        target = issue.get('block_id') or claims.get(issue.get('claim_id'))
        if target not in valid:
            return []
        targets.add(target)
    return [b['id'] for b in blocks if b['id'] in targets]


def validate_preserved_blocks(result, previous, targets):
    if not targets:
        return []
    old = {b['id']: b for b in previous.get('blocks', [])}
    new = {b['id']: b for b in result.get('blocks', [])}
    errors = ['Unrequested block changed: ' + bid for bid, block in old.items()
              if bid not in targets and new.get(bid) != block]
    old_claims = {c['id']: c for c in previous.get('claims', [])}
    new_claims = {c['id']: c for c in result.get('claims', [])}
    for bid, block in old.items():
        if bid not in targets:
            for cid in block.get('claim_ids', []):
                if old_claims.get(cid) != new_claims.get(cid):
                    errors.append('Unrequested claim changed: ' + cid)
    return errors


def build_block_plan(root, context):
    path = Path(root) / 'content-system/00_system/templates/articles/content-block-guides.json'
    if not path.exists():
        raise ValueError('Content block guide catalog missing')
    raw = path.read_text(encoding='utf-8-sig')
    catalog = json.loads(raw)
    guides = {b['block_id']: b for b in catalog['blocks']}
    strategy = context.get('strategy') or {}
    chosen = strategy.get('content_blocks') or (context.get('brief') or {}).get('content_blocks')
    if not chosen:
        # Preserve the strategy order; do not pretend to infer semantic roles from prose.
        body = strategy.get('body') or ['독자 질문 해결']
        if not isinstance(body, list):
            body = [body]
        chosen = [{'id': 'title', 'role': 'title'},
                  {'id': 'opening', 'roles': ['opening.greeting', 'opening.business_notice', 'opening.problem_topic'], 'purpose': strategy.get('opening', '')}]
        chosen += [{'id': f'body-{i:02d}', 'role': 'body.explanation', 'purpose': item,
                    'role_assignment': 'fallback_needs_review'} for i, item in enumerate(body, 1)]
        chosen += [{'id': 'closing', 'roles': ['closing.summary', 'closing.consultation', 'closing.greeting'], 'purpose': strategy.get('closing', '')}]
    rules = context.get('rules', [])
    fact_ids = [f['id'] for f in context.get('facts', [])]
    policy = context.get('fact_policy') or {}
    excluded = set(policy.get('excluded_fact_ids', []))
    overrides = policy.get('block_fact_ids', {})
    if set(overrides) - {item['id'] for item in chosen}:
        raise ValueError('Unknown block in Fact override')
    plan = []
    for item in chosen:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id']:
            raise ValueError('Invalid block plan entry')
        roles = item.get('roles') or [item.get('role')]
        if not roles or any(role not in guides for role in roles):
            raise ValueError('Unknown content block role')
        assigned_facts = overrides.get(item['id'], item.get('fact_ids', fact_ids))
        assigned_facts = [fid for fid in assigned_facts if fid not in excluded] if isinstance(assigned_facts, list) else assigned_facts
        if not isinstance(assigned_facts, list) or set(assigned_facts) - set(fact_ids):
            raise ValueError('Unknown block Fact IDs')
        hints = []
        parents = set()
        for role in roles:
            guide = guides[role]
            hints.append({'role': role, 'purpose': guide['purpose'], 'content_guide': guide['content_guide'],
                          'avoid': guide.get('avoid', []), 'review_questions': guide.get('review_questions', []),
                          'source_policy_refs': guide.get('existing_policy_ids', [])})
            parents.update(pid.split('-V2N')[0] for pid in guide.get('existing_policy_ids', []))
        assigned_rules = item.get('rule_ids')
        if assigned_rules is None:
            assigned_rules = [r['id'] for r in rules if r['id'] in parents]
        if not isinstance(assigned_rules, list) or set(assigned_rules) - {r['id'] for r in rules}:
            raise ValueError('Unknown block rule IDs')
        evidence_ids = [e['id'] for e in context.get('web_evidence', []) if set(roles).intersection(e['target_roles'])]
        plan.append({'id': item['id'], 'roles': roles, 'purpose': item.get('purpose', hints[0]['purpose']),
                     'web_evidence_ids': evidence_ids,
                     'fact_ids': assigned_facts, 'rule_ids': assigned_rules, 'guide': hints,
                     'role_assignment': item.get('role_assignment', 'explicit')})
    if len({b['id'] for b in plan}) != len(plan):
        raise ValueError('Duplicate block IDs')
    return plan, {'catalog_sha256': hashlib.sha256(raw.encode()).hexdigest(),
                  'workspace_revision': catalog.get('workspace_revision'),
                  'rules_scope': 'actual_selected_release_documents',
                  'fallback_roles': [b['id'] for b in plan if b['role_assignment'] != 'explicit']}


def validate_blocks(result, plan):
    errors = []
    blocks = result.get('blocks')
    if not isinstance(blocks, list) or any(not isinstance(b, dict) for b in blocks):
        return ['Missing or invalid blocks']
    if [b.get('id') for b in blocks] != [b['id'] for b in plan]:
        errors.append('Block order/coverage mismatch')
    if any(not isinstance(b.get('markdown'), str) or not b['markdown'].strip() for b in blocks):
        return errors + ['Empty block markdown']
    if result.get('markdown') != '\n\n'.join(b['markdown'] for b in blocks):
        errors.append('Article differs from assembled blocks')
    claims = {c['id']: c for c in result.get('claims', [])}
    assignments = []
    for block, spec in zip(blocks, plan):
        ids = block.get('claim_ids')
        if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids):
            errors.append('Invalid block claim_ids: ' + str(block.get('id')))
            continue
        assignments.extend(ids)
        for cid in ids:
            claim = claims.get(cid)
            if not claim or claim.get('text', '') not in block['markdown'] or set(claim.get('fact_ids', [])) - set(spec['fact_ids']):
                errors.append('Block claim/evidence mismatch: ' + cid)
    if set(assignments) != set(claims) or len(assignments) != len(set(assignments)):
        errors.append('Claim block coverage/duplicates mismatch')
    return errors
