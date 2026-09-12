from pathlib import Path
p=Path('final_ux.py')
p.write_text('''"""Readable evidence presentation; original evidence remains intact."""
from decimal import Decimal, InvalidOperation
from pathlib import Path
import streamlit as st
from workflow_ui import label,display,resources
from final_demo import references

def human_progress(rows):
    required=[r for r in rows if r['status']!='資料正常']
    return required,sum(r['reviewed'] for r in required),len(rows)-len(required)

def evidence_sources(row):
    if row['kind']=='AI Agent 模擬':return row['evidence']['sources']
    if row['kind']=='規定條件檢核':return row['evidence']['rule']['source_documents']
    refs=references()
    return refs['staff' if row['key'] in ('DATA-07','DATA-08') else 'hours' if row['key']=='DATA-01' else 'cost']

def readable_evidence(case,row):
    d=case['case_data'];evidence=row['evidence']
    st.markdown('### A. 案件資料')
    st.table([{'案件欄位':label(k) if not k.startswith('objectives') else '訓練需求與目標',
        '原始值':display(v),'來源工作表／儲存格':'；'.join(s['sheet']+' / '+s.get('range',s.get('cell','')) for s in d['field_sources'].get(k,[])) or '請展開原表欄位來源核對'} for k,v in row['values'].items()])
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
''',encoding='utf-8')
p=Path('final_poc.py');s=p.read_text(encoding='utf-8').replace('import time\n','')
s=s.replace('from final_ux import human_progress,readable_evidence','from final_ux import human_progress,readable_evidence\nfrom final_demo import demo_rows,save_demo,NOTICE')
s=s.replace("PAGES=['首頁／選擇案件','審查結果','相關補助資源','審查摘要','⚙ 審查依據設定']","PAGES=['首頁／選擇案件','審查結果','審查摘要','⚙ 審查依據設定']")
s=s.replace("def final_rows(case,state):return [r for r in flow.items(case,state) if r['kind']!='AI 語意輔助']","def final_rows(case,state):return sorted([r for r in flow.items(case,state) if r['kind']!='AI 語意輔助']+demo_rows(case),key=lambda r:flow.ORDER[r['status']])")
a=s.index('def start(path):');b=s.index('\ndef home():',a)
s=s[:a]+'''def start(path):
    st.session_state.pending_path=path
    st.session_state.final_progress={'stage':1,'error':None,'loaded':False}
    nav('進度')

def next_step():
    st.session_state.final_progress['stage']+=1
    if st.session_state.final_progress['stage']==4:nav('審查結果')

def progress():
    state=st.session_state.final_progress
    step=state['stage']
    st.header(f'Step {step}/4 '+{1:'讀取案件資料',2:'比對審查規定',3:'整理檢核結果'}[step])
    try:
        if not state['loaded']:
            path=Path(st.session_state.pending_path)
            data=parsed(path.read_bytes(),path.name,path.name,PARSER_VERSION)
            cid=load_case(st.session_state.cases,data);st.session_state.active_case_id=cid
            state['case_id']=cid;state['loaded']=True
        case=st.session_state.cases[state['case_id']];d=case['case_data']
        rs=state_for(st.session_state.rule_cases,case['case_id'])
        if step==1:
            st.write('已讀取：'+d['course']['name']+'｜'+d['organization']['name'])
            st.write('計畫別：'+display(d['plan']['name']))
            st.write(f"訓練時數：{d['course']['declared_hours']} 小時；訓練人數：{d['course']['enrollment']} 人")
            st.write(f"固定費用：{d['budget']['fixed_total']} 元；材料費：{d['budget']['materials_total']} 元")
            st.write(f"已讀取 {len(d['sessions'])} 筆課表內容")
            with st.expander('查看課程內容'):st.table([{'內容':x['content'],'時數':display(x['hours'])} for x in d['sessions']])
            st.button('下一步：比對審查規定',key='final_step_next',on_click=next_step,type='primary')
        elif step==2:
            if not state.get('checked'):
                execute_checks(case);rules,docs=resources();flow.synchronize(case,rs,rules,docs);state['checked']=True
            _,docs=resources()
            st.write('案件計畫別：'+d['plan']['name'])
            st.write('已載入的審查文件（載入不代表確認適用）：')
            for doc in docs.values():st.write('• '+doc['file_name'])
            st.write('比對面向：課程名稱／內容、時數、人數、師資、經費、職類。')
            st.caption('版本未確認的正式規則不執行；模擬分析另外標示來源與限制。')
            st.button('下一步：整理優先提醒',key='final_step_next',on_click=next_step,type='primary')
        else:
            rows=final_rows(case,rs)
            for col,(k,v) in zip(st.columns(4),flow.counts(rows).items()):col.metric(STATUS[k],f'{v} 項')
            st.write('已完成既有 8 項資料品質檢查；可執行規則依版本與公式確認狀態執行。另整理 8 個模擬關注面向，並非真實 AI 判斷。')
            st.button('下一步：查看智慧檢核結果',key='final_step_next',on_click=next_step,type='primary')
    except (OSError,ValueError,KeyError) as exc:
        state['error']=str(exc);st.error('未完成檢核：'+str(exc))

''' + s[b:]
s=s.replace("st.caption('分析完成 5 / 5｜'","st.caption('Step 4/4 完成｜'")
s=s.replace('PAGES[4]','PAGES[3]')
s=s.replace("st.button('下一步：查詢相關補助資源',on_click=nav,args=(PAGES[2],),type='primary')","st.button('下一步：審查摘要',on_click=nav,args=(PAGES[2],),type='primary')")
s=s.replace("st.button('下一步：查詢相關補助資源',key='final_next_resources',on_click=nav,args=(PAGES[2],),type='primary')","st.button('下一步：審查摘要',key='final_next_summary',on_click=nav,args=(PAGES[2],),type='primary')")
a=s.index("    a,b=st.columns(2)\n    with a:",s.index('def result'))
b=s.index("    with st.expander('查看完整依據與證據'):",a)
s=s[:a]+"    st.write('**建議處理**');st.write(r['suggestion'])\n"+s[b:]
s=s.replace('flow.save(case,state,r,choice,note);st.rerun()',"save_demo(case,r,choice,note) if r['kind']=='AI Agent 模擬' else flow.save(case,state,r,choice,note)\n            st.rerun()")
s=s.replace("elif page==PAGES[2]:resource_page()\n",'')
s=s.replace("Workshop-POC-FINAL｜案件資料：實際計畫表｜系統輔助審查，最終由承辦人確認","POC 概念展示｜AI Agent 模擬分析非正式審查結論｜最終由承辦人確認")
s=s.replace("st.caption('系統先找疑點、整理依據，承辦人聚焦判斷。')","st.caption('系統先找疑點、整理依據，承辦人聚焦判斷。')\nst.caption(NOTICE)")
s=s.replace('人工審查與補助資源查詢流程','人工審查與摘要流程')
s=s.replace("lines += ['五、承辦人處理結果',f'需人工處理共 {len(required)} 項，已完成 {done} / {len(required)}。']","lines += ['五、承辦人處理結果',f'系統已初步檢核：{normal} 項',f'需承辦人確認：{len(required)} 項',f'承辦人已處理：{done} 項',f'尚待處理：{len(required)-done} 項',f'需人工處理共 {len(required)} 項，已完成 {done} / {len(required)}。']")
s=s.replace("lines += ['本摘要為系統輔助整理結果，最終審查內容以承辦人確認為準。']","lines += [NOTICE,'本摘要為系統輔助整理結果，最終審查內容以承辦人確認為準。']")
p.write_text(s,encoding='utf-8')
