import unittest
from pathlib import Path
from hashlib import sha256
import json
import tempfile
import shutil
from streamlit.testing.v1 import AppTest
from policy_parser import scan_pdfs
import subsidy_resources as resources

ROOT=Path(__file__).parent

class FinalTests(unittest.TestCase):
    def app(self):return AppTest.from_file(str(ROOT/'final_poc.py'),default_timeout=120).run()

    def started(self):
        app=self.app();app.button(key='final_start').click().run();self.finish(app);return app

    def finish(self,app):
        for _ in range(3):app.button(key='final_step_next').click().run()

    def test_twenty_selection_summary_progress_and_counts(self):
        app=self.app()
        self.assertEqual(len(app.selectbox(key='final_candidate').options),20)
        self.assertTrue(all(s.startswith('[') for s in app.selectbox(key='final_candidate').options))
        self.assertTrue(any('大同大學' in x.value for x in app.markdown))
        app.button(key='final_start').click().run();self.finish(app)
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['final_progress']['stage'],4)
        self.assertEqual(app.session_state['final_nav'],'審查結果')
        self.assertEqual([m.value for m in app.metric],['6 項','8 項','0 項','3 項'])
        self.assertFalse(any('AI 語意' in b.label for b in app.button))

    def test_save_evidence_resource_search_and_summary(self):
        app=self.started();cid=app.session_state['active_case_id']
        app.selectbox(key='final_item_'+cid).set_value('DATA-07').run()
        evidence=next(e for e in app.expander if e.label=='查看完整依據與證據')
        self.assertFalse(evidence.proto.expanded);self.assertTrue(evidence.json)
        prefix=cid+'DATA-07'+'0'
        app.selectbox(key='final_choice_'+prefix).set_value('要求補充資料')
        app.text_area(key='final_note_'+prefix).set_value('請補師資資料')
        next(b for b in app.button if b.label=='儲存本項確認').click().run()
        app.button(key='final_next_summary').click().run()
        self.assertFalse(app.exception)
        text='\n'.join(x.value for x in app.text)
        self.assertIn('正常 6 項',text);self.assertIn('請補師資資料',text)
        self.assertIn('需人工處理共 11 項，已完成 1 / 11',text)
        self.assertIn('四、相關審查依據',text)

    def test_settings_return_same_case_and_rule_source(self):
        app=self.started();cid=app.session_state['active_case_id']
        app.button(key='final_setup').click().run()
        from policy_parser import get_document,POLICY_FOLDER
        doc=get_document(POLICY_FOLDER/'產業人才投資計畫作業手冊.pdf');did=doc['document_id']
        app.selectbox(key='confirm_doc_'+cid).set_value(did).run()
        app.selectbox(key='doc_choice_'+cid+did).set_value('確認適用')
        next(b for b in app.button if b.label=='儲存適用版本確認').click().run()
        app.button(key='final_approve').click().run()
        app.button(key='final_return').click().run()
        self.assertFalse(app.exception);self.assertEqual(app.session_state['active_case_id'],cid)
        self.assertTrue(app.session_state['rule_cases'][cid]['runs'][-1]['results'][0]['executed'])
        next(b for b in app.button if b.label=='審查摘要').click().run()
        self.assertTrue(any('產業人才投資計畫作業手冊.pdf，PDF 第 26 頁' in x.value for x in app.text))

    def test_a_b_a_preserves_processing(self):
        app=self.started();a=app.session_state['active_case_id']
        app.toggle(key='final_filter_'+a).set_value(False).run()
        app.selectbox(key='final_item_'+a).set_value('DATA-01').run();prefix=a+'DATA-01'+'0'
        app.selectbox(key='final_choice_'+prefix).set_value('改判')
        app.text_area(key='final_note_'+prefix).set_value('A 案備註')
        next(b for b in app.button if b.label=='儲存本項確認').click().run()
        next(b for b in app.button if b.label=='首頁／選擇案件').click().run()
        app.selectbox(key='final_candidate').select_index(1).run();app.button(key='final_start').click().run();self.finish(app)
        b=app.session_state['active_case_id'];self.assertNotEqual(a,b)
        self.assertFalse(app.session_state['cases'][b]['reviews']['DATA-01']['saved_at'])
        next(b for b in app.button if b.label=='首頁／選擇案件').click().run()
        app.selectbox(key='final_candidate').select_index(0).run();app.button(key='final_start').click().run();self.finish(app)
        self.assertEqual(app.session_state['active_case_id'],a)
        self.assertEqual(app.session_state['cases'][a]['reviews']['DATA-01']['note'],'A 案備註')

    def test_resource_sources_pages_keywords_and_read_only(self):
        # Original optional folder was removed outside this patch. Exercise the preserved
        # lookup against byte-identical archived source PDFs without touching v1.
        with tempfile.TemporaryDirectory() as folder:
            for archive in (ROOT/'resource_cache').iterdir():
                data=json.loads(next(archive.glob('*.json')).read_text(encoding='utf-8'))
                self.assertEqual(sha256((archive/'source.pdf').read_bytes()).hexdigest(),data['sha256'])
                shutil.copyfile(archive/'source.pdf',Path(folder)/data['file_name'])
            self.verify_resource_sources(Path(folder))

    def verify_resource_sources(self,folder):
        files=scan_pdfs(folder);before={str(p):sha256(p.read_bytes()).hexdigest() for p in files}
        docs=resources.catalogue(folder);self.assertEqual(len(docs),9)
        lookup={d['document_id']:d for d in docs}
        for query in ('青年','在職訓練','企業人才','特定對象','職業訓練','補助','失業者'):
            hits=resources.search(docs,query)
            # Exact search does not manufacture results for a phrase absent in the documents.
            for hit in hits:
                self.assertIn(hit['text'],lookup[hit['document_id']]['pages'][hit['page_start']-1]['text'])
                self.assertTrue(hit['file_name']);self.assertTrue(hit['category'])
                self.assertNotIn('applicability',hit)
        self.assertTrue(resources.search(docs,'青年'))
        self.assertEqual(before,{str(p):sha256(p.read_bytes()).hexdigest() for p in files})

    def test_v1_seal_unchanged(self):
        v1=ROOT.parent/'AI_Course_Review_POC'
        manifest=json.loads((v1/'封版檔案校驗.json').read_text(encoding='utf-8-sig'))
        for item in manifest['files']:self.assertEqual(sha256((v1/item['file']).read_bytes()).hexdigest().upper(),item['sha256'])

if __name__=='__main__':unittest.main()
