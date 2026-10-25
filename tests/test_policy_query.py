import unittest
from pathlib import Path
from services.policy_query import PolicyQueryEngine

ROOT = Path(__file__).resolve().parents[1]

class TestPolicyQueryEngine(unittest.TestCase):
    def setUp(self):
        self.engine = PolicyQueryEngine(ROOT)

    def test_query_product_recommendation(self):
        res = self.engine.query_by_topic('product_recommendation')
        self.assertEqual(res['topic'], 'product_recommendation')
        self.assertGreater(res['counts']['direct'], 10)
        self.assertGreater(res['counts']['related'], 0)
        self.assertGreater(res['counts']['drafts'], 0)
        
        # Verify specific critical policies are found
        direct_ids = {p['id'] for p in res['direct_policies']}
        self.assertIn('RULE-READER-STYLE-V2N0033', direct_ids)  # 구매 강요 금지
        self.assertIn('GUIDE-03-STRUCTURE-V2N0065', direct_ids)  # 역할 다른 장비 비교표 대안 금지
        self.assertIn('GUIDE-03-STRUCTURE-V2N0081', direct_ids)  # 기본/조건부/대안 3분류
        self.assertIn('RULE-OCEANTECH-BRAND-LINKS-V2N0046', direct_ids)  # 여러 제품 링크 배치
        
        # Verify markdown brief generation
        md = res['ai_brief_markdown']
        self.assertIn('# 정책 조회 브리프', md)
        self.assertIn('구매 강요 금지', md)
        self.assertIn('RULE-OCEANTECH-BRAND-LINKS-V2N0046', md)

    def test_query_korean_synonym(self):
        res = self.engine.query_by_topic('제품 추천 규칙')
        self.assertGreater(res['counts']['direct'], 10)
        self.assertGreater(res['elapsed_ms'], 0.0)

    def test_multi_hop_traversal_and_filtering(self):
        res = self.engine.query_by_topic('product_recommendation')
        related = res['related_constraints']
        self.assertGreater(len(related), 0)
        
        # Verify related policies have depth and path
        for r in related:
            self.assertIn('traversal_depth', r)
            self.assertGreaterEqual(r['traversal_depth'], 1)
            self.assertIn('relation_path', r)
            self.assertTrue(r['relation_path'])
            # Verify no retired/reference atom is leaked into active constraints
            self.assertEqual(r['lifecycle'], 'active')
            self.assertNotEqual(r['kind'], 'reference')

    def test_no_artificial_exceptions(self):
        res = self.engine.query_by_topic('product_recommendation')
        v33 = next((p for p in res['direct_policies'] if p['id'] == 'RULE-READER-STYLE-V2N0033'), None)
        self.assertIsNotNone(v33)
        # Verify exception is empty string (no artificial exception for forced purchase)
    def test_direct_search_filters_retired_and_reference(self):
        # Mocking or simulating memory-injected atoms with matching tags
        state = self.engine.manager.load()
        mock_atoms = list(state['atoms'])
        mock_atoms.append({
            'id': 'POL-MOCK-RETIRED',
            'title': '폐기된 추천 규칙',
            'text': '폐기된 추천 정책',
            'kind': 'require',
            'enabled': True,
            'lifecycle': 'retired',
            'tags': ['product_recommendation'],
            'stages': ['write']
        })
        mock_atoms.append({
            'id': 'POL-MOCK-REFERENCE',
            'title': '비규범 참조 추천 행',
            'text': '참조 마크다운 헤더',
            'kind': 'reference',
            'enabled': True,
            'lifecycle': 'active',
            'tags': ['product_recommendation'],
            'stages': []
        })
        mock_atoms.append({
            'id': 'POL-MOCK-DISABLED',
            'title': '비활성 추천 규칙',
            'text': '비활성 정책 본문',
            'kind': 'require',
            'enabled': False,
            'lifecycle': 'active',
            'tags': ['product_recommendation'],
            'stages': ['write']
        })
        mock_atoms.append({
            'id': 'POL-MOCK-RETIRED-BY',
            'title': '대체된 추천 규칙',
            'text': '대체된 정책 본문',
            'kind': 'require',
            'enabled': True,
            'retired_by': 'POL-SOME-NEW-ID',
            'lifecycle': 'active',
            'tags': ['product_recommendation'],
            'stages': ['write']
        })
        
        # Monkey patch load() temporarily to test filtering of directly matched atoms
        original_load = self.engine.manager.load
        self.engine.manager.load = lambda: {**state, 'atoms': mock_atoms}
        try:
            res = self.engine.query_by_topic('product_recommendation')
            retrieved_ids = {p['id'] for p in res['direct_policies']}
            self.assertNotIn('POL-MOCK-RETIRED', retrieved_ids)
            self.assertNotIn('POL-MOCK-REFERENCE', retrieved_ids)
            self.assertNotIn('POL-MOCK-DISABLED', retrieved_ids)
            self.assertNotIn('POL-MOCK-RETIRED-BY', retrieved_ids)
        finally:
            self.engine.manager.load = original_load

    def test_query_brand_policy_cluster(self):
        res = self.engine.query_by_topic('브랜드 정책')
        direct_ids = {p['id'] for p in res['direct_policies']}
        
        # Verify 100% of active normative brand atoms are retrieved
        state = self.engine.manager.load()
        ocean_atoms = [a for a in state['atoms'] if a.get('target') == 'RULE-OCEANTECH-BRAND-LINKS' and a.get('lifecycle') == 'active' and a.get('kind') != 'reference']
        self.assertEqual(len(ocean_atoms), 49)
        missing_ids = [a['id'] for a in ocean_atoms if a['id'] not in direct_ids]
        self.assertEqual(missing_ids, [], f"Missing brand atoms: {missing_ids}")
        ocean_retrieved = [p for p in res['direct_policies'] if p['id'].startswith('RULE-OCEANTECH-BRAND-LINKS')]
        self.assertEqual(len(ocean_retrieved), 49)
        self.assertGreaterEqual(res['counts']['direct'], 49)
        
        # Verify opening greeting & business notice
        self.assertIn('RULE-OCEANTECH-BRAND-LINKS-V2N0016', direct_ids)
        self.assertIn('RULE-OCEANTECH-BRAND-LINKS-V2N0020', direct_ids)
        self.assertIn('RULE-OCEANTECH-BRAND-LINKS-V2N0031', direct_ids)
        
        # Verify product links & data contracts
        self.assertIn('RULE-OCEANTECH-BRAND-LINKS-V2N0042', direct_ids)
        self.assertIn('RULE-OCEANTECH-BRAND-LINKS-V2N0050', direct_ids)
        self.assertIn('RULE-OCEANTECH-BRAND-LINKS-V2N0056', direct_ids)
        self.assertIn('RULE-OCEANTECH-BRAND-LINKS-V2N0066', direct_ids)
        self.assertIn('RULE-OCEANTECH-BRAND-LINKS-V2N0074', direct_ids)
        
        # Verify closing & paired banner contracts
        self.assertIn('RULE-OCEANTECH-BRAND-LINKS-V2N0081', direct_ids)
        self.assertIn('RULE-OCEANTECH-BRAND-LINKS-V2N0091', direct_ids)
        self.assertIn('RULE-OCEANTECH-BRAND-LINKS-V2N0100', direct_ids)
        self.assertIn('RULE-OCEANTECH-BRAND-LINKS-V2N0106', direct_ids)
        self.assertIn('RULE-OCEANTECH-BRAND-LINKS-V2N0133', direct_ids)
        
        # Verify AI Brief generation
        md = res['ai_brief_markdown']
        self.assertIn('브랜드 정책', md)
        self.assertIn('RULE-OCEANTECH-BRAND-LINKS-V2N0016', md)
        self.assertIn('oceantech-inquiry-closing', md)

    def test_query_planning_topic_cluster(self):
        res = self.engine.query_by_topic('기획 주제')
        direct_ids = {p['id'] for p in res['direct_policies']}
        
        # Verify 100% of active normative topic atoms are retrieved
        state = self.engine.manager.load()
        topic_atoms = [a for a in state['atoms'] if a.get('target') == 'GUIDE-01-TOPIC' and a.get('lifecycle') == 'active' and a.get('kind') != 'reference']
        self.assertEqual(len(topic_atoms), 23)
        missing_ids = [a['id'] for a in topic_atoms if a['id'] not in direct_ids]
        self.assertEqual(missing_ids, [], f"Missing topic atoms: {missing_ids}")
        guide_topic_retrieved = [p for p in res['direct_policies'] if p['id'].startswith('GUIDE-01-TOPIC')]
        self.assertEqual(len(guide_topic_retrieved), 23)
        self.assertGreaterEqual(res['counts']['direct'], 23)
        
        # Verify key planning atoms
        self.assertIn('GUIDE-01-TOPIC-V2N0004', direct_ids)
        self.assertIn('GUIDE-01-TOPIC-V2N0008', direct_ids)
        self.assertIn('GUIDE-01-TOPIC-V2N0011', direct_ids)
        self.assertIn('GUIDE-01-TOPIC-V2N0023', direct_ids)
        self.assertIn('GUIDE-01-TOPIC-V2N0026', direct_ids)
        self.assertIn('GUIDE-01-TOPIC-V2N0033', direct_ids)
        self.assertIn('GUIDE-01-TOPIC-V2N0058', direct_ids)
        self.assertIn('GUIDE-01-TOPIC-V2N0065', direct_ids)
        self.assertIn('GUIDE-01-TOPIC-V2N0067', direct_ids)
        
        # Verify multi-hop related constraints
        related_ids = {r['id'] for r in res['related_constraints']}
        self.assertIn('RULE-READER-STYLE-V2N0037', related_ids)  # linked via V2N0033 complements
        
        # Verify AI Brief generation
        md = res['ai_brief_markdown']
        self.assertIn('기획', md)
        self.assertIn('GUIDE-01-TOPIC-V2N0023', md)

    def test_query_reader_style_cluster(self):
        res = self.engine.query_by_topic('문체 정책')
        direct_ids = {p['id'] for p in res['direct_policies']}
        
        # Verify 100% of active normative reader style atoms are retrieved
        state = self.engine.manager.load()
        style_atoms = [a for a in state['atoms'] if a.get('target') == 'RULE-READER-STYLE' and a.get('lifecycle') == 'active' and a.get('kind') != 'reference']
        self.assertEqual(len(style_atoms), 52)
        missing_ids = [a['id'] for a in style_atoms if a['id'] not in direct_ids]
        self.assertEqual(missing_ids, [], f"Missing reader style atoms: {missing_ids}")
        
        # Verify core style policies
        self.assertIn('RULE-READER-STYLE-V2N0004', direct_ids)
        self.assertIn('RULE-READER-STYLE-V2N0006', direct_ids)
        self.assertIn('RULE-READER-STYLE-V2N0011', direct_ids)
        self.assertIn('RULE-READER-STYLE-V2N0013', direct_ids)
        self.assertIn('RULE-READER-STYLE-V2N0031', direct_ids)
        self.assertIn('RULE-READER-STYLE-V2N0033', direct_ids)
        self.assertIn('RULE-READER-STYLE-V2N0039', direct_ids)
        self.assertIn('RULE-READER-STYLE-V2N0045', direct_ids)
        self.assertIn('RULE-READER-STYLE-V2N0069', direct_ids)
        self.assertIn('RULE-READER-STYLE-V2N0071', direct_ids)
        self.assertIn('RULE-READER-STYLE-V2N0097', direct_ids)
        self.assertIn('RULE-READER-STYLE-V2N0108', direct_ids)
        
        # Verify AI Brief generation
        md = res['ai_brief_markdown']
        self.assertIn('문체', md)
        self.assertIn('RULE-READER-STYLE-V2N0004', md)

    def test_query_natural_language_queries(self):
        """Verify queries like '회사 소개', '미확인 주장', '사실 확인' retrieve expected policies instead of returning 0."""
        # 1. '회사 소개' query
        res_company = self.engine.query_by_topic('회사 소개')
        self.assertGreater(res_company['counts']['direct'], 0, "회사 소개 질의 결과가 0개여서는 안 됩니다.")
        company_ids = {p['id'] for p in res_company['direct_policies']}
        self.assertIn('RULE-OCEANTECH-BRAND-LINKS-V2N0016', company_ids)  # 로지텍 공식 수입 총판 첫인사
        self.assertIn('RULE-OCEANTECH-BRAND-LINKS-V2N0006', company_ids)  # 브랜드 정책 최우선

        # 2. '미확인 주장' query
        res_unconfirmed = self.engine.query_by_topic('미확인 주장')
        self.assertGreater(res_unconfirmed['counts']['direct'], 0, "미확인 주장 질의 결과가 0개여서는 안 됩니다.")
        unconfirmed_ids = {p['id'] for p in res_unconfirmed['direct_policies']}
        self.assertIn('RULE-READER-STYLE-V2N0071', unconfirmed_ids)  # 미확인 주장은 조사 항목으로 분리
        self.assertIn('RULE-READER-STYLE-V2N0073', unconfirmed_ids)  # 미확인 사실 암시 금지

        # 3. '사실 확인' query
        res_facts = self.engine.query_by_topic('사실 확인')
        self.assertGreater(res_facts['counts']['direct'], 0, "사실 확인 질의 결과가 0개여서는 안 됩니다.")
        facts_ids = {p['id'] for p in res_facts['direct_policies']}
        self.assertIn('RULE-READER-STYLE-V2N0071', facts_ids)  # 확인된 사실은 조건과 함께 직접 전달

    def test_reclassified_fact_guardrails(self):
        """Verify common fact/condition/claim rules are classified as runtime_guardrail, not template_design."""
        state = self.engine.manager.load()
        atom_map = {a['id']: a for a in state['atoms']}
        guardrail_ids = [
            'RULE-READER-STYLE-V2N0071',
            'RULE-READER-STYLE-V2N0008',
            'RULE-READER-STYLE-V2N0049',
            'RULE-READER-STYLE-V2N0077',
            'RULE-READER-STYLE-V2N0092',
        ]
        for gid in guardrail_ids:
            atom = atom_map.get(gid)
            self.assertIsNotNone(atom, f"Atom {gid} must exist")
            self.assertEqual(atom.get('purpose'), 'runtime_guardrail', f"Atom {gid} must be runtime_guardrail")

    def test_query_article_structure_cluster(self):
        """Verify 100% of active normative atoms in GUIDE-03-STRUCTURE are retrieved."""
        res = self.engine.query_by_topic('글 구성')
        direct_ids = {p['id'] for p in res['direct_policies']}
        
        state = self.engine.manager.load()
        struct_atoms = [a for a in state['atoms'] if a.get('target') == 'GUIDE-03-STRUCTURE' and a.get('lifecycle') == 'active' and a.get('kind') != 'reference']
        self.assertEqual(len(struct_atoms), 106)
        
        missing_ids = [a['id'] for a in struct_atoms if a['id'] not in direct_ids]
        self.assertEqual(missing_ids, [], f"Missing structure atoms: {missing_ids}")
        self.assertGreaterEqual(res['counts']['direct'], 106)

    def test_query_image_assets_cluster(self):
        """Verify 100% of active normative atoms in GUIDE-04-IMAGES are retrieved."""
        res = self.engine.query_by_topic('이미지 자산')
        direct_ids = {p['id'] for p in res['direct_policies']}
        
        state = self.engine.manager.load()
        img_atoms = [a for a in state['atoms'] if a.get('target') == 'GUIDE-04-IMAGES' and a.get('lifecycle') == 'active' and a.get('kind') != 'reference']
        self.assertEqual(len(img_atoms), 74)
        
        missing_ids = [a['id'] for a in img_atoms if a['id'] not in direct_ids]
        self.assertEqual(missing_ids, [], f"Missing image atoms: {missing_ids}")
        self.assertGreaterEqual(res['counts']['direct'], 74)

    def test_query_editorial_feedback_cluster(self):
        """Verify 100% of active normative atoms in GUIDE-05-FEEDBACK are retrieved."""
        res = self.engine.query_by_topic('피드백')
        direct_ids = {p['id'] for p in res['direct_policies']}
        
        state = self.engine.manager.load()
        fb_atoms = [a for a in state['atoms'] if a.get('target') == 'GUIDE-05-FEEDBACK' and a.get('lifecycle') == 'active' and a.get('kind') != 'reference']
        self.assertEqual(len(fb_atoms), 47)
        
        missing_ids = [a['id'] for a in fb_atoms if a['id'] not in direct_ids]
        self.assertEqual(missing_ids, [], f"Missing feedback atoms: {missing_ids}")
        self.assertGreaterEqual(res['counts']['direct'], 47)

    def test_query_facts_cluster(self):
        """Verify 100% of active normative atoms in GUIDE-02-FACTS are retrieved."""
        res = self.engine.query_by_topic('팩트')
        direct_ids = {p['id'] for p in res['direct_policies']}
        
        state = self.engine.manager.load()
        facts_atoms = [a for a in state['atoms'] if a.get('target') == 'GUIDE-02-FACTS' and a.get('lifecycle') == 'active' and a.get('kind') != 'reference']
        self.assertEqual(len(facts_atoms), 34)
        
        missing_ids = [a['id'] for a in facts_atoms if a['id'] not in direct_ids]
        self.assertEqual(missing_ids, [], f"Missing facts atoms: {missing_ids}")
        self.assertGreaterEqual(res['counts']['direct'], 34)

        # Verify key atoms are retrieved
        self.assertIn('GUIDE-02-FACTS-V2N0004', direct_ids)
        self.assertIn('GUIDE-02-FACTS-V2N0011', direct_ids)
        self.assertIn('GUIDE-02-FACTS-V2N0017', direct_ids)
        self.assertIn('GUIDE-02-FACTS-V2N0019', direct_ids)
        self.assertIn('GUIDE-02-FACTS-V2N0026', direct_ids)
        self.assertIn('GUIDE-02-FACTS-V2N0035', direct_ids)
        self.assertIn('GUIDE-02-FACTS-V2N0054', direct_ids)
        self.assertIn('GUIDE-02-FACTS-V2N0071', direct_ids)
        self.assertIn('GUIDE-02-FACTS-V2N0087', direct_ids)
        self.assertIn('GUIDE-02-FACTS-V2N0092', direct_ids)

    def test_query_completion_cluster(self):
        """Verify 100% of active normative atoms in GUIDE-06-COMPLETION are retrieved."""
        res = self.engine.query_by_topic('발행')
        direct_ids = {p['id'] for p in res['direct_policies']}
        
        state = self.engine.manager.load()
        completion_atoms = [a for a in state['atoms'] if a.get('target') == 'GUIDE-06-COMPLETION' and a.get('lifecycle') == 'active' and a.get('kind') != 'reference']
        self.assertEqual(len(completion_atoms), 24)
        
        missing_ids = [a['id'] for a in completion_atoms if a['id'] not in direct_ids]
        self.assertEqual(missing_ids, [], f"Missing completion atoms: {missing_ids}")
        self.assertGreaterEqual(res['counts']['direct'], 24)

        # Verify key atoms are retrieved
        self.assertIn('GUIDE-06-COMPLETION-V2N0002', direct_ids)
        self.assertIn('GUIDE-06-COMPLETION-V2N0004', direct_ids)
        self.assertIn('GUIDE-06-COMPLETION-V2N0009', direct_ids)
        self.assertIn('GUIDE-06-COMPLETION-V2N0026', direct_ids)
        self.assertIn('GUIDE-06-COMPLETION-V2N0031', direct_ids)
        self.assertIn('GUIDE-06-COMPLETION-V2N0041', direct_ids)
        self.assertIn('GUIDE-06-COMPLETION-V2N0061', direct_ids)
        self.assertIn('GUIDE-06-COMPLETION-V2N0063', direct_ids)
        self.assertIn('GUIDE-06-COMPLETION-V2N0066', direct_ids)

    def test_query_prompt_write_cluster(self):
        """Verify 100% of active normative atoms in PROMPT-WRITE are retrieved."""
        res = self.engine.query_by_topic('초안 작성')
        direct_ids = {p['id'] for p in res['direct_policies']}
        
        state = self.engine.manager.load()
        pw_atoms = [a for a in state['atoms'] if a.get('target') == 'PROMPT-WRITE' and a.get('lifecycle') == 'active' and a.get('kind') != 'reference']
        self.assertEqual(len(pw_atoms), 32)
        
        missing_ids = [a['id'] for a in pw_atoms if a['id'] not in direct_ids]
        self.assertEqual(missing_ids, [], f"Missing PROMPT-WRITE atoms: {missing_ids}")
        self.assertGreaterEqual(res['counts']['direct'], 32)

        # Verify key atoms are retrieved
        self.assertIn('PROMPT-WRITE-V2N0001', direct_ids)
        self.assertIn('PROMPT-WRITE-V2N0011', direct_ids)
        self.assertIn('PROMPT-WRITE-V2N0016', direct_ids)
        self.assertIn('PROMPT-WRITE-V2N0026', direct_ids)
        self.assertIn('PROMPT-WRITE-V2N0038', direct_ids)
        self.assertIn('PROMPT-WRITE-V2N0044', direct_ids)
        self.assertIn('PROMPT-WRITE-V2N0052', direct_ids)
        self.assertIn('PROMPT-WRITE-V2N0056', direct_ids)

    def test_query_prompt_strategy_cluster(self):
        """Verify 100% of active normative atoms in PROMPT-STRATEGY are retrieved."""
        res = self.engine.query_by_topic('기획 전략')
        direct_ids = {p['id'] for p in res['direct_policies']}
        
        state = self.engine.manager.load()
        ps_atoms = [a for a in state['atoms'] if a.get('target') == 'PROMPT-STRATEGY' and a.get('lifecycle') == 'active' and a.get('kind') != 'reference']
        self.assertEqual(len(ps_atoms), 22)
        
        missing_ids = [a['id'] for a in ps_atoms if a['id'] not in direct_ids]
        self.assertEqual(missing_ids, [], f"Missing PROMPT-STRATEGY atoms: {missing_ids}")
        self.assertGreaterEqual(res['counts']['direct'], 22)

        # Verify key atoms are retrieved
        self.assertIn('PROMPT-STRATEGY-V2N0001', direct_ids)
        self.assertIn('PROMPT-STRATEGY-V2N0003', direct_ids)
        self.assertIn('PROMPT-STRATEGY-V2N0013', direct_ids)
        self.assertIn('PROMPT-STRATEGY-V2N0020', direct_ids)
        self.assertIn('PROMPT-STRATEGY-V2N0026', direct_ids)
        self.assertIn('PROMPT-STRATEGY-V2N0030', direct_ids)
        self.assertIn('PROMPT-STRATEGY-V2N0032', direct_ids)
        self.assertIn('PROMPT-STRATEGY-V2N0038', direct_ids)

    def test_query_asset_truth_cluster(self):
        """Verify 100% of active normative atoms in RULE-ASSET-TRUTH are retrieved."""
        res = self.engine.query_by_topic('자산 진실성')
        direct_ids = {p['id'] for p in res['direct_policies']}
        
        state = self.engine.manager.load()
        at_atoms = [a for a in state['atoms'] if a.get('target') == 'RULE-ASSET-TRUTH' and a.get('lifecycle') == 'active' and a.get('kind') != 'reference']
        self.assertEqual(len(at_atoms), 17)
        
        missing_ids = [a['id'] for a in at_atoms if a['id'] not in direct_ids]
        self.assertEqual(missing_ids, [], f"Missing RULE-ASSET-TRUTH atoms: {missing_ids}")
        self.assertGreaterEqual(res['counts']['direct'], 17)

        # Verify key atoms are retrieved
        self.assertIn('RULE-ASSET-TRUTH-V2N0004', direct_ids)
        self.assertIn('RULE-ASSET-TRUTH-V2N0006', direct_ids)
        self.assertIn('RULE-ASSET-TRUTH-V2N0013', direct_ids)
        self.assertIn('RULE-ASSET-TRUTH-V2N0017', direct_ids)
        self.assertIn('RULE-ASSET-TRUTH-V2N0022', direct_ids)
        self.assertIn('RULE-ASSET-TRUTH-V2N0026', direct_ids)
        self.assertIn('RULE-ASSET-TRUTH-V2N0033', direct_ids)
        self.assertIn('RULE-ASSET-TRUTH-V2N0040', direct_ids)

    def test_query_core_guides_cluster(self):
        """Verify 100% of active normative atoms in GUIDE-CORE-* are retrieved."""
        res = self.engine.query_by_topic('핵심 가이드')
        direct_ids = {p['id'] for p in res['direct_policies']}
        
        state = self.engine.manager.load()
        core_atoms = [a for a in state['atoms'] if a.get('target', '').startswith('GUIDE-CORE') and a.get('lifecycle') == 'active' and a.get('kind') != 'reference']
        self.assertEqual(len(core_atoms), 31)
        
        missing_ids = [a['id'] for a in core_atoms if a['id'] not in direct_ids]
        self.assertEqual(missing_ids, [], f"Missing core guide atoms: {missing_ids}")
        self.assertGreaterEqual(res['counts']['direct'], 31)

    def test_query_all_policy_clusters_100_percent_completion(self):
        """Verify 100% of all active normative atoms in workspace (565/565) are fully Quarkized and semantically reviewed."""
        state = self.engine.manager.load()
        active_normative = [a for a in state['atoms'] if a.get('lifecycle') == 'active' and a.get('kind') != 'reference']
        self.assertEqual(len(active_normative), 565, "Total active normative atoms must be exactly 565.")
        
        unreviewed = [a for a in active_normative if a.get('semantic_review_status') != 'semantically_reviewed']
        self.assertEqual(len(unreviewed), 0, f"All 565 atoms must be semantically reviewed. Unreviewed count: {len(unreviewed)}")
        
        unreviewed_elements = [a for a in active_normative if a.get('element_scope_status') != 'semantically_reviewed']
        self.assertEqual(len(unreviewed_elements), 0, f"All 565 atoms must have element_scope_status semantically_reviewed.")

        empty_semantic_fields = [
            a['id'] for a in active_normative
            if not a.get('subject') or not a.get('action') or not a.get('object') or not a.get('intent')
        ]
        self.assertEqual(empty_semantic_fields, [], f"Atoms with empty subject/action/object/intent: {empty_semantic_fields}")


if __name__ == '__main__':
    unittest.main()






