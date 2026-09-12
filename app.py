from html import escape
from pathlib import Path
import os
import time

import streamlit as st

from demo_data import BANNER, RULE_WARNING, RULE_VERSION, COURSE, ORG, DOCUMENT, SECTIONS, CHECKS, HISTORY, STAGES
from review_logic import (DECISIONS, new_case, reviewed_count, stale, save_review,
                          generate_draft, edit_draft, archive_draft, confirmation_issues,
                          confirm, case_status, pending_review_ids, analysis_completed,
                          start_analysis, advance_analysis, analysis_snapshot)

st.set_page_config(page_title="AI 課程審查智慧助手｜POC", page_icon="📋", layout="wide")
st.markdown(f"<style>{Path(__file__).with_name('ui.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
st.markdown(f'<div class="poc-banner">{BANNER}</div>', unsafe_allow_html=True)

if "case" not in st.session_state:
    st.session_state.case = new_case()
    st.session_state.page = "首頁"

case = st.session_state.case
PAGES = ["首頁", "AI 模擬分析進度", "審查結果", "歷史案例與 AI 幕僚初審意見"]


def go(page):
    st.session_state.page = page
    st.rerun()


def clear_ack():
    st.session_state.pop("ack", None)


def badge(status):
    css, symbol = {"符合": ("ok", "✓"), "待確認": ("warn", "?"), "疑似異常": ("bad", "!")}[status]
    st.markdown(f'<span class="badge {css}">{symbol} {status}</span>', unsafe_allow_html=True)


def commit_review(rule_id, decision_key, note_key):
    # A submit callback runs before rendering either the list or the counters.
    current = st.session_state["case"]
    if save_review(current, rule_id, st.session_state[decision_key], st.session_state[note_key]):
        clear_ack()
    st.session_state.flash = f"{rule_id} 本項確認與備註已儲存。"


def draft_changed():
    edit_draft(st.session_state["case"], st.session_state["draft_editor"])
    clear_ack()


def show_document(section, highlight=None):
    content = escape(SECTIONS[section])
    if highlight:
        content = content.replace(escape(highlight), f"<mark>{escape(highlight)}</mark>")
    st.caption(f"{DOCUMENT}｜{section}")
    st.markdown(f'<div class="evidence">{content}</div>', unsafe_allow_html=True)


st.markdown('<div class="eyebrow">勞動力發展署 AI 策略領航工作坊</div>', unsafe_allow_html=True)
st.title("產業人才投資方案 AI 課程審查智慧助手")

nav = st.columns([1, 1.3, 1.1, 2.1, .8])
for i, p in enumerate(PAGES):
    enabled = i == 0 or (i == 1 and case["loaded"]) or (i >= 2 and analysis_completed(case))
    if nav[i].button(f"{i+1:02d}　{p}", key=f"nav{i}", use_container_width=True,
                     type="primary" if st.session_state.page == p else "secondary", disabled=not enabled):
        go(p)
if nav[4].button("重設示範", use_container_width=True):
    st.session_state.reset_prompt = True
if st.session_state.get("reset_prompt"):
    with st.container(border=True):
        st.warning("重設將清除本次檢核、備註、草稿與確認結果，回到尚未載入狀態。")
        yes, no, _ = st.columns([1, 1, 4])
        if yes.button("確認重設", type="primary"):
            st.session_state.clear()
            st.rerun()
        if no.button("取消重設"):
            st.session_state.reset_prompt = False
            st.rerun()

display_status = case_status(case)
st.markdown(f'<div class="case-strip"><div class="case-top"><div><span class="case-id">DEMO-001</span>{COURSE}</div>'
            f'<span class="case-state">{display_status}</span></div>'
            f'<div class="case-meta">{ORG}　｜　資料版本 v1.0　｜　{RULE_VERSION}</div></div>', unsafe_allow_html=True)
st.caption(RULE_WARNING)
if st.session_state.get("flash"):
    st.success(st.session_state.pop("flash"))


def home():
    st.header("找出審查疑點，整理有依據的初審意見")
    st.markdown('<div class="home-purpose">讀取計畫書　→　標示疑點與依據　→　草擬初審意見</div>', unsafe_allow_html=True)
    st.write("由承辦人逐項檢視，作最後確認。")
    left, right = st.columns([1.45, 1], gap="large")
    with left:
        with st.container(border=True):
            st.subheader("示範課程計畫書")
            st.write(f"**{COURSE}**")
            if not case["loaded"]:
                if st.button("載入示範計畫書", type="primary", use_container_width=True):
                    case["loaded"] = True
                    st.rerun()
            else:
                st.success("示範計畫書已載入，可以開始分析或預覽內容。")
            if st.button("開始 AI 模擬分析", type="primary", disabled=not case["loaded"] or analysis_completed(case), use_container_width=True):
                start_analysis(case)
                go(PAGES[1])
            if analysis_completed(case) and st.button("回到審查結果", use_container_width=True):
                go(PAGES[2])
            if st.button("預覽示範計畫書", disabled=not case["loaded"], use_container_width=True):
                case["preview"] = not case["preview"]
    with right:
        with st.container(border=True):
            st.subheader("這個 AI 可以協助您")
            st.markdown("**找疑點**　辨識待確認與疑似異常\n\n**查依據**　對照原文與示範規定\n\n**寫意見**　參考案例，草擬初審意見")
            st.caption("本次使用固定虛構資料模擬分析與草稿，無須上傳檔案。")
    with st.expander("案件摘要與檢核範圍"):
        c1, c2, c3 = st.columns(3)
        c1.metric("摘要時數", "36 小時")
        c2.metric("所列經費", "68,000 元")
        c3.metric("檢核規則", "8 項")
        st.caption("以上為虛構計畫書所列資料，尚待檢核。")
    if case["preview"] and case["loaded"]:
        st.subheader("虛構計畫書預覽")
        for section in SECTIONS:
            with st.expander(section):
                show_document(section)
    with st.expander("檢視 8 項 DEMO 示範規則"):
        st.warning(RULE_WARNING)
        for c in CHECKS:
            st.write(f"**{c['id']}｜{c['name']}**：{c['rule']}")


def progress_page():
    st.header("AI 模擬分析進度")
    st.info("目前為預設流程與結果的模擬展示。分析完成後，由您點選進入結果頁。")
    snapshot = analysis_snapshot(case)
    st.progress(snapshot["progress"], text=f"已完成 {snapshot['completed']}／{snapshot['total']} 個階段")
    stage_cards = []
    for i, ((title, desc, result), state) in enumerate(zip(STAGES, snapshot["states"])):
        detail = result if state == "已完成" else desc
        stage_cards.append(f'<div class="stage {"active" if state == "處理中" else ""}"><strong>{i+1:02d}　{title}</strong>'
                           f'　｜　{state}<br><small>{detail}</small></div>')
    # One complete render per run; no partial replacement of nested placeholders.
    st.markdown("".join(stage_cards), unsafe_allow_html=True)
    if case["analysis_started"] and not snapshot["finished"] and not case["error"]:
        try:
            time.sleep(float(os.environ.get("POC_STEP_SECONDS", "0.65")))
            advance_analysis(case)
        except Exception:
            case["error"] = "本次模擬分析未完成，請重新分析。"
        st.rerun()
    if case["error"]:
        st.error(case["error"])
        if st.button("重新分析", type="primary"):
            start_analysis(case)
            st.rerun()
        if st.button("返回首頁"):
            go(PAGES[0])
    elif snapshot["finished"]:
        if st.button("查看審查結果", type="primary", use_container_width=True):
            go(PAGES[2])


def results():
    st.header("審查結果")
    for col, status, tone in zip(st.columns(3), ["符合", "待確認", "疑似異常"], ["ok", "warn", "bad"]):
        with col, st.container(key=f"summary_{tone}"):
            st.metric(status, f"{sum(c['status'] == status for c in CHECKS)} 項")
    st.caption("符合僅指單一檢核項目；疑似異常不等同違規定論。AI 原始結果與承辦人判斷分開保留。")
    st.write(f"**承辦人已檢視 {reviewed_count(case)}／{len(CHECKS)} 項　｜　尚未確認 {len(pending_review_ids(case))} 項**")
    left, right = st.columns([1, 2], gap="large")
    with left:
        with st.container(key="review_list"):
            st.subheader("檢核清單")
            filter_value = st.selectbox("篩選 AI 狀態", ["全部", "疑似異常", "待確認", "符合"], key="status_filter")
            only_pending = st.checkbox("只顯示尚未確認項目", key="only_pending")
            ordered = sorted(CHECKS, key=lambda c: {"疑似異常": 0, "待確認": 1, "符合": 2}[c["status"]])
            visible = [c for c in ordered if (filter_value == "全部" or c["status"] == filter_value)
                       and (not only_pending or case["reviews"][c["id"]]["decision"] == "尚未確認")]
            ids = [c["id"] for c in visible]
            if not ids:
                st.info("沒有符合此篩選條件的項目。可切換篩選查看其他項目。")
            else:
                if st.session_state.get("selected_check") not in ids:
                    st.session_state.selected_check = ids[0]
                lookup = {c["id"]: c for c in CHECKS}
                selected = st.radio("選擇檢核項目", ids, key="selected_check",
                                    format_func=lambda rid: f"**{ {'符合': '✓', '待確認': '?', '疑似異常': '!'}[lookup[rid]['status']]} {lookup[rid]['status']}｜{lookup[rid]['name']}**  \n承辦人：{case['reviews'][rid]['decision']}")
                st.caption(f"{len(ids)} 項符合篩選條件")
    with right:
        if visible:
            c = next(c for c in CHECKS if c["id"] == selected)
            with st.container(key="review_detail"):
                st.subheader(f"{c['id']}　{c['name']}")
                badge(c["status"])
                st.caption(f"檢核類別：{c['category']}")
                tone = {"符合": "ok", "待確認": "warn", "疑似異常": "bad"}[c["status"]]
                if c["id"] == "DEMO-R07":
                    st.markdown('<div class="hours-comparison" aria-label="摘要 36 小時，課表 42 小時，相差 6 小時">'
                                '<div><span>計畫摘要</span><strong>36<small> 小時</small></strong></div>'
                                '<div><span>課表合計</span><strong>42<small> 小時</small></strong></div>'
                                '<div class="hours-difference"><span>相差</span><strong>6<small> 小時</small></strong></div></div>', unsafe_allow_html=True)
                st.markdown(f'<div class="review-card finding {tone}"><div class="section-label"><span>01</span>AI 發現</div>'
                            f'<p>{escape(c["finding"])}</p></div>', unsafe_allow_html=True)
                evidence_col, rule_col = st.columns([1.2, 1], gap="medium")
                with evidence_col:
                    with st.expander("02　計畫書證據與對應原文"):
                        st.caption(DOCUMENT)
                        st.markdown(f'<div class="quote-source">{escape(c["section"])}</div><div class="quote-text">{escape(c["evidence"])}</div>', unsafe_allow_html=True)
                        if c.get("extra_evidence"):
                            st.markdown(f'<div class="quote-source">{escape(c["extra_section"])}</div><div class="quote-text">{escape(c["extra_evidence"])}</div>', unsafe_allow_html=True)
                        st.divider()
                        show_document(c["section"], c["evidence"])
                        if c.get("extra_section"):
                            st.divider()
                            show_document(c["extra_section"], c["extra_evidence"])
                with rule_col:
                    with st.expander("03　示範規定依據"):
                        st.caption(c["id"])
                        st.markdown(f'<div class="rule-text">{escape(c["rule"])}</div>', unsafe_allow_html=True)
                        st.caption(RULE_WARNING)
                        st.caption(RULE_VERSION)
                        st.write(f"本項以計畫書所載內容檢查「{c['rule']}」，對應上方 AI 發現。")
                st.markdown(f'<div class="review-card"><div class="section-label"><span>04</span>建議處理</div>'
                            f'<p>{escape(c["suggestion"])}</p></div>', unsafe_allow_html=True)
                st.divider()
                st.subheader("承辦人確認")
                decision_key, note_key = f"review_decision_{selected}", f"review_note_{selected}"
                if decision_key not in st.session_state:
                    st.session_state[decision_key] = case["reviews"][selected]["decision"]
                if note_key not in st.session_state:
                    st.session_state[note_key] = case["reviews"][selected]["note"]
                with st.form(f"review_form_{selected}", border=False):
                    st.selectbox("處理結果", DECISIONS, key=decision_key)
                    with st.container(key="note_input"):
                        st.text_area("承辦人備註", key=note_key, height=110,
                                     placeholder="例如：請提案機構釐清 36／42 小時差異，補正摘要與課表。")
                    st.caption("按「儲存本項確認」後，結果與備註才會寫入案件並同步更新統計。")
                    st.form_submit_button("儲存本項確認", key=f"save_review_{selected}",
                                          on_click=commit_review, args=(selected, decision_key, note_key))
    if stale(case):
        st.warning("檢核內容已變更，初審意見內容待更新。請重新產生草稿後再確認。")
    if st.button("前往歷史案例與初審意見", type="primary", use_container_width=True):
        go(PAGES[3])


def opinion():
    st.header("歷史案例與 AI 幕僚初審意見")
    st.caption("歷史案例僅供參考，不作為本案核准依據。以下三筆全部為虛構案例。")
    if not HISTORY:
        st.info("沒有相似歷史案例，仍可依本案檢核結果產生草稿。")
    for col, h in zip(st.columns(3), HISTORY):
        with col, st.container(border=True):
            st.subheader(h["name"])
            st.write(h["reason"])
            st.write(f"**重要差異：**{h['difference']}")
            if st.button("查看比較", key=h["id"], use_container_width=True):
                st.session_state.history_id = h["id"]
    selected_history = st.session_state.get("history_id", HISTORY[0]["id"] if HISTORY else None)
    if selected_history:
        h = next(h for h in HISTORY if h["id"] == selected_history)
        with st.expander(f"本案與 {h['id']} 比較", expanded="history_id" in st.session_state):
            st.caption(f"{h['id']}｜{h['year']}｜{h['hours']} 小時｜招生對象：{h['audience']}")
            st.table([
                {"比較項目": "課程", "本案 DEMO-001": COURSE, "歷史案例": h["name"]},
                {"比較項目": "時數", "本案 DEMO-001": "摘要 36 小時／課表 42 小時", "歷史案例": f"{h['hours']} 小時"},
                {"比較項目": "招生對象", "本案 DEMO-001": "在職行政人員", "歷史案例": h["audience"]},
                {"比較項目": "補充資料", "本案 DEMO-001": "授課經驗、軟體授權資訊；釐清時數及場地費", "歷史案例": h["supplement"]},
            ])
            st.write(f"**相似原因：**{h['reason']}")
            st.write(f"**主要差異：**{h['difference']}")
            st.write(f"**歷史處理摘要：**{h['outcome']}")
    st.divider()
    st.subheader("AI 初審摘要")
    summary_items = [(status, sum(c["status"] == status for c in CHECKS), tone)
                     for status, tone in [("符合", "ok"), ("待確認", "warn"), ("疑似異常", "bad")]]
    summary_cards = "".join(f'<div class="brief-stat {tone}"><strong>{count}<small> 項</small></strong><span>{status}</span></div>'
                            for status, count, tone in summary_items)
    st.markdown(f'<div class="brief-summary"><div class="brief-stats">{summary_cards}</div>'
                '<div class="brief-line"><span>主要問題</span><strong>課程時數不一致、經費計算不一致</strong></div>'
                '<div class="brief-line"><span>建議</span><strong>補充師資佐證、軟體授權資料並確認時數與經費</strong></div></div>', unsafe_allow_html=True)
    st.caption("以上為原始 AI 模擬檢核摘要；承辦人處理結果與人工修訂請見下方完整意見。")
    st.divider()
    st.subheader("AI 幕僚初審意見")
    st.markdown('<div class="reading-guide">閱讀 AI 草稿　→　修訂文字與處理意見　→　由承辦人確認<br>本份意見供初審使用，不代表課程核定。</div>', unsafe_allow_html=True)
    st.caption("以固定範本彙整本案檢核、承辦人判斷與備註及三筆歷史案例，無外部 AI 連線。")
    st.write(f"已檢視 {reviewed_count(case)}／{len(CHECKS)} 項　｜　尚未確認 {len(pending_review_ids(case))} 項")
    if case["draft"] is None:
        if st.button("產生 AI 初審意見草稿", type="primary"):
            generate_draft(case)
            st.session_state.pop("draft_editor", None)
            clear_ack()
            st.rerun()
    else:
        if stale(case):
            st.warning("內容待更新：上游檢核或備註已變更，請重新產生草稿。")
        if case["confirmed_at"]:
            st.success(f"初審意見已確認｜{case['confirmed_at']}（臺北時間）。不代表課程核定或審查通過。")
        else:
            st.info("AI 產生，尚未經承辦人確認。請閱讀、修訂後再確認。")
        if "draft_editor" not in st.session_state:
            st.session_state.draft_editor = case["draft"]
        st.text_area("初審意見（可人工編輯）", key="draft_editor", height=520, on_change=draft_changed)
        save, regenerate, back = st.columns(3)
        if save.button("儲存草稿", use_container_width=True):
            archive_draft(case)
            st.success("已保存一份草稿版本於本次工作階段。")
        if regenerate.button("重新產生草稿", use_container_width=True):
            st.session_state.regenerate_prompt = True
        if back.button("返回檢核", use_container_width=True):
            go(PAGES[2])
        if st.session_state.get("regenerate_prompt"):
            st.warning("重新產生將取代編輯區內容；目前內容會先保存為歷史版本。")
            y, n = st.columns(2)
            if y.button("保留目前版本並重新產生", type="primary"):
                generate_draft(case)
                st.session_state.pop("draft_editor", None)
                clear_ack()
                st.session_state.regenerate_prompt = False
                st.rerun()
            if n.button("取消重新產生"):
                st.session_state.regenerate_prompt = False
                st.rerun()
        if case["versions"]:
            with st.expander(f"已保存版本（{len(case['versions'])} 份）"):
                version = st.selectbox("選擇保存版本", range(len(case["versions"])),
                                       format_func=lambda i: f"版本 {i+1}｜{case['versions'][i]['time']}")
                st.text(case["versions"][version]["text"])
        st.divider()
        issues = confirmation_issues(case)
        if issues:
            st.warning("確認前請完成：\n\n" + "\n\n".join(issues))
        ack = st.checkbox("我已檢視並確認本份初審意見", key="ack", disabled=bool(issues) or bool(case["confirmed_at"]))
        if st.button("確認並儲存初審意見", type="primary", use_container_width=True,
                     disabled=bool(issues) or not ack or bool(case["confirmed_at"])):
            errors = confirm(case, ack)
            if errors:
                st.error("；".join(errors))
            else:
                st.rerun()
        export_status = f"初審意見已確認｜{case['confirmed_at']}（臺北時間）" if case["confirmed_at"] else "內容待更新，尚未確認" if stale(case) else "草稿，尚未經承辦人確認"
        exported = f"{BANNER}\n{RULE_WARNING}\n匯出狀態：{export_status}\n本意見不代表課程核定或審查通過。\n\n{case['draft']}"
        st.download_button("下載目前意見文字檔", data=exported.encode("utf-8-sig"), file_name="DEMO-001_初審意見.txt", mime="text/plain")
        st.caption("下載檔案包含目前確認狀態與虛構資料聲明。")


page = st.session_state.page
if page == PAGES[0]:
    home()
elif page == PAGES[1] and case["loaded"]:
    progress_page()
elif page == PAGES[2] and analysis_completed(case):
    results()
elif page == PAGES[3] and analysis_completed(case):
    opinion()
else:
    go(PAGES[0])

st.divider()
st.caption("本機展示工作階段保存操作內容；重新整理瀏覽器、關閉工作階段或重設示範後可能清除。需要保留意見時請下載文字檔。")
