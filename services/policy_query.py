"""Topic and relational policy query service for AI and human review."""
import json
import re
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

from services.policy_manager import PolicyManager

TOPIC_SYNONYMS = {
    'product_recommendation': [
        '추천', '제품 추천', '대안', '비교표', '추가 장비', '부속', '기본 구성',
        '구매 강요', '소개 링크', '보조 노드', '인지', '호환', '과장', 'recommend'
    ],
    'evidence_boundary': [
        '근거', '스펙', '단위', '수치', '사실', '증거', 'fact', '미확인 주장', '미확인', '주장',
        '사실 확인', '조사 항목', '팩트', '진위', '검증', '확인된 사실'
    ],
    'evidence_facts': [
        '팩트', '팩트 검증', '사실 확인', '근거 데이터', 'facts', 'evidence_facts', 'fact_verification', '팩트 규칙', '출처'
    ],
    'brand_identity': [
        '브랜드', '오션텍', '오우션', '블로그 링크', '배너', '소개 링크', '회사 소개',
        '총판', '오우션 테크놀러지', '첫인사', '인사말', '공식 수입', '정체성'
    ],
    'planning_topic': [
        '기획', '주제', '키워드', '부족 키워드', '진단', '검색어', '엔티티', 'topic', 'keyword', 'planning'
    ],
    'reader_style': [
        '문체', '독자', '스타일', '질문 해결', '가독성', '작성 지시', '편집 검토', 'reader_style', 'editorial_tone', 'style',
        '독자 관점', '풀어쓰기', '응집도'
    ],
    'article_structure': [
        '글 구성', '본문 구조', '구조', '도입부', '본문', '마무리', '단락', '섹션', 'structure', 'article_structure'
    ],
    'image_assets': [
        '이미지', '자산', '시각 자산', '사진', 'gif', '슬라이드', '설명 카드', '배너', 'images', 'media', 'asset', '자산 진실성', '시각 자산 검증', 'asset_truth'
    ],
    'editorial_feedback': [
        '피드백', '리뷰', '검토', '자체 교정', '재작성', '수정 요청', 'feedback', 'review'
    ],
    'completion_console': [
        '완료', '발행', '콘솔', '상태 전이', 'publish_ready', 'completion', 'console', 'publishing', '발행 승인', '승인 스냅샷'
    ],
    'prompt_write': [
        '초안 작성', '원고 집필 프롬프트', 'claims_map', 'unresolved_items', 'need_id', 'used_asset_need_ids', 'prompt_write', '집필 프롬프트'
    ],
    'prompt_strategy': [
        '기획 전략', '전략 프롬프트', 'asset_needs', 'primary_playbook', 'prompt_strategy', '전략 기획'
    ],
    'core_guide': [
        '핵심 가이드', '핵심 지침', '기본 원칙', 'core_guide', 'core_safety', 'core_style', 'core_writing', '핵심 원칙'
    ],
    'prompt_feedback': [
        '피드백 프롬프트', '초안 검토 프롬프트', 'issues', 'missing_claims', 'passed', 'prompt_feedback'
    ],
    'prompt_official': [
        '공식 검토 프롬프트', 'verdict', 'insufficient_evidence', 'prompt_official', '공식 근거 검토'
    ],
    'numeric_scope': [
        '수치 범위', '단위 변환', '측정 수치', 'numeric_scope', '수치 표기'
    ],
    'component_role': [
        '부품 역할', '하드웨어 부품', '기능 주체', 'component_role', '장비 기능'
    ],
    'platform_scope': [
        '플랫폼 범위', 'byod', '플랫폼 연동', 'platform_scope', '실행 모드'
    ],
    'configuration_source': [
        '설정 출처', '배선 절차', '메뉴 경로', 'configuration_source', '설정 순서'
    ],
    'experience_business': [
        '경험 실증', '쇼룸 실증', '고객 사례', '기업 정책', 'experience_business', '자체 측정'
    ]
}

