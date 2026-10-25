"""Feed the actual external response to a temporary real gate, never approve production."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.test_publish_gate_scenarios import PublishGateScenarios, change_status
from services.content_pipeline import atomic
from services.pipeline_context import digest


def main():
    base = ROOT / 'audit/content-quality-eval-20261025'
    live = json.loads((base / 'latest-article.json').read_text(encoding='utf-8'))
    folder = ROOT / live['folder']
    draft = (folder / 'draft.md').read_text(encoding='utf-8')
    identity = json.loads((folder / 'draft-identity.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(draft.encode()).hexdigest() == identity['sha256']
    official_file = folder / 'official-review.json'
    official = json.loads(official_file.read_text(encoding='utf-8')) if official_file.exists() else {'status': 'ERROR', 'claims': [], 'draft_sha256': digest(draft)}
    test = PublishGateScenarios('test_valid_review_and_approval_allows_command')
    test.setUp()
    try:
        for field in ('REGISTRY_FILE', 'BRIEFS_DIR', 'QUEUE_DIR', 'LOCKS_DIR', 'LOGS_DIR', 'EVENTS_LOG'):
            assert Path(getattr(change_status, field)).resolve().is_relative_to(test.root.resolve())
        test.draft.write_text(draft, encoding='utf-8')
        test.latest.update(draft_sha256=digest(draft), official_review=official, approval=None)
        # QA/outcome are isolated fixture values to exercise the later checks.
        # They are not a newly executed QA or a production approval.
        atomic(test.latest_path, test.latest)
        before = hashlib.sha256(test.registry.read_bytes()).hexdigest()
        try:
            change_status.execute_status_transaction(test.cid, 'READY_TO_PUBLISH')
        except ValueError as error:
            result = {'allowed': False, 'reason': str(error)}
        else:
            raise AssertionError('No human approval exists; publication must remain blocked')
        assert before == hashlib.sha256(test.registry.read_bytes()).hexdigest()
        result.update(source_content_id='CNT-2026W39-002', isolated_content_id=test.cid,
                      draft_sha256=digest(draft), official_status=official['status'],
                      registry_unchanged=True, human_approval=None,
                      scope='Actual external response + real gate in an isolated fixture. QA/outcome fixtures; no IDE official_interpret or production state transition.')
        result['gate_events'] = [json.loads(x) for x in (test.pipeline.work(test.cid)/'publish-gate.jsonl').read_text(encoding='utf-8').splitlines()]
        (folder/'gate-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False))
    finally:
        test.doCleanups()


if __name__ == '__main__':
    main()
