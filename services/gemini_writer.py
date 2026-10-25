"""Compatibility entry point; orchestration lives in content_pipeline.py."""
import sys
from pathlib import Path
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.content_pipeline import ContentPipeline, main

def generate_draft(content_id, max_retries=3):
    result = ContentPipeline().run(content_id, max_revisions=max_retries)
    if not result.get("draft_file") or result["outcome"] == "FAILED":
        raise RuntimeError(result.get("error", result["outcome"]))
    path = result["draft_file"]
    text = Path(path).read_text(encoding="utf-8")
    return (path, text, 100 if result.get("qa", {}).get("passed") else 0)

if __name__ == "__main__":
    raise SystemExit(main())
