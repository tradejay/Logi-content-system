import unittest
from services.paragraph_edit_experiment import validate


class ParagraphTest(unittest.TestCase):
    def test_same_block_reordering_allowed(self):
        original=[{'id':'B','claim_ids':[],'markdown':'기본 케이블은 3.0m입니다. 별매 케이블은 5.0m입니다.'}]
        edited={'blocks':[{'id':'B','claim_ids':[],'markdown':'별매 케이블은 5.0m입니다.\n\n기본 케이블은 3.0m입니다.'}],'claims':[]}
        self.assertEqual(validate(original,edited,[]),[])

    def test_values_cannot_move_to_other_block(self):
        original=[{'id':'A','claim_ids':[],'markdown':'화각은 120.0°입니다.'},{'id':'B','claim_ids':[],'markdown':'길이는 5.0m입니다.'}]
        edited={'blocks':[{'id':'A','claim_ids':[],'markdown':'길이는 5.0m입니다.'},{'id':'B','claim_ids':[],'markdown':'화각은 120.0°입니다.'}],'claims':[]}
        self.assertTrue(validate(original,edited,[]))

    def test_claim_assignment_and_quote_checked(self):
        original=[{'id':'A','claim_ids':['C'],'markdown':'화각은 120.0°입니다.'}]
        claim={'id':'C','text':'없는 인용','fact_ids':['F']}
        edited={'blocks':original,'claims':[claim]}
        self.assertTrue(validate(original,edited,[claim]))


if __name__=='__main__':unittest.main()
