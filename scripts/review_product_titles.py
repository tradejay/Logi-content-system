"""Host controller: sequential 50-title IDE reviews, fixed worker.cmd dispatch."""
import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/blog_performance/product-search/20261021T054347Z/relevance-review'


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path,data): path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')


def command(args):
    proc=subprocess.run([str(ROOT/'worker.cmd'),*args],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
    raw=proc.stdout
    start=raw.find('{')
    if start<0:raise RuntimeError('Worker command returned no JSON')
    return json.loads(raw[start:])


def validate(batch,result,product_ids):
    expected={r['id'] for r in batch['items']}
    decisions=result.get('decisions',[])
    actual=[r.get('id') for r in decisions]
    if len(actual)!=len(expected) or set(actual)!=expected or len(actual)!=len(set(actual)):
        raise ValueError('Missing, duplicate or unexpected title decisions')
    for row in decisions:
        if row.get('decision') not in {'keep','reject','uncertain'}:raise ValueError('Invalid title decision')
        ids=row.get('product_ids',[])
        if not isinstance(ids,list) or not set(ids)<=product_ids:raise ValueError('Invalid product identifiers')
        if row['decision']=='keep' and not ids:raise ValueError('Kept title requires a concrete product')
        if not row.get('reason'):raise ValueError('Decision reason missing')
    return decisions


def export(state):
    source=load(BASE/'title-review-queue.json')
    all_decisions={r['id']:r for b in state['batches'] if b.get('status')=='completed' for r in load(BASE/'title-batches'/f'result-{b["number"]:03}.json')['decisions']}
    counts={'keep':0,'reject':0,'uncertain':0,'pending':0}
    flat=[];kept=[]
    for row in source['items']:
        decision=all_decisions.get(row['candidate_id'])
        if decision:
            row['title_review']={'status':'completed',**{k:v for k,v in decision.items() if k!='id'}}
            counts[decision['decision']]+=1
            if decision['decision']=='keep':kept.append(row)
        else:counts['pending']+=1
        row['eligible_for_scoring']=False
        flat.append({'candidate_id':row['candidate_id'],'title':row['titles'][0], 'blog_id':row['blog_id'], 'url':row['url'],
                     'decision':decision['decision'] if decision else 'pending',
                     'product_ids':','.join(decision.get('product_ids',[])) if decision else '',
                     'reason':decision.get('reason','') if decision else ''})
    source.update(status='title_review_complete' if counts['pending']==0 else 'title_review_running',counts=counts)
    save(BASE/'title-review-queue.json',source)
    save(BASE/'title-kept-candidates.json',{'scope':'title_screen_only_body_validation_required','counts':counts,'items':kept})
    with (BASE/'reviewed-titles.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
    state['counts']=counts
    return counts


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--first-task');args=parser.parse_args()
    path=BASE/'title-batch-progress.json'
    state=load(path) if path.exists() else {'status':'running','pid':os.getpid(),'batch_size':50,'batches':[]}
    state.update(status='running',pid=os.getpid())
    product_path=ROOT/'services/blog_performance/product-search-catalog.json'
    product_ids={p['product_id'] for p in load(product_path)}
    try:
        for file in sorted((BASE/'title-batches').glob('batch-*.json')):
            batch=load(file);number=batch['batch']
            record=next((b for b in state['batches'] if b['number']==number),None)
            if record and record['status']=='completed':continue
            if not record:
                task=args.first_task if number==1 and args.first_task else None
                if not task:
                    sent=command(['send','review','--input',str(file),'--input',str(BASE/'title-batches/GUIDE.md'),
                                  '--input',str(product_path),'--message',f'제목 의미 검토 batch-{number:03}: 입력1의 최대50개 전부 직접 읽고 입력2 GUIDE를 따른다. 입력3 카탈로그 기준. JSON decisions에 id/decision/product_ids/reason만 판단. 코드 분류·본문수집·외부API·로그 작성 금지. uncertain은 채택 아님.'])
                    task=sent.get('task_id')
                    if not task:raise RuntimeError('Dispatch failed')
                record={'number':number,'task_id':task,'status':'waiting','count':len(batch['items'])}
                state['batches'].append(record);save(path,state)
            tid=record['task_id']
            output=ROOT/'worker-workspaces/04_review/work'/tid/'feedback/result.json'
            # Delivery is idempotent. During work observe output file changes, not transcripts.
            command(['status','--task',tid])
            started=time.monotonic();last_change=None
            while True:
                if output.exists():
                    stamp=(output.stat().st_mtime_ns,output.stat().st_size)
                    if stamp==last_change:
                        result=load(output)
                        decisions=validate(batch,result,product_ids)
                        save(BASE/'title-batches'/f'result-{number:03}.json',{'batch':number,'task_id':tid,'decisions':decisions})
                        command(['status','--task',tid])
                        record['status']='completed';counts=export(state);save(path,state)
                        print(json.dumps({'batch':number,'total_batches':37,'counts':counts},ensure_ascii=False),flush=True)
                        break
                    last_change=stamp
                if time.monotonic()-started>900:raise TimeoutError(f'Batch {number} requires attention; task {tid}')
                time.sleep(3)
        state['status']='completed';export(state);save(path,state)
    except Exception as error:
        state.update(status='needs_attention',error=f'{type(error).__name__}: {str(error)[:200]}')
        save(path,state);print(json.dumps({'status':state['status'],'error':state['error']},ensure_ascii=False),flush=True)
        raise


if __name__=='__main__':main()
