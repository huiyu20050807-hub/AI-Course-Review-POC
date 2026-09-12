"""Source browser only. Never mutates cases or attaches clauses to DATA checks."""
import os
from hashlib import sha256
from pathlib import Path
import streamlit as st
from excel_parser import DEFAULT_FOLDER, PARSER_VERSION, scan_folder
from policy_parser import POLICY_FOLDER, get_document, scan_pdfs
from policy_applicability import LABELS, applicability, case_context
from policy_search import search_documents

PLAN_LABELS = {"industrial": "產業人才投資計畫", "self_learning": "提升勞工自主學習計畫", "both": "兩計畫（正文明示）", "unknown": "unknown（待確認）"}


def show_source(doc, page):
    st.caption(f"來源 PDF：{doc['file_name']}｜PDF 實體第 {page} 頁（含封面，可能與印刷頁碼不同）")


def render_policy_page(active, excel_cached_parser):
    st.header("規定與審查依據")
    st.warning("本頁僅提供規定來源整理與適用性提示，不代表正式法規判定。")
    try:
        paths = scan_pdfs(Path(os.environ.get("WORKSHOP_POLICY_DIR", str(POLICY_FOLDER))))
    except OSError as exc:
        st.error(str(exc)); return
    documents = []
    with st.spinner("讀取規定文件與版本快照…"):
        for path in paths:
            try:
                documents.append(get_document(path))
            except (OSError, ValueError) as exc:
                st.error(f"{path.name}：{exc}")
    if not documents:
        st.info("沒有可瀏覽的 PDF。"); return
    folder = Path(os.environ.get("WORKSHOP_EXCEL_DIR", str(DEFAULT_FOLDER)))
    candidates = {}
    try:
        for path in scan_folder(folder):
            d = excel_cached_parser(path.read_bytes(), path.name, str(path.relative_to(folder)), PARSER_VERSION)
            if d["parse_report"]["status"] != "failed":
                candidates[d["case_id"]] = d
    except OSError as exc:
        st.error(str(exc))
    if active:
        candidates.setdefault(active["case_id"], active["case_data"])
    if candidates:
        # A browser-only selector: it does not load/switch the processing case.
        default = active["case_id"] if active else next(iter(candidates))
        active_id = active["case_id"] if active else None
        if active_id and st.session_state.get("policy_last_active") != active_id:
            st.session_state.policy_case = active_id
        st.session_state.policy_last_active = active_id
        if st.session_state.get("policy_case") not in candidates:
            st.session_state.policy_case = default
        selected = st.selectbox("適用性比對案件", list(candidates), key="policy_case",
                                format_func=lambda k: (candidates[k]["course"].get("name") or "課名未提供") + "｜" + (candidates[k]["organization"].get("name") or "單位未提供"))
        context = case_context(candidates[selected])
    else:
        context = {"plan_type": "unknown", "roc_year": "unknown", "period": "unknown"}
    st.caption(f"比對條件：{PLAN_LABELS.get(context['plan_type'], 'unknown')}｜{context['roc_year']} 年｜{context['period']}。此選擇不更動案件處理頁的 state。")
    evaluated = {d["document_id"]: applicability(d, context) for d in documents}
    for col, (key, label) in zip(st.columns(4), LABELS.items()):
        col.metric(label, sum(a["status"] == key for a in evaluated.values()))
    st.caption("unknown 表示證據不足；檔名的年度提示與正文明示的適用期間分開保存。")
    if candidates:
        from review_ui import document_confirmation_ui
        document_confirmation_ui(candidates[selected], documents, evaluated)
    st.table([{"文件標題": d["title"], "計畫別": PLAN_LABELS.get(d["plan_type"], "unknown"),
               "正文適用年度": str(d["roc_year"]), "正文期別": d["period"],
               "檔名年度提示": f"{d['filename_hints'].get('roc_year', 'unknown')}／{d['filename_hints'].get('period', 'unknown')}",
               "PDF 頁數": d["page_count"], "適用性": evaluated[d["document_id"]]["label"]} for d in documents])
    query = st.text_input("關鍵字搜尋", placeholder="例如：師資、訓練時數、經費、招生", key="policy_query")
    scope_label = st.selectbox("搜尋範圍", ["全部", "文件名稱", "章節標題", "段落全文"], key="policy_scope")
    if query.strip():
        scope = {"全部": "all", "文件名稱": "title", "章節標題": "heading", "段落全文": "text"}[scope_label]
        results = search_documents(documents, query, context, scope)
        st.write(f"搜尋結果：{len(results)} 段（一般關鍵字比對，忽略排版空白）")
        pages = max(1, (len(results) + 9) // 10)
        if st.session_state.get("policy_search_page", 1) not in range(1, pages + 1):
            st.session_state.policy_search_page = 1
        page_no = st.selectbox("搜尋結果頁", list(range(1, pages + 1)), key="policy_search_page")
        for hit in results[(page_no-1)*10:page_no*10]:
            with st.expander(f"{hit['title']}｜第 {hit['page_start']} 頁｜{hit['applicability']['label']}｜{hit['section_id'].split(':')[-1]}"):
                st.write("章節：", hit["heading"])
                st.caption("命中：" + "、".join(hit["matched_fields"]))
                st.text(hit["text"])
                st.caption(f"來源：{hit['file_name']}｜PDF 第 {hit['page_start']} 頁")
                st.write(hit["applicability"]["reason"])
    st.subheader("文件與章節瀏覽")
    lookup = {d["document_id"]: d for d in documents}
    if st.session_state.get("policy_document") not in lookup:
        st.session_state.policy_document = next(iter(lookup))
    chosen = st.selectbox("選擇規定文件", list(lookup), format_func=lambda k: lookup[k]["file_name"], key="policy_document")
    doc = lookup[chosen]
    st.write("**正式標題（正文擷取）：**", doc["title"])
    st.write("**適用性：**", evaluated[chosen]["label"], "—", evaluated[chosen]["reason"])
    for note in doc["applicability_notes"]:
        st.caption(note)
    with st.expander("文件版本與判斷證據"):
        st.json({k: doc[k] for k in ("document_id", "source_path", "sha256", "parser_version", "document_type", "plan_type", "roc_year", "period", "effective_from", "effective_to", "revision_date", "publication_date", "document_date", "status", "filename_hints", "metadata_evidence", "parse_report")})
    # Always serve original bytes, not a reconstructed PDF.
    try:
        original = Path(doc.get("archived_source_path", doc["source_path"])).read_bytes()
        if sha256(original).hexdigest() != doc["sha256"]:
            raise ValueError("PDF 已更新，請重新選取文件以載入新版本。")
        st.download_button("下載原始 PDF 核對", data=original, file_name=doc["file_name"], mime="application/pdf", key="policy_download_" + chosen)
    except (OSError, ValueError) as exc:
        st.error(str(exc))
    if not doc["pages"]:
        st.error("PDF 解析失敗，沒有可瀏覽頁面。"); return
    page = st.selectbox("PDF 頁碼", list(range(1, doc["page_count"] + 1)), key="policy_page_" + chosen)
    show_source(doc, page)
    sections = [s for s in doc["sections"] if s["page_start"] <= page <= s["page_end"]]
    st.caption(f"此頁 {len(sections)} 個章節／段落切片。unknown 條號不會補成自訂法規條號。")
    for s in sections:
        label = s["heading"] if s["heading"] != "unknown" else "章節未辨識"
        with st.expander(f"{label}｜條次 {s['article_no']}｜項次 {s['item_no']}｜{s['section_id'].split(':')[-1]}"):
            st.text(s["source_excerpt"])
            show_source(doc, s["page_start"])
    with st.expander("完整頁面文字（保留排版）"):
        st.caption(doc["pages"][page-1]["text_status"])
        st.text(doc["pages"][page-1]["text"])
