from copy import deepcopy
from decimal import Decimal
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path
from streamlit.testing.v1 import AppTest
from excel_parser import parse_excel, scan_folder
from policy_parser import get_document, scan_pdfs
from policy_applicability import case_context
from case_state import new_case, execute_checks
from review_rules import *

class RuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = load_rules()
        cls.docs = {d['document_id']: d for d in [get_document(p) for p in scan_pdfs()]}
        cls.data = parse_excel(scan_folder()[0])
        cls.rule = next(r for r in cls.rules if r['status']=='enabled' and case_context(cls.data)['plan_type'] in r['applicable_plan_types'])
        cls.doc = cls.docs[cls.rule['source_documents'][0]['document_id']]

    def ready(self):
        state = new_state()
        confirm_document(state, self.doc, case_context(self.data), '確認適用', '測試人工確認')
        approve_rule(state, self.rule, True)
        return state

    def run_one(self, state, data=None, docs=None):
        return execute(state, data or self.data, [self.rule], self.docs if docs is None else docs)

    def test_candidates_sources(self):
        self.assertEqual(len(self.rules),20)
        self.assertEqual({s['document_id'] for r in self.rules for s in r['source_documents']},set(self.docs))
        for r in self.rules: self.assertTrue(validate_rule(r))

    def test_page_and_exact_text(self):
        for r in self.rules:
            for s in r['source_documents']:
                self.assertIn(s['text'],self.docs[s['document_id']]['pages'][s['page']-1]['text'])

    def test_missing_source_rejected(self):
        r=deepcopy(self.rule); r['source_documents']=[]
        with self.assertRaises(ValueError): validate_rule(r)

    def test_invented_text_rejected(self):
        r=deepcopy(self.rule); r['source_documents'][0]['text']='不存在的門檻'
        with self.assertRaises(ValueError): validate_rule(r)

    def test_invented_threshold_rejected(self):
        r=deepcopy(self.rule); r['parameters']={'minimum':999}
        with self.assertRaises(ValueError): validate_rule(r)

    def test_unknown_does_not_execute(self):
        result=self.run_one(new_state())['results'][0]
        self.assertFalse(result['executed']); self.assertEqual(result['system_result'],'待人工確認')

    def test_confirmed_document_and_formula_execute(self):
        self.assertTrue(self.run_one(self.ready())['results'][0]['executed'])

    def test_confirmation_not_override_parser(self):
        original=deepcopy(self.doc); s=self.ready()
        self.assertEqual(self.doc,original)
        self.assertEqual(s['documents'][self.doc['document_id']]['system_applicability']['status'],'unknown')

    def test_reject_document_blocks(self):
        s=self.ready(); confirm_document(s,self.doc,case_context(self.data),'確認不適用','')
        r=self.run_one(s)['results'][0]
        self.assertFalse(r['executed']); self.assertEqual(r['system_result'],'不適用')

    def test_formula_requires_confirmation(self):
        s=self.ready(); approve_rule(s,self.rule,False)
        self.assertFalse(self.run_one(s)['results'][0]['executed'])

    def test_data_validation_separate(self):
        case=new_case(self.data); execute_checks(case); old=deepcopy(case)
        self.run_one(self.ready()); self.assertEqual(case,old)

    def test_override_keeps_system_and_history(self):
        s=self.ready(); run=self.run_one(s); original=deepcopy(run['results'][0])
        save_human(s,run,0,'改判','核對精度後採人工意見')
        self.assertEqual(run['results'][0]['system_result'],original['system_result'])
        self.assertEqual(run['results'][0]['human_result'],'改判')
        self.assertEqual(len(run['results'][0]['human_history']),1)

    def test_case_isolation(self):
        store={}; a=state_for(store,'A'); b=state_for(store,'B')
        confirm_document(a,self.doc,case_context(self.data),'確認適用','A note')
        self.assertEqual(b['documents'],{})
        self.assertEqual(state_for(store,'A')['documents'][self.doc['document_id']]['human_note'],'A note')

    def test_version_hash_snapshot(self):
        s=self.ready(); run=self.run_one(s); old=deepcopy(run)
        edited=deepcopy(self.rule); edited['version']='future'
        with tempfile.TemporaryDirectory() as tmp, patch('review_rules.VERSION_STORE',Path(tmp)):
            execute(s,self.data,[edited],self.docs)
        self.assertEqual(run,old)
        self.assertEqual(run['results'][0]['rule_digest'],digest(self.rule))

    def test_same_version_cannot_replace_definition(self):
        with tempfile.TemporaryDirectory() as tmp, patch('review_rules.VERSION_STORE',Path(tmp)):
            pin_rule(self.rule)
            edited=deepcopy(self.rule); edited['notes']='不同解釋'
            with self.assertRaises(ValueError): pin_rule(edited)

    def test_pdf_update_blocks_without_changing_old_run(self):
        s=self.ready(); old=self.run_one(s); snapshot=deepcopy(old)
        updated=deepcopy(self.docs); updated.pop(self.doc['document_id'])
        r=self.run_one(s,docs=updated)['results'][0]
        self.assertEqual(r['system_result'],'無法執行'); self.assertFalse(r['executed'])
        self.assertEqual(old,snapshot)

    def test_changes_make_old_confirmation_stale(self):
        s=self.ready(); run=self.run_one(s)
        confirm_document(s,self.doc,case_context(self.data),'保留待確認','需查新版')
        with self.assertRaises(ValueError): save_human(s,run,0,'改判','')

    def test_missing_not_zero(self):
        d=deepcopy(self.data); d['budget']['fixed_total']=None
        self.assertEqual(self.run_one(self.ready(),d)['results'][0]['system_result'],'資料不足')

    def test_zero_denominator_fails(self):
        d=deepcopy(self.data); d['course']['enrollment']=Decimal(0)
        self.assertEqual(self.run_one(self.ready(),d)['results'][0]['system_result'],'無法執行')

    def test_mismatch_is_suspicion_not_legal_verdict(self):
        d=deepcopy(self.data); d['budget']['hourly_cost']=Decimal('999999')
        self.assertEqual(self.run_one(self.ready(),d)['results'][0]['system_result'],'疑似不符合規則條件')

    def test_cross_plan_blocked(self):
        d=deepcopy(self.data); d['plan']['name']='提升勞工自主學習計畫' if case_context(d)['plan_type']=='industrial' else '產業人才投資計畫'
        self.assertEqual(self.run_one(self.ready(),d)['results'][0]['system_result'],'不適用')

    def test_all_twenty_cases_formula_evidence(self):
        for path in scan_folder():
            data=parse_excel(path); state=new_state()
            r=next(r for r in self.rules if r['status']=='enabled' and case_context(data)['plan_type'] in r['applicable_plan_types'])
            doc=self.docs[r['source_documents'][0]['document_id']]
            confirm_document(state,doc,case_context(data),'確認適用','測試情境，不代表正式適用')
            approve_rule(state,r,True)
            item=execute(state,data,[r],self.docs)['results'][0]
            self.assertTrue(item['executed'])
            for refs in item['field_sources'].values(): self.assertTrue(refs)

    def test_ui_end_to_end_and_navigation(self):
        at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=120).run()
        at.button(key='load').click().run()
        cid=at.session_state['active_case_id']
        at.radio(key='nav').set_value('審查規則檢核').run()
        self.assertTrue(at.button(key='run_rules').disabled)
        at.radio(key='nav').set_value('規定與審查依據').run()
        at.selectbox(key='confirm_doc_'+cid).set_value(self.doc['document_id']).run()
        at.selectbox(key='doc_choice_'+cid+self.doc['document_id']).set_value('確認適用')
        next(b for b in at.button if b.label=='儲存適用版本確認').click().run()
        at.radio(key='nav').set_value('審查規則檢核').run()
        at.button(key='approve_'+cid+self.rule['rule_id']).click().run()
        at.button(key='run_rules').click().run()
        ix=next(i for i,r in enumerate(self.rules) if r['rule_id']==self.rule['rule_id'])
        at.selectbox(key='rule_item_'+cid).set_value(ix).run()
        at.selectbox(key=f'rule_choice_{cid}_1_{ix}').set_value('改判')
        at.text_area(key=f'rule_note_{cid}_1_{ix}').set_value('人工核對')
        next(b for b in at.button if b.label=='儲存規則處理結果').click().run()
        at.radio(key='nav').set_value('案件摘要').run()
        at.radio(key='nav').set_value('審查規則檢核').run()
        self.assertFalse(at.exception)
        result=at.session_state['rule_cases'][cid]['runs'][-1]['results'][ix]
        self.assertEqual(result['human_note'],'人工核對')
        self.assertTrue(result['executed'])

if __name__=='__main__': unittest.main()
