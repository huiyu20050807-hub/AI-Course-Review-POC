"""Acceptance tests use source files read-only; mutations are XML in memory."""
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
import re
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED
import openpyxl
from streamlit.testing.v1 import AppTest
from excel_parser import DEFAULT_FOLDER, parse_excel, parse_excel_bytes, scan_folder
from case_state import load_case, new_case, execute_checks, save_review, review_counts
from data_checks import run_checks, STATUSES

ROOT = Path(__file__).parent
V1 = ROOT.parent / "AI_Course_Review_POC"
HOURS = [54,36,45,36,30,42,47,70,47,16,42,48,77,40,54,24,90,54,54,89]
COUNTS = [18,12,15,12,10,14,14,20,17,10,14,16,22,10,18,8,30,18,18,27]
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def mutate(content, replacements=None, shift_from=None, shift=0):
    """Never saves a workbook or touches the source file."""
    dest = BytesIO()
    with ZipFile(BytesIO(content)) as src, ZipFile(dest, "w", ZIP_DEFLATED) as out:
        for name in src.namelist():
            payload = src.read(name)
            if name == "xl/worksheets/sheet1.xml":
                tree = ET.fromstring(payload)
                for cell in tree.iter(NS + "c"):
                    if cell.attrib["r"] in (replacements or {}):
                        val = replacements[cell.attrib["r"]]
                        for child in list(cell):
                            cell.remove(child)
                        cell.attrib.pop("t", None)
                        if val is None:
                            pass
                        elif isinstance(val, (int, float)):
                            ET.SubElement(cell, NS + "v").text = str(val)
                        elif str(val).startswith("="):
                            ET.SubElement(cell, NS + "f").text = str(val)[1:]
                        else:
                            cell.set("t", "inlineStr")
                            ET.SubElement(ET.SubElement(cell, NS + "is"), NS + "t").text = str(val)
                if shift_from is not None:
                    def shifted(ref):
                        return re.sub(r"([A-Z]+)(\d+)", lambda m: m[1] + str(int(m[2]) + shift if int(m[2]) >= shift_from else int(m[2])), ref)
                    for node in tree.iter():
                        if node.tag in (NS + "c",):
                            node.set("r", shifted(node.attrib["r"]))
                        elif node.tag == NS + "row" and int(node.attrib["r"]) >= shift_from:
                            node.set("r", str(int(node.attrib["r"]) + shift))
                        elif node.tag in (NS + "mergeCell", NS + "dimension"):
                            node.set("ref", shifted(node.attrib["ref"]))
                payload = ET.tostring(tree, encoding="utf-8", xml_declaration=True)
            out.writestr(name, payload)
    return dest.getvalue()


class ExcelAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths = scan_folder()
        cls.data = [parse_excel(p) for p in cls.paths]
        cls.content = cls.paths[0].read_bytes()

    def test_20_workbooks_load_and_schema(self):
        self.assertEqual(len(self.data), 20)
        for d in self.data:
            with self.subTest(file=d["source"]["filename"]):
                self.assertEqual(d["parse_report"]["status"], "success", d["parse_report"])
                self.assertTrue(set(("source", "plan", "organization", "course", "objectives", "audience", "sessions", "instructors", "assistants", "facilities", "budget", "other_sections", "derived", "field_sources", "parse_report")) <= d.keys())

    def test_20_core_values_against_independent_source_cells(self):
        for path, d in zip(self.paths, self.data):
            with self.subTest(file=path.name):
                book = openpyxl.load_workbook(BytesIO(path.read_bytes()), data_only=False)
                sheet = book.active
                self.assertEqual(d["course"]["name"], sheet["D7"].value)
                self.assertEqual(d["organization"]["name"], sheet["D5"].value)
                self.assertEqual(d["course"]["occupation"], sheet["D6"].value)
                self.assertEqual(d["course"]["declared_hours"], Decimal(sheet["K10"].value))
                self.assertEqual(d["plan"]["name"], sheet["A2"].value)
                book.close()

    def test_323_sessions_and_20_audited_totals(self):
        self.assertEqual([len(d["sessions"]) for d in self.data], COUNTS)
        self.assertEqual(sum(len(d["sessions"]) for d in self.data), 323)
        self.assertEqual([d["derived"]["schedule_hours"] for d in self.data], HOURS)

    def test_skill_variant_column_and_evidence(self):
        d = self.data[16]
        self.assertEqual(d["source"]["format_variant"], "skill_hours")
        self.assertEqual([s["skill_hours"] for s in d["sessions"]], [Decimal(3)] * 30)
        self.assertEqual(d["field_sources"]["sessions.0.content"][0]["cell"], "I68")
        self.assertEqual(d["field_sources"]["sessions.0.skill_hours"][0]["cell"], "H68")
        self.assertTrue(all(s["content"] and s["content"] != "3" for s in d["sessions"]))

    def test_blank_staff_and_assignments_are_not_fabricated(self):
        for d in self.data:
            self.assertEqual(d["instructors"], [])
            self.assertEqual(d["assistants"], [])
            for s in d["sessions"]:
                for k in ("teacher", "assistant", "remote", "outdoor"):
                    self.assertIsNone(s[k])

    def test_all_source_refs_trace_raw_values(self):
        for p, d in zip(self.paths, self.data):
            book = openpyxl.load_workbook(BytesIO(p.read_bytes()), data_only=False)
            s = book[d["source"]["sheet"]]
            for key, refs in d["field_sources"].items():
                for ref in refs:
                    self.assertEqual(ref["sheet"], s.title)
                    self.assertEqual(ref["file"], p.name)
                    if "cell" in ref:
                        raw = s[ref["cell"]].value
                        raw = raw.isoformat() if hasattr(raw, "isoformat") else raw
                        self.assertEqual(ref["raw_value"], raw, key)
            book.close()

    def test_20_deterministic_results(self):
        for d in self.data:
            with self.subTest(file=d["source"]["filename"]):
                results = run_checks(d)
                self.assertEqual([x["status"] for x in results], ["資料一致"] * 6 + ["資料未提供"] * 2)
                self.assertTrue(all(x["status"] in STATUSES for x in results))

    def test_shifted_sections_not_fixed_rows(self):
        d = parse_excel_bytes(mutate(self.content, shift_from=30, shift=7), "shifted.xlsx")
        self.assertEqual(d["parse_report"]["status"], "success", d["parse_report"])
        self.assertEqual(d["derived"]["schedule_hours"], 54)
        self.assertEqual(len(d["sessions"]), 18)
        self.assertEqual(d["field_sources"]["sessions.0.hours"][0]["cell"], "G78")

    def test_blank_hours_do_not_become_zero_or_consistent(self):
        d = parse_excel_bytes(mutate(self.content, {"G71": None}), "blank.xlsx")
        self.assertEqual(len(d["sessions"]), 18)
        self.assertIsNone(d["sessions"][0]["hours"])
        self.assertIsNone(d["derived"]["schedule_hours"])
        self.assertEqual(run_checks(d)[0]["status"], "資料未提供")

    def test_blank_core_value_not_unknown_format(self):
        d = parse_excel_bytes(mutate(self.content, {"D7": None}), "blank_name.xlsx")
        self.assertEqual(d["parse_report"]["status"], "success")
        self.assertIsNone(d["course"]["name"])
        self.assertEqual(run_checks(d)[5]["status"], "資料未提供")

    def test_bad_number_reported_not_consistent(self):
        d = parse_excel_bytes(mutate(self.content, {"G71": "不明"}), "badnumber.xlsx")
        self.assertEqual(d["parse_report"]["status"], "partial")
        self.assertEqual(run_checks(d)[0]["status"], "無法解析")

    def test_formula_is_not_treated_as_cached_success(self):
        d = parse_excel_bytes(mutate(self.content, {"G71": "=1+2"}), "formula.xlsx")
        self.assertEqual(run_checks(d)[0]["status"], "無法解析")

    def test_missing_budget_inputs_and_money_mismatches(self):
        for coordinate, index in (("E137", 1), ("L137", 2), ("K53", 4)):
            with self.subTest(cell=coordinate):
                d = parse_excel_bytes(mutate(self.content, {coordinate: None}), "missing_money.xlsx")
                self.assertEqual(run_checks(d)[index]["status"], "資料未提供")
        for coordinate, newvalue, index in (("L137", 1, 2), ("K53", "固定費用總額：1元", 4)):
            with self.subTest(cell=coordinate):
                d = parse_excel_bytes(mutate(self.content, {coordinate: newvalue}), "different_money.xlsx")
                self.assertEqual(run_checks(d)[index]["status"], "資料不一致")

    def test_bad_date_is_partial_and_core_check_cannot_pass(self):
        d = parse_excel_bytes(mutate(self.content, {"Q8": "自2026/99/99"}), "bad_date.xlsx")
        self.assertEqual(d["parse_report"]["status"], "partial")
        self.assertIsNone(d["course"]["start_date"])
        self.assertEqual(run_checks(d)[5]["status"], "無法解析")

    def test_mismatch_and_zero_are_distinct_from_missing(self):
        d = parse_excel_bytes(mutate(self.content, {"G71": 0, "E137": 1}), "mismatch.xlsx")
        self.assertEqual(d["sessions"][0]["hours"], 0)
        self.assertEqual(d["derived"]["schedule_hours"], 51)
        results = run_checks(d)
        self.assertEqual(results[0]["status"], "資料不一致")
        self.assertEqual(results[1]["status"], "資料不一致")
        self.assertEqual(results[3]["status"], "資料不一致")

    def test_unknown_format_and_corruption_cannot_load(self):
        for content in (b"not an Excel", mutate(self.content, {"H69": "unknown column"})):
            d = parse_excel_bytes(content, "unknown.xlsx")
            self.assertEqual(d["parse_report"]["status"], "failed")
            self.assertTrue(all(c["status"] == "無法解析" for c in run_checks(d)))
            with self.assertRaises(ValueError):
                new_case(d)

    def test_presence_requires_manual_judgment_when_provided(self):
        d = parse_excel_bytes(mutate(self.content, {"D50": "測試師資（非真實）", "Q71": "測試教師"}), "staff.xlsx")
        self.assertEqual(run_checks(d)[6]["status"], "待人工確認")
        self.assertEqual(run_checks(d)[7]["status"], "資料未提供")

    def test_scan_ignores_excel_lockfiles(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            (p / "~$locked.xlsx").write_bytes(b"")
            (p / "case.xlsx").write_bytes(b"")
            self.assertEqual([x.name for x in scan_folder(p)], ["case.xlsx"])

    def test_a_b_a_state_isolation_and_rechecking(self):
        cases = {}
        a = load_case(cases, self.data[0])
        execute_checks(cases[a])
        save_review(cases[a], "DATA-01", "已核對資料", "A 案備註")
        b = load_case(cases, self.data[1])
        execute_checks(cases[b])
        save_review(cases[b], "DATA-01", "請補充資料", "B 案備註")
        self.assertEqual(load_case(cases, self.data[0]), a)
        execute_checks(cases[a])
        self.assertEqual(cases[a]["reviews"]["DATA-01"]["note"], "A 案備註")
        self.assertEqual(cases[b]["reviews"]["DATA-01"]["note"], "B 案備註")
        self.assertEqual(review_counts(cases[a]), (1,7,8))
        cases[a]["case_data"]["course"]["name"] = "isolated"
        self.assertNotEqual(self.data[0]["course"]["name"], "isolated")

    def test_source_revision_does_not_inherit_confirmation(self):
        changed = parse_excel_bytes(mutate(self.content, {"G71": 4}), self.paths[0].name)
        cases = {}
        a = load_case(cases, self.data[0]); execute_checks(cases[a])
        save_review(cases[a], "DATA-01", "已核對資料", "old source")
        b = load_case(cases, changed); execute_checks(cases[b])
        self.assertNotEqual(a, b)
        self.assertEqual(review_counts(cases[b]), (0,8,8))

    def test_unsaved_is_not_reviewed(self):
        c = new_case(self.data[0]); execute_checks(c)
        with self.assertRaises(ValueError):
            save_review(c, "DATA-01", "尚未處理", "just a note")
        self.assertEqual(review_counts(c), (0,8,8))


class SealTests(unittest.TestCase):
    def test_original_v1_and_legacy_copy_seals_unchanged(self):
        manifest = json.loads((V1 / "封版檔案校驗.json").read_text(encoding="utf-8-sig"))
        for root in (V1, ROOT / "legacy_v1"):
            for entry in manifest["files"]:
                self.assertEqual(sha256((root / entry["file"]).read_bytes()).hexdigest().upper(), entry["sha256"], str(root / entry["file"]))

    def test_original_and_copied_excels_unchanged(self):
        manifest = json.loads((ROOT / "source_manifest.json").read_text(encoding="utf-8"))
        for root in (V1, ROOT):
            for name, digest in manifest.items():
                self.assertEqual(sha256((root / name).read_bytes()).hexdigest(), digest)


class UIAcceptanceTests(unittest.TestCase):
    def test_real_selection_preview_load_checks_and_a_b_a(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.selectbox(key="candidate").options), 20)
        self.assertEqual(app.session_state["cases"], {})
        app.button(key="load").click().run()
        a = app.session_state["active_case_id"]
        app.button(key="run_checks").click().run()
        self.assertFalse(app.exception)
        self.assertEqual([m.value for m in app.metric], ["6", "0", "2", "0", "0"])
        app.selectbox(key=f"decision_{a}_DATA-01").set_value("已核對資料")
        app.text_area(key=f"note_{a}_DATA-01").set_value("A 案 UI 備註")
        next(b for b in app.button if b.label == "儲存本項處理").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("已檢視 1/8" in x.value for x in app.markdown))
        app.selectbox(key="item_" + a).set_value("DATA-02").run()
        app.selectbox(key="item_" + a).set_value("DATA-01").run()
        self.assertEqual(app.text_area(key=f"note_{a}_DATA-01").value, "A 案 UI 備註")
        app.radio(key="nav").set_value("選擇案件").run()
        app.selectbox(key="candidate").select_index(1).run()
        self.assertEqual(len(app.session_state["cases"]), 1)
        app.button(key="load").click().run()
        b = app.session_state["active_case_id"]
        app.button(key="run_checks").click().run()
        self.assertEqual(app.text_area(key=f"note_{b}_DATA-01").value, "")
        app.selectbox(key=f"decision_{b}_DATA-01").set_value("請補充資料")
        app.text_area(key=f"note_{b}_DATA-01").set_value("B 案 UI 備註")
        next(x for x in app.button if x.label == "儲存本項處理").click().run()
        app.radio(key="nav").set_value("選擇案件").run()
        app.selectbox(key="candidate").select_index(0).run()
        app.button(key="load").click().run()
        app.button(key="run_checks").click().run()
        self.assertEqual(app.session_state["active_case_id"], a)
        self.assertEqual(app.text_area(key=f"note_{a}_DATA-01").value, "A 案 UI 備註")
        self.assertEqual(app.selectbox(key=f"decision_{a}_DATA-01").value, "已核對資料")
        for i in range(2,9):
            ident = f"DATA-{i:02}"
            app.selectbox(key="item_" + a).set_value(ident).run()
            app.selectbox(key=f"decision_{a}_{ident}").set_value("保留待人工確認")
            app.text_area(key=f"note_{a}_{ident}").set_value("備註 " + ident)
            next(x for x in app.button if x.label == "儲存本項處理").click().run()
        self.assertTrue(any("已檢視 8/8" in x.value and "尚未處理 0" in x.value for x in app.markdown))
        app.radio(key="nav").set_value("案件摘要").run()
        self.assertTrue(any("已檢視 8/8" in x.value for x in app.markdown))
        app.button(key="run_checks").click().run()
        self.assertEqual(review_counts(app.session_state["cases"][a]), (8,0,8))
        self.assertEqual(app.session_state["cases"][b]["reviews"]["DATA-01"]["note"], "B 案 UI 備註")
        self.assertFalse(app.exception)

    def test_failed_file_ui_has_no_load_button(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / "broken.xlsx").write_bytes(b"broken")
            with patch.dict("os.environ", {"WORKSHOP_EXCEL_DIR": temp}):
                app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
                self.assertFalse(app.exception)
                self.assertTrue(app.error)
                self.assertFalse(any(b.label == "載入此案件" for b in app.button))
                self.assertEqual(app.session_state["cases"], {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
