"""Finish one authorized body-analysis task when its worker result appears."""
import argparse,hashlib,json,subprocess,sys,time
from pathlib import Path
from services.blog_performance.insights.collect_common_query_ranks import ROOT,read,save
from services.blog_performance.insights.analyze_browser_search_bodies import paths
from services.ide_worker_bridge import process

def main():
    p=argparse.ArgumentParser();p.add_argument('--task',required=True);p.add_argument('--timeout',type=int,default=1800);p.add_argument('--base',type=Path);p.add_argument('--mode',choices=['common','products'],default='common');a=p.parse_args()
    record=read(ROOT/'worker-control/dispatch/tasks'/(a.task+'.json'))
    if record['worker_folder']!='04_review':raise ValueError('Wrong worker role')
    task=read(ROOT/'worker-workspaces/04_review/inbox'/a.task/'task.json')
    result=ROOT/'worker-workspaces/04_review'/task['ai_output']
    base,out=(a.base.resolve(),a.base.resolve()/'body-analysis') if a.base else paths();state=out/'completion-state.json';deadline=time.monotonic()+a.timeout;last=None
    save(state,{'task_id':a.task,'status':'waiting_for_worker_result','result_file':str(result.relative_to(ROOT))})
    while time.monotonic()<deadline:
        if result.exists():
            signature=(result.stat().st_mtime_ns,result.stat().st_size)
            if signature==last:
                try:json.loads(result.read_text(encoding='utf-8'))
                except (ValueError,OSError):time.sleep(2);continue
                try:
                    collected=process('04_review',a.task)
                    if collected['status']!='collected':raise RuntimeError('Worker artifact not collected')
                    save(state,{'task_id':a.task,'status':'validating_and_merging'})
                    merge=('services.blog_performance.insights.merge_product_browser_ranks',['--base',str(base),'--result',str(result)]) if a.mode=='products' else ('services.blog_performance.insights.merge_browser_body_classifications',['--result',str(result)])
                    for module,args in [merge,('services.blog_performance.insights.build_search_insights_html',[])]:
                        proc=subprocess.run([sys.executable,'-m',module,*args],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
                        (out/(module.rsplit('.',1)[-1]+'.log')).write_text(proc.stdout+proc.stderr,encoding='utf-8')
                        if proc.returncode:raise RuntimeError(module+' failed; see local log')
                    report_path=out/('product-report.json' if a.mode=='products' else 'report.json');report=read(report_path)
                    save(state,{'task_id':a.task,'status':'completed','coverage':report.get('coverage',report.get('body_collection')),'result_sha256':hashlib.sha256(result.read_bytes()).hexdigest(),'report_file':str(report_path.relative_to(ROOT))})
                except Exception as error:
                    save(state,{'task_id':a.task,'status':'failed','error':str(error)[:300]})
                return
            last=signature
        time.sleep(2)
    save(state,{'task_id':a.task,'status':'timeout','result_file':str(result.relative_to(ROOT))})

if __name__=='__main__':main()
