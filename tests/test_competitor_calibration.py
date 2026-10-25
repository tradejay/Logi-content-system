from datetime import date,timedelta
import json
import sqlite3
import unittest
import tempfile
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
from services.competitor_calibration import normalize_weights,measurement_context,build_samples,calibrate,FEATURES
from services.competitor_engine import Config,SCHEMA,compute_index,Store,run_scan

BASE={'exposure':.4,'activity':.25,'focus':.2,'content':.15}


class CalibrationTests(unittest.TestCase):
    def samples(self,reverse_test=False):
        values=[];start=date(2026,1,1)
        for day in range(24):
            features={b:{'exposure':1-i/3,'activity':i/3,'focus':.5,'content':.5} for i,b in enumerate('abcd')}
            target={b:(1-i/3 if reverse_test and day>=16 else i/3) for i,b in enumerate('abcd')}
            values.append({'date':str(start+timedelta(days=day)),'target_date':str(start+timedelta(days=day+1)),
                           'features':features,'target':target,'measurement_key':'M','cohort_key':'C'})
        return values

    def test_weights_normalized_and_invalid_rejected(self):
        self.assertAlmostEqual(sum(normalize_weights({k:v*100 for k,v in BASE.items()}).values()),1)
        for value in [-1,float('nan'),True]:
            with self.assertRaises(ValueError):normalize_weights({**BASE,'content':value})
        with self.assertRaises(ValueError):normalize_weights(dict.fromkeys(FEATURES,0))

    def test_no_history_retains_baseline(self):
        result=calibrate([],BASE)
        self.assertEqual(result['status'],'insufficient_data');self.assertIsNone(result['candidate_weights'])

    def test_improvement_validated_without_application(self):
        result=calibrate(self.samples(),BASE)
        self.assertEqual(result['status'],'validated_candidate')
        self.assertGreater(result['test_candidate'],result['test_baseline'])
        self.assertTrue(result['active_weights_unchanged']);self.assertFalse(result['auto_apply'])

    def test_training_fit_that_fails_future_holdout_is_rejected(self):
        result=calibrate(self.samples(reverse_test=True),BASE)
        self.assertEqual(result['status'],'keep_baseline')

    def test_overlap_is_purged(self):
        samples=self.samples()
        for s in samples:s['target_date']=str(date.fromisoformat(s['date'])+timedelta(days=20))
        result=calibrate(samples,BASE)
        self.assertEqual(result['status'],'insufficient_data');self.assertEqual(result['train_dates'],[])

    def test_legacy_and_same_day_outcomes_are_not_training_data(self):
        c=sqlite3.connect(':memory:');c.executescript(SCHEMA)
        cfg=Config(pinpoint_keywords=['kw'],general_keywords=[],longtail_keywords=[])
        context=measurement_context(cfg,['a','b'],{'kw'},True,True)
        c.execute('INSERT INTO benchmark_run_context VALUES(?,?)',('2026-01-01',json.dumps(context)))
        for b in ['a','b']:c.execute('INSERT INTO index_snapshots VALUES(?,?,?,?,?,?,?)',('2026-01-01',b,.1,.2,.3,.4,250))
        samples,_=build_samples(c);self.assertEqual(samples,[]);c.close()

    def test_changed_measurement_or_missing_data_not_comparable(self):
        c=sqlite3.connect(':memory:');c.executescript(SCHEMA)
        cfg=Config(pinpoint_keywords=['kw'],general_keywords=[],longtail_keywords=[])
        context=measurement_context(cfg,['a','b'],{'kw'},True,True)
        other={**context,'measurement_key':'different'}
        for day,ctx in [('2026-01-01',context),('2026-01-08',other)]:
            c.execute('INSERT INTO benchmark_run_context VALUES(?,?)',(day,json.dumps(ctx)))
        samples,_=build_samples(c);self.assertEqual(samples,[]);c.close()

    def test_default_scoring_stays_compatible(self):
        out=compute_index({'a':dict.fromkeys(FEATURES,0),'b':dict.fromkeys(FEATURES,1)},BASE)
        self.assertEqual(out['a']['total'],0);self.assertEqual(out['b']['total'],1000)

    def test_scan_records_context_and_scores_together_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg=Config(my_blog_id='mine',pinpoint_keywords=['kw'],general_keywords=[],longtail_keywords=[],db_path=str(Path(directory)/'bench.db'))
            store=Store(cfg.db_path)
            class Client:
                def search_hits(self,keyword,depth):return [{'rank':1,'blog_id':'mine','blog_name':'Mine','post_url':'https://blog.naver.com/mine/1','title':'kw','postdate':'20260101'}]
            posts=[{'title':'화상회의','link':'https://blog.naver.com/mine/1','published':datetime(2026,1,1,tzinfo=timezone.utc)}]
            with patch('services.competitor_engine.rf.select_competitors',return_value={'selected':[],'rejected':[]}):
                run_scan(cfg,Client(),store,crawl_content=True,snap_date='2026-01-01',
                         now=datetime(2026,1,1,tzinfo=timezone.utc),rss_fetcher=lambda b:posts,
                         post_fetcher=lambda u:{'title':'kw','char_count':1000,'image_count':3},sleep=lambda t:None)
            self.assertTrue(store.get_run_context('2026-01-01')['complete'])
            self.assertIn('mine',store.get_index('2026-01-01'))


if __name__=='__main__':unittest.main()
