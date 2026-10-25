"""Stable CLI; no inline Python or handcrafted task manifests needed."""
import argparse
import json
from pathlib import Path
import uuid
import subprocess
import sys
from services.worker_dispatch import ROOT,load,save,enqueue,fetch_post,status
from services.ide_worker_bridge import process


def main():
    parser=argparse.ArgumentParser();commands=parser.add_subparsers(dest='command',required=True)
    send=commands.add_parser('send');send.add_argument('role',choices=['manager','planner','writer','review','assets','system']);send.add_argument('--message',required=True);send.add_argument('--input',action='append',default=[])
    review=commands.add_parser('review-url');review.add_argument('url')
    check=commands.add_parser('status');check.add_argument('--task')
    result=commands.add_parser('result');result.add_argument('--task')
    commands.add_parser('watch-once')
    commands.add_parser('start')
    preflight=commands.add_parser('preflight');preflight.add_argument('--pipeline',choices=['insights','workers'],default='insights');preflight.add_argument('--offline',action='store_true');preflight.add_argument('--json',action='store_true')
    insights=commands.add_parser('insights');insights_sub=insights.add_subparsers(dest='insights_cmd',required=True)
    insights_sub.add_parser('prepare').add_argument('--run-id')
    insights_sub.add_parser('status').add_argument('--run-id')
    st_p=insights_sub.add_parser('start');st_p.add_argument('--run-id');st_p.add_argument('--common-json',type=Path);st_p.add_argument('--products-json',type=Path);st_p.add_argument('--ai-decisions',type=Path);st_p.add_argument('--offline',action='store_true',default=True)
    insights_sub.add_parser('resume').add_argument('--run-id')
    bld_p=insights_sub.add_parser('build');bld_p.add_argument('--run-id');bld_p.add_argument('--out',type=Path)
    insights_sub.add_parser('preflight')
    args=parser.parse_args()
    if args.command=='preflight':
        from services.worker_preflight import run
        value=run(pipeline=args.pipeline,online=not args.offline)
        if not args.json:
            value={k:value[k] for k in ['pipeline','mode','required_workers_ready','pipeline_ready','issues','limits']} | {
                'workers':[{k:w[k] for k in ['role','required','connected','workspace_matches','can_dispatch','issues']} |
                           {'pending_count':len(w.get('pending_tasks',[]))} for w in value['workers']],
                'missing_files':[d['path'] for d in value['dependencies'] if not d['exists']],
                'servers':value['servers']}
    elif args.command=='start':
        subprocess.Popen(['powershell','-NoProfile','-File',str(ROOT/'scripts/start_ide_worker_bridge.ps1')],
                         stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        value={'status':'start_requested'}
    elif args.command in ['status','result']:
        value=status(args.task)
        if args.command=='result' and value['status']=='collected':
            record=load(ROOT/'worker-control/dispatch/tasks'/f'{value["task_id"]}.json')
            path=ROOT/'worker-workspaces'/record['worker_folder']/value['result_file']
            value['result']=load(path)
    elif args.command=='review-url':
        data,html=fetch_post(args.url)
        cache=ROOT/'worker-control/dispatch/sources'/uuid.uuid4().hex;cache.mkdir(parents=True)
        save(cache/'published-post.json',data)
        (cache/'published-body.html').write_text(html,encoding='utf-8')
        presets=load(ROOT/'worker-control/dispatch-presets.json')
        record=enqueue('review',presets['published_review_message'],[cache/'published-post.json',cache/'published-body.html'],kind='published-review')
        value=status(record['task_id'])
    elif args.command=='send':
        record=enqueue(args.role,args.message,[Path(p) for p in args.input]);value=status(record['task_id'])
    elif args.command=='insights':
        from services.blog_performance.insights import main as insights_main
        if args.insights_cmd=='prepare':
            value=insights_main.prepare_run(args.run_id)
        elif args.insights_cmd=='status':
            value=insights_main.get_status(args.run_id)
        elif args.insights_cmd in ['start','resume']:
            value=insights_main.run_pipeline(
                run_id=args.run_id,
                common_json=getattr(args,'common_json',None),
                products_json=getattr(args,'products_json',None),
                ai_decisions=getattr(args,'ai_decisions',None),
                offline=getattr(args,'offline',True)
            )
        elif args.insights_cmd=='build':
            rid=args.run_id or insights_main.get_latest_run_id()
            run_dir=ROOT/'data/blog_performance/insights'/rid
            out=args.out or run_dir/'report.html'
            from services.blog_performance.insights import build_search_insights_html
            common_rep=run_dir/'common/body-analysis/report.json'
            prod_rep=run_dir/'products/body-analysis/product-report.json'
            activity_src=ROOT/f'data/blog_performance/product-search/{insights_main.ACTIVITY_SAMPLE_ID}/name-matched-diagnostic/report.json'
            build_search_insights_html.build(activity_src,out,common_rep,prod_rep)
            valid,issues=insights_main.verify_html(out)
            value={'html':str(out),'valid':valid,'issues':issues}
        elif args.insights_cmd=='preflight':
            value=insights_main.preflight(offline=True)
    else:
        value=[status(p.stem) for p in (ROOT/'worker-control/dispatch/tasks').glob('*.json')]
    print(json.dumps(value,ensure_ascii=False,indent=2))


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,RuntimeError) as error:
        print(json.dumps({'status':'error','error':str(error)[:240]},ensure_ascii=False))
        sys.exit(1)
