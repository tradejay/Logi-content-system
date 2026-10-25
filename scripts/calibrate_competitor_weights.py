"""Write an offline calibration report; never scan or overwrite active weights."""
import argparse
import json
from pathlib import Path
from services.blog_performance.competitor_engine import Config
from services.blog_performance.competitor_calibration import run
from services.ide_worker_bridge import ROOT,save


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--db');parser.add_argument('--horizon-days',type=int,default=7)
    parser.add_argument('--output',default='audit/competitor-weight-calibration.json')
    args=parser.parse_args();config=Config.load()
    result=run(args.db or config.db_path,config.index_weights,args.horizon_days)
    target=Path(args.output)
    if not target.is_absolute():target=ROOT/target
    if not target.resolve().is_relative_to(ROOT):raise ValueError('Report must stay inside project')
    save(target,result)
    print(json.dumps({k:result.get(k) for k in ['status','reason','comparable_date_pairs','candidate_weights','active_weights_unchanged']},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