TOPIC_TAG_MAP = {
    'product_recommendation': ['product_recommendation'],
    'evidence_boundary': ['evidence_boundary', 'evidence'],
    'evidence_facts': ['evidence_facts', 'evidence_boundary', 'evidence', 'fact_verification'],
    'brand_identity': ['brand_identity', 'oceantech_brand', 'brand_links'],
    'planning_topic': ['planning_topic', 'seo_keyword'],
    'reader_style': ['reader_style', 'editorial_tone'],
    'article_structure': ['article_structure', 'structure'],
    'image_assets': ['images', 'media', 'asset_planning', 'asset_truth'],
    'editorial_feedback': ['feedback', 'review', 'governance'],
    'completion_console': ['completion', 'console', 'publishing', 'governance'],
    'prompt_write': ['prompt_write', 'authoring_prompt', 'write_instructions', 'claims_map', 'unresolved_items', 'asset_need'],
    'prompt_strategy': ['prompt_strategy', 'strategy_planning', 'asset_needs', 'playbook_selection', 'branding_plan'],
    'core_guide': ['core_guide', 'core_safety', 'core_style', 'core_writing', 'safety', 'governance'],
    'prompt_feedback': ['prompt_feedback', 'feedback', 'review'],
    'prompt_official': ['prompt_official', 'official_verification', 'fact_verification'],
    'numeric_scope': ['numeric_scope', 'evidence', 'specification'],
    'component_role': ['component_role', 'compatibility', 'hardware'],
    'platform_scope': ['platform_scope', 'compatibility', 'fit_conditions'],
    'configuration_source': ['configuration_source', 'configuration', 'setup'],
    'experience_business': ['experience_business', 'experience', 'business_policy']
}

