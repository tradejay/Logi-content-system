"""Fixed CLI test runner for Insights pipeline tests with Pytest and Allure.

Adheres to ROOT-INSIGHTS-PYTEST-ALLURE-20261023:
- Runs pytest with Allure results recording
- Supports full test suite execution and failed test rerun (pytest --lf)
- Distinguishes test rerun from operational pipeline resume
- Preserves historical Allure results and links stable test IDs
- Generates/verifies Allure HTML report or provides clear installation guidance
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ALLURE_RESULTS_DIR = ROOT / 'data/blog_performance/insights/allure-results'
ALLURE_REPORT_DIR = ROOT / 'static/reports/insights-allure-report'
LATEST_FAILURE_FILE = ROOT / 'data/blog_performance/insights/latest-test-failure.json'
PYTEST_CACHE_LASTFAILED = ROOT / '.pytest_cache/v/cache/lastfailed'

INSIGHTS_TEST_FILES = [
    'tests/test_insights_config_pipeline.py',
    'tests/test_insights_regression_and_monitor.py',
    'tests/test_insights_pipeline.py',
    'tests/test_insights_test_review.py',
    'tests/test_insights_dispatch_isolation.py',
]


def find_allure_cmd():
    """Detect available Allure CLI (native or npx)."""
    # 1. Native allure in PATH
    native = shutil.which('allure')
    if native:
        return [native]

    # 2. npx allure
    npx = shutil.which('npx') or shutil.which('npx.cmd')
    if npx:
        try:
            res = subprocess.run([npx, 'allure', '--version'], capture_output=True, text=True, timeout=10)
            if res.returncode == 0:
                return [npx, 'allure']
        except Exception:
            pass

    return None


def run_tests(rerun: bool = False, extra_args: list = None) -> int:
    """Execute pytest with Allure results collection."""
    extra = list(extra_args or [])
    ALLURE_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    evidence_dir = ROOT / 'static/reports/insights-tests' / ('verification-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:6])
    evidence_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, '-m', 'pytest',
        f'--alluredir={str(ALLURE_RESULTS_DIR)}'
    ]
    cmd.extend([
        '--json-report', f'--json-report-file={evidence_dir / "results.json"}',
        f'--junitxml={evidence_dir / "junit.xml"}',
        f'--html={evidence_dir / "index.html"}', '--self-contained-html',
        '--cov=services.blog_performance.insights',
        f'--cov-report=json:{evidence_dir / "coverage.json"}', '--cov-report=term',
    ])

    if rerun:
        has_failed = False
        if PYTEST_CACHE_LASTFAILED.exists():
            try:
                failed_data = json.loads(PYTEST_CACHE_LASTFAILED.read_text(encoding='utf-8'))
                has_failed = bool(failed_data)
            except Exception:
                has_failed = False

        if not has_failed:
            print("\n================================================================================")
            print("[재시험 안내] 최근 실패한 테스트가 없습니다 (All tests passed in previous run).")
            print("참고: 'pytest --lf'는 개발 테스트 실패 건 재시험이며,")
            print("      운영 파이프라인 이어달리기('insights.cmd resume')와 구별됩니다.")
            print("전체 테스트를 실행합니다.")
            print("================================================================================\n")
        else:
            print("\n================================================================================")
            print("[재시험 안내] 최근 실패한 테스트를 다시 실행합니다.")
            print("참고: 'pytest --lf'는 개발 테스트 실패 건 재시험이며,")
            print("      운영 파이프라인 이어달리기('insights.cmd resume')와 구별됩니다.")
            print("================================================================================\n")
            cmd.append('--lf')

    # Add default target test files if not specified in extra
    has_test_target = any(a.startswith('tests/') or a.endswith('.py') for a in extra)
    if not has_test_target:
        cmd.extend(INSIGHTS_TEST_FILES)

    cmd.extend(extra)

    print(f"Executing: {' '.join(cmd)}")
    env = os.environ.copy()
    env['COVERAGE_FILE'] = str(evidence_dir / '.coverage')
    proc = subprocess.run(cmd, cwd=str(ROOT), env=env)
    print(f'검증 기록: {evidence_dir.relative_to(ROOT)}')
    try:
        from .test_review import queue_test_review
        receipt = queue_test_review(evidence_dir, proc.returncode, ROOT)
        print(f"자동 리뷰 등록: {receipt['job_id']} ({receipt['status']})")
    except Exception as exc:
        # Review transport must not mask pytest's exit status.
        (evidence_dir / 'review-registration.json').write_text(
            json.dumps({'status': 'registration_failed', 'error_type': type(exc).__name__}), encoding='utf-8')
        print(f'자동 리뷰 등록 실패: {type(exc).__name__}; 테스트 기록은 보존됨')

    if proc.returncode != 0:
        if LATEST_FAILURE_FILE.exists():
            try:
                fail_info = json.loads(LATEST_FAILURE_FILE.read_text(encoding='utf-8'))
                print("\n--------------------------------------------------------------------------------")
                print("[테스트 실패 요약]")
                print(f"- 테스트 ID : {fail_info.get('test_id')}")
                print(f"- 실패 단계 : {fail_info.get('failed_step')}")
                print(f"- 오류 내용 : {fail_info.get('error')}")
                print(f"- 증거 경로 : {fail_info.get('evidence_paths')}")
                print(f"- 실패 기록 : {LATEST_FAILURE_FILE.relative_to(ROOT)}")
                print("--------------------------------------------------------------------------------\n")
            except Exception:
                pass

    return proc.returncode


def generate_report(clean: bool = True) -> int:
    """Generate Allure HTML Report from accumulated results."""
    allure_cmd = find_allure_cmd()
    if not allure_cmd:
        print("\n================================================================================")
        print("[미생성] Allure CLI를 시스템에서 찾을 수 없습니다.")
        print("설치 안내:")
        print("  - NPM: npm install -g allure-commandline")
        print("  - Scoop: scoop install allure")
        print("  - Chocolatey: choco install allure-commandline")
        print(f"결과 JSON 원천 데이터는 안전하게 보존되어 있습니다: {ALLURE_RESULTS_DIR.relative_to(ROOT)}")
        print("================================================================================\n")
        return 1

    # Preserve history for run-over-run trends
    history_src = ALLURE_REPORT_DIR / 'history'
    history_dst = ALLURE_RESULTS_DIR / 'history'
    if history_src.exists():
        history_dst.mkdir(parents=True, exist_ok=True)
        for item in history_src.glob('*'):
            if item.is_file():
                try:
                    shutil.copyfile(item, history_dst / item.name)
                except Exception:
                    pass

    ALLURE_REPORT_DIR.parent.mkdir(parents=True, exist_ok=True)
    if clean and ALLURE_REPORT_DIR.exists():
        import time
        for _ in range(5):
            try:
                shutil.rmtree(ALLURE_REPORT_DIR, ignore_errors=True)
                break
            except Exception:
                time.sleep(0.15)

    gen_cmd = list(allure_cmd) + [
        'generate',
        str(ALLURE_RESULTS_DIR),
        '--output', str(ALLURE_REPORT_DIR)
    ]
    if clean and ALLURE_REPORT_DIR.exists():
        gen_cmd.append('--clean')

    print(f"Generating Allure Report: {' '.join(gen_cmd)}")
    subprocess.run(gen_cmd, cwd=str(ROOT))

    # Allure 3 writes to 'awesome/' before flattening; on Windows EBUSY may stop the flatten step.
    awesome_dir = ALLURE_REPORT_DIR / 'awesome'
    report_index = ALLURE_REPORT_DIR / 'index.html'

    if awesome_dir.exists() and (awesome_dir / 'index.html').exists() and not report_index.exists():
        for item in awesome_dir.glob('*'):
            try:
                dest = ALLURE_REPORT_DIR / item.name
                if item.is_file():
                    shutil.copy2(item, dest)
                elif item.is_dir() and not dest.exists():
                    shutil.copytree(item, dest)
            except Exception:
                pass

    if report_index.exists():
        print("\n================================================================================")
        print("[Allure 리포트 생성 완료]")
        print(f"리포트 경로: {report_index.resolve()}")
        print(f"상대 경로: {report_index.relative_to(ROOT)}")
        print("확인 명령: .\\test_insights.cmd open")
        print("================================================================================\n")
        return 0
    else:
        print("\n[오류] Allure 리포트 생성에 실패하였습니다.")
        return 1


def open_report() -> int:
    """Open or serve the generated Allure HTML Report."""
    report_index = ALLURE_REPORT_DIR / 'index.html'
    if not report_index.exists():
        print(f"[오류] 리포트 파일이 없습니다: {report_index.relative_to(ROOT)}")
        print("먼저 '.\\test_insights.cmd report'를 실행하여 리포트를 생성하세요.")
        return 1

    allure_cmd = find_allure_cmd()
    if allure_cmd:
        open_cmd = list(allure_cmd) + ['open', str(ALLURE_REPORT_DIR)]
        subprocess.run(open_cmd, cwd=str(ROOT))
        return 0
    else:
        # Fallback to default browser
        if sys.platform == 'win32':
            os.startfile(str(report_index))
            return 0
        return 1


def main():
    parser = argparse.ArgumentParser(description="Insights Test Suite & Allure Reporter Runner")
    subparsers = parser.add_subparsers(dest='subcommand')

    # Subcommand: run
    p_run = subparsers.add_parser('run', help="Run full insights test suite")
    p_run.add_argument('pytest_args', nargs=argparse.REMAINDER, help="Arguments passed to pytest")

    # Subcommand: rerun
    p_rerun = subparsers.add_parser('rerun', help="Rerun failed tests only (pytest --lf)")
    p_rerun.add_argument('pytest_args', nargs=argparse.REMAINDER, help="Arguments passed to pytest")

    # Subcommand: report
    subparsers.add_parser('report', help="Generate Allure HTML Report")

    # Subcommand: open
    subparsers.add_parser('open', help="Open Allure HTML Report in browser")

    # Default without subcommand
    args, unknown = parser.parse_known_args()

    if args.subcommand == 'rerun':
        code = run_tests(rerun=True, extra_args=args.pytest_args)
        sys.exit(code)
    elif args.subcommand == 'report':
        code = generate_report()
        sys.exit(code)
    elif args.subcommand == 'open':
        code = open_report()
        sys.exit(code)
    elif args.subcommand == 'run':
        code = run_tests(rerun=False, extra_args=args.pytest_args)
        # Automatically generate report after run
        generate_report()
        sys.exit(code)
    else:
        # Default behavior: run all insights tests + generate report
        code = run_tests(rerun=False, extra_args=unknown)
        generate_report()
        sys.exit(code)


if __name__ == '__main__':
    main()
