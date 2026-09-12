"""Workshop-POC-FINAL presentation entry; existing parsers and engines unchanged."""
from pathlib import Path
import os
from html import escape
import streamlit as st
from excel_parser import scan_folder,parse_excel_bytes,DEFAULT_FOLDER,PARSER_VERSION
from case_state import load_case,execute_checks
from review_rules import state_for,HUMAN_CHOICES,approve_rule,digest
from workflow_ui import resources,display,label
import workflow as flow
import subsidy_resources as subsidy
from final_ux import human_progress,readable_evidence
from final_demo import demo_rows,save_demo,NOTICE

ROOT=Path(__file__).parent
PAGES=['首頁／選擇案件','審查結果','審查摘要','⚙ 審查依據設定']
STAGES=['讀取課程計畫','檢查基本資料','比對審查條件','查找審查依據','整理需確認項目']
STATUS={'資料正常':'正常','待人工確認':'待確認','疑似異常':'疑似異常','資料不足':'資料不足'}

def nav(page):st.session_state.final_nav=page

@st.cache_data(show_spinner=False)
def parsed(content,filename,relative,version):return parse_excel_bytes(content,filename,relative)

def final_rows(case,state):return sorted([r for r in flow.items(case,state) if r['kind']!='AI 語意輔助']+demo_rows(case),key=lambda r:flow.ORDER[r['status']])

def cited(rows):
    refs={}
    for r in rows:
        if r['kind']=='規定條件檢核' and r['executed']:
            for src in r['evidence']['rule']['source_documents']:
                refs[(src['file_name'],src['page'])]=src
    return list(refs.values())

def summary_text(case,rows):
    d=case['case_data'];c=d['course'];counts=flow.counts(rows)
    lines=['審查摘要','一、案件基本資料',f"課程名稱：{c['name']}",f"訓練單位：{d['organization']['name']}",
        f"計畫別：{d['plan']['name']}",f"時數：{display(c['declared_hours'])} 小時；人數：{display(c['enrollment'])} 人",
        '二、系統初步檢核結果']
    lines += [f'{STATUS[k]} {v} 項' for k,v in counts.items()]
    lines += [f'實際執行 {sum(r["executed"] for r in rows)} 項；其餘尚待設定或確認。','三、需優先處理事項']
    lines += [f'• {r["name"]}：{r["finding"]}' for r in flow.priorities(rows)] or ['無非正常項目。']
    lines += ['四、相關審查依據']
    lines += [f'• {s["file_name"]}，PDF 第 {s["page"]} 頁' for s in cited(rows)] or ['尚無已執行規則引用的 PDF；資料品質檢查不冒充法規判定。']
    demo_refs={(s['file_name'],s['page']) for r in rows if r['kind']=='AI Agent 模擬' for s in r['evidence']['sources']}
    lines += [f'• 模擬參考（非已採用版本）：{name}，PDF 第 {page} 頁' for name,page in sorted(demo_refs)]
    required,done,normal=human_progress(rows)
    lines += ['五、承辦人處理結果',f'系統已初步檢核：{normal} 項',f'需承辦人確認：{len(required)} 項',f'承辦人已處理：{done} 項',f'尚待處理：{len(required)-done} 項',f'需人工處理共 {len(required)} 項，已完成 {done} / {len(required)}。']
    lines += [f'• {r["name"]}：{r["human"] or "尚未處理"}；備註：{r["note"] or "未填寫"}' for r in required]
    lines += [f'另有 {normal} 項系統檢核結果正常，無須逐項人工確認。']
    lines += [NOTICE,'本摘要為系統輔助整理結果，最終審查內容以承辦人確認為準。']
    return '\n'.join(lines)

def start(path):
    st.session_state.pending_path=path
    st.session_state.final_progress={'stage':1,'error':None,'loaded':False}
    nav('進度')

