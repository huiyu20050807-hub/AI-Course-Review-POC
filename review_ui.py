"""Phase 2B UI; separate from Phase 1 data checks."""
import os
from pathlib import Path
import streamlit as st
from policy_parser import get_document, scan_pdfs, POLICY_FOLDER
from policy_applicability import case_context
from review_rules import *

def document_confirmation_ui(data, documents, evaluated):
    st.subheader('適用版本確認')
    st.info('系統適用性提示與人工確認分開保存；最終採用文件由承辦人確認。')
    cid = data['case_id']
    store = st.session_state.setdefault('rule_cases', {})
    state = store.get(cid, new_state())
    st.write(case_context(data))
    st.table([{'文件名稱': d['file_name'], '計畫別': d['plan_type'],
        '文件日期資訊': str(d.get('document_date', 'unknown')) + '／修訂 ' + str(d['revision_date']),
        '檔名提示': str(d['filename_hints']), '系統 applicability': evaluated[d['document_id']]['status'],
        '判斷理由': evaluated[d['document_id']]['reason'],
        '人工確認': state['documents'].get(d['document_id'], {}).get('human_result', '尚未確認')}
        for d in documents])
    lookup = {d['document_id']: d for d in documents}
    chosen = st.selectbox('選擇要確認的文件', list(lookup), format_func=lambda k: lookup[k]['file_name'], key='confirm_doc_'+cid)
    saved = state['documents'].get(chosen, {})
    prefix = cid + chosen
    with st.form('doc_form_'+prefix):
        choice = st.selectbox('人工適用結果', DOCUMENT_CHOICES, index=DOCUMENT_CHOICES.index(saved.get('human_result', '保留待確認')), key='doc_choice_'+prefix)
        note = st.text_area('適用版本確認備註', value=saved.get('human_note', ''), key='doc_note_'+prefix)
        st.caption('確認適用表示承辦人已核對版本；檔名 116 上半年不會自動套用至 115 下半年案件。')
        if st.form_submit_button('儲存適用版本確認'):
            confirm_document(state_for(store, cid), lookup[chosen], case_context(data), choice, note)
            st.rerun()
    if saved:
        st.caption('已儲存時間：'+saved['confirmed_at'])
        with st.expander('原始系統提示與人工確認紀錄'):
            st.json(saved)

def render_review_page(active):
    st.header('審查規則檢核')
    st.warning('系統規則檢核結果為審查輔助資訊，不代表案件核定、退件或正式審查結果。')
    st.caption('Review Rule Validation｜與 DATA-01～08 資料品質檢查分開保存。候選規則均待承辦人確認。')
    if not active:
        st.info('請先選擇案件並按「載入此案件」。'); return
    data = active['case_data']; cid = data['case_id']
    st.subheader(data['course']['name'])
    st.write(data['organization']['name'], '｜', data['plan']['name'], '｜', case_context(data))
    state = state_for(st.session_state.setdefault('rule_cases', {}), cid)
    try:
        docs = {d['document_id']: d for d in [get_document(p) for p in scan_pdfs(Path(os.environ.get('WORKSHOP_POLICY_DIR', str(POLICY_FOLDER))))]}
        rules = load_rules()
    except (OSError, ValueError, KeyError) as exc:
        st.error('規則或來源驗證失敗：'+str(exc)); return
    confirmed = [d['file_name'] for k, d in docs.items() if state['documents'].get(k, {}).get('human_result') == '確認適用']
    st.subheader('適用文件')
    if not confirmed:
        st.warning('尚未確認本案適用規定版本，正式規則檢核暫不執行。')
    else:
        for name in confirmed: st.write('• '+name)
    with st.expander('候選規則清單與可執行公式確認', expanded=bool(confirmed) and not state['runs']):
        st.table([{'ID': r['rule_id'], '名稱': r['rule_name'], '分類': r['category'], '實作': r['status'], '限制': r['notes']} for r in rules])
        for r in rules:
            if r['status'] != 'enabled': continue
            st.write(r['rule_id'], r['rule_name'], '｜', r['source_documents'][0]['file_name'], 'PDF 第', r['source_pages'][0], '頁')
            st.caption('欄位映射：budget.fixed_total ÷ course.enrollment ÷ course.declared_hours，比對 budget.hourly_cost。'+r['notes'])
            st.text(r['source_text'])
            if st.button('已核對原文與欄位映射，採用此公式', key='approve_'+cid+r['rule_id']):
                approve_rule(state, r, True); st.rerun()
            st.caption('本案公式確認：'+('已確認' if state['approvals'].get(digest(r)) else '待承辦人確認'))
    if st.button('執行規則檢核', key='run_rules', disabled=not confirmed, type='primary'):
        execute(state, data, rules, docs); st.rerun()
    if not state['runs']: return
    run = state['runs'][-1]
    stale = run['revision'] != state['revision'] or any(r['rule_digest'] != digest(next((x for x in rules if x['rule_id'] == r['rule']['rule_id']), {})) or any(s['document_id'] not in docs for s in r['rule']['source_documents']) for r in run['results'])
    if stale:
        st.warning('文件確認、規則或來源已變更；以下為舊結果快照，請重新執行，舊依據不會被覆寫。')
    st.table([{'ID': i['rule']['rule_id'], '規則': i['rule']['rule_name'], '系統結果': i['system_result'], '已計算': i['executed'], '承辦人': i['human_result'] or '尚未確認'} for i in run['results']])
    index = st.selectbox('選擇規則查看 Evidence Chain', range(len(run['results'])), format_func=lambda i: run['results'][i]['rule']['rule_id']+'｜'+run['results'][i]['rule']['rule_name'], key='rule_item_'+cid)
    item = run['results'][index]; rule = item['rule']
    st.subheader(rule['rule_name']+'｜'+item['system_result'])
    st.write('**案件資料 → Excel 原始來源**')
    st.json({'案件值': item['case_values'], 'Excel': item['excel_source'], '儲存格': item['field_sources']})
    st.write('**檢核規則 → PDF 原文與頁碼**')
    st.caption(f"{rule['rule_id']}｜{rule['rule_type']}｜版本 {rule['version']}｜建立日期 {rule['created_at']}｜規則 SHA-256 {item['rule_digest']}")
    for src in rule['source_documents']:
        st.write(src['file_name'], '｜PDF 實體第', src['page'], '頁')
        st.caption('來源 SHA-256：'+src['sha256']+'｜章節：'+src['section_id'])
        st.text(src['text'])
    st.write('**系統計算／判斷方式 → 系統結果**')
    st.write(item['calculation']); st.write(item['system_result'])
    st.info('建議承辦人核對原文適用前提、Excel 欄位與精度；資料不足時取得附件，不以空白推定不符合。')
    prefix = f"{cid}_{run['run_id']}_{index}"
    with st.form('rule_human_'+prefix):
        choice = st.selectbox('承辦人處理結果', HUMAN_CHOICES, index=HUMAN_CHOICES.index(item['human_result'] or '保留待確認'), key='rule_choice_'+prefix)
        note = st.text_area('承辦人備註／改判理由與結果', value=item['human_note'], key='rule_note_'+prefix)
        if st.form_submit_button('儲存規則處理結果', disabled=stale):
            save_human(state, run, index, choice, note); st.rerun()
    st.caption('承辦人處理結果與系統原始結果分開保存。資料保留於本次連線；本階段沒有跨連線資料庫。')
    with st.expander('本案執行歷史與確認快照'):
        st.json(state)
