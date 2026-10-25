"""Guide repository for versioned policy loading, dependency resolution, immutable release bundles, and release management."""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from services.guide_contracts import (
    GuideContract,
    GuideRegistryContract,
    GuideReleaseManifest,
    RuleContract,
    RuleRegistryContract,
)


class GuideRepositoryError(Exception):
    """Base error for guide repository operations."""


class DependencyCycleError(GuideRepositoryError):
    """Raised when circular dependencies are detected."""


class MissingDependencyError(GuideRepositoryError):
    """Raised when an item depends on an unknown or inactive item."""


class IntegrityError(GuideRepositoryError):
    """Raised when file integrity or hash check fails."""


def digest_str(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def digest_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def contained(base: Path, relative: str | Path) -> Path:
    path = (base / relative).resolve()
    if not path.is_relative_to(base.resolve()):
        raise GuideRepositoryError(f"Path escapes its root: {relative}")
    return path


def get_code_revision(workspace_root: Path) -> str:
    """Return a deterministic hash of services/ and scripts/ code."""
    hasher = hashlib.sha256()
    for folder in ("services", "scripts"):
        dir_path = workspace_root / folder
        if dir_path.exists():
            for p in sorted(dir_path.glob("*.py")):
                hasher.update(p.name.encode("utf-8"))
                hasher.update(p.read_bytes())
    return hasher.hexdigest()[:16]


def canonical_json_hash(data: Dict[str, Any], ignore_keys: Optional[Set[str]] = None) -> str:
    """Return deterministic SHA256 of dictionary excluding transient hash fields."""
    ignore = ignore_keys or {'sha256', 'meta_sha256'}
    cleaned = {k: v for k, v in data.items() if k not in ignore}
    canonical = json.dumps(cleaned, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


class GuideRepository:
    def __init__(self, workspace_root: Optional[Path | str] = None):
        if workspace_root is None:
            workspace_root = Path(__file__).resolve().parent.parent
        self.root = Path(workspace_root).resolve()
        self.authoring_dir = self.root / "content-system" / "02_writer_ai" / "authoring"
        self.rules_dir = self.authoring_dir / "rules"
        self.prompts_dir = self.authoring_dir / "prompts"
        self.releases_dir = self.authoring_dir / "releases"
        self.active_pointer_file = self.releases_dir / "active_release.json"

    def compute_bundle_hash(
        self,
        release_id: str,
        rules: Dict[str, Dict[str, Any]],
        guides: Dict[str, Dict[str, Any]],
        prompts: Dict[str, Dict[str, Any]],
        dependencies: Dict[str, List[str]],
        code_rev: str,
    ) -> str:
        hasher = hashlib.sha256()
        hasher.update(release_id.encode('utf-8'))
        hasher.update(code_rev.encode('utf-8'))
        for k in sorted(rules.keys()):
            hasher.update(k.encode('utf-8'))
            hasher.update(rules[k].get('sha256', '').encode('utf-8'))
            hasher.update(rules[k].get('meta_sha256', '').encode('utf-8'))
        for k in sorted(guides.keys()):
            hasher.update(k.encode('utf-8'))
            hasher.update(guides[k].get('sha256', '').encode('utf-8'))
            hasher.update(guides[k].get('meta_sha256', '').encode('utf-8'))
        for k in sorted(prompts.keys()):
            hasher.update(k.encode('utf-8'))
            hasher.update(prompts[k].get('sha256', '').encode('utf-8'))
        dep_str = json.dumps(dependencies, sort_keys=True, separators=(',', ':'))
        hasher.update(dep_str.encode('utf-8'))
        return hasher.hexdigest()

    def load_rule_registry(self) -> RuleRegistryContract:
        reg_file = self.rules_dir / "registry.json"
        if not reg_file.is_file():
            raise GuideRepositoryError(f"Rules registry not found: {reg_file}")
        data = json.loads(reg_file.read_text(encoding="utf-8-sig"))
        return RuleRegistryContract.model_validate(data)

    def load_guide_registry(self) -> GuideRegistryContract:
        guide_file = self.authoring_dir / "guide-registry.json"
        if not guide_file.is_file():
            raise GuideRepositoryError(f"Guide registry not found: {guide_file}")
        data = json.loads(guide_file.read_text(encoding="utf-8-sig"))
        return GuideRegistryContract.model_validate(data)

    def get_rule_body(self, rule: RuleContract) -> Tuple[str, str]:
        path = contained(self.rules_dir, rule.path)
        if not path.is_file():
            raise GuideRepositoryError(f"Rule file missing: {rule.path} for {rule.id}")
        content = path.read_text(encoding="utf-8-sig")
        return content, digest_str(content)

    def get_guide_body(self, guide: GuideContract) -> Tuple[str, str]:
        # Guide paths can be relative to authoring_dir or writer_ai root
        candidate = (self.authoring_dir / guide.path).resolve()
        writer_root = (self.authoring_dir.parent).resolve()
        if not candidate.is_relative_to(writer_root):
            raise GuideRepositoryError(f"Path escapes its root: {guide.path}")
        if not candidate.is_file():
            raise GuideRepositoryError(f"Guide file missing: {guide.path} for {guide.id}")
        content = candidate.read_text(encoding="utf-8-sig")
        return content, digest_str(content)

    def validate_all(self) -> Dict[str, Any]:
        """Perform comprehensive validation of registries, files, dependencies, cycles, and contracts."""
        rule_reg = self.load_rule_registry()
        guide_reg = self.load_guide_registry()

        rule_map: Dict[str, RuleContract] = {r.id: r for r in rule_reg.rules}
        guide_map: Dict[str, GuideContract] = {g.id: g for g in guide_reg.guides}

        # 1. Check rule file existence and body hashes
        for r in rule_reg.rules:
            self.get_rule_body(r)

        # 2. Check guide file existence and body hashes
        for g in guide_reg.guides:
            self.get_guide_body(g)

        # 3. Check prompt files
        prompts = list(self.prompts_dir.glob("*.md"))
        if not prompts:
            raise GuideRepositoryError(f"No prompt files found in {self.prompts_dir}")

        # 4. Dependency & reference validity
        for r in rule_reg.rules:
            for dep in r.depends_on:
                if dep not in rule_map:
                    raise MissingDependencyError(f"Rule {r.id} depends on missing rule: {dep}")
                if rule_map[dep].status != "active" and r.status == "active":
                    raise MissingDependencyError(f"Active rule {r.id} depends on non-active rule: {dep}")

        for g in guide_reg.guides:
            for dep in g.depends_on:
                if dep not in guide_map and dep not in rule_map:
                    raise MissingDependencyError(f"Guide {g.id} depends on missing item: {dep}")
            for ref in g.references_rule_ids:
                if ref not in rule_map:
                    raise MissingDependencyError(f"Guide {g.id} references missing rule: {ref}")
                if rule_map[ref].status != "active" and g.status == "active":
                    raise MissingDependencyError(f"Active guide {g.id} references non-active rule: {ref}")

        # 5. Cycle detection
        adj: Dict[str, List[str]] = {}
        for r in rule_reg.rules:
            adj[r.id] = list(r.depends_on)
        for g in guide_reg.guides:
            adj[g.id] = list(g.depends_on) + list(g.references_rule_ids)

        visited: Dict[str, int] = {}  # 0: visiting, 1: visited

        def dfs(node: str, path: List[str]):
            visited[node] = 0
            for neighbor in adj.get(node, []):
                if visited.get(neighbor) == 0:
                    cycle = path + [neighbor]
                    raise DependencyCycleError(f"Circular dependency detected: {' -> '.join(cycle)}")
                if neighbor not in visited:
                    dfs(neighbor, path + [neighbor])
            visited[node] = 1

        for node in adj:
            if node not in visited:
                dfs(node, [node])

        return {
            "valid": True,
            "rules_count": len(rule_reg.rules),
            "guides_count": len(guide_reg.guides),
            "prompts_count": len(prompts),
        }

    def resolve_closure(self, initial_ids: List[str]) -> List[str]:
        """Return the complete dependency closure (topologically ordered, unique)."""
        rule_reg = self.load_rule_registry()
        guide_reg = self.load_guide_registry()
        rule_map = {r.id: r for r in rule_reg.rules}
        guide_map = {g.id: g for g in guide_reg.guides}

        closure: List[str] = []
        visited: Set[str] = set()

        def collect(item_id: str):
            if item_id in visited:
                return
            visited.add(item_id)
            deps = []
            if item_id in rule_map:
                deps.extend(rule_map[item_id].depends_on)
                deps.extend(rule_map[item_id].references_rule_ids)
            elif item_id in guide_map:
                deps.extend(guide_map[item_id].depends_on)
                deps.extend(guide_map[item_id].references_rule_ids)
            for d in deps:
                collect(d)
            closure.append(item_id)

        for iid in initial_ids:
            collect(iid)

        return closure

    def build_release(
        self,
        release_id: Optional[str] = None,
        activate: bool = False,
        eval_report_ref: Optional[str] = None,
    ) -> GuideReleaseManifest:
        """Create an immutable policy release bundle with atomic guarantee and hash integrity."""
        # 1. Pre-validation
        self.validate_all()

        if not release_id:
            now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
            release_id = f"rel_{now_str}"

        target_release_dir = self.releases_dir / release_id
        if target_release_dir.exists():
            raise GuideRepositoryError(f"Release already exists: {release_id}")

        # Compute pre-build snapshot hashes to guard against file mutations during build
        rule_reg = self.load_rule_registry()
        guide_reg = self.load_guide_registry()

        initial_hashes: Dict[str, str] = {}
        for r in rule_reg.rules:
            _, h = self.get_rule_body(r)
            initial_hashes[f"rule:{r.id}"] = h
        for g in guide_reg.guides:
            _, h = self.get_guide_body(g)
            initial_hashes[f"guide:{g.id}"] = h
        for p in self.prompts_dir.glob("*.md"):
            initial_hashes[f"prompt:{p.name}"] = digest_str(p.read_text(encoding="utf-8-sig"))

        # Build in a temporary directory
        temp_dir = Path(tempfile.mkdtemp(prefix="guide_rel_build_", dir=str(self.releases_dir.parent)))
        try:
            rel_rules_dir = temp_dir / "rules"
            rel_guides_dir = temp_dir / "guides"
            rel_prompts_dir = temp_dir / "prompts"
            rel_rules_dir.mkdir(parents=True, exist_ok=True)
            rel_guides_dir.mkdir(parents=True, exist_ok=True)
            rel_prompts_dir.mkdir(parents=True, exist_ok=True)

            manifest_rules: Dict[str, Dict[str, Any]] = {}
            for r in rule_reg.rules:
                body, h = self.get_rule_body(r)
                if initial_hashes[f"rule:{r.id}"] != h:
                    raise IntegrityError(f"Rule file {r.id} modified during build")
                filename = Path(r.path).name
                target_file = rel_rules_dir / filename
                target_file.write_text(body, encoding="utf-8-sig")
                r_dict = r.model_dump()
                r_dict["sha256"] = h
                r_dict["filename"] = filename
                r_dict["meta_sha256"] = canonical_json_hash(r_dict)
                manifest_rules[r.id] = r_dict

            manifest_guides: Dict[str, Dict[str, Any]] = {}
            for g in guide_reg.guides:
                body, h = self.get_guide_body(g)
                if initial_hashes[f"guide:{g.id}"] != h:
                    raise IntegrityError(f"Guide file {g.id} modified during build")
                filename = Path(g.path).name
                target_file = rel_guides_dir / filename
                target_file.write_text(body, encoding="utf-8-sig")
                g_dict = g.model_dump()
                g_dict["sha256"] = h
                g_dict["filename"] = filename
                g_dict["meta_sha256"] = canonical_json_hash(g_dict)
                manifest_guides[g.id] = g_dict

            manifest_prompts: Dict[str, Dict[str, Any]] = {}
            for p in self.prompts_dir.glob("*.md"):
                content = p.read_text(encoding="utf-8-sig")
                h = digest_str(content)
                if initial_hashes[f"prompt:{p.name}"] != h:
                    raise IntegrityError(f"Prompt file {p.name} modified during build")
                target_file = rel_prompts_dir / p.name
                target_file.write_text(content, encoding="utf-8-sig")
                manifest_prompts[p.name] = {
                    "name": p.name,
                    "sha256": h,
                    "path": f"prompts/{p.name}",
                }

            # Dependencies map
            dependencies: Dict[str, List[str]] = {}
            for r in rule_reg.rules:
                dependencies[r.id] = list(r.depends_on)
            for g in guide_reg.guides:
                dependencies[g.id] = list(g.depends_on) + list(g.references_rule_ids)

            code_rev = get_code_revision(self.root)
            bundle_sha256 = self.compute_bundle_hash(
                release_id=release_id,
                rules=manifest_rules,
                guides=manifest_guides,
                prompts=manifest_prompts,
                dependencies=dependencies,
                code_rev=code_rev,
            )

            manifest = GuideReleaseManifest(
                release_id=release_id,
                created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                schema_version="1.0.0",
                bundle_sha256=bundle_sha256,
                code_revision=code_rev,
                guides=manifest_guides,
                rules=manifest_rules,
                prompts=manifest_prompts,
                dependencies=dependencies,
                eval_report_ref=eval_report_ref,
            )

            manifest_file = temp_dir / "manifest.json"
            manifest_file.write_text(
                manifest.model_dump_json(indent=2),
                encoding="utf-8-sig",
            )

            # Move temp directory to target release directory
            self.releases_dir.mkdir(parents=True, exist_ok=True)
            temp_dir.rename(target_release_dir)
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

        if activate:
            self.activate_release(release_id)

        return manifest

    def verify_release(self, release_id: str) -> GuideReleaseManifest:
        """Verify the integrity of a stored release bundle including metadata, files, and bundle hash."""
        rel_dir = self.releases_dir / release_id
        if not rel_dir.is_dir():
            raise GuideRepositoryError(f"Release directory does not exist: {release_id}")

        manifest_file = rel_dir / "manifest.json"
        if not manifest_file.is_file():
            raise IntegrityError(f"Missing manifest.json in release: {release_id}")

        manifest_data = json.loads(manifest_file.read_text(encoding="utf-8-sig"))
        manifest = GuideReleaseManifest.model_validate(manifest_data)

        # 1. Check rules (both content hash and metadata hash)
        for rid, rdata in manifest.rules.items():
            fname = rdata.get("filename") or Path(rdata["path"]).name
            rule_file = rel_dir / "rules" / fname
            if not rule_file.is_file():
                raise IntegrityError(f"Missing rule file in release {release_id}: {rule_file.name}")
            actual_h = digest_str(rule_file.read_text(encoding="utf-8-sig"))
            if actual_h != rdata["sha256"]:
                raise IntegrityError(f"Hash mismatch for rule {rid} in release {release_id}")
            # Verify rule metadata integrity
            expected_meta_h = rdata.get("meta_sha256")
            if expected_meta_h and canonical_json_hash(rdata) != expected_meta_h:
                raise IntegrityError(f"Metadata tampering detected in rule {rid} of release {release_id}")

        # 2. Check guides (both content hash and metadata hash)
        for gid, gdata in manifest.guides.items():
            fname = gdata.get("filename") or Path(gdata["path"]).name
            guide_file = rel_dir / "guides" / fname
            if not guide_file.is_file():
                raise IntegrityError(f"Missing guide file in release {release_id}: {guide_file.name}")
            actual_h = digest_str(guide_file.read_text(encoding="utf-8-sig"))
            if actual_h != gdata["sha256"]:
                raise IntegrityError(f"Hash mismatch for guide {gid} in release {release_id}")
            # Verify guide metadata integrity
            expected_meta_h = gdata.get("meta_sha256")
            if expected_meta_h and canonical_json_hash(gdata) != expected_meta_h:
                raise IntegrityError(f"Metadata tampering detected in guide {gid} of release {release_id}")

        # 3. Check prompts
        for pname, pdata in manifest.prompts.items():
            prompt_file = rel_dir / "prompts" / pname
            if not prompt_file.is_file():
                raise IntegrityError(f"Missing prompt file in release {release_id}: {pname}")
            actual_h = digest_str(prompt_file.read_text(encoding="utf-8-sig"))
            if actual_h != pdata["sha256"]:
                raise IntegrityError(f"Hash mismatch for prompt {pname} in release {release_id}")

        # 4. Check overall bundle SHA256 integrity
        expected_bundle = self.compute_bundle_hash(
            release_id=manifest.release_id,
            rules=manifest.rules,
            guides=manifest.guides,
            prompts=manifest.prompts,
            dependencies=manifest.dependencies,
            code_rev=manifest.code_revision,
        )
        if expected_bundle != manifest.bundle_sha256:
            raise IntegrityError(f"Bundle hash mismatch in release {release_id}: manifest has {manifest.bundle_sha256} but computed {expected_bundle}")

        return manifest

    def activate_release(self, release_id: str) -> None:
        """Atomically update the active release pointer to release_id after verification."""
        manifest = self.verify_release(release_id)

        pointer_data = {
            "active_release_id": release_id,
            "bundle_sha256": manifest.bundle_sha256,
            "activated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "code_revision": manifest.code_revision,
        }

        self.releases_dir.mkdir(parents=True, exist_ok=True)
        temp_pointer = self.releases_dir / f"pointer_temp_{os.getpid()}.json"
        temp_pointer.write_text(json.dumps(pointer_data, indent=2), encoding="utf-8")
        temp_pointer.replace(self.active_pointer_file)

    def get_active_release_id(self) -> Optional[str]:
        if not self.active_pointer_file.is_file():
            return None
        data = json.loads(self.active_pointer_file.read_text(encoding="utf-8"))
        return data.get("active_release_id")

    def load_active_release(self) -> GuideReleaseManifest:
        active_id = self.get_active_release_id()
        if not active_id:
            raise GuideRepositoryError("No active guide release is currently set.")
        return self.verify_release(active_id)

    def load_bundle_for_run(self, release_id: Optional[str] = None) -> Tuple[GuideReleaseManifest, Path]:
        """Return the manifest and directory path for the designated release (or active if None)."""
        if not release_id:
            release_id = self.get_active_release_id()
            if not release_id:
                # If no release is active yet, automatically build and activate an initial one
                self.build_release(release_id="rel_v3_initial", activate=True)
                release_id = "rel_v3_initial"

        manifest = self.verify_release(release_id)
        release_dir = self.releases_dir / release_id
        return manifest, release_dir

    def rollback(self, target_release_id: str) -> None:
        """Rollback active pointer to a verified previous release."""
        self.verify_release(target_release_id)
        self.activate_release(target_release_id)
