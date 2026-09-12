"""狀態同步回歸：檢查實際畫面、提交與跨頁結果，不只檢查內部旗標。"""
import os
os.environ["POC_STEP_SECONDS"] = "0"
import unittest
from unittest.mock import patch
from pathlib import Path
from streamlit.testing.v1 import AppTest
from streamlit.runtime.memory_media_file_storage import MemoryMediaFileStorage
from demo_data import CHECKS
from review_logic import (reviewed_count, stale, new_case, analysis_snapshot,
                          start_analysis, advance_analysis, save_review, generate_draft)


class StateInvariantTests(unittest.TestCase):
    def test_every_analysis_snapshot_and_retry(self):
        case = new_case()
        self.assertEqual(analysis_snapshot(case)["states"], ["尚未開始"] * 5)
        start_analysis(case)
        for completed in range(6):
            snapshot = analysis_snapshot(case)
            self.assertEqual(snapshot["completed"], completed)
            self.assertEqual(snapshot["progress"], completed / 5)
            self.assertEqual(snapshot["states"].count("已完成"), completed)
            self.assertEqual(snapshot["finished"], completed == 5)
            if completed < 5:
                self.assertEqual(snapshot["states"][completed], "處理中")
                self.assertEqual(snapshot["states"][completed+1:], ["尚未開始"] * (4-completed))
            advance_analysis(case)
        self.assertEqual(case["stage"], 5)
        start_analysis(case)
        advance_analysis(case)
        case["error"] = "模擬中斷"
        snapshot = analysis_snapshot(case)
        self.assertEqual(snapshot["states"], ["已完成", "處理失敗", "尚未開始", "尚未開始", "尚未開始"])
        advance_analysis(case)
        self.assertEqual(case["stage"], 1)
        start_analysis(case)
        self.assertEqual(analysis_snapshot(case)["completed"], 0)

    def test_save_idempotent_notes_invalidate_and_sessions_independent(self):
        case, other = new_case(), new_case()
        save_review(case, "DEMO-R01", "確認符合", "第一次備註")
        generate_draft(case)
        revision = case["revision"]
        self.assertFalse(save_review(case, "DEMO-R01", "確認符合", "第一次備註"))
        self.assertEqual(case["revision"], revision)
        self.assertFalse(stale(case))
        save_review(case, "DEMO-R01", "確認符合", "只修改備註")
        self.assertEqual(reviewed_count(case), 1)
        self.assertTrue(stale(case))
        self.assertEqual(reviewed_count(other), 0)
        self.assertEqual(other["reviews"]["DEMO-R01"]["note"], "")


