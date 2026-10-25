"""Tests for guide contracts, guide repository, immutable releases, context assembler, and governance."""
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from services.guide_contracts import (
    GuideContract,
    GuideKind,
    GuideRegistryContract,
    GuideReleaseManifest,
    RuleContract,
    RuleRegistryContract,
    RuleSeverity,
    RuleStatus,
    SectionPlan,
    ReviewReport,
    ReviewItem,
    ReviewCheckCategory,
    ReviewStatus as ContractReviewStatus,
)
from services.guide_repository import (
    DependencyCycleError,
    GuideRepository,
    GuideRepositoryError,
    IntegrityError,
    MissingDependencyError,
)
from services.context_assembler import ContextAssembler, extract_source_sections
from services.prompt_repository import LocalPromptRepository, LangfusePromptAdapter
from services.content_pipeline import ContentPipeline, atomic


class GuideSystemTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        # Create minimal content-system structure
        self.authoring = self.root / "content-system" / "02_writer_ai" / "authoring"
        self.rules_dir = self.authoring / "rules"
        self.prompts_dir = self.authoring / "prompts"
        self.core_dir = self.root / "content-system" / "02_writer_ai" / "core"

        self.rules_dir.mkdir(parents=True, exist_ok=True)
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        self.core_dir.mkdir(parents=True, exist_ok=True)

        # Write core guide
        (self.core_dir / "SAFETY_CORE.md").write_text("# Core Safety Guide\nNever invent facts.", encoding="utf-8")
        (self.rules_dir / "rule1.md").write_text("# Rule 1\nCheck bounds.", encoding="utf-8")
        (self.rules_dir / "rule2.md").write_text("# Rule 2\nCheck links.", encoding="utf-8")
        (self.prompts_dir / "write.md").write_text("Write instruction.", encoding="utf-8")
        (self.prompts_dir / "feedback.md").write_text("Feedback instruction.", encoding="utf-8")
        (self.prompts_dir / "strategy.md").write_text("Strategy instruction.", encoding="utf-8")
        (self.prompts_dir / "official.md").write_text("Official instruction.", encoding="utf-8")

        # Registries
        self.rule_reg_data = {
            "schema_version": "1.0.0",
            "guide_version": "3.0.0",
            "rules": [
                {
                    "id": "RULE-1",
                    "path": "rule1.md",
                    "required": True,
                    "severity": "blocking",
                    "priority": 10,
                    "status": "active",
                    "match": {"all": [], "any": []}
                },
                {
                    "id": "RULE-2",
                    "path": "rule2.md",
                    "required": False,
                    "severity": "blocking",
                    "priority": 20,
                    "status": "active",
                    "match": {"all": [], "any": [{"field": "claim_kinds", "op": "intersects", "values": ["numeric_spec"]}]}
                }
            ]
        }
        (self.rules_dir / "registry.json").write_text(json.dumps(self.rule_reg_data), encoding="utf-8")

        self.guide_reg_data = {
            "schema_version": "1.0.0",
            "guide_version": "3.0.0",
            "guides": [
                {
                    "id": "GUIDE-SAFETY",
                    "path": "../core/SAFETY_CORE.md",
                    "kind": "core",
                    "description": "Safety core",
                    "stages": ["write", "feedback"],
                    "required": True,
                    "status": "active",
                    "references_rule_ids": ["RULE-1"]
                }
            ]
        }
        (self.authoring / "guide-registry.json").write_text(json.dumps(self.guide_reg_data), encoding="utf-8")

        self.repo = GuideRepository(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    # 1. Pydantic validation and duplicate ID rejection
    def test_pydantic_contracts_and_duplicate_ids(self):
        dup_rules = {
            "rules": [
                {"id": "R1", "path": "r1.md"},
                {"id": "R1", "path": "r2.md"},
            ]
        }
        with self.assertRaises(ValueError):
            RuleRegistryContract.model_validate(dup_rules)

        dup_guides = {
            "guides": [
                {"id": "G1", "path": "g1.md", "description": "d1"},
                {"id": "G1", "path": "g2.md", "description": "d2"},
            ]
        }
        with self.assertRaises(ValueError):
            GuideRegistryContract.model_validate(dup_guides)

    # 2. Cycle detection and missing dependency error
    def test_cycle_and_missing_dependency_rejection(self):
        # Missing dep
        bad_rules = dict(self.rule_reg_data)
        bad_rules["rules"][0]["depends_on"] = ["RULE-NONEXISTENT"]
        (self.rules_dir / "registry.json").write_text(json.dumps(bad_rules), encoding="utf-8")
        with self.assertRaises(MissingDependencyError):
            self.repo.validate_all()

        # Cycle
        cyclic_rules = dict(self.rule_reg_data)
        cyclic_rules["rules"][0]["depends_on"] = ["RULE-2"]
        cyclic_rules["rules"][1]["depends_on"] = ["RULE-1"]
        (self.rules_dir / "registry.json").write_text(json.dumps(cyclic_rules), encoding="utf-8")
        with self.assertRaises(DependencyCycleError):
            self.repo.validate_all()

    # 3. Path escape rejection
    def test_path_escape_rejected(self):
        bad_guide = dict(self.guide_reg_data)
        bad_guide["guides"][0]["path"] = "../../../../escaped.md"
        (self.authoring / "guide-registry.json").write_text(json.dumps(bad_guide), encoding="utf-8")
        with self.assertRaises(GuideRepositoryError):
            self.repo.validate_all()

    # 4. Immutable release build, verification, and atomic rollback
    def test_release_build_verify_and_rollback(self):
        # Build rel_1
        rel_1 = self.repo.build_release(release_id="rel_1", activate=True)
        self.assertEqual(self.repo.get_active_release_id(), "rel_1")
        self.assertTrue(self.repo.verify_release("rel_1").bundle_sha256)

        # Build rel_2
        (self.rules_dir / "rule1.md").write_text("# Rule 1 modified\nUpdated.", encoding="utf-8")
        rel_2 = self.repo.build_release(release_id="rel_2", activate=True)
        self.assertEqual(self.repo.get_active_release_id(), "rel_2")
        self.assertNotEqual(rel_1.bundle_sha256, rel_2.bundle_sha256)

        # Rollback to rel_1
        self.repo.rollback("rel_1")
        self.assertEqual(self.repo.get_active_release_id(), "rel_1")

    # 5. Tampered release bundle integrity rejection
    def test_tampered_release_rejected(self):
        self.repo.build_release(release_id="rel_clean", activate=True)
        # Tamper with stored file
        tampered_file = self.repo.releases_dir / "rel_clean" / "rules" / "rule1.md"
        tampered_file.write_text("HACKED CONTENT", encoding="utf-8")

        with self.assertRaises(IntegrityError):
            self.repo.verify_release("rel_clean")

    # 6. Context Assembler: rule selection and legacy fallback
    def test_context_assembler_rule_selection(self):
        manifest = self.repo.build_release(release_id="rel_asm", activate=True)
        assembler = ContextAssembler(manifest)

        snapshot = {
            "brief": {"intent": ["explain"]},
            "facts": [{"id": "F1", "property": "fov", "claim_kinds": ["numeric_spec"]}],
            "entities": {"claim_kinds": ["numeric_spec"]},
            "legacy_claim_metadata": False
        }
        # RULE-1 (global required) and RULE-2 (claim_kinds intersects numeric_spec) should both be selected
        model_input, report = assembler.assemble_context("write", None, snapshot)
        selected_ids = {r["id"] for r in report.selected_rules}
        self.assertIn("RULE-1", selected_ids)
        self.assertIn("RULE-2", selected_ids)

        # Test omitting RULE-2 when claim_kinds does not match
        snapshot_no_num = {
            "brief": {"intent": ["explain"]},
            "facts": [{"id": "F1", "property": "color", "claim_kinds": ["color_spec"]}],
            "entities": {"claim_kinds": ["color_spec"]},
            "legacy_claim_metadata": False
        }
        _, report_no_num = assembler.assemble_context("write", None, snapshot_no_num)
        selected_ids_no_num = {r["id"] for r in report_no_num.selected_rules}
        self.assertIn("RULE-1", selected_ids_no_num)
        self.assertNotIn("RULE-2", selected_ids_no_num)

    # 7. Source locator mismatch detection without blind 2000 char truncation
    def test_source_locator_mismatch_detected(self):
        manifest = self.repo.build_release(release_id="rel_src", activate=True)
        assembler = ContextAssembler(manifest)

        snapshot = {
            "brief": {},
            "facts": [{
                "id": "F_LOC",
                "source": {"id": "S1", "locator": {"heading": "Nonexistent Section"}}
            }],
            "sources": {
                "S1": {"id": "S1", "body": "# Available Section\nSome content."}
            }
        }
        _, report = assembler.assemble_context("write", None, snapshot)
        missing_kinds = [m.get("kind") for m in report.missing_required]
        self.assertIn("source_locator_failed", missing_kinds)

    # 8. Review Report: Self-reported pass with unresolved issues or fact failures must evaluate to False via real pipeline method
    def test_review_report_blocks_falsely_passed_claims(self):
        pipeline = ContentPipeline(root=self.root)
        manifest = self.repo.build_release(release_id="rel_rev", activate=True)

        # Case A: Model reports passed=True, but has semantic issue
        feedback_with_issue = {
            "passed": True,
            "issues": [{"id": "ISS-1", "rule_id": "RULE-1", "detail": "규칙 위반"}]
        }
        cov, rep, _ = pipeline._generate_coverage_and_review_report(
            cid="CNT-TEST",
            run_id="run-1",
            revision=1,
            markdown="# 본문\n90도 화각 지원",
            claims=[{"id": "c1", "text": "90도 화각 지원", "fact_ids": ["F1"]}],
            feedback=feedback_with_issue,
            errors=[],
            official=None,
            admin_checks=[],
            guide_manifest=manifest,
            requirements={
                "RULE-1": {"id": "RULE-1", "kind": "rule"},
                "RULE-2": {"id": "RULE-2", "kind": "rule"},
                "F1": {"id": "F1", "kind": "fact"}
            },
            selected_rule_ids=["RULE-1"]
        )
        self.assertFalse(rep.passed, "ReviewReport MUST be False when semantic issue exists even if feedback.passed is True")
        self.assertFalse(cov.passed, "CoverageReport MUST be False when semantic issue exists")
        self.assertIn("RULE-1", cov.unresolved)

        # Case B: Unselected rule is marked not_applicable, not satisfied
        self.assertEqual(cov.requirements.get("RULE-2", {}).get("status"), "not_applicable")

        # Case C: Fact not cited in markdown remains unresolved
        cov2, rep2, _ = pipeline._generate_coverage_and_review_report(
            cid="CNT-TEST",
            run_id="run-2",
            revision=1,
            markdown="# 본문\n완전 다른 텍스트만 존재함",
            claims=[{"id": "c1", "text": "90도 화각 지원", "fact_ids": ["F1"]}],
            feedback={"passed": True, "issues": []},
            errors=[],
            official=None,
            admin_checks=[],
            guide_manifest=manifest,
            requirements={"RULE-1": {"id": "RULE-1", "kind": "rule"}, "F1": {"id": "F1", "kind": "fact"}},
            selected_rule_ids=["RULE-1"]
        )
        self.assertIn("F1", cov2.unresolved, "Uncited fact MUST remain unresolved")
        self.assertFalse(rep2.passed, "Review report MUST fail when fact is uncited")

        # Case D: Official contradiction marks review report as failed
        cov3, rep3, _ = pipeline._generate_coverage_and_review_report(
            cid="CNT-TEST",
            run_id="run-3",
            revision=1,
            markdown="# 본문\n90도 화각 지원",
            claims=[{"id": "c1", "text": "90도 화각 지원", "fact_ids": ["F1"]}],
            feedback={"passed": True, "issues": []},
            errors=[],
            official={"status": "REVIEWED", "claims": [{"id": "c1", "verdict": "contradicted", "evidence": "수치 왜곡"}]},
            admin_checks=[],
            guide_manifest=manifest,
            requirements={"RULE-1": {"id": "RULE-1", "kind": "rule"}, "F1": {"id": "F1", "kind": "fact"}},
            selected_rule_ids=["RULE-1"]
        )
        self.assertFalse(rep3.passed, "Official contradiction MUST cause review report to fail")
        self.assertIn("F1", cov3.unresolved)

    # 9. Prompt repository local consistency and Langfuse fallback
    def test_prompt_repository_local_and_adapter(self):
        local_repo = LocalPromptRepository(self.prompts_dir)
        content, h, src = local_repo.get_prompt("write")
        self.assertIn("Write instruction.", content)
        self.assertTrue(h)

        adapter = LangfusePromptAdapter(local_repo)
        c2, h2, src2 = adapter.get_prompt("write")
        self.assertEqual(content, c2)
        self.assertEqual(h, h2)

    # 10. Metadata tampering rejection (Issue 7)
    def test_tampered_manifest_metadata_rejected(self):
        manifest = self.repo.build_release(release_id="rel_meta", activate=True)
        manifest_path = self.repo.releases_dir / "rel_meta" / "manifest.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))

        # Tamper with rule metadata (required field)
        data["rules"]["RULE-1"]["required"] = False
        manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        with self.assertRaises(IntegrityError):
            self.repo.verify_release("rel_meta")

    # 11. Safety Core body loaded correctly without path traversal issues (Issue 4)
    def test_context_assembler_safety_core_body_loaded(self):
        manifest = self.repo.build_release(release_id="rel_core_test", activate=True)
        release_dir = self.repo.releases_dir / "rel_core_test"
        assembler = ContextAssembler(manifest, release_dir=release_dir)

        snapshot = {
            "brief": {"intent": ["explain"]},
            "facts": [],
            "entities": {}
        }
        model_input, report = assembler.assemble_context("write", None, snapshot)
        guides = model_input.get("guides", {})
        self.assertTrue(len(guides) > 0)
        self.assertIn("GUIDE-SAFETY", guides)
        self.assertIsNotNone(guides["GUIDE-SAFETY"])
        self.assertIn("Never invent facts.", guides["GUIDE-SAFETY"])

    # 12. Source locator heading missing rejected & multiple locators merged (Issue 5)
    def test_source_locator_heading_missing_rejected_and_merged(self):
        # A: Heading requested but source markdown has NO headings -> failure
        no_heading_text = "This document has no markdown headings at all."
        sec, ok = extract_source_sections(no_heading_text, ["Camera Specs"])
        self.assertFalse(ok)
        self.assertEqual(sec, "")

        # B: Multiple locators on same source merged
        doc_with_headings = (
            "# Camera Specs\nField of view: 90 degrees.\n"
            "# Audio Specs\nBeamforming mic array with 7m range.\n"
            "# Dimension\nWidth: 700mm\n"
        )
        manifest = self.repo.build_release(release_id="rel_multi_loc", activate=True)
        assembler = ContextAssembler(manifest, release_dir=self.repo.releases_dir / "rel_multi_loc")

        multi_loc_snapshot = {
            "brief": {},
            "facts": [
                {"id": "F1", "source": {"id": "S1", "locator": {"heading": "Camera Specs"}}},
                {"id": "F2", "source": {"id": "S1", "locator": {"heading": "Audio Specs"}}}
            ],
            "sources": {
                "S1": {"id": "S1", "body": doc_with_headings}
            }
        }
        model_input, report = assembler.assemble_context("write", None, multi_loc_snapshot)
        src_body = model_input["sources"]["S1"]["body"]
        self.assertIn("Field of view: 90 degrees.", src_body)
        self.assertIn("Beamforming mic array with 7m range.", src_body)
        self.assertNotIn("Width: 700mm", src_body)  # Dimension wasn't requested


    # 13. Pipeline actually sends assembled input and enforces budget (Issue 1 & 2)
    def test_pipeline_assembled_input_called_and_budget_enforced(self):
        class CapturingProvider:
            def __init__(self):
                self.calls = []
            def count_tokens(self, stage, instruction, context):
                return 1200
            def complete(self, stage, instruction, context):
                self.calls.append({"stage": stage, "instruction": instruction, "context": context})
                def response(value):
                    if 'block_plan' in context:
                        value['blocks'] = [{'id': b['id'], 'markdown': value['markdown'] if i == 0 else '본문 ' + str(i), 'claim_ids': [c['id'] for c in value['claims']] if i == 0 else []} for i, b in enumerate(context['block_plan'])]
                        value['markdown'] = '\n\n'.join(b['markdown'] for b in value['blocks'])
                    return json.dumps({'receipt': context['policy_receipt'], 'result': value})
                if stage == 'strategy':
                    return response({
                        'article_goal': 'goal', 'reader': {'questions': ['q']}, 'primary_playbook': 'p',
                        'must_cover': [], 'can_omit': [], 'avoid': [], 'technical_depth': {},
                        'opening': 'o', 'body': ['b'], 'closing': 'c', 'asset_needs': []
                    })
                elif stage == 'write':
                    return response({
                        'markdown': '# Draft\nField of view is 90.',
                        'claims': [{'id': 'c1', 'text': 'Field of view is 90.', 'fact_ids': ['F1']}],
                        'changes': [], 'used_asset_need_ids': [], 'unresolved_items': []
                    })
                return response({'passed': True, 'issues': [], 'missing_claims': []})
            def official(self, instruction, context):
                return json.dumps({'receipt': context['policy_receipt'], 'result': {'claims': [{'id': 'c1', 'verdict': 'confirmed', 'evidence': 'ok'}]}})

        # Set up working environment
        system = self.root / "content-system"
        guide_target = system / '00_system/templates/articles'
        guide_target.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(__file__).resolve().parents[1] / 'content-system/00_system/templates/articles/content-block-guides.json', guide_target / 'content-block-guides.json')
        atomic(system / "01_keyword_ai" / "briefs" / "CNT-TEST.brief.yaml", {
            "topic": "회의실", "search": {"primary_keyword": "회의실"}, "knowledge_packs": ["P1"]
        })
        atomic(system / "03_sources" / "knowledge" / "products" / "P1.yaml", {
            "knowledge_id": "P1", "scope": {"applies_to": ["DEVICE"]},
            "facts": [{"id": "F1", "value": 90, "property": "field_of_view", "source": {"id": "S1"}}]
        })
        atomic(system / "03_sources" / "INDEX.yaml", {
            "sources": [{"id": "S1", "status": "VALID", "path": "docs/spec.md"}]
        })
        atomic(system / "03_sources" / "docs" / "spec.md", "# Camera Specs\nField of view 90")

        # Activate release
        self.repo.build_release(release_id="rel_pipe_test", activate=True)

        provider = CapturingProvider()
        pipeline = ContentPipeline(root=self.root, provider=provider)
        res = pipeline.run("CNT-TEST", max_revisions=1)

        # Verify provider actually received assembled input
        self.assertTrue(len(provider.calls) > 0)
        write_call = next((c for c in provider.calls if c["stage"] == "write"), None)
        self.assertIsNotNone(write_call)
        sent_ctx = write_call["context"]
        self.assertIn("guides", sent_ctx)
        self.assertIn("rules", sent_ctx)
        self.assertIn("brief", sent_ctx)

        # Verify release prompt was used and recorded
        run_dir = pipeline.work("CNT-TEST") / "runs" / res["run_id"]
        prompt_record_path = run_dir / "prompts" / "r1.write.json"
        self.assertTrue(prompt_record_path.is_file())
        prompt_record = json.loads(prompt_record_path.read_text(encoding="utf-8"))
        self.assertEqual(prompt_record["prompt"]["release_id"], "rel_pipe_test")

        # Verify budget exceeded blocks provider call
        atomic(self.root / 'config/config.json', {'pipeline_input_token_budget': 10})
        res_exceeded = pipeline.run("CNT-TEST", max_revisions=1)
        self.assertEqual(res_exceeded["outcome"], "FAILED")
        ledger = json.loads((Path(res_exceeded['run_directory']) / 'rule-audit/strategy.json').read_text(encoding='utf-8'))
        self.assertEqual(ledger['dispatch_status'], 'blocked_token_budget')
