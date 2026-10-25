"""Offline chronological weight calibration. No AI, collection or automatic deployment."""
from collections import defaultdict
from datetime import date,timedelta
import hashlib
import json
import math
from pathlib import Path
import sqlite3

FEATURES=('exposure','activity','focus','content')
VERSION='relative-minmax-v2-missingness'


def normalize_weights(weights):
    if set(weights)!=set(FEATURES):raise ValueError('Exactly four benchmark weights required')
    if any(isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or v<0 for v in weights.values()):
        raise ValueError('Weights must be finite nonnegative numbers')
    total=sum(weights.values())
    if total<=0:raise ValueError('Weight sum must be positive')
    return {k:weights[k]/total for k in FEATURES}


def measurement_context(cfg,cohort,successful_keywords,rss_complete,content_complete):
    keywords=sorted(set(k for k,_ in cfg.all_keywords()))
    spec={'feature_version':VERSION,'keywords':keywords,'volumes':{k:cfg.volume(k) for k in keywords},
          'rank_depth':cfg.rank_depth,'sov_max_rank':cfg.sov_max_rank,'topic_terms':sorted(cfg.topic_terms)}
    key=lambda value:hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return {'measurement_key':key(spec),'cohort_key':key(sorted(cohort)),'feature_version':VERSION,
            'spec':spec,'cohort':sorted(cohort),'successful_keywords':sorted(successful_keywords),
            'complete':set(successful_keywords)==set(keywords) and rss_complete and content_complete,
            'rss_complete':rss_complete,'content_complete':content_complete,
            'weights':normalize_weights(cfg.index_weights)}


