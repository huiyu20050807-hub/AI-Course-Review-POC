import unittest
from copy import deepcopy
from pathlib import Path
from streamlit.testing.v1 import AppTest
from excel_parser import parse_excel,scan_folder,DEFAULT_FOLDER
from case_state import load_case
from final_demo import demo_rows,save_demo,references
from final_ux import evidence_sources
from workflow_ui import resources

ROOT=Path(__file__).parent

class DemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases={}
        for p in scan_folder(DEFAULT_FOLDER)[:2]:load_case(cls.cases,parse_excel(p))

    def test_all_sources_are_exact_pdf_excerpts(self):
        _,docs=resources()
        for refs in references().values():
            for s in refs:
                d=docs[s['document_id']]
                self.assertEqual(s['sha256'],d['sha256'])
                self.assertIn(s['text'],d['pages'][s['page']-1]['text'])
                self.assertGreater(len(s['text']),40)

    def test_real_numbers_missing_data_and_version_limits(self):
        case=deepcopy(next(iter(self.cases.values())))
        rows=demo_rows(case);self.assertEqual(len(rows),8)
        cost=next(r for r in rows if r['key']=='SIM-cost')
        self.assertIn('140.00 ≤ 170',cost['finding'])
        self.assertEqual(cost['status'],'待人工確認')
        self.assertIn('116 上半年',cost['finding'])
        self.assertEqual(next(r for r in rows if r['key']=='SIM-staff')['status'],'資料不足')
        case['case_data']['budget']['hourly_cost']=None
        self.assertEqual(next(r for r in demo_rows(case) if r['key']=='SIM-cost')['status'],'資料不足')

    def test_human_isolation_and_evidence_changes_invalidate(self):
        a,b=deepcopy(list(self.cases.values()))
        r=demo_rows(a)[0];original=deepcopy(r['evidence'])
        save_demo(a,r,'改判','人工意見')
        self.assertEqual(demo_rows(a)[0]['human'],'改判')
        self.assertIsNone(demo_rows(b)[0]['human'])
        self.assertEqual(demo_rows(a)[0]['evidence'],original)
        a['case_data']['course']['name']='更改後的課名'
        self.assertIsNone(demo_rows(a)[0]['human'])

    def test_attention_evidence_and_hidden_subsidy(self):
        app=AppTest.from_file(str(ROOT/'final_poc.py'),default_timeout=120).run()
        self.assertFalse(any('補助資源' in b.label for b in app.button))
        app.button(key='final_start').click().run()
        for _ in range(3):app.button(key='final_step_next').click().run()
        cid=app.session_state['active_case_id']
        self.assertTrue(app.toggle(key='final_filter_'+cid).value)
        # Every first-layer selectable item is a real attention item, with all four evidence blocks.
        keys=list(app.selectbox(key='final_item_'+cid).value for _ in range(1))
        case=app.session_state['cases'][cid]
        keys=['DATA-07','DATA-08',app.session_state['rule_cases'][cid]['runs'][-1]['results'][0]['rule']['rule_id']]+[r['key'] for r in demo_rows(case)]
        for key in keys:
            app.selectbox(key='final_item_'+cid).set_value(key).run()
            self.assertFalse(app.exception)
            ex=next(e for e in app.expander if e.label=='查看完整依據與證據')
            self.assertTrue(ex.table);self.assertTrue(ex.text)
            headings=' '.join(m.value for m in ex.markdown)
            for text in ('A. 案件資料','B. 對應審查規定','C. AI Agent','D. 為什麼'):self.assertIn(text,headings)
            self.assertFalse(any(getattr(v,'type',None)=='json' for v in ex.children.values()))
        app.button(key='final_next_summary').click().run()
        self.assertNotIn('補助資源',' '.join(t.value for t in app.text))

if __name__=='__main__':unittest.main()
