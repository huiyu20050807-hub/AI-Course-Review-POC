"""Run: .venv/Scripts/python.exe -m unittest -v test_poc.py"""
import os
os.environ["POC_STEP_SECONDS"] = "0"
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from demo_data import CHECKS, SECTIONS, HISTORY, BANNER
from review_logic import new_case, save_review, generate_draft, confirm, stale, edit_draft, analysis_completed


class ReviewLogicTests(unittest.TestCase):
    def test_evidence_and_fixed_rules(self):
        self.assertEqual([c["id"] for c in CHECKS], [f"DEMO-R{i:02}" for i in range(1, 9)])
        self.assertEqual([sum(c["status"] == s for c in CHECKS) for s in ["符合", "待確認", "疑似異常"]], [4, 2, 2])
        self.assertEqual(len(HISTORY), 3)
        for c in CHECKS:
            self.assertIn(c["evidence"], SECTIONS[c["section"]])
            if c.get("extra_evidence"):
                self.assertIn(c["extra_evidence"], SECTIONS[c["extra_section"]])

    def test_confirmation_guard_and_stale_draft(self):
        case = new_case()
        case["stage"] = 5
        generate_draft(case)
        self.assertTrue(confirm(case, True))
        for c in CHECKS:
            save_review(case, c["id"], "確認符合" if c["status"] == "符合" else "列為補件事項", "測試備註")
        self.assertTrue(stale(case))
        self.assertTrue(confirm(case, True))
        generate_draft(case)
        self.assertIn("測試備註", case["draft"])
        self.assertTrue(confirm(case, False))
        self.assertFalse(confirm(case, True))
        self.assertIsNotNone(case["confirmed_at"])
        edit_draft(case, case["draft"] + "\n人工修訂")
        self.assertIsNone(case["confirmed_at"])
        self.assertFalse(confirm(case, True))
        save_review(case, "DEMO-R07", "保留待確認", "再次釐清")
        self.assertTrue(stale(case))
        self.assertIsNone(case["confirmed_at"])


class InterfaceFlowTests(unittest.TestCase):
    def setUp(self):
        self.app = AppTest.from_file(str(Path(__file__).with_name("app.py")), default_timeout=20).run()
        self.assert_clean()

    def assert_clean(self):
        self.assertEqual(len(self.app.exception), 0, str(self.app.exception))

    def button(self, label):
        return next(b for b in self.app.button if b.label == label)

    def field(self, kind, label):
        return next(w for w in getattr(self.app, kind) if w.label == label)

    def click(self, label):
        self.button(label).click().run()
        self.assert_clean()

    def load_results(self):
        self.assertTrue(self.button("開始 AI 模擬分析").disabled)
        self.click("載入示範計畫書")
        self.click("預覽示範計畫書")
        self.assertTrue(self.app.session_state["case"]["preview"])
        self.click("開始 AI 模擬分析")
        self.assertEqual(self.app.session_state["case"]["stage"], 5)
        self.assertTrue(analysis_completed(self.app.session_state["case"]))
        self.click("查看審查結果")

    def test_complete_workflow_and_revision(self):
        self.load_results()
        self.assertEqual([m.value for m in self.app.metric], ["4 項", "2 項", "2 項"])
        self.assertEqual(self.app.radio(key="selected_check").value, "DEMO-R07")
        for c in CHECKS:
            self.app.radio(key="selected_check").set_value(c["id"]).run()
            decision = "確認符合" if c["status"] == "符合" else "保留待確認" if c["status"] == "待確認" else "列為補件事項"
            self.field("selectbox", "處理結果").set_value(decision)
            self.field("text_area", "承辦人備註").set_value(f"人工備註 {c['id']}")
            self.click("儲存本項確認")
            self.assert_clean()
        self.click("前往歷史案例與初審意見")
        for h in HISTORY:
            self.app.button(key=h["id"]).click().run()
            self.assert_clean()
            self.assertEqual(self.app.session_state["history_id"], h["id"])
        self.click("產生 AI 初審意見草稿")
        self.assertIn("人工備註 DEMO-R07", self.app.text_area(key="draft_editor").value)
        self.assertTrue(self.button("確認並儲存初審意見").disabled)
        original = self.app.text_area(key="draft_editor").value
        self.app.text_area(key="draft_editor").set_value(original + "\n承辦人補充：依補件結果續辦。").run()
        self.click("儲存草稿")
        self.app.checkbox(key="ack").check().run()
        self.click("確認並儲存初審意見")
        self.assertIsNotNone(self.app.session_state["case"]["confirmed_at"])
        self.click("返回檢核")
        self.app.radio(key="selected_check").set_value("DEMO-R07").run()
        self.assertEqual(self.field("text_area", "承辦人備註").value, "人工備註 DEMO-R07")
        self.field("text_area", "承辦人備註").set_value("更新備註")
        self.click("儲存本項確認")
        self.click("前往歷史案例與初審意見")
        self.assertTrue(self.button("確認並儲存初審意見").disabled)
        self.assertIsNone(self.app.session_state["case"]["confirmed_at"])
        self.click("重新產生草稿")
        self.click("保留目前版本並重新產生")
        self.assertIn("更新備註", self.app.text_area(key="draft_editor").value)
        self.assertTrue(any("承辦人補充" in v["text"] for v in self.app.session_state["case"]["versions"]))
        self.click("重設示範")
        self.click("取消重設")
        self.assertTrue(self.app.session_state["case"]["loaded"])
        self.click("重設示範")
        self.click("確認重設")
        self.assertFalse(self.app.session_state["case"]["loaded"])
        self.assertIsNone(self.app.session_state["case"]["draft"])

    def test_pending_filter_and_unreviewed_guard(self):
        self.load_results()
        self.app.selectbox(key="status_filter").select("待確認").run()
        self.assertEqual(len(self.app.radio(key="selected_check").options), 2)
        self.app.checkbox(key="only_pending").check().run()
        self.field("selectbox", "處理結果").select("保留待確認")
        self.click("儲存本項確認")
        self.field("selectbox", "處理結果").select("列為補件事項")
        self.click("儲存本項確認")
        self.assertEqual(len(self.app.radio), 0)
        self.click("前往歷史案例與初審意見")
        self.click("產生 AI 初審意見草稿")
        self.assertTrue(self.button("確認並儲存初審意見").disabled)
        self.assertIn("尚未完成檢視：DEMO-R01", self.app.text_area(key="draft_editor").value)

    def test_analysis_failure_retry(self):
        self.click("載入示範計畫書")
        self.app.session_state["case"]["error"] = "測試失敗狀態"
        self.app.session_state["page"] = "AI 模擬分析進度"
        self.app.run()
        self.assert_clean()
        self.click("重新分析")
        self.assertTrue(analysis_completed(self.app.session_state["case"]))


if __name__ == "__main__":
    unittest.main()