def next_step():
    st.session_state.final_progress['stage']+=1
    if st.session_state.final_progress['stage']==4:nav('審查結果')

def progress():
    state=st.session_state.final_progress
    step=state['stage']
    st.header(f'Step {step}/4 '+{1:'讀取案件資料',2:'比對審查規定',3:'整理優先提醒'}[step])
    try:
        if not state['loaded']:
            path=Path(st.session_state.pending_path)
            data=parsed(path.read_bytes(),path.name,path.name,PARSER_VERSION)
            cid=load_case(st.session_state.cases,data);st.session_state.active_case_id=cid
            state['case_id']=cid;state['loaded']=True
        case=st.session_state.cases[state['case_id']];d=case['case_data']
        rs=state_for(st.session_state.rule_cases,case['case_id'])
        if step==1:
            with st.container(border=True,key='step_case_card'):
                st.caption('案件摘要')
                st.subheader(d['course']['name'])
                st.write(d['organization']['name'])
                chips=[display(d['plan']['name']),f"{display(d['course']['declared_hours'])} 小時",f"{display(d['course']['enrollment'])} 人"]
                st.markdown('<div class="step-chips">'+''.join('<span>'+escape(x)+'</span>' for x in chips)+'</div>',unsafe_allow_html=True)
                a,b=st.columns(2)
                a.metric('固定費用',display(d['budget']['fixed_total'])+' 元')
                b.metric('材料費',display(d['budget']['materials_total'])+' 元')
                st.caption(f"已讀取 {len(d['sessions'])} 筆課表內容")
                original=Path(st.session_state.pending_path)
                st.download_button('查看原始訓練班別計畫表',original.read_bytes(),file_name=original.name,mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',key='step_excel',on_click='ignore')
            with st.expander('查看課程內容'):st.table([{'內容':x['content'],'時數':display(x['hours'])} for x in d['sessions']])
            st.button('下一步：比對審查規定 →',key='final_step_next',on_click=next_step,type='primary')
        elif step==2:
            if not state.get('checked'):
                execute_checks(case);rules,docs=resources();flow.synchronize(case,rs,rules,docs);state['checked']=True
            _,docs=resources()
            st.subheader(f'已載入 {len(docs)} 份審查依據')
            st.caption('本案計畫別：'+d['plan']['name'])
            st.markdown('<div class="step-focus"><strong>本次比對面向</strong><br>課程名稱／內容 ｜ 時數 ｜ 人數 ｜ 師資 ｜ 經費 ｜ 職類</div>',unsafe_allow_html=True)
            main_name='提升勞工自主學習計畫' if '自主學習' in d['plan']['name'] else '產業人才投資計畫'
            main_files={main_name+'.pdf',main_name+'作業手冊.pdf'}
            def file_card(doc):
                with st.container(border=True):
                    text,button=st.columns([3,1])
                    text.write('**'+doc['file_name']+'**')
                    text.caption('作業手冊' if '作業手冊' in doc['file_name'] else '審查作業原則／程序' if '116年度' in doc['file_name'] else '計畫文件')
                    button.download_button('查看／下載完整 PDF',Path(doc['source_path']).read_bytes(),file_name=doc['file_name'],mime='application/pdf',key='step_pdf_'+doc['document_id'],on_click='ignore')
            st.markdown('### 主要審查依據')
            for doc in docs.values():
                if doc['file_name'] in main_files:file_card(doc)
            st.markdown('### 補充審查依據')
            for doc in docs.values():
                if '116年度' in doc['file_name']:file_card(doc)
            with st.expander('其他已載入文件'):
                for doc in docs.values():
                    if doc['file_name'] not in main_files and '116年度' not in doc['file_name']:file_card(doc)
            st.warning('載入不代表確認適用；部分文件版本仍待承辦人確認。')
            st.button('下一步：整理優先提醒 →',key='final_step_next',on_click=next_step,type='primary')
        else:
            rows=final_rows(case,rs)
            counts=flow.counts(rows)
            st.write(f'已完成 {sum(r["executed"] for r in rows)} 項初步檢核')
            st.write(f'✓ {counts["資料正常"]} 項系統初步未發現異常')
            st.write(f'⚠ {counts["待人工確認"]} 項需要承辦人判斷')
            st.write(f'○ {counts["資料不足"]} 項資料不足')
            st.write(f'🔴 {counts["疑似異常"]} 項疑似異常')
            st.write('系統已將需要人工判斷的項目整理完成，下一步進入審查工作台。')
            st.button('下一步：進入審查工作台 →',key='final_step_next',on_click=next_step,type='primary')
    except (OSError,ValueError,KeyError) as exc:
        state['error']=str(exc);st.error('未完成檢核：'+str(exc))


def home():
    st.subheader('選擇待審案件')
    folder=Path(os.environ.get('WORKSHOP_EXCEL_DIR',str(DEFAULT_FOLDER)))
    options={}
    try:
        for p in scan_folder(folder):
            d=parsed(p.read_bytes(),p.name,str(p.relative_to(folder)),PARSER_VERSION)
            if d['parse_report']['status']!='failed':options[str(p)]=d
            else:st.error(p.name+' 無法解析，未列入可選案件。')
    except OSError as exc:st.error(str(exc))
    if not options:return
    def caption(k):
        d=options[k];return f"[{d['course']['occupation']}] {d['organization']['name']}－{d['course']['name']}"
    selected=st.selectbox('選擇待審案件',list(options),format_func=caption,key='final_candidate')
    d=options[selected];c=d['course']
    with st.container(border=True):
        st.subheader(c['name'])
        st.write('訓練單位：'+display(d['organization']['name']))
        st.write('職類：'+display(c['occupation'])+'　｜　計畫別：'+display(d['plan']['name']))
        a,b=st.columns(2);a.write('**訓練時數：** '+display(c['declared_hours'])+' 小時');b.write('**訓練人數：** '+display(c['enrollment'])+' 人')
    st.button('開始智慧檢核',key='final_start',type='primary',on_click=start,args=(selected,),use_container_width=True)
    st.caption('案件資料為實際計畫表；審查依據為實際規定文件。系統結果僅供輔助審查，最終仍由承辦人確認。')

def result(case,state):
    rows=final_rows(case,state)
    st.header('審查工作台');st.caption('Step 4/4｜承辦人依系統整理結果進行確認與處理')
    for col,k,key in zip(st.columns(4),flow.STATES,['normal','pending','alert','missing']):
        with col.container(key='final_'+key):st.metric(STATUS[k],f'{flow.counts(rows)[k]} 項')
    required,done,normal=human_progress(rows)
    st.write(f'**需人工處理：{len(required)} 項　｜　承辦人已處理：{done} / {len(required)}**')
    st.write(f'系統自動檢核正常：{normal} 項')
    st.caption(f'已執行 {sum(r["executed"] for r in rows)} 項；未完成版本／公式確認的規定項目暫不執行。正常不代表案件核定。')
    if not any(x['human_result']=='確認適用' for x in state['documents'].values()):
        st.warning('本案尚未確認適用審查依據')
    if any(not r['executed'] for r in rows):
        st.button('設定審查依據',key='final_setup',on_click=nav,args=(PAGES[3],))
    filtered=st.toggle('只看需要處理',value=True,key='final_filter_'+case['case_id'])
    visible=flow.priorities(rows) if filtered else rows
    if not visible:
        st.success('目前沒有非正常提醒項目。')
        st.button('下一步：審查摘要',on_click=nav,args=(PAGES[2],),type='primary')
        return
    lookup={r['key']:r for r in visible};key='final_item_'+case['case_id']
    if st.session_state.get(key) not in lookup:st.session_state[key]=next(iter(lookup))
    selected=st.selectbox('查看需要注意的項目',list(lookup),format_func=lambda k:lookup[k]['name']+'｜'+STATUS[lookup[k]['status']],key=key)
    r=lookup[selected];st.subheader(r['name']);st.write('**狀態：'+STATUS[r['status']]+'**')
    st.write('**系統發現**');st.write(r['finding'])
    st.write('**建議處理**');st.write(r['suggestion'])
    with st.expander('查看完整依據與證據'):
        readable_evidence(case,r)
    st.subheader('承辦人確認')
    if r['status']=='資料正常':st.caption('系統檢核完成－無需人工逐項處理。仍可自願記錄人工意見。')
    else:st.caption('已保存：'+(r['human'] or '尚未處理'))
    prefix=case['case_id']+r['key']+str(r.get('run',{}).get('run_id',0))
    with st.form('final_review_'+prefix):
        choice=st.selectbox('處理結果',HUMAN_CHOICES,index=HUMAN_CHOICES.index(r['human'] or '保留待確認'),key='final_choice_'+prefix)
        note=st.text_area('備註',value=r['note'],key='final_note_'+prefix)
        if st.form_submit_button('儲存本項確認',type='primary'):
            save_demo(case,r,choice,note) if r['kind']=='AI Agent 模擬' else flow.save(case,state,r,choice,note)
            st.rerun()
    st.button('下一步：審查摘要',key='final_next_summary',on_click=nav,args=(PAGES[2],),type='primary')

def resource_page():
    st.header('相關補助資源查詢')
    st.info('搜尋結果僅供資源查詢參考，實際資格與適用條件仍應依各計畫規定確認。')
    try:
        docs=subsidy.catalogue()
    except (OSError,ValueError) as exc:st.error(str(exc));return
    st.caption(f'資料來源：{len(docs)} 份 PDF｜一般關鍵字搜尋，非資格判定或 AI 推薦。')
    for d in docs:
        if d['parse_report']['status']!='success':st.warning(d['file_name']+'：部分內容無法擷取，請查看來源原檔。')
    query=st.text_input('搜尋補助資源',placeholder='青年、在職訓練、企業人才、特定對象、職業訓練、補助、失業者',key='resource_query')
    if query.strip():
        hits=subsidy.search(docs,query);st.write(f'找到 {len(hits)} 段相關內容')
        if hits:
            page=st.selectbox('結果頁',list(range(1,(len(hits)+4)//5+1)))
            for i,hit in enumerate(hits[(page-1)*5:page*5]):
                with st.container(border=True):
                    st.subheader(hit['resource_name']);st.caption(hit['category'])
                    st.write(hit['file_name']+f"｜PDF 第 {hit['page_start']} 頁")
                    st.text(hit['text'])
                    with st.expander('查看來源'):
                        st.caption('原始 PDF，可依上述實體頁碼回查。')
                        st.download_button('開啟／下載來源 PDF',Path(hit['source_path']).read_bytes(),file_name=hit['file_name'],mime='application/pdf',key=f'resource_pdf_{page}_{i}')
        else:st.info('沒有找到此關鍵字，請改用較短的詞。')
    st.button('下一步：產出審查摘要',key='final_next_summary',on_click=nav,args=(PAGES[3],),type='primary')

st.set_page_config(page_title='AI 課程審查智慧助手｜Workshop-POC-FINAL',layout='wide')
st.markdown('<style>'+(ROOT/'ui.css').read_text(encoding='utf-8')+'\n.stApp {background:white;} [data-testid="stMetric"]{background:#f4f6f8;} .st-key-final_normal [data-testid="stMetric"]{border-top:4px solid #477d62;} .st-key-final_pending [data-testid="stMetric"]{border-top:4px solid #c39a36;} .st-key-final_alert [data-testid="stMetric"]{border-top:4px solid #ac5050;} .st-key-final_missing [data-testid="stMetric"]{border-top:4px solid #82909e;}\n</style>',unsafe_allow_html=True)
st.markdown("""<style>
[data-testid="stMainBlockContainer"] {max-width:1160px;padding-top:2.5rem;padding-bottom:3rem;}
.step-chips {display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 20px;}
.step-chips span {background:#eaf0f6;color:#214766;padding:5px 12px;border-radius:18px;font-size:16px;}
.step-focus {background:#eef3f8;border-radius:12px;padding:18px 22px;margin:12px 0 24px;color:#23435f;line-height:1.9;}
.st-key-step_case_card {background:#f7f9fc;border-radius:14px;padding:8px;}
.header-poc-note {font-size:14px!important;color:#687889;margin:4px 0 28px;}
.poc-banner {font-size:13px!important;font-weight:400!important;}
[data-testid="stBaseButton-primary"] {background:#173b60;border-color:#173b60;color:white;}
</style>""",unsafe_allow_html=True)
st.markdown('<div class="poc-banner">POC 概念展示｜AI Agent 模擬分析非正式審查結論｜最終由承辦人確認</div>',unsafe_allow_html=True)
st.session_state.setdefault('cases',{});st.session_state.setdefault('rule_cases',{})
st.session_state.setdefault('active_case_id',None);st.session_state.setdefault('final_nav',PAGES[0])
st.sidebar.title('課程審查智慧助手')
for page in PAGES:st.sidebar.button(page,on_click=nav,args=(page,),use_container_width=True)
st.sidebar.caption('本次連線保存處理結果；關機或新連線後不保證保留。')
st.title('產業人才投資方案 AI 課程審查智慧助手')
st.caption('系統先找疑點、整理依據，承辦人聚焦判斷。')
st.markdown('<p class="header-poc-note">AI Agent POC 模擬｜目前未串接生成式 AI｜最終仍由承辦人確認</p>',unsafe_allow_html=True)
page=st.session_state.final_nav
case=st.session_state.cases.get(st.session_state.active_case_id)
if page==PAGES[0]:home()
elif page=='進度':progress()
elif page==PAGES[3]:
    st.button('返回原案件審查結果',key='final_return',on_click=nav,args=(PAGES[1],))
    from policy_ui import render_policy_page
    with st.expander('查看 PDF、查詢原文與確認適用版本',expanded=True):render_policy_page(case,parsed)
    if case:
        rules,docs=resources();state=state_for(st.session_state.rule_cases,case['case_id'])
        for r in flow.applicable_rules(case['case_data'],rules):
            with st.expander('核對並採用計算方式'):
                st.write(r['rule_name']);st.write('單一人時成本＝固定費用÷人數÷時數。請核對原文、欄位及精度限制。')
                with st.expander('查看計算依據'):st.json(r)
                if st.button('確認採用此計算方式',key='final_approve'):
                    approve_rule(state,r,True);st.success('已保存，請返回原案件審查結果。')
elif not case:st.info('請先從首頁選擇案件並開始智慧檢核。')
elif st.session_state.get('final_progress',{}).get('case_id')==case['case_id'] and st.session_state.final_progress['stage']<4:progress()
else:
    state=state_for(st.session_state.rule_cases,case['case_id'])
    try:
        rules,docs=resources();flow.synchronize(case,state,rules,docs)
        if page==PAGES[1]:result(case,state)
        else:
            st.header('審查摘要');st.text(summary_text(case,final_rows(case,state)))
    except (OSError,ValueError,KeyError) as exc:st.error('未能完成依據核對：'+str(exc))
with st.expander('關於本 POC'):
    st.write('本版本主要驗證案件資料解析、規則比對、規定來源追溯、人工審查與摘要流程。生成式 AI 語意分析可於後續串接經核准模型。')
    st.caption('本展示入口不提供 LLM 語意分析、RAG 或生成式初審意見。原有進階版本檔案及功能保留，未修改其核心。')
