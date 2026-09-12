from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import unittest
from streamlit.testing.v1 import AppTest
from excel_parser import parse_excel,scan_folder
from policy_parser import get_document,scan_pdfs
from policy_applicability import case_context
from review_rules import load_rules,state_for,confirm_document,approve_rule,execute,save_human
import workflow as flow

ROOT=Path(__file__).parent

class UXTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules=load_rules()
        cls.docs={d['document_id']:d for d in map(get_document,scan_pdfs())}
        cls.a,cls.b=[parse_excel(p) for p in scan_folder()[:2]]

    def setup_case(self):
        cases,states={},{}
        cid=flow.start(cases,states,self.a,self.rules,self.docs)
        return cases[cid],states[cid]

    def test_core_and_previous_tests_unchanged(self):
        baseline=json.loads((ROOT/'phase2b1_baseline.json').read_text())
        for name,h in baseline.items():self.assertEqual(sha256((ROOT/name).read_bytes()).hexdigest(),h,name)

    def test_unified_data_and_review(self):
        case,state=self.setup_case();rows=flow.items(case,state)
        self.assertEqual(len(rows),9)
        self.assertEqual({r['kind'] for r in rows},{'資料品質檢查','規定條件檢核'})

    def test_four_counts(self):
        case,state=self.setup_case()
        self.assertEqual(flow.counts(flow.items(case,state)),{'資料正常':6,'待人工確認':1,'疑似異常':0,'資料不足':2})

    def test_needs_filter(self):
        case,state=self.setup_case(); rows=flow.priorities(flow.items(case,state))
        self.assertEqual(len(rows),3)
        self.assertTrue(all(r['status']!='資料正常' for r in rows))

    def test_priority_sort(self):
        case,state=self.setup_case()
        case['checks'][0]['status']='資料不一致'
        rows=flow.items(case,state)
        self.assertEqual(rows[0]['status'],'疑似異常')
        self.assertEqual(rows[1]['status'],'待人工確認')

    def test_full_evidence_preserved(self):
        case,state=self.setup_case()
        row=next(r for r in flow.items(case,state) if r['kind']=='規定條件檢核')
        self.assertEqual(row['evidence'],state['runs'][-1]['results'][0])
        self.assertTrue(row['evidence']['field_sources'])
        self.assertTrue(row['evidence']['rule']['source_documents'][0]['sha256'])

    def test_unknown_never_calculated(self):
        case,state=self.setup_case()
        rule=next(r for r in flow.items(case,state) if r['kind']=='規定條件檢核')
        self.assertFalse(rule['executed'])

    def test_settings_resume_executes_existing_rule(self):
        case,state=self.setup_case();r=flow.applicable_rules(self.a,self.rules)[0]
        d=self.docs[r['source_documents'][0]['document_id']]
        confirm_document(state,d,case_context(self.a),'確認適用','測試')
        approve_rule(state,r,True)
        flow.synchronize(case,state,self.rules,self.docs)
        self.assertTrue(state['runs'][-1]['results'][0]['executed'])

    def test_human_data_saved_in_legacy_and_summary(self):
        case,state=self.setup_case();row=flow.items(case,state)[0]
        row=next(r for r in flow.items(case,state) if r['key']=='DATA-07')
        flow.save(case,state,row,'改判','附件另有提供')
        refreshed=next(r for r in flow.items(case,state) if r['key']=='DATA-07')
        self.assertEqual(refreshed['human'],'改判')
        self.assertEqual(case['reviews']['DATA-07']['note'],'附件另有提供')
        self.assertIn('承辦人已處理 1/9',flow.summary_text(case,flow.items(case,state)))

    def test_a_b_a_no_contamination(self):
        cases,states={},{}
        for data in (self.a,self.b):flow.start(cases,states,data,self.rules,self.docs)
        a,b=self.a['case_id'],self.b['case_id']
        flow.save(cases[a],states[a],flow.items(cases[a],states[a])[0],'改判','A')
        flow.start(cases,states,self.a,self.rules,self.docs)
        self.assertTrue(any(r['note']=='A' for r in flow.items(cases[a],states[a])))
        self.assertFalse(any(r['reviewed'] for r in flow.items(cases[b],states[b])))

    def test_summary_exact_current_results(self):
        case,state=self.setup_case();rows=flow.items(case,state);s=flow.summary_text(case,rows)
        for k,v in flow.counts(rows).items():self.assertIn(f'{k} {v} 項',s)
        self.assertIn('實際已執行 8 項',s)
        self.assertIn('不是 AI 初審意見',s)

    def test_advanced_human_result_survives_main_entry(self):
        case,state=self.setup_case()
        run=execute(state,self.a,self.rules,self.docs)
        index=next(i for i,x in enumerate(run['results']) if x['rule']['rule_id']==flow.applicable_rules(self.a,self.rules)[0]['rule_id'])
        save_human(state,run,index,'改判','進階頁確認')
        flow.synchronize(case,state,self.rules,self.docs)
        self.assertTrue(any(r['note']=='進階頁確認' for r in flow.items(case,state)))

    def test_confirmation_change_invalidates_rules_only(self):
        case,state=self.setup_case()
        row=next(r for r in flow.items(case,state) if r['key']=='DATA-01')
        flow.save(case,state,row,'確認系統結果','資料備註')
        r=flow.applicable_rules(self.a,self.rules)[0];d=self.docs[r['source_documents'][0]['document_id']]
        confirm_document(state,d,case_context(self.a),'確認不適用','重新核對')
        flow.synchronize(case,state,self.rules,self.docs)
        self.assertEqual(state['runs'][-1]['results'][0]['system_result'],'不適用')
        self.assertEqual(case['reviews']['DATA-01']['note'],'資料備註')

    def test_ui_direct_start_filter_confirm_summary(self):
        app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=120).run()
        app.button(key='smart_start').click().run()
        self.assertFalse(app.exception)
        cid=app.session_state['active_case_id']
        self.assertEqual(app.session_state['nav'],'審查結果')
        self.assertEqual([m.value for m in app.metric],['6 項','1 項','0 項','2 項'])
        self.assertTrue(any('本案尚未設定適用審查依據' in w.value for w in app.warning))
        self.assertTrue(all('REV-' not in o and 'DATA-' not in o for o in app.selectbox(key='ux_item_'+cid).options))
        evidence=next(e for e in app.expander if e.label=='查看完整依據與證據')
        self.assertFalse(evidence.proto.expanded)
        self.assertTrue(evidence.json)
        app.checkbox(key='needs_'+cid).check().run()
        self.assertEqual(len(app.selectbox(key='ux_item_'+cid).options),3)
        app.selectbox(key='ux_item_'+cid).set_value('DATA-07').run()
        app.selectbox(key=f'ux_choice_{cid}_DATA-07_0').set_value('要求補充資料')
        app.text_area(key=f'ux_note_{cid}_DATA-07_0').set_value('請補師資附件')
        next(b for b in app.button if b.label=='儲存本項確認').click().run()
        app.button(key='make_summary').click().run()
        self.assertTrue(any('請補師資附件' in t.value and '承辦人已處理 1/9' in t.value for t in app.text))
        next(b for b in app.button if b.label=='返回審查結果').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('承辦人已檢視 1 / 9' in m.value for m in app.markdown))

    def test_ui_settings_return(self):
        app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=120).run()
        app.button(key='smart_start').click().run();cid=app.session_state['active_case_id']
        app.button(key='setup_basis').click().run()
        r=flow.applicable_rules(self.a,self.rules)[0];did=r['source_documents'][0]['document_id']
        app.selectbox(key='confirm_doc_'+cid).set_value(did).run()
        app.selectbox(key='doc_choice_'+cid+did).set_value('確認適用')
        next(b for b in app.button if b.label=='儲存適用版本確認').click().run()
        app.button(key='simple_approve_'+r['rule_id']).click().run()
        app.button(key='return_workflow').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.session_state['rule_cases'][cid]['runs'][-1]['results'][0]['executed'])

if __name__=='__main__':unittest.main()
