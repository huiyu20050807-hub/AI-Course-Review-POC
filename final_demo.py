"""Local presentation templates only. Never register executable review rules."""
from decimal import Decimal, InvalidOperation
from copy import deepcopy
from data_checks import value
from review_rules import digest
from workflow_ui import resources

NOTICE='AI Agent POC 模擬｜目前未串接生成式 AI；分析文字用於展示未來 AI 輔助審查之操作方式，最終仍由承辦人確認。'

def references():
    _,docs=resources()
    sop=next(d for d in docs.values() if '標準作業程序' in d['file_name'])
    manual=next(d for d in docs.values() if d['file_name']=='產業人才投資計畫作業手冊.pdf')
    def ref(doc,page,start,end=None):
        text=doc['pages'][page-1]['text']; a=text.index(start); b=text.index(end,a) if end else len(text)
        return dict(document_id=doc['document_id'],file_name=doc['file_name'],page=page,
                    text=text[a:b].strip(),sha256=doc['sha256'],source_path=doc['source_path'])
    return {
        'name':[ref(sop,8,'(8)','3.  訓練職類')],
        'goals':[ref(sop,10,'12.  訓練需求調查','14.  訓練師資'),ref(sop,20,'4.  課程內容大綱','5.  課程內容')],
        'hours':[ref(sop,9,'10.  訓練時數','(2)  單日')],
        'people':[ref(sop,9,'7.  訓練人數','8.')],
        'staff':[ref(sop,21,'10.  課程師資','13.  教材')],
        'cost':[ref(manual,23,'(一) 單一人時成本','(二)')],
        'materials':[ref(manual,23,'(二) 材料費','經費分類代碼')],
        'occupation':[ref(sop,8,'3.  訓練職類','6.  政策性')],
    }

def demo_rows(case):
    d=case['case_data'];refs=references();out=[]
    content={f'sessions.{i}.content':s.get('content') for i,s in enumerate(d['sessions'])}
    specs=[('name','課程名稱與課程內容','course.name'),('goals','訓練需求、目標與職場應用','objectives'),
           ('hours','訓練時數原則','course.declared_hours'),('people','每班補助人數原則','course.enrollment'),
           ('staff','師資／助教及授課時數','instructors'),('cost','單一人時成本上限','budget.hourly_cost'),
           ('materials','固定費用與材料費比例','budget.materials_total'),('occupation','職類／職能與課程內容','course.occupation')]
    for key,name,field in specs:
        vals={field:value(d,field)}
        if key=='goals':vals={f'objectives.{k}':v for k,v in d['objectives'].items()}
        if key in ('name','goals','occupation'):vals.update(content)
        if key=='staff':
            vals['assistants']=d['assistants']
            vals.update({f'sessions.{i}.{k}':s.get(k) for i,s in enumerate(d['sessions']) for k in ('teacher','assistant','hours')})
        if key in ('cost','materials'):vals.update({f:value(d,f) for f in ('course.declared_hours','course.enrollment','budget.fixed_total','budget.hourly_cost','course.occupation')})
        missing=value(d,field) in (None,'',[],{})
        if key in ('name','goals','occupation'):missing=missing or not content or any(v in (None,'') for v in content.values())
        if key=='staff':missing=missing or any(s.get('teacher') is None for s in d['sessions'])
        status='資料不足' if missing else '待人工確認'
        analysis='AI POC 模擬：建議人工確認。已整理原表文字與下方規定；文字關聯性未經模型判讀，不能因欄位有填就認定內容相符。'
        if key in ('name','goals','occupation'):
            heading=str(value(d,field)) if key!='goals' else str(d['objectives'].get('goals_raw') or '')
            sample=next((str(v) for v in content.values() if v),'未提供')
            analysis=f'案件摘錄：{heading[:180]}；首筆課程內容：{sample[:180]}。'+analysis
        reason='本項涉及語意、資格或例外情況，且文件適用版本仍須確認，因此列入人工提醒。'
        if missing:analysis='資料不足 → 建議承辦人確認／補件；未以空白推定不符合，也未完成資格或語意判斷。'
        elif key in ('hours','people','cost','materials'):
            try:
                number=Decimal(str(value(d,field)))
                if key=='hours':
                    analysis=f'案件資料：{number:g} 小時。假設採用所列版本的一般時數原則：16 ≤ {number:g} ≤ 144。模擬數值比對：'+('落於範圍內' if 16<=number<=144 else '超出一般範圍，發現可能疑點')+'。學分班等例外與開課期間未在此判定。'
                elif key=='people':
                    analysis=f'案件資料：計畫訓練人數 {number:g} 人；原文限制的是核定補助人數 40 人。示範比較：{number:g} '+('≤' if number<=40 else '>')+' 40。兩種人數意義不同，請確認實際申請補助人數與訓練容量，不能直接認定符合。'
                elif key=='cost':
                    hours=Decimal(str(d['course']['declared_hours']));limit=Decimal('195.50') if hours<48 else Decimal('170')
                    analysis=f'案件：{hours:g} 小時；表列單一人時成本 {number} 元。假設採用所列版本：'+('170 × 1.15 = 195.50 元（低於 48 小時）' if hours<48 else '一般上限 170 元（未低於 48 小時）')+f'。比對：{number} '+('≤' if number<=limit else '>')+f' {limit}。模擬判斷：'+('未超過此項一般上限' if number<=limit else '超出一般上限，發現可能疑點')+'；政策性產業等例外另需確認。'
                else:
                    fixed=Decimal(str(d['budget']['fixed_total']))
                    analysis=f'案件材料費 {number} 元；固定費用 {fixed} 元。'+(f'材料費 ÷ 固定費用 × 100 = {number/fixed*100:.2f}%。' if fixed>0 else '固定費用非正值，無法計算比例。')+'原文要求依職類比例上限編列；本展示未自動選取職類比例，不能據此宣稱未超標，請核對職類與材料品項。'
            except (InvalidOperation,TypeError,KeyError):status='資料不足';analysis='資料不足 → 必要數值缺漏或無法解析，請補充原表資料。'
        elif key=='staff' and not missing:
            analysis='師資與課表欄位已提供；請逐一核對專業、資格佐證及同一講師授課時數是否超過 54 小時原則。助教空白不代表不需要助教，亦不代表資格符合。本展示未辨識同名師資或附件資格。'
        analysis+=' 注意：以下來源只作模擬參考，不表示已確認適用本案；116 上半年文件不可自動套用至 115 下半年。'
        evidence={'sources':refs[key],'values':deepcopy(vals),'analysis':analysis,'reason':reason,'template_version':'final-demo-1'}
        fingerprint=digest(evidence);saved=case.get('final_demo_reviews',{}).get(key,{})
        current=saved.get('fingerprint')==fingerprint
        out.append(dict(key='SIM-'+key,name=name+'（模擬）',kind='AI Agent 模擬',status=status,values=vals,
            finding=analysis,requirement='所列原文的假設性展示；非正式規則檢核',suggestion=reason,evidence=evidence,
            human=saved.get('human') if current else None,note=saved.get('note','') if current else '',reviewed=current and bool(saved.get('human')),
            executed=False,fingerprint=fingerprint))
    return out

def save_demo(case,row,choice,note):
    case.setdefault('final_demo_reviews',{})[row['key'][4:]]={'fingerprint':row['fingerprint'],'human':choice,'note':note}
