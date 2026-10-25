import unittest
from services.article_stage import current_stage


class ArticleStageTests(unittest.TestCase):
    def test_finished_with_failed_qa_is_review_not_complete(self):
        stage=current_stage({'stage':'finished','outcome':'REVISION_REQUIRED','qa':{'passed':False}}, {'markdown':'원고'})
        self.assertEqual(stage['number'],3)

    def test_official_conflict_precedes_pending_images(self):
        stage=current_stage({'qa':{'passed':True},'official_review':{'status':'REVIEWED','claims':[{'verdict':'contradicted'}]}},
                            {'markdown':'원고','asset_bindings':[{'candidate':None}]})
        self.assertEqual(stage['number'],4)

    def test_candidate_image_is_not_final_approval(self):
        result={'qa':{'passed':True},'official_review':{'status':'REVIEWED','claims':[{'verdict':'confirmed'}]}}
        details={'markdown':'원고','asset_bindings':[{'status':'pending_review','candidate':{'review_status':'candidate'}}]}
        self.assertEqual(current_stage(result,details)['number'],5)
        details['asset_bindings'][0]['candidate']['review_status']='approved'
        self.assertEqual(current_stage(result,details)['number'],6)

    def test_approved_ready_and_published_are_distinct(self):
        result={'outcome':'COMPLETED_READY','publish_ready':True}
        self.assertEqual(current_stage(result,{})['number'],7)
        self.assertEqual(current_stage(result,{},'PUBLISHED')['number'],8)

    def test_edit_goes_back_to_review(self):
        stage=current_stage({'outcome':'REVISION_REQUIRED','manual_edit':{'requires_review':True}}, {'markdown':'수정 원고'})
        self.assertEqual(stage['number'],3)
        self.assertIn('변경',stage['reason'])
        self.assertTrue(stage['intervention_required'])
        self.assertIn('AI',stage['actors'])

    def test_ai_work_and_manager_intervention_are_distinct(self):
        stage=current_stage({'outcome':'RUNNING','stage':'write'}, {})
        self.assertEqual(stage['actors'],'집필 AI')
        self.assertFalse(stage['intervention_required'])
        stage=current_stage({'qa':{'passed':True},'official_review':{'status':'REVIEWED','claims':[{'verdict':'confirmed'}]}},
                            {'markdown':'원고','asset_bindings':[{'candidate':{'review_status':'candidate'}}]})
        self.assertEqual(stage['number'],5)
        self.assertTrue(stage['intervention_required'])

    def test_empty_official_claims_cannot_advance_to_images(self):
        stage=current_stage({'qa':{'passed':True},'official_review':{'status':'REVIEWED','claims':[]}}, {'markdown':'원고'})
        self.assertEqual(stage['number'],4)
        self.assertIn('누락',stage['reason'])


if __name__=='__main__':unittest.main()
