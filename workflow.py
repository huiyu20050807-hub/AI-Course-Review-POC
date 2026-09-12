"""Presentation/state adapter. Does not change any parser or rule evaluator."""
from collections import Counter
from copy import deepcopy
from case_state import load_case, execute_checks, save_review
from data_checks import value
from policy_applicability import case_context
from review_rules import state_for, execute, digest, save_human, HUMAN_CHOICES

STATES = ['資料正常', '待人工確認', '疑似異常', '資料不足']
ORDER = {'疑似異常': 0, '待人工確認': 1, '資料不足': 2, '資料正常': 3}
MAPPING = {'資料一致':'資料正常', '資料不一致':'疑似異常', '資料未提供':'資料不足',
    '無法解析':'待人工確認', '待人工確認':'待人工確認', '符合規則條件':'資料正常',
    '疑似不符合規則條件':'疑似異常', '資料不足':'資料不足', '不適用':'待人工確認', '無法執行':'待人工確認'}
LEGACY = {'確認系統結果':'已核對資料', '改判':'已核對資料', '要求補充資料':'請補充資料', '不適用':'保留待人工確認', '保留待確認':'保留待人工確認'}
LEGACY_BACK = {'已核對資料':'確認系統結果', '請補充資料':'要求補充資料', '保留待人工確認':'保留待確認'}

def applicable_rules(data, rules):
    plan = case_context(data)['plan_type']
    return [r for r in rules if r['status']=='enabled' and (plan in r['applicable_plan_types'] or 'both' in r['applicable_plan_types'])]

def synchronize(case, state, rules, docs):
    selected = applicable_rules(case['case_data'], rules)
    fingerprint = digest({'rules': selected, 'revision':state['revision'], 'docs':{k:d['sha256'] for k,d in docs.items()}})
    # Reuse the latest real run (including a run performed in the advanced UI).
    if state.get('ux_fingerprint') == fingerprint and state.get('ux_run_id') == (state['runs'][-1]['run_id'] if state['runs'] else None):
        return
    latest = state['runs'][-1] if state['runs'] else None
    if latest and latest['revision']==state['revision'] and all(any(x['rule_digest']==digest(r) for x in latest['results']) for r in selected) and all(s['document_id'] in docs and docs[s['document_id']]['sha256']==s['sha256'] for r in selected for s in r['source_documents']) and state.get('ux_fingerprint',fingerprint)==fingerprint:
        state['ux_fingerprint']=fingerprint
        state['ux_run_id']=latest['run_id']
        return
    execute(state, case['case_data'], selected, docs)
    state['ux_fingerprint'] = fingerprint
    state['ux_run_id'] = state['runs'][-1]['run_id']

def start(cases, rule_cases, data, rules, docs):
    cid = load_case(cases, data)
    execute_checks(cases[cid])
    synchronize(cases[cid], state_for(rule_cases,cid), rules, docs)
    return cid

def items(case, state):
    rows = []
    for c in case['checks']:
        saved = case['reviews'][c['id']]
        overlay = case.get('ux_reviews',{}).get(c['id'],{})
        # An edit from the retained legacy page takes precedence over stale UX metadata.
        same = overlay.get('legacy_snapshot') == saved
        human = overlay.get('human_result') if same else LEGACY_BACK.get(saved['decision'])
        rows.append(dict(key=c['id'], name=c['name'], status=MAPPING[c['status']], original_status=c['status'],
            kind='資料品質檢查', finding=c['finding'], requirement='核對計畫表內部資料；這項不作法規符合判定。',
            values={k:value(case['case_data'],k) for k in c['input_fields']}, suggestion=c['suggestion'],
            evidence=deepcopy(c), human=human, note=saved['note'], reviewed=saved['saved_at'] is not None, executed=True))
    if state['runs']:
        run = state['runs'][-1]
        for index,r in enumerate(run['results']):
            rule=r['rule']
            if not applicable_rules(case['case_data'],[rule]): continue
            findings = {'待人工確認':'本項尚待核對適用文件或計算方式，暫未進行規定檢核。',
                '不適用':'本項來源文件或計畫別不適用；請核對是否排除本項。',
                '無法執行':'目前無法完成計算，請查看依據並核對資料或文件版本。',
                '資料不足':'計算所需資料未完整提供，請確認計畫表或附件。',
                '符合規則條件':'表列單一人時成本與固定費用、人數、時數的計算結果一致。',
                '疑似不符合規則條件':'表列單一人時成本與計算值不同；請核對計價與顯示精度。'}
            rows.append(dict(key=rule['rule_id'],name=rule['rule_name'], status=MAPPING[r['system_result']],
                original_status=r['system_result'], kind='規定條件檢核', finding=findings[r['system_result']],
                requirement='單一人時成本＝固定費用÷人數÷時數；不另假設四捨五入容差。',
                values=deepcopy(r['case_values']),suggestion='核對適用文件、原表金額及計算精度，再確認本項結果。',
                evidence=deepcopy(r), human=r['human_result'],note=r['human_note'],reviewed=bool(r['human_result']),
                executed=r['executed'],run=run,index=index))
    if case.get('semantic'):
        from semantic_checks import rows as semantic_rows
        rows.extend(semantic_rows(case))
    return sorted(rows,key=lambda r:ORDER[r['status']])

def counts(rows):
    c=Counter(r['status'] for r in rows)
    return {k:c[k] for k in STATES}

def priorities(rows):
    return [r for r in rows if r['status']!='資料正常']

def pending(rows):
    return [r for r in priorities(rows) if not r['reviewed']]

def save(case,state,row,choice,note):
    if choice not in HUMAN_CHOICES: raise ValueError('請選擇承辦人處理結果')
    if row['kind']=='資料品質檢查':
        save_review(case,row['key'],LEGACY[choice],note)
        case.setdefault('ux_reviews',{})[row['key']]={'human_result':choice,'legacy_snapshot':deepcopy(case['reviews'][row['key']])}
    else:
        save_human(state,row['run'],row['index'],choice,note)

def summary_text(case,rows):
    c=counts(rows); viewed=sum(r['reviewed'] for r in rows)
    lines=['系統審查摘要',case['case_data']['course']['name'],
        f'本案共檢核 {len(rows)} 項（含待設定項目；實際已執行 {sum(r["executed"] for r in rows)} 項）']
    lines += [f'{k} {c[k]} 項' for k in STATES]
    if case.get('semantic'):lines += ['其中 4 項為 AI 示範流程，不代表已執行真實模型語意判讀。']
    lines += [f'承辦人已處理 {viewed}/{len(rows)} 項','優先處理事項：']
    lines += [f'• {r["name"]}：{r["finding"]} 承辦人：{r["human"] or "尚未處理"}；備註：{r["note"] or "未填寫"}' for r in priorities(rows)] or ['目前沒有優先提醒。']
    lines += ['本摘要由固定範本整理，不是 AI 初審意見；系統檢核為審查輔助，不代表案件核定或正式審查結果。']
    return '\n'.join(lines)
