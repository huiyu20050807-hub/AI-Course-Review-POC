"""Small third layer inside existing result/summary screens; mock only."""
import streamlit as st
import semantic_checks as sem

def controls(case,state,docs):
    st.caption('AI 語意輔助｜AI 示範模式：固定回應驗證流程，未對真實案件作模型判斷。')
    st.caption('AI 僅接收本次語意檢核所需最小資料範圍。本輪全部在本機處理，不傳送外部模型。')
    if st.button('執行 AI 語意輔助（示範模式）',key='semantic_start'):
        try:
            sem.run(case,state,docs);st.rerun()
        except (ValueError,KeyError,TypeError):
            st.error('語意示範未完成：輸入不符合資料安全或格式要求；沒有外部傳輸。')

def card(case,row):
    item=row['evidence'];st.subheader(item['check_name'])
    st.warning('以下為 AI 語意分析結果，僅供承辦人審查參考。')
    st.caption('AI 示範模式｜不是對本案的真實模型判讀。')
    st.write('**'+row['original_status']+'**　｜　AI 語意輔助')
    st.write('**AI 發現**');st.write(row['finding'])
    st.write('**為什麼需要注意**')
    st.write('以下文字是提供人工核對的案件內容，並非 mock 模型已發現矛盾的證據。')
    fields=list(item['used_input']['case_context'].items())
    for field,text in fields[:2]:st.text(('未提供' if text is None else str(text))[:350])
    st.write('**建議承辦人確認**');st.write(item['suggested_attention'])
    with st.expander('查看 AI 分析依據'):
        st.json({'AI使用的最小資料（已遮罩）':item['used_input'],'Excel儲存格（本機來源）':item['source_evidence'],
            '規定段落與PDF頁碼':item['policy_context'],'prompt_version':item['prompt_version'],
            'provider':item['provider'],'model':item['model_name'],'原始輸出':item['raw_output'],
            'limitations':item['limitations'],'confidence':item['confidence'],'資料安全檢查':item['data_policy']})
        st.caption('confidence 僅為自評／系統參考，不是真實準確率；mock 不提供分數。')
    if case['semantic']['stale']:
        st.warning('來源已變更；保留舊分析及人工紀錄，請重新執行示範。');return
    st.caption('已保存人工結果：'+(item['human_result'] or '尚未處理'))
    prefix=f"{case['case_id']}_{row['key']}_{row['batch_id']}"
    with st.form('semantic_form_'+prefix):
        choice=st.selectbox('承辦人對 AI 建議的處理',sem.HUMAN,index=sem.HUMAN.index(item['human_result'] or '保留待確認'),key='sem_choice_'+prefix)
        note=st.text_area('承辦人備註',value=item['human_note'],key='sem_note_'+prefix)
        if st.form_submit_button('儲存 AI 建議處理'):
            sem.save(case,row['key'],choice,note);st.rerun()

def draft_panel(case,state,rows):
    if not case.get('semantic'):return
    st.subheader('AI 初審意見草稿')
    st.caption('AI 示範模式：本輪由固定範本整理已保存結果，未呼叫真實 AI。')
    ready=sem.draft_ready(case,state,rows)
    if ready:
        if st.button('產生 AI 初審意見草稿',key='ai_draft_generate'):
            sem.generate_draft(case,state,rows);st.rerun()
    else:
        st.info('請先完成資料品質、規定條件與四項語意示範檢核，並儲存全部項目的人工處理結果。')
    draft=case.get('ai_draft')
    if not draft:return
    stale=not ready or draft['fingerprint']!=sem.draft_signature(case,state,rows)
    st.warning('AI 產生之初審意見草稿，須經承辦人確認後始可使用。')
    if stale:
        st.warning('來源或人工處理已變更，舊草稿已過期，請完成處理後重新產生。')
        with st.expander('查看過期草稿（不可確認）'):st.text(draft['text'])
        return
    key=case['case_id']+draft['created_at']
    text=st.text_area('人工編輯草稿',value=draft['text'],height=450,key='ai_draft_text_'+key)
    checked=st.checkbox('我已核對草稿內容與承辦人處理結果',key='ai_draft_ack_'+key)
    if st.button('儲存並確認本草稿',disabled=not checked,key='ai_draft_confirm'):
        sem.confirm_draft(case,state,rows,text);st.success('已保存人工確認；不代表案件核定。')
    if draft['confirmed_at'] and text==draft['text']:st.caption('人工確認時間：'+draft['confirmed_at'])
    else:st.caption('草稿尚未經人工確認，或編輯內容尚未重新確認。')
    with st.expander('查看草稿使用資料與示範原稿'):
        st.json({'input':draft['input'],'provider':draft['provider'],'model':draft['model'],'original_text':draft['original_text']})
