"""Plain-language front end over unchanged Phase 1/2A/2B capabilities."""
import os
from pathlib import Path
import streamlit as st
from policy_parser import POLICY_FOLDER, scan_pdfs, get_document
from review_rules import load_rules, state_for, HUMAN_CHOICES
import workflow as flow

def resources():
    docs=[get_document(p) for p in scan_pdfs(Path(os.environ.get('WORKSHOP_POLICY_DIR',str(POLICY_FOLDER))))]
    return load_rules(),{d['document_id']:d for d in docs}

def go(page):
    st.session_state.nav=page

def begin(data):
    try:
        rules,docs=resources()
        cid=flow.start(st.session_state.cases,st.session_state.setdefault('rule_cases',{}),data,rules,docs)
        st.session_state.active_case_id=cid
        st.session_state.nav='審查結果'
    except (ValueError,OSError,KeyError) as exc:
        st.session_state.workflow_error='無法完成檢核：'+str(exc)

def compact_summary(data):
    st.subheader(data['course']['name'] or '課名未提供')
    st.write('**訓練單位：**',data['organization'].get('name') or '未提供')
    st.write('**職類：**',data['course'].get('occupation') or '未提供')
    cols=st.columns(2)
    cols[0].write('**訓練時數：** '+str(data['course'].get('declared_hours') or '未提供')+' 小時')
    cols[1].write('**訓練人數：** '+str(data['course'].get('enrollment') or '未提供')+' 人')
    st.caption('計畫別：'+str(data['plan'].get('name') or '未提供'))

def label(field):
    known={'budget.fixed_total':'固定費用','budget.hourly_cost':'表列單一人時成本',
        'course.enrollment':'訓練人數','course.declared_hours':'計畫訓練時數',
        'organization.name':'訓練單位','course.name':'課程名稱','course.occupation':'職類',
        'plan.name':'計畫別','plan.year_roc':'年度','plan.term':'期別','course.start_date':'開訓日期','course.end_date':'結訓日期','instructors':'師資資料',
        'budget.materials_total':'材料費'}
    if field in known:return known[field]
    if field.startswith('sessions.'):
        _,n,k=field.split('.')
        return f'第 {int(n)+1} 筆課表'+{'hours':'時數','teacher':'教師','assistant':'助教'}.get(k,'資料')
    if field.startswith('budget.'):
        return ('每班' if '.per_class.' in field else '每人')+{'subsidy':'補助','self_paid':'自付','total':'總計'}.get(field.split('.')[-1],'金額')
    return '案件欄位'

def display(value):
    return '未提供' if value is None or value==[] or value=='' else str(value)

