"""Pytest configuration and Allure integration hooks for Insights pipeline tests.

Adheres to ROOT-INSIGHTS-PYTEST-ALLURE-20261023:
- Automated Allure attachments (sanitized test config, error, step, execution artifacts)
- Secret redaction (tokens, CSRF, auth headers, private keys)
- Stable test identification (no timestamp identity)
- Compact failure JSON generation (no manual AI rewriting required)
- Strict offline network guard for unit tests
"""
import hashlib
import json
import re
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

try:
    import allure
    HAS_ALLURE = True
except ImportError:
    allure = None
    HAS_ALLURE = False

ROOT = Path(__file__).resolve().parents[1]
FAILURES_DIR = ROOT / 'data/blog_performance/insights/test-failures'
LATEST_FAILURE_FILE = ROOT / 'data/blog_performance/insights/latest-test-failure.json'

SENSITIVE_KEYS = {'token', 'csrf', 'key', 'secret', 'password', 'credential', 'auth', 'cookie', 'authorization'}


def sanitize_dict(data: Any) -> Any:
    """Recursively scrub secrets, tokens, and credentials from test evidence."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if any(s in str(k).lower() for s in SENSITIVE_KEYS):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_dict(v)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_dict(item) for item in data]
    elif isinstance(data, str):
        # Scrub inline token patterns
        cleaned = re.sub(r'--csrf_token\s+[^\s]+', '--csrf_token [REDACTED]', data)
        cleaned = re.sub(r'Bearer\s+[A-Za-z0-9_\-\.]+', 'Bearer [REDACTED]', cleaned)
        return cleaned
    return data


@pytest.fixture(autouse=True)
def offline_network_guard(request):
    """Guard against unintended external network calls in default offline tests."""
    if 'online' in request.keywords:
        yield
        return

    orig_connect = socket.socket.connect

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        # Allow localhost / loopback addresses
        if host in ('localhost', '127.0.0.1', '::1', '0.0.0.0'):
            return orig_connect(self, address)
        raise RuntimeError(
            f"[OFFLINE GUARD] External network connection to {address} blocked. "
            f"Insights default unit tests must run strictly offline."
        )

    socket.socket.connect = guarded_connect
    try:
        yield
    finally:
        socket.socket.connect = orig_connect


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if report.when == "call":
        # Extract user properties
        props = dict(item.user_properties)
        test_id = item.nodeid
        stable_hash = hashlib.sha256(test_id.encode('utf-8')).hexdigest()[:12]

        if HAS_ALLURE:
            try:
                # Set stable history ID
                allure.dynamic.history_id(stable_hash)
                allure.dynamic.parameter("test_id", test_id)
            except Exception:
                pass

        if report.failed:
            err_msg = str(call.excinfo.value) if call.excinfo else "Unknown test failure"
            err_type = call.excinfo.typename if call.excinfo else "Failure"

            # Detect failed step if available
            failed_step = props.get('step')
            if not failed_step:
                for s in ['preflight', 'panel_preparation', 'collection_dispatch', 'common_import',
                          'products_import', 'body_collection', 'term_review', 'merge', 'top5_audit',
                          'html_build', 'qa_verification', 'activation']:
                    if s in err_msg or s in str(call.excinfo.traceback):
                        failed_step = s
                        break

            evidence_paths = []
            FAILURES_DIR.mkdir(parents=True, exist_ok=True)
            fail_record_file = FAILURES_DIR / f"failure-{stable_hash}.json"

            # Search for test run artifacts in testbed if attached to props
            run_dir = props.get('run_dir')
            if run_dir and Path(run_dir).exists():
                r_path = Path(run_dir)
                for f_name in ['config.json', 'state.json', 'manifest.json', 'report.html']:
                    cand = r_path / f_name
                    if cand.exists():
                        evidence_paths.append(str(cand))
                        if HAS_ALLURE:
                            try:
                                if cand.suffix == '.json':
                                    content = json.loads(cand.read_text(encoding='utf-8', errors='ignore'))
                                    allure.attach(
                                        json.dumps(sanitize_dict(content), ensure_ascii=False, indent=2),
                                        name=f"artifact_{f_name}",
                                        attachment_type=allure.attachment_type.JSON
                                    )
                                elif cand.suffix == '.html':
                                    allure.attach(
                                        cand.read_text(encoding='utf-8', errors='ignore'),
                                        name=f"artifact_{f_name}",
                                        attachment_type=allure.attachment_type.HTML
                                    )
                            except Exception:
                                pass

            compact_failure = {
                'schema_version': 'insights-test-failure-v1',
                'test_id': test_id,
                'stable_hash': stable_hash,
                'config_ref': props.get('config_ref', 'unspecified'),
                'failed_step': failed_step or 'unknown',
                'error_type': err_type,
                'error': err_msg[:500],
                'duration_seconds': round(report.duration, 3),
                'evidence_paths': evidence_paths,
                'recorded_at': datetime.now(timezone.utc).isoformat()
            }

            fail_record_file.write_text(json.dumps(compact_failure, ensure_ascii=False, indent=2), encoding='utf-8')
            LATEST_FAILURE_FILE.parent.mkdir(parents=True, exist_ok=True)
            LATEST_FAILURE_FILE.write_text(json.dumps(compact_failure, ensure_ascii=False, indent=2), encoding='utf-8')

            if HAS_ALLURE:
                try:
                    allure.attach(
                        json.dumps(compact_failure, ensure_ascii=False, indent=2),
                        name="compact_failure.json",
                        attachment_type=allure.attachment_type.JSON
                    )
                except Exception:
                    pass
