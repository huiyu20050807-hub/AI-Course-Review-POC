"""Sourced deterministic rules. No generated legal interpretation or DATA state."""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from policy_applicability import applicability, case_context
from policy_parser import get_document

ROOT = Path(__file__).parent
VERSION_STORE = ROOT/'rule_store'
DOCUMENT_CHOICES = ['確認適用', '確認不適用', '保留待確認']
HUMAN_CHOICES = ['確認系統結果', '改判', '要求補充資料', '不適用', '保留待確認']
RESULTS = ['符合規則條件', '疑似不符合規則條件', '資料不足', '不適用', '待人工確認', '無法執行']
RULE_TYPES = ['arithmetic', 'presence', 'consistency', 'threshold', 'cross_field', 'manual']
REQUIRED = ['rule_id', 'rule_name', 'category', 'description', 'rule_type', 'severity', 'applicable_plan_types', 'required_case_fields', 'evaluation_method', 'parameters', 'source_documents', 'source_sections', 'source_pages', 'source_text', 'version', 'status', 'created_from', 'created_at', 'requires_human_confirmation', 'notes']

def now():
    return datetime.now(timezone.utc).isoformat()

def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()

def validate_rule(rule):
    if any(k not in rule for k in REQUIRED) or rule['rule_type'] not in RULE_TYPES:
        raise ValueError('規則結構不完整或類型不支援')
    if not rule['source_documents'] or not rule['version']:
        raise ValueError('規則必須有真實來源與版本')
    for src in rule['source_documents']:
        path = Path(src['archived_source_path'])
        if sha256(path.read_bytes()).hexdigest() != src['sha256']:
            raise ValueError('來源快照雜湊不符')
        doc = get_document(path)
        sections = {s['section_id']: s for s in doc['sections']}
        s = sections.get(src['section_id'])
        if doc['document_id'] != src['document_id'] or not s or s['page_start'] != src['page']:
            raise ValueError('來源文件、章節或頁碼不符')
        if not src['text'] or src['text'] != s['text'] or src['text'] not in doc['pages'][src['page']-1]['text']:
            raise ValueError('來源原文無法回查')
    if rule['source_sections'] != [s['section_id'] for s in rule['source_documents']] or rule['source_pages'] != [s['page'] for s in rule['source_documents']] or rule['source_text'] != rule['source_documents'][0]['text']:
        raise ValueError('規則來源欄位互相矛盾')
    if rule['status'] == 'enabled':
        # Only this curated formula has an implemented evaluator; no dynamic eval.
        from policy_parser import compact
        if rule['evaluation_method'] != 'hourly_formula' or rule['parameters'] or '單一人時成本=固定費用÷人數÷時數' not in compact(rule['source_text']):
            raise ValueError('沒有核對過原式的可執行規則')
        if rule['required_case_fields'] != ['budget.fixed_total', 'budget.hourly_cost', 'course.enrollment', 'course.declared_hours']:
            raise ValueError('公式欄位映射不符')
    return True

def load_rules():
    rules = json.loads((ROOT/'candidate_rules.json').read_text(encoding='utf-8'))
    for r in rules:
        validate_rule(r)
        pin_rule(r)
    if len({r['rule_id'] for r in rules}) != len(rules):
        raise ValueError('規則 ID 重複')
    return rules

def pin_rule(rule):
    # Version identifiers cannot traverse paths. One definition per id/version.
    import re
    if not all(re.fullmatch(r'[A-Za-z0-9_.-]+', rule[k]) and rule[k] not in ('.', '..') for k in ('rule_id', 'version')):
        raise ValueError('無效規則版本識別碼')
    path = VERSION_STORE/rule['rule_id']/rule['version']/'definition.json'
    if path.exists():
        if digest(json.loads(path.read_text(encoding='utf-8'))) != digest(rule):
            raise ValueError('相同 rule_id/version 不得替換定義；請建立新版本')
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8') as f:
            json.dump(rule, f, ensure_ascii=False, indent=2)

def new_state():
    return dict(documents={}, document_history=[], revision=0, runs=[], approvals={})

def state_for(store, cid):
    return store.setdefault(cid, new_state())

