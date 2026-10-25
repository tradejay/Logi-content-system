"""Code-owned assembly, diff, bookkeeping, and slim review inputs."""
from copy import deepcopy
import difflib
import hashlib
import re
from .ide_worker_bridge import load, save, local


def finalize(worker, task_id, task):
    """Consume content-only AI output; all IDs, hashes, reports and diffs are host-owned."""
    if task.get('output_protocol') != 'content_only_v1':
        return False
    report_path=worker/'outbox'/task_id/'report.json'
    if report_path.exists():return True
    result_path=local(worker,task['ai_output'])
    if not result_path.is_file():return False
    result=load(result_path)
    work=local(worker,'work/'+task_id)
    if not result_path.is_relative_to(work):raise ValueError('AI output outside task')
    artifacts=[result_path]
    if task['stage']=='naver_edit':
        original=load(local(worker,task['system_inputs']['blocks']))['blocks']
        claims=load(local(worker,task['system_inputs']['claims']))['claims']
        edits=result.get('blocks',[])
        if [b['id'] for b in edits]!=[b['id'] for b in original]:raise ValueError('Incomplete or reordered edited blocks')
        blocks=[]
        for source,edited in zip(original,edits):
            if not isinstance(edited.get('markdown'),str) or not edited['markdown'].strip():raise ValueError('Empty block')
            blocks.append({**deepcopy(source),'markdown':edited['markdown']})
        by_claim={cid:b['markdown'] for b in blocks for cid in b.get('claim_ids',[])}
        mapped=[]
        for c in claims:
            # Formatting-only claims may gain line breaks. Never infer semantic rewrites.
            pattern=r'\s+'.join(re.escape(t) for t in c['text'].split())
            match=re.search(pattern,by_claim.get(c['id'],''))
            if not match:raise ValueError('Protected claim wording changed: '+c['id'])
            mapped.append({**deepcopy(c),'text':match.group(0)})
        changes=[]
        for a,b in zip(original,blocks):
            if a['markdown']!=b['markdown']:
                changes.append({'block_id':a['id'],'diff':list(difflib.unified_diff(a['markdown'].splitlines(),b['markdown'].splitlines(),lineterm='')),
                                'before_linebreaks':a['markdown'].count('\n'),'after_linebreaks':b['markdown'].count('\n')})
        outputs={'edited-blocks.json':{'blocks':blocks},'claim-map.json':{'claims':mapped},
                 'changes.json':{'generated_by':'system','changes':changes},
                 'edited.md':'\n\n'.join(b['markdown'].strip() for b in blocks)+'\n'}
        for name,value in outputs.items():
            path=work/'naver_edit'/name
            if isinstance(value,str):path.write_text(value,encoding='utf-8')
            else:save(path,value)
            artifacts.append(path)
    elif task['stage']=='feedback':
        if type(result.get('passed')) is not bool or not isinstance(result.get('issues'),list):raise ValueError('Invalid review decision')
        if result['passed'] and result['issues']:raise ValueError('Passing review contains issues')
        path=work/'feedback/review.json';save(path,result);artifacts.append(path)
    elif task.get('result_contract')=='object_v1':
        if not isinstance(result,dict):raise ValueError('Expected content JSON object')
    else:raise ValueError('Unsupported content-only stage')
    save(report_path,{'task_id':task_id,'worker_id':task['worker_id'],'stage':task['stage'],
        'execution_type':'ide','status':'completed','summary':'System collected AI content',
        'content_id':task.get('content_id'),'publication_approved':False,'generated_by':'system',
        'assigned_rule_ids':task.get('assigned_rule_ids',[]),
        'input_sha256':hashlib.sha256((worker/'inbox'/task_id/'task.json').read_bytes()).hexdigest(),
        'artifacts':[{'path':p.relative_to(worker).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in artifacts]})
    return True


def review_packet(original, edited):
    """One ordered set of blocks; unchanged text is included only once."""
    if [b['id'] for b in original]!=[b['id'] for b in edited]:raise ValueError('Review block order mismatch')
    return {'blocks':[{'id':a['id'],'edited':b['markdown'],
                      **({'before':a['markdown']} if a['markdown']!=b['markdown'] else {})}
                     for a,b in zip(original,edited)]}
