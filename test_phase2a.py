"""PDF metadata, traceability, conservative applicability and real Streamlit UI."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
import tempfile
import unittest
from pypdf import PdfReader, PdfWriter
from streamlit.testing.v1 import AppTest
from policy_parser import POLICY_FOLDER, PARSER_VERSION, scan_pdfs, get_document, parse_policy_bytes, metadata, compact
from policy_applicability import applicability, case_context
from policy_search import search_documents

ROOT = Path(__file__).parent
CTX = {"plan_type": "industrial", "roc_year": 115, "period": "下半年"}
PAGE_COUNTS = {
    "116年度上半年產業人才投資方案各職類課程審查標準作業原則1150317.pdf": 2,
    "116年度上半年產業人才投資方案訓練計畫職類審查標準作業程序1150902.pdf": 29,
    "提升勞工自主學習計畫.pdf": 22, "提升勞工自主學習計畫作業手冊.pdf": 80,
    "產業人才投資計畫.pdf": 22, "產業人才投資計畫作業手冊.pdf": 79,
}


class PolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths = scan_pdfs()
        cls.docs = [get_document(p) for p in cls.paths]
        cls.industrial = next(d for d in cls.docs if d["file_name"] == "產業人才投資計畫.pdf")

    def scoped(self, **fields):
        d = deepcopy(self.industrial)
        for k, v in fields.items():
            d[k] = v
            d["metadata_evidence"][k] = {"kind": "document_text", "page": 1, "excerpt": "測試專用明示範圍（不屬真實來源）"}
        return d

    def test_six_pdf_scan(self):
        self.assertEqual({p.name for p in self.paths}, set(PAGE_COUNTS))

    def test_all_sha256_and_source_copy_match(self):
        for path, d in zip(self.paths, self.docs):
            self.assertEqual(d["sha256"], sha256(path.read_bytes()).hexdigest())
            original = ROOT.parent / "AI_Course_Review_POC" / "產投規定及審查原則" / path.name
            self.assertEqual(d["sha256"], sha256(original.read_bytes()).hexdigest())

    def test_234_pdf_pages_and_text_success(self):
        self.assertEqual(sum(d["page_count"] for d in self.docs), 234)
        for d in self.docs:
            with self.subTest(file=d["file_name"]):
                self.assertEqual(d["page_count"], PAGE_COUNTS[d["file_name"]])
                self.assertEqual(len(PdfReader(d["source_path"]).pages), d["page_count"])
                self.assertEqual(d["parse_report"]["status"], "success")
                self.assertEqual(d["parse_report"]["text_pages"], d["page_count"])

    def test_schema_and_exact_page_offsets(self):
        for d in self.docs:
            self.assertTrue(set(("document_id", "source_path", "file_name", "sha256", "title", "document_type", "plan_type", "roc_year", "period", "effective_from", "effective_to", "revision_date", "status", "applicability_notes", "pages", "sections", "parse_report")) <= d.keys())
            self.assertTrue(d["sections"])
            for s in d["sections"]:
                self.assertGreaterEqual(s["page_start"], 1)
                self.assertLessEqual(s["page_end"], d["page_count"])
                self.assertEqual(s["page_start"], s["page_end"])
                page = d["pages"][s["page_start"]-1]
                self.assertEqual(s["source_excerpt"], page["text"][s["char_start"]:s["char_end"]])
                self.assertEqual(s["text"], s["source_excerpt"])
                if s["article_no"] != "unknown":
                    self.assertTrue(s["text"].lstrip().startswith(s["article_no"]))

    def test_titles_and_plan_types_from_body(self):
        for d in self.docs:
            self.assertNotEqual(d["title"], "unknown")
            self.assertIn(compact(d["title"]), compact(d["pages"][0]["text"]))
            self.assertEqual(d["metadata_evidence"]["title"]["kind"], "document_text")
        self.assertEqual(self.industrial["plan_type"], "industrial")
        self.assertEqual(next(d for d in self.docs if "程序" in d["file_name"])["plan_type"], "both")
        self.assertEqual(next(d for d in self.docs if "原則" in d["file_name"])["plan_type"], "unknown")

    def test_revision_dates_not_invented_from_bare_dates(self):
        for d in self.docs:
            if d["file_name"].startswith("116"):
                self.assertEqual(d["revision_date"], "unknown")
            else:
                self.assertEqual(d["revision_date"], "2024-12-25")
            self.assertEqual(d["effective_from"], "unknown")
            self.assertEqual(d["effective_to"], "unknown")

    def test_filename_hints_separated_and_115_not_auto_applied(self):
        for d in self.docs:
            self.assertEqual(d["roc_year"], "unknown")
            self.assertEqual(d["period"], "unknown")
            if d["file_name"].startswith("116"):
                self.assertEqual(d["filename_hints"]["roc_year"], 116)
                self.assertEqual(d["filename_hints"]["period"], "上半年")
                self.assertEqual(applicability(d, CTX)["status"], "unknown")

    def test_body_period_mismatch_not_applicable(self):
        d = self.scoped(roc_year=116, period="上半年")
        self.assertEqual(applicability(d, CTX)["status"], "not_applicable")

    def test_plan_mismatch_not_applicable(self):
        self.assertEqual(applicability(self.industrial, dict(CTX, plan_type="self_learning"))["status"], "not_applicable")

    def test_no_period_is_unknown_even_with_revision_date(self):
        self.assertEqual(applicability(self.industrial, CTX)["status"], "unknown")

    def test_matching_explicit_period_and_plan(self):
        d = self.scoped(roc_year=115, period="下半年")
        self.assertEqual(applicability(d, CTX)["status"], "applicable")

    def test_date_range_overlap_and_no_overlap(self):
        for start, end, expected in (("2026-07-01", "2026-12-31", "applicable"), ("2026-10-01", "2026-12-31", "possibly_applicable"), ("2027-01-01", "2027-06-30", "not_applicable")):
            self.assertEqual(applicability(self.scoped(effective_from=start, effective_to=end), CTX)["status"], expected)

    def test_untrusted_filename_fields_cannot_create_applicable(self):
        d = deepcopy(self.industrial)
        d.update(roc_year=115, period="下半年")
        d["metadata_evidence"]["roc_year"] = {"kind": "filename"}
        d["metadata_evidence"]["period"] = {"kind": "filename"}
        self.assertEqual(applicability(d, CTX)["status"], "unknown")

    def test_conflicting_filename_and_body_stays_unknown(self):
        d = self.scoped(roc_year=115, period="下半年")
        d["filename_hints"] = {"roc_year": 116, "period": "上半年"}
        self.assertEqual(applicability(d, CTX)["status"], "unknown")

    def test_four_keyword_searches_exact_source_and_page(self):
        lookup = {d["document_id"]: d for d in self.docs}
        for query in ("師資", "訓練時數", "經費", "招生"):
            hits = search_documents(self.docs, query, CTX, "text")
            self.assertTrue(hits, query)
            for hit in hits:
                d = lookup[hit["document_id"]]
                self.assertEqual(hit["file_name"], d["file_name"])
                self.assertIn(query, compact(hit["text"]))
                self.assertIn(hit["text"], d["pages"][hit["page_start"]-1]["text"])
                self.assertIn(hit["applicability"]["status"], ("unknown", "not_applicable"))

    def test_title_heading_scopes_and_empty_query(self):
        self.assertTrue(search_documents(self.docs, "作業手冊", CTX, "title"))
        hits = search_documents(self.docs, "目的", CTX, "heading")
        self.assertTrue(hits)
        self.assertTrue(all("目的" in h["heading"] for h in hits))
        self.assertEqual(search_documents(self.docs, "   ", CTX), [])

    def test_corrupt_and_textless_pdf_fail_explicitly(self):
        writer = PdfWriter(); writer.add_blank_page(width=200, height=200)
        out = BytesIO(); writer.write(out)
        for content in (b"corrupt", out.getvalue()):
            d = parse_policy_bytes(content, "bad.pdf", "memory")
            self.assertEqual(d["parse_report"]["status"], "failed")
            self.assertEqual(applicability(d, CTX)["status"], "unknown")

    def test_case_adapter_does_not_change_phase1_schema(self):
        source = {"plan": {"name": "產業人才投資方案(提升勞工自主學習計畫)", "year_roc": 115, "term": "下半年"}}
        before = deepcopy(source)
        self.assertEqual(case_context(source), dict(CTX, plan_type="self_learning"))
        self.assertEqual(source, before)

    def test_content_versions_preserve_old_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); p = root / "version.pdf"; store = root / "store"
            p.write_bytes(self.paths[0].read_bytes())
            first = get_document(p, store)
            p.write_bytes(self.paths[1].read_bytes())
            second = get_document(p, store)
            self.assertNotEqual(first["document_id"], second["document_id"])
            self.assertEqual(len(list(store.rglob("*.json"))), 2)
            self.assertEqual(sha256(Path(first["archived_source_path"]).read_bytes()).hexdigest(), first["sha256"])
            self.assertEqual(sha256(Path(second["archived_source_path"]).read_bytes()).hexdigest(), second["sha256"])

    def test_phase1_core_and_tests_hashes_unchanged(self):
        baseline = json.loads((ROOT / "phase1_baseline.json").read_text())
        for name in ("excel_parser.py", "data_checks.py", "case_state.py", "test_phase1.py"):
            self.assertEqual(sha256((ROOT / name).read_bytes()).hexdigest(), baseline[name])


class PolicyUITests(unittest.TestCase):
    def test_new_active_case_updates_policy_comparison(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
        app.button(key="load").click().run()
        first_id = app.session_state["active_case_id"]
        app.radio(key="nav").set_value("規定與審查依據").run()
        self.assertEqual(app.session_state["policy_case"], first_id)
        app.radio(key="nav").set_value("選擇案件").run()
        app.selectbox(key="candidate").select_index(17).run()
        app.button(key="load").click().run()
        second_id = app.session_state["active_case_id"]
        app.radio(key="nav").set_value("規定與審查依據").run()
        self.assertNotEqual(first_id, second_id)
        self.assertEqual(app.session_state["policy_case"], second_id)
        self.assertEqual(app.session_state["cases"][first_id]["revision"], 0)
        self.assertEqual(app.session_state["cases"][second_id]["revision"], 0)
        self.assertFalse(app.exception)

    def test_switch_case_refreshes_applicability_and_search(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
        app.radio(key="nav").set_value("規定與審查依據").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.selectbox(key="policy_document").options), 6)
        self.assertEqual(len(app.selectbox(key="policy_case").options), 20)
        self.assertEqual(app.session_state["cases"], {})
        self.assertEqual([m.value for m in app.metric], ["0", "0", "2", "4"])
        self.assertTrue(any("不代表正式法規判定" in w.value for w in app.warning))
        # Choose an industrial document, then change only the comparison case to self-learning.
        from policy_parser import get_document
        d = get_document(POLICY_FOLDER / "產業人才投資計畫.pdf")
        app.selectbox(key="policy_document").set_value(d["document_id"]).run()
        self.assertTrue(any("未取得正文適用期間" in m.value for m in app.markdown))
        app.selectbox(key="policy_case").select_index(17).run()
        self.assertTrue(any("計畫別與案件不同" in m.value for m in app.markdown))
        app.text_input(key="policy_query").set_value("師資").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("搜尋結果：" in m.value for m in app.markdown))
        self.assertEqual(app.session_state["cases"], {})
        self.assertIsNone(app.session_state["active_case_id"])
