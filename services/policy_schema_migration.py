"""Safe policy schema migration to v2 with zero content alteration."""
from copy import deepcopy
from services.policy_manager import PolicyManager, PolicyConflict, PolicyError

def migrate_to_v2(manager: PolicyManager, expected_revision: int = None):
    manager.ensure()
    with manager.lock():
        state = manager.load()
        if expected_revision is not None:
            manager.check_revision(state, expected_revision)
        if state.get('schema_version') == 2:
            return state

        before = manager.assemble(state)
        
        for atom in state['atoms']:
            # Preserve existing fields
            atom.setdefault('condition', '')
            atom.setdefault('exception', '')
            atom.setdefault('intent', '')
            atom.setdefault('sub_aspects', [])
            atom.setdefault('relations', [])
            atom.setdefault('semantic_review_status', 'needs_review')
            atom.setdefault('unresolved_questions', [])
            atom.setdefault('authority_issuer', 'project_governance' if atom.get('level') in ('L1', 'L2') else 'authoring_team')
            atom.setdefault('lifecycle', 'retired' if (atom.get('retired_by') or not atom.get('enabled')) else 'active')
            atom.setdefault('element_scope_status', 'needs_review')
            atom.setdefault('purpose_reason', '')

        state['schema_version'] = 2
        after = manager.assemble(state)
        if before != after:
            raise PolicyError('마이그레이션 중 조립 본문이 변경되었습니다.')

        manager.commit(state, {
            'policy_id': 'SCHEMA-MIGRATION-V2',
            'before': None,
            'after': {
                'review_note': '원자 데이터 계약 v2 필드 추가 (condition, exception, relations, sub_aspects 등); 본문 및 조립 무결성 보존'
            }
        })
    return state
