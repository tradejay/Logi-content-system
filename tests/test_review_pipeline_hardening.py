import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from services.official_review_contract import validate_claim_verdicts
from services.evaluation_manifest import seal_run, seal_labels, verify_labels

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('bad', [
    {}, {'claims': []}, {'claims': [{'id': 'x', 'verdict': 'confirmed', 'evidence': 'url'}]},
    {'claims': [{'id': 'c', 'verdict': 'pass'}]},
    {'claims': [{'id': 'c', 'verdict': 'confirmed'}]},
    {'claims': [{'id': 'c', 'verdict': 'confirmed', 'evidence': '   '}]},
    {'claims': [{'id': 'c', 'verdict': 'confirmed', 'evidence': []}]},
    {'claims': [{'id': 'c', 'verdict': 'confirmed', 'evidence': 'u'}, {'id': 'c', 'verdict': 'confirmed', 'evidence': 'u'}]},
])
def test_shared_contract_rejects_bad_payload(bad):
    with pytest.raises(ValueError):
        validate_claim_verdicts(bad, [{'id': 'c'}])


@pytest.mark.parametrize('failed', [False, True])
def test_real_cli_exit_and_status_agree(tmp_path, failed):
    out = tmp_path / 'out'
    out.mkdir()
    prompt = tmp_path / 'content-system/02_writer_ai/authoring/prompts/official.md'
    prompt.parent.mkdir(parents=True)
    prompt.write_text('test policy', encoding='utf-8')
    (out / 'request.json').write_text(json.dumps({'claims': [{'id': 'c', 'statement': 'one'}]}))
    (out / 'dataset.json').write_text(json.dumps({'items': [{'id': 'c', 'statement': 'one', 'split': 'holdout'}], 'human_review': {'approved': False}}))
    code = """
import importlib.util,json,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('eval_cli',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.ROOT=Path(sys.argv[2]);m.OUT=m.ROOT/'out'
failed=sys.argv[3]=='True'
def official(self,*args):
 if failed: raise RuntimeError('offline transport fixture')
 return json.dumps({'claims':[{'id':'c','verdict':'confirmed','evidence':'https://example.com/spec'}]})
m.ModelProvider.official=official
sys.argv=['eval_cli','quality'];m.main()
"""
    proc = subprocess.run([sys.executable, '-c', code, str(ROOT/'scripts/run_content_quality_eval.py'), str(tmp_path), str(failed)], cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == (1 if failed else 0), proc.stderr
    status = json.loads((out/'latest-quality.json').read_text())
    assert status['status'] == ('failed' if failed else 'parsed')


def prepare_manifest(tmp_path):
    request = {'instruction': 'policy-v1', 'context': {'claims': [{'id': 'c', 'statement': 'one'}]}}
    (tmp_path/'request.json').write_text(json.dumps(request))
    (tmp_path/'response.txt').write_text('raw response')
    (tmp_path/'parsed.json').write_text(json.dumps({'claims': [{'id': 'c', 'verdict': 'confirmed', 'evidence': 'url'}]}))
    seal_run(tmp_path, {'items': [{'id': 'c', 'split': 'holdout'}]})
    labels = tmp_path/'human.csv'
    with labels.open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=['id','statement','split','human_label','reviewer']);w.writeheader()
        w.writerow({'id':'c','statement':'one','split':'holdout','human_label':'confirmed','reviewer':'fixture-human'})
    seal_labels(tmp_path, labels)
    return labels


@pytest.mark.parametrize('changed', ['request.json','response.txt','parsed.json','policy.snapshot.txt','split.snapshot.json','labels.snapshot.csv','human.csv'])
def test_scoring_rejects_each_changed_version(tmp_path, changed):
    labels = prepare_manifest(tmp_path)
    (tmp_path/changed).write_text('changed')
    with pytest.raises(ValueError):
        verify_labels(tmp_path, labels)


def test_sealed_inputs_score_without_external_call(tmp_path):
    labels = prepare_manifest(tmp_path)
    spec=importlib.util.spec_from_file_location('score_eval',ROOT/'scripts/score_content_quality_eval.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.score(tmp_path, labels)
    result=json.loads((tmp_path/'human-scored-metrics.json').read_text())
    assert result['all']['accuracy']==1.0
    assert result['input_manifest']['labels']['sha256']


@pytest.fixture
def pipeline_case():
    # Only provider boundaries are fakes; real operational stages and gates run.
    from tests.test_content_pipeline import PipelineTests
    case = PipelineTests('test_context_reaches_writer_and_no_automatic_final')
    case.setUp()
    try:
        yield case
    finally:
        case.tearDown()


def test_real_operating_stages_repair_qa_approve_export(pipeline_case):
    c=pipeline_case
    reviews=c.natural_review_provider('rewrite')
    stages=[]
    complete=c.provider.complete
    def traced(stage,instruction,context):
        stages.append(stage)
        return complete(stage,instruction,context)
    c.provider.complete=traced
    result=c.run_pipeline()
    assert result['outcome']=='COMPLETED_REVIEW_PENDING', result.get('error')
    assert len(reviews)==2
    first=stages.index('official_interpret')
    assert 'feedback' in stages[first+1:]
    assert stages.count('official_interpret')==2
    with pytest.raises(ValueError):c.pipeline.export('CNT-test')
    approved=c.approve(result)
    exported=c.pipeline.export('CNT-test',expected_run_id=result['run_id'],expected_sha256=approved['draft_sha256'])
    assert exported['draft_sha256']==approved['draft_sha256']
    assert (c.root/'content-system/05_publish/ready/CNT-test.naver.html').is_file()


def test_hold_is_distinct_from_missing_approval(pipeline_case):
    c=pipeline_case
    c.natural_review_provider('hold')
    result=c.run_pipeline()
    assert result['outcome']=='REVISION_REQUIRED'
    assert result['official_review']['interpretation']['decision']=='hold'
    with pytest.raises(ValueError):c.approve(result)
    # Exercise the unresolved-review gate independently of the earlier outcome/approval gates.
    result.update(outcome='COMPLETED_READY',publish_ready=True,
                  approval={'reviewer':'fixture-human','draft_sha256':result['draft_sha256'],'resolutions':['resolved']*len(result['admin_checks'])})
    from services.content_pipeline import atomic
    atomic(c.pipeline.work('CNT-test')/'pipeline-latest.json',result)
    with pytest.raises(ValueError,match='Official review'):
        c.pipeline.export('CNT-test')
    assert not (c.root/'content-system/05_publish/ready/CNT-test.naver.html').exists()


def test_malformed_interpretation_blocks_approval_and_export(pipeline_case):
    c=pipeline_case
    original=c.provider.complete
    def complete(stage,instruction,context):
        raw=original(stage,instruction,context)
        if stage=='official_interpret':
            value=json.loads(raw)
            value['result']['claims']=[{'id':'c1','verdict':'confirmed'}]
            return json.dumps(value)
        return raw
    c.provider.complete=complete
    result=c.run_pipeline()
    assert result['official_review']['status']=='ERROR'
    with pytest.raises(ValueError):c.approve(result)
    result.update(outcome='COMPLETED_READY',publish_ready=True,
                  approval={'reviewer':'fixture-human','draft_sha256':result['draft_sha256'],'resolutions':['resolved']*len(result['admin_checks'])})
    from services.content_pipeline import atomic
    atomic(c.pipeline.work('CNT-test')/'pipeline-latest.json',result)
    with pytest.raises(ValueError,match='Official review'):c.pipeline.export('CNT-test')
    assert not (c.root/'content-system/05_publish/ready/CNT-test.naver.html').exists()
