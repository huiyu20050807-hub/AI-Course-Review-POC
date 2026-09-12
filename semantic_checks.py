"""Four minimal local mock checks, immutable AI output and separate human review."""
from copy import deepcopy
import json
from data_checks import value
from review_rules import digest, now
from ai_data_policy import sanitize, require_local, DataPolicyError
from ai_provider import get_provider,validate_output,PROMPT_VERSION,MODEL,BOUNDARY

SPECS={
 'SEM-001':('課程名稱與內容一致性',['course.name'],'課程內容'),
 'SEM-002':('訓練目標與內容一致性',['objectives.goals_raw'],'訓練目標'),
 'SEM-003':('招生對象與內容合理性',['audience.education_raw','audience.qualification_raw'],'招生'),
 'SEM-004':('課程內容完整性／重複性',[],'課程大綱'),
}
HUMAN=['同意 AI 建議','不同意 AI 建議','要求補件','保留待確認']
MAPPING={'未發現明顯問題':'資料正常','建議確認':'待人工確認','需要補充資訊':'資料不足','AI 無法判斷':'待人工確認'}

def policy_context(check_id,state,documents):
    result=[]
    for did,doc in sorted(documents.items()):
        confirmed=state['documents'].get(did,{})
        if confirmed.get('human_result')!='確認適用' or confirmed.get('sha256')!=doc['sha256']:continue
        for section in doc['sections']:
            text=section['text']
            if SPECS[check_id][2] in ''.join(text.split()) and len(text)<=1600:
                result.append({'document_id':did,'file_name':doc['file_name'],'sha256':doc['sha256'],
                    'section_id':section['section_id'],'page':section['page_start'],'text':text})
                break
        if len(result)==2:break
    return result

def build_input(data,check_id,state,documents):
    fields=SPECS[check_id][1]+[f'sessions.{i}.content' for i in range(len(data['sessions']))]
    minimal={field:value(data,field) for field in fields}
    policies=policy_context(check_id,state,documents)
    # References are local evidence, NOT part of the provider request.
    request={'case_context':minimal,'policy_context':[{'reference':f'P{i+1}','text':p['text']} for i,p in enumerate(policies)]}
    cleaned,report=sanitize(request)
    if len(json.dumps(cleaned,ensure_ascii=False))>50000:raise DataPolicyError('必要文字超過安全輸入上限，請人工分段核對；未送出。')
    return {'request':cleaned,'field_names':fields,'policies':policies,'data_policy':report,
        'sources':{k:deepcopy(data['field_sources'].get(k,[])) for k in fields},'fingerprint':digest({'input':cleaned,'policy_versions':[(p['sha256'],p['section_id']) for p in policies]})}

def current_fingerprint(case,state,docs):
    return digest({k:build_input(case['case_data'],k,state,docs)['fingerprint'] for k in SPECS})

def run(case,state,documents,provider_name='mock'):
    require_local(provider_name)
    provider=get_provider(provider_name)
    outputs=[]
    # Nothing mutates deterministic results or human decisions.
    for ident,(name,_,_) in SPECS.items():
        request=build_input(case['case_data'],ident,state,documents)
        try:
            raw=validate_output(provider.analyze_semantic_check(ident,**request['request']))
            completed=True
        except (ValueError,TypeError,KeyError):
            raw={'status':'AI 無法判斷','analysis':'示範回應未通過格式驗證，請人工核對。',
                'risk_level':'unknown','confidence':None,'suggested_attention':'請重新執行或保留待確認。',
                'limitations':['回應格式驗證失敗，沒有完成語意輔助。']}
            completed=False
        outputs.append(dict(semantic_check_id=ident,check_name=name,category='AI 語意輔助',input_fields=request['field_names'],
            source_evidence=request['sources'],policy_context=request['policies'],prompt_version=PROMPT_VERSION,
            model_name=MODEL,provider='mock',analysis=raw['analysis'],status=raw['status'],risk_level=raw['risk_level'],
            confidence=raw['confidence'],suggested_attention=raw['suggested_attention'],limitations=raw['limitations'],
            human_result=None,human_note='',created_at=now(),raw_output=deepcopy(raw),human_history=[],
            used_input=request['request'],data_policy=request['data_policy'],completed=completed,prompt_boundary=BOUNDARY))
    previous=case.get('semantic')
    if previous:case.setdefault('semantic_history',[]).append(deepcopy(previous))
    case['semantic']={'batch_id':(previous['batch_id']+1 if previous else 1),'results':outputs,
        'fingerprint':current_fingerprint(case,state,documents),'stale':False}

def refresh(case,state,docs):
    if 'semantic' not in case:return
    try:case['semantic']['stale']=case['semantic']['fingerprint']!=current_fingerprint(case,state,docs)
    except (ValueError,KeyError):case['semantic']['stale']=True

