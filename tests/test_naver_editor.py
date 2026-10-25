import unittest
from services.naver_editor import apply_edit
from services.naver_blog_compiler import compile_markdown_to_naver_html,mobile_lines


class NaverEditTests(unittest.TestCase):
    def setUp(self):
        self.original={'markdown':'# 회의실\n\n화각은 120도입니다.\n\n{{asset:NEED-1}}',
            'claims':[{'id':'C1','text':'화각은 120도입니다.','fact_ids':['F1']}],
            'used_asset_need_ids':['NEED-1'],'unresolved_items':[{'kind':'asset'}]}

    def test_metadata_preserved(self):
        edited={**self.original,'markdown':self.original['markdown'].replace('입니다.','예요.'),
            'claims':[{'id':'C1','text':'화각은 120도예요.','fact_ids':['F1']}],'changes':['어투 정리']}
        out=apply_edit(self.original,edited)
        self.assertEqual(out['unresolved_items'],self.original['unresolved_items'])
        self.assertEqual(out['used_asset_need_ids'],['NEED-1'])

    def test_block_only_response_is_assembled(self):
        blocks=[{'id':'B1','markdown':self.original['markdown'],'claim_ids':['C1']}]
        original={**self.original,'blocks':blocks}
        out=apply_edit(original,{'blocks':blocks,'claims':original['claims'],'changes':[]})
        self.assertEqual(out['markdown'],original['markdown'])

    def test_number_asset_and_fact_changes_blocked(self):
        for edited in ({**self.original,'markdown':self.original['markdown'].replace('120','90')},
                       {**self.original,'markdown':self.original['markdown'].replace('NEED-1','NEED-X')},
                       {**self.original,'claims':[{'id':'C1','text':'화각은 120도입니다.','fact_ids':['F2']}]}):
            with self.assertRaises(ValueError):apply_edit(self.original,edited)

    def test_mobile_wrap_keeps_markup_and_units(self):
        text='회의실을 설계할 때 카메라 위치와 좌석 사이의 거리를 먼저 확인합니다. **로지텍 MeetUp 2** 장비의 화각은 120 도이며 [공식 자료](https://example.com/spec)에서 확인합니다.'
        wrapped=mobile_lines(text)
        self.assertEqual(wrapped,text)
        self.assertEqual(''.join(wrapped.split()),''.join(text.split()))
        self.assertIn('**로지텍 MeetUp 2**',wrapped)
        self.assertIn('120 도',wrapped)
        self.assertIn('[공식 자료](https://example.com/spec)',wrapped)

    def test_modifier_not_split_by_width_and_origins_reported(self):
        from services.naver_blog_compiler import paragraph_layout
        text='만약 PC 거치 위치와의 거리가 기본 3.0m를 넘는다면 별매 옵션인 5.0m 로지텍 액티브 케이블 사용을 검토해야 합니다.'
        self.assertEqual(mobile_lines(text),text)
        source='첫 문장입니다.  둘째 문장입니다.\n별매 옵션인\n5.0m 로지텍 액티브 케이블입니다.'
        p=paragraph_layout(source,mobile_lines(source),1)
        self.assertEqual([b['origin'] for b in p['boundaries']],['source','source'])
        self.assertIn('수식어와 대상 분리 가능성',p['boundaries'][-1]['hints'])

    def test_html_design_and_explicit_breaks(self):
        result=compile_markdown_to_naver_html('# 제목\n\n## 주요 설명\n\n### 점검 항목\n\n첫 문장입니다.\n둘째 문장입니다.\n\n| 항목 | 값 |\n|---|---|\n| 거리 | 1m |')
        html=result['html']
        for value in ('font-size: 28px','font-size: 24px','font-size: 19px','font-size: 16px','line-height: 1.8','<br>'):
            self.assertIn(value,html)
        self.assertNotIn('border-bottom:',html)
        self.assertIn('border: 1px solid',html)


if __name__=='__main__':unittest.main()