class PolicyQueryEngine:
    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root).resolve() if root else Path(__file__).resolve().parents[1]
        self.manager = PolicyManager(self.root)

    def query_by_topic(self, topic: str, include_drafts: bool = True) -> Dict[str, Any]:
        start_time = time.perf_counter()
        state = self.manager.load()
        active_rel_path = self.manager.authoring / 'releases/active_release.json'
        active_release_id = json.loads(active_rel_path.read_text(encoding='utf-8')).get('active_release_id') if active_rel_path.exists() else None

        atoms = state.get('atoms', [])
        atom_map = {a['id']: a for a in atoms}

        # Normalize topic string
        normalized_topic = topic.strip().lower()

        # 1. Dynamically derive matched tags from TOPIC_SYNONYMS
        matched_tags = set()
        for category, syns in TOPIC_SYNONYMS.items():
            if any(syn in normalized_topic for syn in syns):
                for tag in TOPIC_TAG_MAP.get(category, []):
                    matched_tags.add(tag)

        # 2. Extract significant search tokens
        tokens = [t.strip() for t in re.split(r'[\s,._/-]+', normalized_topic) if len(t.strip()) >= 2]

        direct_atoms = []
        for a in atoms:
            # 1. Skip disabled, retired, or superseded atoms
            if not a.get('enabled', True) or a.get('lifecycle') == 'retired' or a.get('retired_by'):
                continue

            # 2. Skip pure non-normative reference rows
            if a.get('kind') == 'reference':
                continue

            # 3. Handle draft designs inclusion option
            if a.get('lifecycle') == 'draft' and not include_drafts:
                continue

            # Matching checks:
            is_direct = False

            # A. Tag match from synonym dictionary
            atom_tags = set(a.get('tags', []))
            if atom_tags.intersection(matched_tags):
                is_direct = True

            # B. Sub-aspects match
            sub_aspects = set(a.get('sub_aspects', []))
            if any(sub in normalized_topic for sub in sub_aspects):
                is_direct = True

            # C. Natural Language Phrase & Keyword matching across text fields
            full_text = ' '.join([
                a.get('title', ''),
                a.get('text', ''),
                a.get('intent', ''),
                a.get('action', ''),
                a.get('object', ''),
                a.get('section', '')
            ]).lower()

            if len(normalized_topic) >= 2 and normalized_topic in full_text:
                is_direct = True
            elif len(tokens) >= 2 and all(tok in full_text for tok in tokens):
                is_direct = True

            if is_direct:
                direct_atoms.append(a)

        # Multi-hop Graph Traversal (BFS) with strict status & lifecycle filtering
        TRAVERSAL_REL_TYPES = {'requires_context', 'depends_on', 'complements', 'exception_to'}
        max_depth = 3

        visited_ids = {da['id'] for da in direct_atoms}
        # queue item: (target_id, depth, path_str)
        queue = []
        for da in direct_atoms:
            for r in da.get('relations', []):
                tid = r.get('target_id')
                rtype = r.get('type')
                if tid and rtype in TRAVERSAL_REL_TYPES and tid not in visited_ids:
                    queue.append((tid, 1, f"{da['id']} -[{rtype}]-> {tid}"))

        related_active_map = {}  # tid -> (atom, depth, path)
        related_draft_map = {}   # tid -> (atom, depth, path)

        while queue:
            tid, depth, path = queue.pop(0)
            if tid in visited_ids:
                continue
            visited_ids.add(tid)

            target_atom = atom_map.get(tid)
            if not target_atom:
                continue

            # Filtering checks:
            # 1. Skip disabled or retired atoms
            if not target_atom.get('enabled', True) or target_atom.get('lifecycle') == 'retired' or target_atom.get('retired_by'):
                continue

            # 2. Skip pure non-normative reference rows
            if target_atom.get('kind') == 'reference':
                continue

            # 3. Handle draft designs separately from active constraints
            if target_atom.get('lifecycle') == 'draft':
                if include_drafts and tid not in related_draft_map:
                    related_draft_map[tid] = (target_atom, depth, path)
            else:
                if tid not in related_active_map:
                    related_active_map[tid] = (target_atom, depth, path)

            # Recursive BFS continuation up to max_depth
            if depth < max_depth:
                for r in target_atom.get('relations', []):
                    next_tid = r.get('target_id')
                    rtype = r.get('type')
                    if next_tid and rtype in TRAVERSAL_REL_TYPES and next_tid not in visited_ids:
                        queue.append((next_tid, depth + 1, f"{path} -[{rtype}]-> {next_tid}"))

        # Categorize direct atoms
        direct_active = [a for a in direct_atoms if a.get('lifecycle') != 'draft']
        direct_drafts = [a for a in direct_atoms if a.get('lifecycle') == 'draft']

        def summarize_atom(a: Dict[str, Any], include_reason: str = "direct_topic_match", depth: int = 0, path: str = "") -> Dict[str, Any]:
            return {
                'id': a['id'],
                'title': a.get('title'),
                'kind': a.get('kind'),
                'level': a.get('level'),
                'stages': a.get('stages', []),
                'domain': a.get('domain'),
                'purpose': a.get('purpose'),
                'applies_to_elements': a.get('applies_to_elements', []),
                'sub_aspects': a.get('sub_aspects', []),
                'subject': a.get('subject'),
                'action': a.get('action'),
                'object': a.get('object'),
                'condition': a.get('condition'),
                'exception': a.get('exception'),
                'intent': a.get('intent'),
                'relations': a.get('relations', []),
                'lifecycle': a.get('lifecycle', 'active'),
                'semantic_review_status': a.get('semantic_review_status'),
                'source': a.get('source'),
                'include_reason': include_reason,
                'traversal_depth': depth,
                'relation_path': path,
                'text': a.get('text', '')
            }

        direct_summaries = [summarize_atom(a, "direct_topic_match", 0, "") for a in direct_active]
        draft_summaries = [summarize_atom(a, "draft_design_model", 0, "") for a in direct_drafts]
        
        # Include any drafts discovered via traversal into draft_summaries
        for tid, (atom, depth, path) in related_draft_map.items():
            if tid not in {ds['id'] for ds in draft_summaries}:
                draft_summaries.append(summarize_atom(atom, f"relational_draft_expansion (depth {depth})", depth, path))

        related_summaries = [
            summarize_atom(atom, f"relational_constraint_expansion (depth {depth})", depth, path)
            for tid, (atom, depth, path) in sorted(related_active_map.items(), key=lambda x: (x[1][1], x[0]))
        ]

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Build readable AI Brief Markdown
        lines = [
            f"# 정책 조회 브리프: '{topic}'",
            f"- 작업 공간 Revision: r{state['revision']} | 활성 릴리스: `{active_release_id}`",
            f"- 조회 소요 시간: {elapsed_ms:.2f}ms | 직접 정책: {len(direct_summaries)}개 | 연결 제약: {len(related_summaries)}개 | 설계 초안: {len(draft_summaries)}개\n",
            "## 1. 직접 적용 정책 (Direct Rules)",
        ]
        
        for item in direct_summaries:
            lines.append(f"### [{item['id']}] {item['title']}")
            lines.append(f"- **규범/수준**: `{item['kind'].upper()}` / `{item['level']}` | **단계**: `{', '.join(item['stages'])}` | **구성요소**: `{', '.join(item['applies_to_elements'])}`")
            lines.append(f"- **관점**: `{', '.join(item['sub_aspects'])}` | **상태**: `{item['semantic_review_status']}`")
            if item['condition']:
                lines.append(f"- **적용 조건**: {item['condition']}")
            if item['exception']:
                lines.append(f"- **허용 예외**: {item['exception']}")
            if item['intent']:
                lines.append(f"- **목적/취지**: {item['intent']}")
            lines.append(f"- **본문**: {item['text'].strip()}")
            if item['relations']:
                rel_str = ", ".join(f"`{r['type']} -> {r['target_id']}` ({r.get('note', '')})" for r in item['relations'])
                lines.append(f"- **연결 관계**: {rel_str}")
            lines.append(f"- **출처**: `{item['source']['path']}:{item['source']['line']}`\n")

        lines.append("## 2. 확장 연결된 공통 제약 (Relational Constraints)")
        for item in related_summaries:
            lines.append(f"### [{item['id']}] {item['title']}")
            lines.append(f"- **규범/수준**: `{item['kind'].upper()}` / `{item['level']}` | **도메인**: `{item['domain']}` | **용도**: `{item['purpose']}`")
            if item.get('relation_path'):
                lines.append(f"- **탐색 경로 (Depth {item.get('traversal_depth')}):** `{item.get('relation_path')}`")
            lines.append(f"- **본문**: {item['text'].strip()}")
            lines.append(f"- **출처**: `{item['source']['path']}:{item['source']['line']}`\n")

        if draft_summaries:
            lines.append("## 3. 연계 설계 초안 (Draft Design — 활성 릴리스 제외)")
            for item in draft_summaries:
                lines.append(f"### [{item['id']}] {item['title']} (DRAFT)")
                lines.append(f"- **관점**: `{', '.join(item['sub_aspects'])}` | **계약 위치**: `{', '.join(item['applies_to_elements'])}`")
                lines.append(f"- **설계 내용**: {item['text'].strip()}")
                lines.append(f"- **출처**: `{item['source']['path']}:{item['source']['line']}`\n")

        brief_md = "\n".join(lines)

        return {
            'topic': topic,
            'workspace_revision': state['revision'],
            'active_release_id': active_release_id,
            'elapsed_ms': elapsed_ms,
            'counts': {
                'direct': len(direct_summaries),
                'related': len(related_summaries),
                'drafts': len(draft_summaries),
                'total': len(direct_summaries) + len(related_summaries) + len(draft_summaries)
            },
            'direct_policies': direct_summaries,
            'related_constraints': related_summaries,
            'draft_designs': draft_summaries,
            'ai_brief_markdown': brief_md
        }