def render(active,summary=False):
    if not active or not active['checked']:
        st.info('請先選擇案件，按「開始智慧檢核」。');return
    state=state_for(st.session_state.setdefault('rule_cases',{}),active['case_id'])
    try:
        rules,docs=resources()
        flow.synchronize(active,state,rules,docs)
    except (ValueError,OSError,KeyError) as exc:
        st.error('依據讀取或版本驗證失敗；未產生新的檢核結果。'+str(exc));return
    from semantic_checks import refresh
    from semantic_ui import controls, card as semantic_card, draft_panel
    refresh(active,state,docs)
    rows=flow.items(active,state)
    if summary:
        st.header('系統審查摘要')
        st.caption('依目前資料與承辦人處理結果即時整理；使用固定範本，不是 AI 初審意見。')
        st.text(flow.summary_text(active,rows))
        draft_panel(active,state,rows)
        st.button('返回審查結果',on_click=go,args=('審查結果',))
        return
    st.header('審查結果')
    st.caption(active['case_data']['course']['name']+'｜'+active['case_data']['organization']['name'])
    controls(active,state,docs)
    st.subheader('本案需要您優先確認')
    todo=flow.priorities(rows)
    if todo:
        for row in todo:
            st.write('**'+row['name']+'** — '+row['finding']+'　承辦人：'+(row['human'] or '尚未處理'))
    else:
        st.success('目前提醒項目均已記錄處理結果；保留待確認或要求補件的事項仍請持續追蹤。')
    confirmed=any(x['human_result']=='確認適用' and k in docs for k,x in state['documents'].items())
    if not confirmed: st.warning('本案尚未設定適用審查依據')
    elif any(not r['executed'] for r in rows):st.info('部分規定檢核仍待確認計算方式或資料；請由審查依據設定核對。')
    st.button('設定審查依據',key='setup_basis',on_click=go,args=('規定與審查依據',))
    c=flow.counts(rows)
    for col,k,icon in zip(st.columns(4),flow.STATES,['🟢','🟡','🔴','⚪']): col.metric(icon+' '+k,f'{c[k]} 項')
    st.write(f'**承辦人已檢視 {sum(r["reviewed"] for r in rows)} / {len(rows)} 項**')
    st.caption(f'實際已執行 {sum(r["executed"] for r in rows)} 項；其餘為待設定／待確認項目。資料正常僅代表本項條件，並非案件審查通過。')
    if active.get('semantic'):st.caption('上列含 4 項 AI 示範流程，不代表已執行真實模型語意判讀。')
    filtered=st.checkbox('只看需要處理',key='needs_'+active['case_id'])
    visible=flow.priorities(rows) if filtered else rows
    st.caption('排序：疑似異常 → 待人工確認 → 資料不足 → 資料正常。篩選保留已記錄但仍有提醒的項目。')
    if not visible:
        st.info('目前沒有需要處理的提醒項目。')
    else:
        lookup={r['key']:r for r in visible}; key='ux_item_'+active['case_id']
        if st.session_state.get(key) not in lookup:st.session_state[key]=next(iter(lookup))
        selected=st.selectbox('選擇檢核項目',list(lookup),format_func=lambda k:lookup[k]['name']+'｜'+lookup[k]['status'],key=key)
        row=lookup[selected]
        if row.get('semantic'):
            semantic_card(active,row)
            st.button('產生審查摘要',key='make_summary',on_click=go,args=('系統審查摘要',),type='primary')
            return
        st.subheader(row['name'])
        st.write('**'+row['status']+'**　｜　'+row['kind'])
        st.write('**系統發現**');st.write(row['finding'])
        left,right=st.columns(2)
        with left:
            st.write('**案件資料**')
            vals=list(row['values'].items())
            if len(vals)>12:
                st.write(f'本項涉及 {len(vals)} 個欄位，其中 {sum(v is None or v=="" or v==[] for _,v in vals)} 個未提供。')
                with st.expander('查看本項全部案件資料'):
                    st.table([{'欄位':label(k),'原表值':display(v)} for k,v in vals])
            else:st.table([{'欄位':label(k),'原表值':display(v)} for k,v in vals])
        with right:
            st.write('**規定要求**');st.write(row['requirement'])
            st.write('**建議處理**');st.write(row['suggestion'])
        with st.expander('查看完整依據與證據',expanded=False):
            st.caption('Excel 檔名、Sheet、儲存格及原始值；規則編號、版本、PDF 原文與頁碼、來源 SHA-256、計算方式完整保留。')
            st.json({'Excel來源':active['case_data']['source'],'原始系統狀態':row['original_status'],'完整證據':row['evidence']})
        st.subheader('承辦人確認')
        st.caption('已儲存：'+(row['human'] or '尚未處理')+'；人工結果不改寫系統發現。')
        stamp=str(row.get('run',{}).get('run_id',0))
        prefix=active['case_id']+'_'+row['key']+'_'+stamp
        with st.form('ux_form_'+prefix):
            choice=st.selectbox('承辦人處理結果',HUMAN_CHOICES,index=HUMAN_CHOICES.index(row['human'] or '保留待確認'),key='ux_choice_'+prefix)
            note=st.text_area('承辦人備註',value=row['note'],key='ux_note_'+prefix)
            if st.form_submit_button('儲存本項確認',type='primary'):
                flow.save(active,state,row,choice,note);st.rerun()
    st.button('產生審查摘要',key='make_summary',on_click=go,args=('系統審查摘要',),type='primary')
