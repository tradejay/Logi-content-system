"""Modular context assembler for section and stage level AI inputs with policy and fact validation."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from services.guide_contracts import (
    GuideReleaseManifest,
    SectionPlan,
    SelectionReport,
)

# Heading pattern for source sections
_HEADING_RE = re.compile(r'^(#{1,6})\s+(.+?)(?:\s*#*\s*)?$')

# Maximum character budget per stage before raising budget conflict
STAGE_CHAR_BUDGETS = {
    "strategy": 60000,
    "write": 60000,
    "section": 35000,
    "feedback": 60000,
    "official": 30000,
}


def pick(value: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
    return {k: value[k] for k in fields if k in value and value[k] not in (None, "", [], {})}


def extract_source_sections(body: str, headings: Set[str]) -> Tuple[str, bool]:
    """Extract markdown sections matching headings.
    Returns (extracted_body, locator_matched).
    If headings were provided but none matched, locator_matched is False and returns excerpt with flag.
    """
    if not headings:
        return body, True

    lines = body.split("\n")
    entries: List[Tuple[int, int, str]] = []  # line_idx, level, title
    for i, line in enumerate(lines):
        m = _HEADING_RE.match(line.strip())
        if m:
            entries.append((i, len(m.group(1)), m.group(2).strip()))

    if not entries:
        # Headings were requested but source body contains no markdown headings at all
        return "", False

    ranges: List[Tuple[int, int]] = []
    for idx, (li, level, title) in enumerate(entries):
        if any(h.lower() in title.lower() or title.lower() in h.lower() for h in headings):
            end = len(lines)
            for ni in range(idx + 1, len(entries)):
                if entries[ni][1] <= level:
                    end = entries[ni][0]
                    break
            ranges.append((li, end))

    if not ranges:
        # Locator match failed: Do NOT silently pass full body or simple 2000 char truncation as valid
        return "", False

    ranges.sort()
    merged = [ranges[0]]
    for s, e in ranges[1:]:
        if s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    result = "\n\n---\n\n".join("\n".join(lines[s:e]).strip() for s, e in merged)
    return result, True


class ContextAssembler:
    def __init__(self, manifest: GuideReleaseManifest, release_dir: Optional[Any] = None):
        self.manifest = manifest
        self.release_dir = release_dir

    def assemble_context(
        self,
        stage: str,
        section_plan: Optional[SectionPlan | Dict[str, Any]],
        run_snapshot: Dict[str, Any],
        call_id: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], SelectionReport]:
        """Assemble deterministic, immutable, and stage/section-specific context.

        Returns (model_input, selection_report).
        """
        if isinstance(section_plan, dict):
            sec_plan = SectionPlan.model_validate(section_plan)
        elif section_plan is not None:
            sec_plan = section_plan
        else:
            sec_plan = None

        section_id = sec_plan.section_id if sec_plan else None
        report = SelectionReport(stage=stage, section_id=section_id, call_id=call_id)

        from services.context_optimization import apply_fact_policy, optimize_context
        run_snapshot, report.fact_policy = apply_fact_policy(run_snapshot)

        # 1. Normalize entities & search criteria
        brief = run_snapshot.get("brief", {})
        all_facts = run_snapshot.get("facts", [])
        all_sources = run_snapshot.get("sources", {})
        entities = run_snapshot.get("entities", {})

        target_product_ids = set(entities.get("product_ids", []))
        target_claim_kinds = set(entities.get("claim_kinds", []))
        target_intents = set(entities.get("intents", []))
        if brief.get("intent"):
            intent = brief['intent']
            target_intents.update([intent] if isinstance(intent, str) else intent)

        # 2. Section fact filtering (if section_plan provides required_facts)
        if sec_plan and sec_plan.required_facts:
            req_fact_ids = set(sec_plan.required_facts)
            selected_facts = [f for f in all_facts if f.get("id") in req_fact_ids]
            omitted_facts = [f for f in all_facts if f.get("id") not in req_fact_ids]
            # Check for missing required facts
            existing_ids = {f.get("id") for f in selected_facts}
            missing_ids = req_fact_ids - existing_ids
            for mid in missing_ids:
                report.missing_required.append({
                    "kind": "missing_required_fact",
                    "id": mid,
                    "section_id": section_id,
                })
        else:
            selected_facts = list(all_facts)
            omitted_facts = []

        report.selected_facts = [
            {"id": f.get("id"), "property": f.get("canonical_property") or f.get("property")}
            for f in selected_facts
        ]
        report.omitted_facts = [
            {"id": f.get("id"), "property": f.get("canonical_property") or f.get("property")}
            for f in omitted_facts
        ]

        # Update claim_kinds and products based on selected facts
        for f in selected_facts:
            target_claim_kinds.update(f.get("claim_kinds", []))

        # Check legacy mode: if any fact has no claim_kinds, keep legacy protection
        legacy_mode = run_snapshot.get("legacy_claim_metadata", False) or any(
            not bool(f.get("claim_kinds")) for f in selected_facts
        )

        # 3. Rule Selection
        # Gather all rules from release manifest
        rules_dict = self.manifest.rules
        selected_rules: Dict[str, Dict[str, Any]] = {}
        omitted_rules: Dict[str, Dict[str, Any]] = {}

        explicit_caution_ids = set()
        for f in selected_facts:
            explicit_caution_ids.update(f.get("caution_rule_ids", []))
        if sec_plan and sec_plan.assigned_rules:
            explicit_caution_ids.update(sec_plan.assigned_rules)

        for rid, rdata in rules_dict.items():
            if rdata.get("status") != "active":
                continue

            # Stage filter
            rule_stages = rdata.get("stages", ["strategy", "write", "feedback", "official"])
            if stage not in rule_stages and "all" not in rule_stages:
                omitted_rules[rid] = {"reason": f"Stage mismatch ({stage} not in {rule_stages})"}
                continue

            match_spec = rdata.get("match", {})
            all_conds = match_spec.get("all", [])
            any_conds = match_spec.get("any", [])

            # Universal / Global Required Rules (empty match)
            if not all_conds and not any_conds:
                if rdata.get("required", False):
                    selected_rules[rid] = rdata
                    report.reasons.append(f"Rule {rid} selected as global required rule")
                    continue

            # Explicitly assigned/referenced
            if rid in explicit_caution_ids:
                selected_rules[rid] = rdata
                report.reasons.append(f"Rule {rid} selected by explicit fact/section assignment")
                continue

            # Legacy fallback: load broad rule kinds
            if legacy_mode:
                # If rule matches claim_kinds, match it
                has_claim_kind_cond = any(
                    c.get("field") == "claim_kinds" for c in all_conds + any_conds
                )
                if has_claim_kind_cond:
                    selected_rules[rid] = rdata
                    report.reasons.append(f"Rule {rid} selected via legacy broad claim kind match")
                    continue

            # Condition matching
            def match_cond(c: Dict[str, Any]) -> bool:
                field = c.get("field")
                vals = set(c.get("values", []))
                if field == "claim_kinds":
                    return bool(target_claim_kinds & vals)
                if field == "product_ids":
                    return bool(target_product_ids & vals)
                if field == "intents":
                    return bool(target_intents & vals)
                return False

            all_passed = all(match_cond(c) for c in all_conds)
            any_passed = not any_conds or any(match_cond(c) for c in any_conds)

            if all_passed and any_passed:
                selected_rules[rid] = rdata
                report.reasons.append(f"Rule {rid} selected via condition match")
            else:
                omitted_rules[rid] = {"reason": "Match condition not met"}

        # Resolve dependency closure for selected rules
        to_resolve = list(selected_rules.keys())
        visited_deps = set(to_resolve)
        while to_resolve:
            curr_id = to_resolve.pop(0)
            deps = self.manifest.dependencies.get(curr_id, [])
            for dep in deps:
                if dep in rules_dict and dep not in visited_deps:
                    visited_deps.add(dep)
                    selected_rules[dep] = rules_dict[dep]
                    to_resolve.append(dep)
                    report.reasons.append(f"Rule {dep} added via dependency closure from {curr_id}")

        report.selected_rules = [
            {"id": rid, "severity": r.get("severity"), "path": r.get("path")}
            for rid, r in sorted(selected_rules.items())
        ]
        report.omitted_rules = [
            {"id": rid, "reason": data.get("reason")}
            for rid, data in sorted(omitted_rules.items())
            if rid not in selected_rules
        ]

        # 4. Guide Selection (modules, style, core)
        selected_guides: Dict[str, Dict[str, Any]] = {}
        chosen_blocks = (run_snapshot.get('strategy') or {}).get('content_blocks') or brief.get('content_blocks') or []
        elements = {role for block in chosen_blocks for role in (block.get('roles') or [block.get('role')]) if role}
        if sec_plan and sec_plan.elements:
            elements = set(sec_plan.elements)
        for gid, gdata in self.manifest.guides.items():
            if gdata.get("status") != "active":
                continue
            g_stages = gdata.get("stages", [])
            # Stage match or global core
            if stage in g_stages or (gdata.get("kind") == "core" and stage in ("write", "feedback")):
                # Only explicit approved scope can exclude a document. Unknown
                # scope / core / dependency stays broad; no keyword inference.
                scope = set(gdata.get('applies_to_elements') or [])
                dependency_ids = {dep for deps in self.manifest.dependencies.values() for dep in deps}
                if scope and elements and gdata.get('kind') != 'core' and gid not in dependency_ids and not scope.intersection(elements):
                    continue
                selected_guides[gid] = gdata

        # A selected guide's explicit rule dependencies remain mandatory even
        # when a narrow element scope would otherwise omit their match kind.
        pending = [dep for gid in selected_guides for dep in self.manifest.dependencies.get(gid, [])]
        visited = set(selected_rules)
        while pending:
            rid = pending.pop()
            if rid in visited:
                continue
            visited.add(rid)
            if rid in rules_dict:
                selected_rules[rid] = rules_dict[rid]
                pending.extend(self.manifest.dependencies.get(rid, []))
                report.reasons.append(f'Rule {rid} selected by guide dependency')
        report.selected_rules = [{"id": rid, "severity": r.get('severity'), "path": r.get('path')}
                                 for rid, r in sorted(selected_rules.items())]
        report.omitted_rules = [r for r in report.omitted_rules if r['id'] not in selected_rules]

        # 5. Scoped Sources Extraction with Merged Locator Verification
        scoped_sources: Dict[str, Dict[str, Any]] = {}
        locators_by_source: Dict[str, List[Dict[str, Any]]] = {}
        for fact in selected_facts:
            src = fact.get("source", {})
            if isinstance(src, dict):
                sid = src.get("id") or src.get("source_id")
                loc = src.get("locator")
                if sid and loc:
                    locators_by_source.setdefault(sid, []).append((fact.get("id"), loc))

        for sid, source_entry in all_sources.items():
            loc_list = locators_by_source.get(sid, [])
            headings = set()
            for fid, loc in loc_list:
                for k in ("heading", "section"):
                    if loc.get(k):
                        headings.add(loc[k])

            body = source_entry.get("body", "")
            extracted_body, locator_matched = extract_source_sections(body, headings)

            if headings and not locator_matched:
                for fid, loc in loc_list:
                    report.missing_required.append({
                        "kind": "source_locator_failed",
                        "fact_id": fid,
                        "source_id": sid,
                        "locator": loc,
                        "detail": f"출처 절/표를 특정하지 못했습니다 (locator: {loc})",
                    })
                extracted_body = f"[근거 위치 검색 불일치: {list(headings)}]\n" + body[:1000]

            meta = pick(source_entry, ["id", "title", "type", "vendor", "evidence_level", "status", "url", "source_url"])
            meta["body"] = extracted_body
            meta["locator_matched"] = locator_matched
            scoped_sources[sid] = meta

        # 6. Format Model Input Body
        # Load rule bodies and guide bodies from release bundle
        rules_payload = []
        for rid in sorted(selected_rules.keys()):
            rinfo = selected_rules[rid]
            body = rinfo.get("body", "")
            if not body and self.release_dir:
                fname = rinfo.get("filename") or Path(rinfo.get("path", "")).name
                rule_path = self.release_dir / "rules" / fname
                if rule_path.is_file():
                    body = rule_path.read_text(encoding="utf-8-sig")
            rules_payload.append({
                "id": rid,
                "severity": rinfo.get("severity", "blocking"),
                "body": body,
            })

        guides_payload = {}
        for gid in sorted(selected_guides.keys()):
            ginfo = selected_guides[gid]
            body = ginfo.get("body", "")
            if not body and self.release_dir:
                fname = ginfo.get("filename") or Path(ginfo.get("path", "")).name
                guide_path = self.release_dir / "guides" / fname
                if guide_path.is_file():
                    body = guide_path.read_text(encoding="utf-8-sig")
            guides_payload[gid] = body

        # Construct stage-specific model input
        model_input: Dict[str, Any] = {
            "stage": stage,
            "brief": pick(brief, [
                "topic", "one_line_purpose", "audience", "search", "intent",
                "funnel_stage", "questions", "questions3", "product_bridge", "cta", "sections", "content_blocks",
            ]),
            "facts": selected_facts,
            "rules": rules_payload,
            "cautions": rules_payload,
            "guides": guides_payload,
            "sources": scoped_sources,
        }
        if run_snapshot.get('fact_policy'):
            model_input['fact_policy'] = run_snapshot['fact_policy']

        if stage in ('strategy', 'write', 'feedback') and run_snapshot.get('planning_references'):
            model_input['planning_references'] = run_snapshot['planning_references']
        if stage in ('strategy', 'write', 'feedback') and run_snapshot.get('web_evidence'):
            model_input['web_evidence'] = run_snapshot['web_evidence']
            if stage in ('strategy', 'feedback'):
                model_input['web_evidence_decisions'] = run_snapshot.get('web_evidence_decisions', [])

        if sec_plan:
            model_input["section_plan"] = sec_plan.model_dump()
            if sec_plan.connection_memo:
                model_input["connection_memo"] = sec_plan.connection_memo

        if stage == "strategy":
            model_input["playbooks"] = run_snapshot.get("playbooks", {})
            model_input["assets"] = run_snapshot.get("assets", [])
            model_input["gap"] = run_snapshot.get("gap", {})
            if run_snapshot.get("user_feedback"):
                model_input["user_feedback"] = run_snapshot["user_feedback"]
        elif stage in ("write", "feedback"):
            if run_snapshot.get("product_links"):
                model_input["product_links"] = run_snapshot["product_links"]
            if run_snapshot.get("strategy"):
                model_input["strategy"] = run_snapshot["strategy"]
            if run_snapshot.get("asset_plan"):
                model_input["asset_plan"] = run_snapshot["asset_plan"]
            if run_snapshot.get("previous_draft"):
                model_input["previous_draft"] = run_snapshot["previous_draft"]
            for field in ('official_feedback', 'official_raw'):
                if run_snapshot.get(field):
                    model_input[field] = run_snapshot[field]
            if run_snapshot.get("draft"):
                model_input["draft"] = run_snapshot["draft"]
                if run_snapshot['draft'].get('_block_errors'):
                    model_input['block_contract_errors'] = run_snapshot['draft']['_block_errors']
            if run_snapshot.get("feedback") and run_snapshot['feedback'] != {'user_feedback': run_snapshot.get('user_feedback')}:
                model_input["feedback"] = run_snapshot["feedback"]
            if run_snapshot.get("user_feedback"):
                model_input["user_feedback"] = run_snapshot["user_feedback"]
        elif stage == "official":
            model_input["claims"] = run_snapshot.get("claims", [])

        model_input, report.optimization = optimize_context(stage, model_input)
        report.server_guides = report.optimization['server_guides']
        report.selected_guides = [{'id': gid} for gid in model_input.get('guides', {})]

        # 7. Check Character Budget and Conflicts
        raw_json = json.dumps(model_input, ensure_ascii=False, default=str)
        char_count = len(raw_json)
        estimated_tokens = char_count // 3  # Approximate Korean/English mix
        report.char_count = char_count
        report.estimated_tokens = estimated_tokens

        max_budget = STAGE_CHAR_BUDGETS.get(stage, 40000)
        report.budget_status = {
            "char_count": char_count,
            "max_budget": max_budget,
            "within_budget": char_count <= max_budget,
        }

        if char_count > max_budget:
            report.conflicts.append({
                "kind": "budget_exceeded",
                "char_count": char_count,
                "max_budget": max_budget,
                "detail": f"입력 크기({char_count}자)가 단계 예산({max_budget}자)을 초과했습니다.",
            })

        return model_input, report
