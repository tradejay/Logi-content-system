"""Run an allowlisted IDE console action; state and history are host-owned."""
import argparse
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from services.ide_worker_bridge import ROOT, load, save
from services.console_work import current
from scripts.run_ide_article_batch import dispatch
from scripts.correct_official_reviews import wait_result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--job', required=True)
    args = parser.parse_args()
    directory = ROOT / 'worker-control/console-actions' / str(uuid.UUID(args.job))
    path = directory / 'job.json'
    job = load(path)
    job.update(status='running')
    save(path, job)
    try:
        cid, action = job['content_id'], job['action']
        latest, run = current(cid)
        if (latest['run_id'], latest['draft_sha256']) != (job['run_id'], job['draft_sha256']):
            raise ValueError('실행 직전 원고가 변경됐습니다.')
        if action in {'writer', 'official'}:
            command = [sys.executable, '-m', 'scripts.correct_official_reviews', '--content', cid, '--retry', '--instruction', job['instruction']] if action == 'writer' else [sys.executable, '-m', 'scripts.resume_official_reviews', '--content', cid, '--force']
            subprocess.run(command, cwd=ROOT, check=True)
            latest, run = current(cid)
            decision = (latest.get('official_review') or {}).get('decision') or {}
            job.update(status='completed', passed=decision.get('passed'), result_note=latest.get('stage_detail'))
        else:
            markdown = Path(latest['draft_file']).read_text(encoding='utf-8')
            facts = load(run / 'fact-bundle.json') if (run / 'fact-bundle.json').exists() else {}
            payload = {'content_id': cid, 'run_id': run.name, 'markdown': markdown, 'facts': facts,
                       'strategy': load(run / 'strategy.json') if (run / 'strategy.json').exists() else {},
                       'instruction': job['instruction']}
            messages = {
                'manager': '현재 글의 작업 배정·다음 조치를 제안하세요. 실제 승인·설정·원고를 변경하지 마세요. 제안과 필요한 조치만 반환하세요.',
                'planner': '현재 글의 자료·주제·제품 구성을 검토해 기획안을 제안하세요. 제공 근거만 사용하세요. 원고를 수정하거나 Fact를 확정하지 마세요. 결과는 기획 내용만 반환하세요.',
                'review': '현재 원고와 제공 근거의 일치·조건 누락·문단과 줄바꿈·독자 질문 해결을 독립 검토하세요. passed,issues만 반환하세요. 원고·로그를 작성하지 마세요.'}
            task = dispatch(directory, action, messages[action], payload)
            job['task'] = task
            save(path, job)
            result = wait_result(task)
            save(directory / 'result.json', result)
            if action == 'review':
                current_latest, _ = current(cid)
                if current_latest['draft_sha256'] != job['draft_sha256'] or current_latest['run_id'] != job['run_id']:
                    raise ValueError('검토 중 원고가 바뀌어 판정을 적용하지 않았습니다.')
                save(run / 'console-reviews' / (job['id'] + '.json'), result)
                current_latest.update(qa=result, publish_ready=False, approval=None)
                save(ROOT / 'content-system/working' / cid / 'pipeline-latest.json', current_latest)
                save(run / 'run-result.json', current_latest)
            job.update(status='completed', passed=result.get('passed'), result_note='검토 결과 반영' if action == 'review' else '기획·운영 제안 저장 · 원고 자동 변경 없음')
        subprocess.run([sys.executable, '-m', 'scripts.sync_taiga', '--sync'], cwd=ROOT, check=False)
    except Exception as error:
        job.update(status='failed', error=str(error))
    job['completed_at'] = datetime.now(timezone.utc).isoformat()
    save(path, job)


if __name__ == '__main__':
    main()
