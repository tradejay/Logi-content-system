import csv
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from services import daily_tracker,performance_db


class ObservationTests(unittest.TestCase):
    def test_missing_visitors_never_create_estimated_measurement(self):
        with patch.object(daily_tracker,'log'),patch.object(daily_tracker.blog_analyzer,'get_daily_visitors',return_value=None),\
             patch.object(daily_tracker.blog_analyzer,'get_blog_rss_info',return_value={'posts':[]}),\
             patch.object(daily_tracker.blog_analyzer,'calculate_blog_index') as calculate,\
             patch.object(daily_tracker,'record_blog_index') as record:
            self.assertIsNone(daily_tracker.track_blog_index('blog'))
            calculate.assert_not_called();record.assert_not_called()

    def test_missing_rss_never_create_estimated_measurement(self):
        with patch.object(daily_tracker,'log'),patch.object(daily_tracker.blog_analyzer,'get_daily_visitors',return_value=[{'visitor_count':20}]),\
             patch.object(daily_tracker.blog_analyzer,'get_blog_rss_info',return_value=None),\
             patch.object(daily_tracker,'record_blog_index') as record:
            self.assertIsNone(daily_tracker.track_blog_index('blog'));record.assert_not_called()

    def test_only_confirmed_publications_are_registered(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);registry=root/'content-system/registry/CONTENT_REGISTRY.csv';registry.parent.mkdir(parents=True)
            with registry.open('w',encoding='utf-8',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=['content_id','status','published_url','published_date']);writer.writeheader()
                writer.writerows([{'content_id':'DRAFT','status':'READY_TO_PUBLISH'},
                    {'content_id':'NO_URL','status':'PUBLISHED','published_date':'2026-10-14'},
                    {'content_id':'LIVE','status':'PUBLISHED','published_url':'https://blog.naver.com/blog/123','published_date':'2026-10-14'}])
            with patch.object(performance_db,'BASE_DIR',str(root)),patch.object(performance_db,'register_content') as register:
                self.assertEqual(performance_db.auto_register_from_registry('blog'),['LIVE'])
                self.assertEqual(register.call_count,1)
                self.assertEqual(register.call_args.kwargs['published_date'],'2026-10-14')


if __name__=='__main__':unittest.main()
