"""Run only selected paragraph editing + independent review; no publication."""
import argparse
import json
from services.paragraph_edit_experiment import run

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('content_id',nargs='?',default='CNT-LIVE-20261008-VERIFY-001')
    parser.add_argument('--blocks',nargs='+',choices=['TEST-FOV','TEST-CABLE','TEST-CHECKLIST'])
    parser.add_argument('--full-article',action='store_true')
    args=parser.parse_args()
    if args.full_article and args.blocks:parser.error('Choose full article or selected blocks')
    result=run(args.content_id,block_ids=args.blocks,full_article=args.full_article)
    print(json.dumps(result,ensure_ascii=False,indent=2))