def build_samples(connection,horizon_days=7,max_lag_days=3):
    tables={r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'benchmark_run_context' not in tables:return [],{'reason':'missing_measurement_provenance'}
    contexts={r[0]:json.loads(r[1]) for r in connection.execute('SELECT snap_date,context_json FROM benchmark_run_context')}
    samples=[];skipped=defaultdict(int)
    for day,context in sorted(contexts.items()):
        if not context.get('complete') or context.get('feature_version')!=VERSION:
            skipped['incomplete_or_incompatible']+=1;continue
        start=date.fromisoformat(day);future_days=[d for d in contexts if horizon_days<=(date.fromisoformat(d)-start).days<=horizon_days+max_lag_days]
        match=None
        for future in sorted(future_days):
            other=contexts[future]
            if other.get('complete') and all(context.get(k)==other.get(k) for k in ['measurement_key','cohort_key','feature_version']):
                match=future;break
        if not match:skipped['no_comparable_future']+=1;continue
        features={r[0]:dict(zip(FEATURES,r[1:])) for r in connection.execute('SELECT blog_id,exposure,activity,focus,content FROM index_snapshots WHERE snap_date=?',(day,))}
        cohort=context['cohort']
        if set(features)!=set(cohort) or any(v is None or not math.isfinite(v) or not 0<=v<=1 for f in features.values() for v in f.values()):
            skipped['missing_features']+=1;continue
        # The target is future observed API-list positions; never same-day index totals.
        rows=connection.execute('SELECT keyword,blog_id,MIN(rank) FROM rank_snapshots WHERE snap_date=? GROUP BY keyword,blog_id',(match,)).fetchall()
        ranks={(r[0],r[1]):r[2] for r in rows}
        spec=context['spec'];volumes=spec['volumes'];denom=sum(volumes.values())
        if denom<=0:skipped['invalid_volumes']+=1;continue
        target={b:sum(volumes[k]/ranks[k,b] for k in spec['keywords'] if (k,b) in ranks and 0<ranks[k,b]<=spec['sov_max_rank'])/denom for b in cohort}
        samples.append({'date':day,'target_date':match,'features':features,'target':target,
                        'measurement_key':context['measurement_key'],'cohort_key':context['cohort_key']})
    return samples,dict(skipped)


def concordance(samples,weights):
    scores=[];pairs=0
    for sample in samples:
        blogs=sorted(sample['target']);correct=0;count=0
        predictions={b:sum(weights[f]*sample['features'][b][f] for f in FEATURES) for b in blogs}
        for i,a in enumerate(blogs):
            for b in blogs[i+1:]:
                actual=sample['target'][a]-sample['target'][b]
                if abs(actual)<1e-12:continue
                predicted=predictions[a]-predictions[b]
                correct+=0.5 if abs(predicted)<1e-12 else float(actual*predicted>0)
                count+=1
        if count:scores.append(correct/count);pairs+=count
    return (sum(scores)/len(scores) if scores else None),pairs


def candidates():
    # Small fixed grid; no dependency on ML libraries or LLM-generated weights.
    for a in range(11):
        for b in range(11-a):
            for c in range(11-a-b):
                yield dict(zip(FEATURES,[a/10,b/10,c/10,(10-a-b-c)/10]))


def calibrate(samples,baseline,min_train_dates=6,min_test_dates=3,min_gain=0.02):
    baseline=normalize_weights(baseline)
    result={'calibration_version':1,'status':'insufficient_data','active_weights_unchanged':True,
            'baseline_weights':baseline,'candidate_weights':None,'auto_apply':False,
            'metric':'future_api_rank_pairwise_concordance','reason':'need_more_comparable_dates'}
    groups=defaultdict(list)
    for s in samples:groups[s['measurement_key'],s['cohort_key']].append(s)
    # Use only the newest comparable regime; do not cherry-pick the best regime.
    if not groups:return result
    samples=sorted(max(groups.values(),key=lambda g:max(s['date'] for s in g)),key=lambda s:s['date'])
    dates=sorted({s['date'] for s in samples});cut=int(len(dates)*0.7)
    if cut==0 or cut>=len(dates):return result
    first_test=dates[cut]
    train=[s for s in samples if s['date']<first_test and s['target_date']<first_test]
    test=[s for s in samples if s['date']>=first_test]
    result.update(train_dates=sorted({s['date'] for s in train}),test_dates=sorted({s['date'] for s in test}),
                  temporal_purge='training target date must precede first test feature date')
    if len(result['train_dates'])<min_train_dates or len(result['test_dates'])<min_test_dates:return result
    base_train,_=concordance(train,baseline);base_test,test_pairs=concordance(test,baseline)
    if base_train is None or base_test is None or test_pairs<30:
        result['reason']='insufficient_non_tied_pairs';return result
    best=baseline;best_score=base_train
    for weights in candidates():
        score,_=concordance(train,weights)
        distance=lambda w:sum(abs(w[k]-baseline[k]) for k in FEATURES)
        if score is not None and (score>best_score+1e-12 or (abs(score-best_score)<=1e-12 and distance(weights)<distance(best)-1e-12)):
            best,best_score=weights,score
    candidate_test,_=concordance(test,best)
    persistence,_=concordance(test,{'exposure':1.,'activity':0.,'focus':0.,'content':0.})
    gain=candidate_test-base_test
    accepted=gain>=min_gain and candidate_test>persistence+1e-12
    result.update(status='validated_candidate' if accepted else 'keep_baseline',
        reason='holdout_improvement' if accepted else 'no_holdout_gain_over_baselines',
        candidate_weights=best,train_baseline=base_train,train_candidate=best_score,
        test_baseline=base_test,test_candidate=candidate_test,test_exposure_only=persistence,
        holdout_gain=gain,test_pairs=test_pairs)
    return result


def run(db_path,weights,horizon_days=7):
    if horizon_days<1:raise ValueError('Future horizon must be at least one day')
    path=Path(db_path).resolve()
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as connection:
        dates=[r[0] for r in connection.execute('SELECT DISTINCT snap_date FROM index_snapshots ORDER BY snap_date')]
        samples,skipped=build_samples(connection,horizon_days)
    result=calibrate(samples,weights)
    if not samples and skipped.get('reason'):result['reason']=skipped['reason']
    result.update(observed_snapshot_dates=dates,comparable_date_pairs=len(samples),
                  excluded=skipped,horizon_days=horizon_days,
                  scope='Internal relative benchmark; not a Naver internal index or causal publishing effect')
    return result