def save(case,ident,choice,note):
    if choice not in HUMAN or case['semantic']['stale']:raise ValueError('選项無效或分析已過期，請重新執行。')
    result=next(r for r in case['semantic']['results'] if r['semantic_check_id']==ident)
    event={'human_result':choice,'human_note':note.strip(),'confirmed_at':now()}
    result.update(event);result['human_history'].append(deepcopy(event))

def rows(case):
    batch=case.get('semantic')
    if not batch:return []
    result=[]
    for item in batch['results']:
        stale=batch['stale']
        result.append(dict(key=item['semantic_check_id'],name=item['check_name'],kind='AI 語意輔助',
            status='待人工確認' if stale else MAPPING[item['status']], original_status='AI 無法判斷' if stale else item['status'],
            finding='AI 示範模式：依據已變更，請重新執行。' if stale else item['analysis'],
            values=item['used_input']['case_context'],requirement='文字語意參考，不作正式法規結論。',suggestion=item['suggested_attention'],
            evidence=deepcopy(item),human=item['human_result'],note=item['human_note'],
            reviewed=bool(item['human_result']) and not stale,executed=item['completed'] and not stale,
            semantic=True,batch_id=batch['batch_id']))
    return result

def draft_ready(case,state,all_rows):
    from workflow import items
    fields=('key','original_status','human','note','executed','reviewed')
    current=items(case,state)
    if [{k:r[k] for k in fields} for r in current]!=[{k:r[k] for k in fields} for r in all_rows]:return False
    batch=case.get('semantic')
    return bool(case['checked'] and batch and not batch['stale'] and len(batch['results'])==4
        and all(r['completed'] for r in batch['results']) and state['runs'] and state['runs'][-1]['revision']==state['revision']
        and any(r['kind']=='規定條件檢核' for r in all_rows)
        and all(r['executed'] and r['reviewed'] for r in all_rows))

def draft_input(case,state,all_rows):
    if not draft_ready(case,state,all_rows):raise ValueError('需完成三層檢核並儲存各項人工處理，才能產生草稿。')
    payload={'case_summary':{'course_name':case['case_data']['course']['name']},
        'checks':[{'name':r['name'],'layer':r['kind'],'system_result':r['original_status'],
            'finding':r['finding'],'human_result':r['human'],'human_note':r['note']} for r in all_rows],
        'policy_context':[]}
    seen=set()
    for row in all_rows:
        if row['kind']=='規定條件檢核':
            for src in row['evidence']['rule']['source_documents']:
                confirm=state['documents'].get(src['document_id'],{})
                if confirm.get('human_result')!='確認適用' or confirm.get('sha256')!=src['sha256']:raise ValueError('草稿規定來源未確認')
                if src['section_id'] not in seen:
                    payload['policy_context'].append({'text':src['text'],'page':src['page']});seen.add(src['section_id'])
    # Do not include raw workbook paths, all case_data, unsaved widget notes, or source bytes.
    return sanitize(payload)[0]

def draft_signature(case,state,all_rows):
    return digest({'input':draft_input(case,state,all_rows),'semantic_batch':case['semantic']['batch_id'],
        'rule_run':state['runs'][-1]['run_id'],'revision':state['revision'],
        'saved_review_digest':digest([(r['human'],r['note']) for r in all_rows])})

def generate_draft(case,state,all_rows):
    request=draft_input(case,state,all_rows)
    checks=request['checks']
    text=['AI 示範模式｜固定範本草稿，未呼叫真實 AI',
        'AI 產生之初審意見草稿，須經承辦人確認後始可使用。',
        '一、案件摘要',request['case_summary']['course_name'],'二、系統檢核結果']
    text += [f'• {r["name"]}：{r["system_result"]}' for r in checks if r['layer']!='AI 語意輔助']
    text += ['三、建議關注事項']+[f'• {r["name"]}：{r["finding"]}' for r in checks if r['layer']=='AI 語意輔助']
    text += ['四、承辦人處理結果']+[f'• {r["name"]}：{r["human_result"]}；{r["human_note"] or "未填備註"}' for r in checks]
    text += ['五、待補充／待確認事項']+[f'• {r["name"]}：{r["human_result"]}；{r["human_note"] or "請持續追蹤"}' for r in checks if r['human_result'] in ('要求補件','要求補充資料','保留待確認','不同意 AI 建議')]
    text += ['本草稿不代表案件核定、退件或正式審查結果。']
    if case.get('ai_draft'):case.setdefault('ai_draft_history',[]).append(deepcopy(case['ai_draft']))
    case['ai_draft']={'text':'\n'.join(text),'original_text':'\n'.join(text),'input':request,
        'fingerprint':draft_signature(case,state,all_rows),'created_at':now(),'confirmed_at':None,'provider':'mock','model':MODEL}

def confirm_draft(case,state,all_rows,text):
    draft=case['ai_draft']
    if draft['fingerprint']!=draft_signature(case,state,all_rows):raise ValueError('草稿已過期，請重新產生。')
    if not text.strip():raise ValueError('草稿不可空白')
    draft.update(text=text,confirmed_at=now())
