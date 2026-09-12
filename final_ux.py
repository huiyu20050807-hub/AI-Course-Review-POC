"""Readable evidence presentation; original evidence remains intact."""
from decimal import Decimal, InvalidOperation
from pathlib import Path
import streamlit as st
from workflow_ui import label,display,resources
from final_demo import references

def human_progress(rows):
    required=[r for r in rows if r['status']!='資料正常']
    return required,sum(r['reviewed'] for r in required),len(rows)-len(required)

def readable_value(v):
    if isinstance(v,dict):return '\n'.join(str(k)+'：'+readable_value(x) for k,x in v.items())
    if isinstance(v,list):return '\n'.join(readable_value(x) for x in v) or '未提供'
    return display(v)

def evidence_sources(row):
    if row['kind']=='AI Agent 模擬':return row['evidence']['sources']
    if row['kind']=='規定條件檢核':return row['evidence']['rule']['source_documents']
    refs=references()
    return refs['staff' if row['key'] in ('DATA-07','DATA-08') else 'hours' if row['key']=='DATA-01' else 'cost']

def readable_evidence(case,row):
    d=case['case_data'];evidence=row['evidence']
    st.markdown('### A. 案件資料')
    st.table([{'案件欄位':label(k) if not k.startswith('objectives') else '訓練需求與目標',
        '原始值':readable_value(v),'來源工作表／儲存格':'；'.join(s['sheet']+' / '+s.get('range',s.get('cell','')) for s in d['field_sources'].get(k,[])) or '請展開原表欄位來源核對'} for k,v in row['values'].items()])
    st.markdown('### B. 對應審查規定')
    if row['kind']=='資料品質檢查':st.caption('以下為相關審查背景原文；本項計算依據仍為 Excel 內部一致性或缺漏檢查，不把背景原文當作新增法律義務。')
    _,docs=resources()
    for i,source in enumerate(evidence_sources(row)):
        st.write(source['file_name']+f"｜PDF 第 {source['page']} 頁")
        st.text(source['text'])
        doc=docs.get(source['document_id'])
        if doc and doc['sha256']==source['sha256']:
            st.download_button('查看來源 PDF',Path(doc['source_path']).read_bytes(),file_name=source['file_name'],mime='application/pdf',key='evidence_pdf_'+case['case_id']+row['key']+str(i))
        else:st.warning('來源版本已變更，保留原始摘錄；請到審查依據設定核對原版本。')
    st.markdown('### C. AI Agent 模擬比對')
    if row['kind']=='AI Agent 模擬':st.write(row['finding'])
    elif row['kind']=='資料品質檢查':
        st.write('此處展示既有程式檢查結果，並非生成式 AI 判斷。')
        st.write(evidence['method'])
        if evidence['details']:st.table(evidence['details'])
        st.write(row['finding'])
    else:
        v=row['values']
        try:
            fixed,hourly,people,hours=[Decimal(str(v[k])) for k in ('budget.fixed_total','budget.hourly_cost','course.enrollment','course.declared_hours')]
            if people<=0 or hours<=0:raise ValueError('分母無效')
            st.write(f'案件資料：固定費用 {fixed:,} 元、人數 {people:g} 人、時數 {hours:g} 小時。')
            st.write(f'模擬計算：{fixed:,} ÷ {people:g} ÷ {hours:g} ≈ {fixed/people/hours:,.2f} 元；計畫表填列 {hourly} 元。')
            st.write('原始數值精確比較：'+('一致' if fixed/people/hours==hourly else '不同，請核對填表精度。'))
            st.caption('顯示值取兩位小數，不新增容差。若尚未確認版本／公式，以上僅為算式示範，不代表規則引擎已執行。')
        except (InvalidOperation,ValueError,KeyError):st.write('資料不足 → 必要金額、人數或時數不足，建議承辦人確認／補件。')
    st.markdown('### D. 為什麼需要／不需要承辦人確認')
    st.write('本項由既有程式完成資料檢查，初步未發現異常，無須逐項人工處理；不代表案件核定。' if row['status']=='資料正常' else row['suggestion'])
    with st.expander('進階技術資訊',expanded=False):
        st.json({'Excel':d['source'],'欄位來源':{k:d['field_sources'].get(k,[]) for k in row['values']},'檢核':evidence})
