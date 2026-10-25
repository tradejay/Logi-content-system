"""Read-only-to-production scenario evidence, using real gate and temporary fixtures."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.test_publish_gate_scenarios import PublishGateScenarios, change_status
from services.content_pipeline import atomic
from services.pipeline_context import digest


def snapshot(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def run(out):
    variants = [
        ('normal', '正常', None),
        ('server_error_stale_success', '서버 오류', 'error'),
        ('empty_null', '빈 응답', None),
        ('empty_string', '빈 응답', ''),
        ('empty_object', '빈 응답', {}),
        ('empty_claims', '빈 응답', {'status': 'REVIEWED', 'claims': []}),
        ('malformed_text', '잘못된 형식', '{not-json'),
        ('malformed_claims', '잘못된 형식', {'status': 'REVIEWED', 'claims': 'bad'}),
        ('missing_fields', '잘못된 형식', {'claims': [{'verdict': 'confirmed'}]}),
        ('unresolved', '미해결 항목', None),
        ('changed_draft', '원고 변경', None),
    ]
    records = []
    for name, group, value in variants:
        t = PublishGateScenarios('test_valid_review_and_approval_allows_command')
        t.setUp()
        try:
            # Fail before any state transition unless every mutable global is isolated.
            isolated = t.root.resolve()
            assert isolated.is_relative_to((ROOT / '.test-tmp').resolve())
            for field in ('REGISTRY_FILE', 'BRIEFS_DIR', 'QUEUE_DIR', 'LOCKS_DIR', 'LOGS_DIR', 'EVENTS_LOG'):
                assert Path(getattr(change_status, field)).resolve().is_relative_to(isolated), field
            import services.content_pipeline as pipeline_module
            assert pipeline_module.ContentPipeline() is t.pipeline
            assert t.pipeline.root.resolve() == isolated
            assert t.pipeline.system.resolve().is_relative_to(isolated)
            t.latest['approved_assets'] = {}
            initial = json.loads(json.dumps(t.latest))
            if name == 'server_error_stale_success':
                # Keep the old successful review and approval: error must still fail closed.
                t.latest['error'] = 'simulated review service transport failure'
            elif name.startswith(('empty_', 'malformed_')) or name == 'missing_fields':
                t.latest['official_review'] = value
            elif name == 'unresolved':
                t.latest['approval']['resolutions'] = []
            elif name == 'changed_draft':
                t.draft.write_text('승인 이후 수정된 원고', encoding='utf-8')
            atomic(t.latest_path, t.latest)
            approval_archive = t.pipeline.work(t.cid) / 'runs/run-fixture-1/approval.json'
            atomic(approval_archive, {'approval': t.latest['approval'], 'run_id': 'run-fixture-1'})
            ready = t.root / 'content-system/05_publish/ready'
            ready.mkdir(parents=True, exist_ok=True)
            (ready / f'{t.cid}.final.md').write_text('PREVIOUS APPROVED COPY', encoding='utf-8')
            (ready / f'{t.cid}.naver.html').write_text('<p>PREVIOUS APPROVED COPY</p>', encoding='utf-8')
            before = snapshot(t.root)
            results = []
            for mode in ('status_transaction', 'export'):
                try:
                    response = (change_status.execute_status_transaction(t.cid, 'READY_TO_PUBLISH')
                                if mode == 'status_transaction' else t.pipeline.export(t.cid))
                    results.append({'path': mode, 'allowed': True, 'return': list(response) if isinstance(response, tuple) else {'run_id': response['run_id'], 'draft_sha256': response['draft_sha256']}})
                except ValueError as error:
                    results.append({'path': mode, 'allowed': False, 'error_type': 'ValueError', 'message': str(error), 'http_status': None})
            after = snapshot(t.root)
            allowed = name == 'normal'
            assert all(r['allowed'] == allowed for r in results), results
            changed = [p for p in set(before) | set(after) if before.get(p) != after.get(p)]
            audit_path = (t.pipeline.work(t.cid) / 'publish-gate.jsonl').relative_to(t.root).as_posix()
            if not allowed:
                lock_path = (t.pipeline.work(t.cid) / '.gate.lock').relative_to(t.root).as_posix()
                assert set(changed).issubset({audit_path, lock_path}), changed
            with t.registry.open(encoding='utf-8', newline='') as f:
                status = next(csv.DictReader(f))['status']
            assert status == ('READY_TO_PUBLISH' if allowed else 'READY_FOR_QA')
            assert t.latest_path.read_bytes() and before[t.latest_path.relative_to(t.root).as_posix()] == after[t.latest_path.relative_to(t.root).as_posix()]
            approval_key = approval_archive.relative_to(t.root).as_posix()
            assert before[approval_key] == after[approval_key]
            records.append({
                'case': name, 'category': group, 'initial_registry_status': 'READY_FOR_QA',
                'initial_review_approval': initial, 'input_latest': t.latest,
                'current_draft_sha256': digest(t.draft.read_text(encoding='utf-8')),
                'expected_allowed': allowed, 'actual': results, 'final_registry_status': status,
                'changed_files': sorted(changed), 'files_before': before, 'files_after': after,
                'gate_events': [json.loads(x) for x in (t.root / audit_path).read_text(encoding='utf-8').splitlines()],
                'assertions': ['both real gate paths match expected allowance', 'registry status matches expectation',
                               'pipeline-latest approval record unchanged', 'blocked cases change only gate audit log / mutex file; no export or approval writes'],
            })
        finally:
            t.doCleanups()
    out.mkdir(parents=True, exist_ok=True)
    (out / 'detailed-scenarios.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'variants': len(records), 'real_gate_calls': sum(len(r['actual']) for r in records), 'passed': len(records)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    run(parser.parse_args().out)
