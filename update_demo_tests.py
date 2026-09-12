from pathlib import Path
p=Path('test_phase_final.py');s=p.read_text(encoding='utf-8')
s=s.replace("app=self.app();app.button(key='final_start').click().run();return app","app=self.app();app.button(key='final_start').click().run();self.finish(app);return app\n\n    def finish(self,app):\n        for _ in range(3):app.button(key='final_step_next').click().run()")
s=s.replace("app.button(key='final_start').click().run()\n", "app.button(key='final_start').click().run();self.finish(app)\n")
s=s.replace("['stage'],5","['stage'],4").replace("['6 項','1 項','0 項','2 項']","['6 項','8 項','0 項','3 項']")
a=s.index("        app.button(key='final_next_resources')");b=s.index("        self.assertFalse(app.exception)",a)
s=s[:a]+"        app.button(key='final_next_summary').click().run()\n"+s[b:]
s=s.replace('需人工處理共 3 項，已完成 1 / 3','需人工處理共 11 項，已完成 1 / 11')
s=s.replace("app.selectbox(key='final_item_'+a).set_value('DATA-01')","app.toggle(key='final_filter_'+a).set_value(False).run()\n        app.selectbox(key='final_item_'+a).set_value('DATA-01')")
p.write_text(s,encoding='utf-8')
p=Path('test_phase_final_ux.py');s=p.read_text(encoding='utf-8');a=s.index('    def test_progress_feedback_order_and_duration');b=s.index('    def test_three_required',a)
s=s[:a]+'''    def test_manual_steps_no_automatic_transition(self):
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

'''+s[b:]
s=s.replace("app.button(key='final_start').click().run()\n        self.assertFalse(app.exception)","app.button(key='final_start').click().run()\n        for _ in range(3):app.button(key='final_step_next').click().run()\n        self.assertFalse(app.exception)")
s=s.replace("ids=['DATA-07','DATA-08',rule['results'][0]['rule']['rule_id']]","ids=list(app.selectbox(key='final_item_'+cid).options)\n        from final_demo import demo_rows\n        ids=['DATA-07','DATA-08',rule['results'][0]['rule']['rule_id']]+[r['key'] for r in demo_rows(app.session_state['cases'][cid])]")
s=s.replace('承辦人已處理：3 / 3','承辦人已處理：11 / 11').replace('需人工處理共 3 項，已完成 3 / 3','需人工處理共 11 項，已完成 11 / 11')
s=s.replace("['案件資料來源','審查依據','系統如何檢查']","['A. 案件資料','B. 對應審查規定','C. AI Agent 模擬比對','D. 為什麼']")
p.write_text(s,encoding='utf-8')