def confirm_document(state, document, context, choice, note):
    if choice not in DOCUMENT_CHOICES:
        raise ValueError('無效人工適用結果')
    event = dict(document_id=document['document_id'], sha256=document['sha256'],
        system_applicability=deepcopy(applicability(document, context)), human_result=choice,
        human_note=note, confirmed_at=now())
    state['documents'][document['document_id']] = event
    state['document_history'].append(deepcopy(event))
    state['revision'] += 1

def approve_rule(state, rule, approved):
    state['approvals'][digest(rule)] = bool(approved)
    state['revision'] += 1

def get_value(data, field):
    value = data
    for key in field.split('.'):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value

def gate(state, rule, current_documents, data):
    plans = rule['applicable_plan_types']
    if 'both' not in plans and 'unknown' not in plans and case_context(data)['plan_type'] not in plans:
        return '不適用', '案件計畫別與規則来源計畫別不同。'
    for src in rule['source_documents']:
        current = current_documents.get(src['document_id'])
        if current is None or current['sha256'] != src['sha256']:
            return '無法執行', '目前 PDF 已更新或不在來源清單；保留舊快照，不自動換用新版本。'
        confirmation = state['documents'].get(src['document_id'])
        if not confirmation or confirmation['sha256'] != src['sha256'] or confirmation['human_result'] == '保留待確認':
            return '待人工確認', '尚未確認本案適用規定版本，正式規則檢核暫不執行。'
        if confirmation['human_result'] == '確認不適用':
            return '不適用', '承辦人已確認本文件不適用。'
    if rule['status'] != 'enabled':
        return '待人工確認', rule['notes']
    if not state['approvals'].get(digest(rule)):
        return '待人工確認', '候選公式、欄位映射與精度限制尚待承辦人核對採用。'
    return None

def evaluate(rule, data):
    values = {f: get_value(data, f) for f in rule['required_case_fields']}
    if any(v is None or v == '' for v in values.values()):
        return '資料不足', '必要欄位未提供，不代填 0。', values
    if rule['evaluation_method'] != 'hourly_formula':
        return '無法執行', '沒有此類型的已核對 evaluator。', values
    try:
        fixed, hourly, people, hours = [Fraction(Decimal(str(v))) for v in values.values()]
    except (InvalidOperation, ValueError, TypeError):
        return '無法執行', '金額、人數或時數無法解析為有限數值。', values
    if people <= 0 or hours <= 0 or fixed < 0 or hourly < 0:
        return '無法執行', '分母須為正數，金額不可為負；需核對原表。', values
    equal = fixed == hourly * people * hours
    method = f"固定費用 {fixed} ÷ 人數 {people} ÷ 時數 {hours} = {fixed/people/hours}；表列單一人時成本 {hourly}。以分數精確比較，不另創容差；差異可能涉及顯示精度，請人工核對。"
    return ('符合規則條件' if equal else '疑似不符合規則條件'), method, values

def execute(state, data, rules, documents):
    results = []
    for rule in rules:
        validate_rule(rule)
        pin_rule(rule)
        blocked = gate(state, rule, documents, data)
        values = {f: deepcopy(get_value(data, f)) for f in rule['required_case_fields']}
        status, method = blocked if blocked else evaluate(rule, data)[:2]
        sources = {f: deepcopy(data.get('field_sources', {}).get(f, [])) for f in rule['required_case_fields']}
        results.append(dict(rule=deepcopy(rule), rule_digest=digest(rule), case_values=values,
            excel_source=deepcopy(data['source']), field_sources=sources, system_result=status,
            calculation=method, executed=blocked is None, human_result=None, human_note='', human_history=[]))
    run = dict(run_id=len(state['runs'])+1, case_id=data['case_id'], created_at=now(),
        revision=state['revision'], document_confirmations=deepcopy(state['documents']),
        rule_approvals=deepcopy(state['approvals']), results=results)
    state['runs'].append(run)
    return run

def save_human(state, run, index, choice, note):
    if choice not in HUMAN_CHOICES or run['revision'] != state['revision']:
        raise ValueError('結果已過期或處理選項無效；請重新執行。')
    item = run['results'][index]
    event = dict(human_result=choice, human_note=note, confirmed_at=now())
    item.update(event)
    item['human_history'].append(deepcopy(event))
