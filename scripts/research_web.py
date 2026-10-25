"""Run one Google-grounded research call using existing Gemini credentials."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.web_research import collect

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--query', required=True)
    parser.add_argument('--output', default='audit/google-search-test.json')
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT):
        parser.error('Output must stay inside project')
    result = collect(ROOT, args.query, output)
    print(json.dumps({k: result[k] for k in ['status', 'cache_hit', 'observed_query_count', 'results', 'usage_metadata']}, ensure_ascii=False, indent=2))
