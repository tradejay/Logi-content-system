"""Run the common Gemini pipeline for explicit content IDs."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from services.content_pipeline import ContentPipeline

if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('Usage: batch_rewrite.py CONTENT_ID [CONTENT_ID ...]')
    failed = False
    for cid in sys.argv[1:]:
        result = ContentPipeline().run(cid)
        failed |= result['outcome'] in ['FAILED', 'NEEDS_EVIDENCE', 'REVISION_REQUIRED']
    raise SystemExit(int(failed))
