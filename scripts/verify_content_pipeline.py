"""Read-only whole-run verifier; no network or model calls."""
import argparse
import json
from pathlib import Path
from services.pipeline_verifier import verify_pipeline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_directory', help='실행 로그 디렉터리')
    parser.add_argument('--output', help='선택: 검증 JSON 저장 경로')
    args = parser.parse_args()
    report = verify_pipeline(args.run_directory)
    value = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding='utf-8')
    print(value)
    raise SystemExit(0 if report['valid'] else 1)


if __name__ == '__main__':
    main()
