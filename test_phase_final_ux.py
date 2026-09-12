from pathlib import Path
from unittest.mock import patch
import unittest
import streamlit as st
from streamlit.testing.v1 import AppTest
from final_ux import human_progress

ROOT=Path(__file__).parent

class FinalUXTests(unittest.TestCase):
    def started(self):
        app=AppTest.from_file(str(ROOT/'final_poc.py'),default_timeout=120).run()
        app.button(key='final_start').click().run()
        for _ in range(3):app.button(key='final_step_next').click().run()
        self.assertFalse(app.exception)
        return app

    def test_manual_steps_no_automatic_transition(self):
        app=AppTest.from_file(str(ROOT/'final_poc.py'),default_timeout=120).run()
        app.button(key='final_start').click().run()
        for stage in (1,2,3):
            self.assertEqual(app.session_state['final_progress']['stage'],stage)
            app.run()
            self.assertEqual(app.session_state['final_progress']['stage'],stage)
            self.assertNotEqual(app.session_state['final_nav'],'審查結果')
            app.button(key='final_step_next').click().run()
        self.assertEqual(app.session_state['final_progress']['stage'],4)
        self.assertEqual(app.session_state['final_nav'],'審查結果')
        self.assertNotIn('sleep(', (ROOT/'final_poc.py').read_text(encoding='utf-8'))

    def test_three_required_saved_and_summary_excludes_normal(self):
        app=self.started();cid=app.session_state['active_case_id']
        rule=app.session_state['rule_cases'][cid]['runs'][-1]
        ids=list(app.selectbox(key='final_item_'+cid).options)
        from final_demo import demo_rows
        ids=['DATA-07','DATA-08',rule['results'][0]['rule']['rule_id']]+[r['key'] for r in demo_rows(app.session_state['cases'][cid])]
        for ident in ids:
            app.selectbox(key='final_item_'+cid).set_value(ident).run()
            prefix=cid+ident+str(rule['run_id'] if ident.startswith('REV') else 0)
            app.selectbox(key='final_choice_'+prefix).set_value('要求補充資料')
            app.text_area(key='final_note_'+prefix).set_value('請補相關佐證')
            next(b for b in app.button if b.label=='儲存本項確認').click().run()
        self.assertTrue(any('承辦人已處理：11 / 11' in m.value for m in app.markdown))
        self.assertTrue(any('系統自動檢核正常：6 項' in m.value for m in app.markdown))
        self.assertIsNone(app.session_state['cases'][cid]['reviews']['DATA-01']['saved_at'])
        next(b for b in app.button if b.label=='審查摘要').click().run()
        text='\n'.join(x.value for x in app.text).split('五、承辦人處理結果')[1]
        self.assertIn('需人工處理共 11 項，已完成 11 / 11',text)
        self.assertIn('另有 6 項',text)
        self.assertNotIn('課表時數與計畫時數',text)
        self.assertNotIn('尚未處理',text)
        self.assertEqual(human_progress([{'status':'資料正常','reviewed':False}]),([],0,1))

    def test_human_evidence_nested_technical_data_preserved(self):
        app=self.started()
        outer=next(e for e in app.expander if e.label=='查看完整依據與證據')
        tech=next(e for e in outer.expander if e.label=='進階技術資訊')
        self.assertFalse(tech.proto.expanded);self.assertTrue(tech.json)
        self.assertFalse(any(getattr(c,'type',None)=='json' for c in outer.children.values()))
        text='\n'.join(m.value for m in outer.markdown)
        for label in ['A. 案件資料','B. 對應審查規定','C. AI Agent 模擬比對','D. 為什麼']:self.assertIn(label,text)
        self.assertTrue(outer.table)
        self.assertTrue(any('單一人時成本' in t.value for t in outer.text))
        self.assertFalse(app.exception)

if __name__=='__main__':unittest.main()
