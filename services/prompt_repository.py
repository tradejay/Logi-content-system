"""Prompt repository interface providing local immutable release prompts with optional Langfuse fallback."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def digest_str(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class PromptRepository:
    def get_prompt(self, name: str) -> Tuple[str, str, str]:
        """Return (content, sha256_hash, source_info)."""
        raise NotImplementedError


class LocalPromptRepository(PromptRepository):
    def __init__(self, prompts_dir: Path | str, release_manifest: Optional[Any] = None):
        self.prompts_dir = Path(prompts_dir).resolve()
        self.manifest = release_manifest

    def get_prompt(self, name: str) -> Tuple[str, str, str]:
        filename = f"{name}.md" if not name.endswith(".md") else name
        target_file = self.prompts_dir / filename
        if not target_file.is_file():
            raise FileNotFoundError(f"Prompt file not found: {target_file}")
        content = target_file.read_text(encoding="utf-8-sig")
        h = digest_str(content)

        source_info = f"local_bundle:{self.prompts_dir.name}"
        if self.manifest and filename in self.manifest.prompts:
            expected_h = self.manifest.prompts[filename]["sha256"]
            if expected_h != h:
                raise ValueError(f"Prompt integrity failed for {filename} (expected {expected_h}, got {h})")
            source_info = f"release:{self.manifest.release_id}"

        return content, h, source_info


class LangfusePromptAdapter(PromptRepository):
    """Optional Langfuse adapter. Disabled by default unless LANGFUSE_ENABLED is explicitly true."""

    def __init__(self, local_fallback: PromptRepository):
        self.local_repo = local_fallback
        self.enabled = os.environ.get("LANGFUSE_ENABLED", "false").lower() in ("true", "1", "yes")
        self.client = None
        if self.enabled:
            try:
                import langfuse
                self.client = langfuse.Langfuse()
            except Exception as e:
                # If Langfuse library or connection fails, cleanly remain disabled
                self.enabled = False
                self.client = None

    def get_prompt(self, name: str) -> Tuple[str, str, str]:
        if not self.enabled or not self.client:
            return self.local_repo.get_prompt(name)

        try:
            # Langfuse remote prompt lookup attempt
            prompt_obj = self.client.get_prompt(name)
            content = prompt_obj.prompt
            h = digest_str(content)
            version = str(getattr(prompt_obj, "version", "latest"))
            return content, h, f"langfuse:v{version}"
        except Exception:
            # Safe local fallback on any remote issue
            content, h, src = self.local_repo.get_prompt(name)
            return content, h, f"local_fallback_from_langfuse_err({src})"