class StateSyncTests(unittest.TestCase):
    def setUp(self):
        self.app = AppTest.from_file(str(Path(__file__).with_name("app.py")), default_timeout=20).run()

    def clean(self):
        self.assertFalse(self.app.exception, str(self.app.exception))

    def click(self, label):
        next(b for b in self.app.button if b.label == label).click().run()
        self.clean()

    def text(self):
        return "\n".join(m.value for m in self.app.markdown)

    def field(self, kind, label):
        return next(w for w in getattr(self.app, kind) if w.label == label)

    def start(self):
        self.click("載入示範計畫書")
        self.click("開始 AI 模擬分析")

    def save(self, rid, decision, note):
        self.app.radio(key="selected_check").set_value(rid).run()
        self.field("selectbox", "處理結果").set_value(decision)
        self.field("text_area", "承辦人備註").set_value(note)
        self.click("儲存本項確認")

    def test_analysis_render_and_reset(self):
        self.assertIn("尚未分析", self.text())
        self.start()
        stages = "\n".join(m.value for m in self.app.markdown if 'class="stage' in m.value)
        self.assertEqual(stages.count("｜　已完成<br>"), 5)
        self.assertNotIn("處理中", stages)
        self.assertNotIn("尚未開始", stages)
        self.assertEqual(self.app.get("progress")[0].proto.value, 100)
        self.assertIn("5／5", self.app.get("progress")[0].proto.text)
        self.app.run()
        self.clean()
        self.click("重設示範")
        self.click("確認重設")
        self.assertIn("尚未分析", self.text())
        self.assertEqual(reviewed_count(self.app.session_state["case"]), 0)

    def test_changes_are_committed_only_by_save(self):
        self.start()
        self.click("查看審查結果")
        self.app.radio(key="selected_check").set_value("DEMO-R01").run()
        self.field("selectbox", "處理結果").set_value("確認符合").run()
        self.assertEqual(reviewed_count(self.app.session_state["case"]), 0)
        self.field("text_area", "承辦人備註").set_value("R01 已核對")
        self.click("儲存本項確認")
        self.assertEqual(reviewed_count(self.app.session_state["case"]), 1)
        self.assertIn("已檢視 1／8", self.text())
        self.assertIn("尚未確認 7 項", self.text())

    def test_acceptance_cross_page_all_eight_and_stale(self):
        self.start()
        self.click("查看審查結果")
        expected = {}
        for i, c in enumerate(CHECKS, 1):
            rid = c["id"]
            decision = "確認符合" if i <= 4 else "保留待確認" if i <= 6 else "列為補件事項"
            note = f"備註 {rid}：已核對。"
            expected[rid] = {"decision": decision, "note": note}
            self.save(rid, decision, note)
            self.assertIn(f"已檢視 {i}／8", self.text())
            options = self.app.radio(key="selected_check").options
            self.assertTrue(any(c["name"] in o and f"承辦人：{decision}" in o for o in options))
            if i == 1:
                self.app.radio(key="selected_check").set_value("DEMO-R02").run()
                self.app.radio(key="selected_check").set_value(rid).run()
                self.assertEqual(self.field("selectbox", "處理結果").value, decision)
                self.assertEqual(self.field("text_area", "承辦人備註").value, note)
        self.assertIn("尚未確認 0 項", self.text())
        self.click("前往歷史案例與初審意見")
        self.assertIn("已檢視 8／8", self.text())
        self.assertIn("尚未確認 0 項", self.text())
        self.click("產生 AI 初審意見草稿")
        self.assertIn("尚未完成檢視：無", self.field("text_area", "初審意見（可人工編輯）").value)
        self.app.checkbox(key="ack").check().run()
        self.click("確認並儲存初審意見")
        self.assertIsNotNone(self.app.session_state["case"]["confirmed_at"])
        self.click("返回檢核")
        self.assertEqual(self.app.session_state["case"]["reviews"], expected)
        for rid, value in expected.items():
            self.app.radio(key="selected_check").set_value(rid).run()
            self.assertEqual(self.field("selectbox", "處理結果").value, value["decision"])
            self.assertEqual(self.field("text_area", "承辦人備註").value, value["note"])
        self.save("DEMO-R01", "尚未確認", "需再次核對")
        self.assertIn("已檢視 7／8", self.text())
        self.assertIn("尚未確認 1 項", self.text())
        self.assertTrue(stale(self.app.session_state["case"]))
        self.assertIsNone(self.app.session_state["case"]["confirmed_at"])
        self.click("前往歷史案例與初審意見")
        self.assertIn("已檢視 7／8", self.text())
        self.assertTrue(next(b for b in self.app.button if b.label == "確認並儲存初審意見").disabled)
        self.click("重新產生草稿")
        self.click("保留目前版本並重新產生")
        draft = self.field("text_area", "初審意見（可人工編輯）").value
        self.assertIn("尚未完成檢視：DEMO-R01", draft)
        self.assertIn("需再次核對", draft)

    def test_release_export_navigation_and_full_reset(self):
        self.start()
        self.click("查看審查結果")
        for c in CHECKS:
            self.save(c["id"], "確認符合" if c["status"] == "符合" else "列為補件事項", f"封版核對 {c['id']}")
        for index in [0, 1, 2, 3, 2, 3]:
            self.app.button(key=f"nav{index}").click().run()
            self.clean()
            self.assertEqual(reviewed_count(self.app.session_state["case"]), 8)
            if index in (2, 3):
                self.assertIn("已檢視 8／8", self.text())
                self.assertIn("尚未確認 0 項", self.text())
        self.click("產生 AI 初審意見草稿")
        self.click("儲存草稿")
        saved_text = self.app.session_state["case"]["draft"]
        self.click("返回檢核")
        self.click("前往歷史案例與初審意見")
        self.assertEqual(self.field("text_area", "初審意見（可人工編輯）").value, saved_text)
        self.app.checkbox(key="ack").check().run()
        storage = MemoryMediaFileStorage("/mock/media")
        with patch("streamlit.testing.v1.app_test.MemoryMediaFileStorage", return_value=storage):
            self.click("確認並儲存初審意見")
        download = self.app.get("download_button")[0].proto
        self.assertFalse(download.disabled)
        self.assertTrue(download.url)
        media = storage.get_file(download.url.rsplit("/", 1)[-1])
        self.assertEqual(media.filename, "DEMO-001_初審意見.txt")
        self.assertEqual(media.mimetype, "text/plain")
        text = media.content.decode("utf-8-sig")
        self.assertIn("匯出狀態：初審意見已確認", text)
        self.assertIn("二、AI 初步檢核結果", text)
        self.assertNotIn("二、AI 檢核符合項目", text)
        statement = "承辦人處理結果可與 AI 初步判斷不同，以人工確認結果為準。"
        self.assertLess(text.index("三、待確認與疑似異常"), text.index(statement))
        self.assertLess(text.index(statement), text.index("四、承辦人確認與處理結果"))
        for c in CHECKS:
            self.assertIn(f"封版核對 {c['id']}", text)
        self.assertEqual(self.app.session_state["case"]["draft"], saved_text)
        self.click("重設示範")
        self.click("確認重設")
        self.assertEqual(self.app.session_state["case"], new_case())
        self.assertEqual(self.app.session_state["page"], "首頁")
        self.assertFalse(self.app.get("download_button"))
        self.assertTrue(next(b for b in self.app.button if b.label == "開始 AI 模擬分析").disabled)


if __name__ == "__main__":
    unittest.main()
