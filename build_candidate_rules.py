"""Explicit, locally curated candidates; never called by the application."""
import json
from pathlib import Path
from policy_parser import get_document, scan_pdfs, compact

ROOT = Path(__file__).parent

def build():
    rules = []
    for path in scan_pdfs():
        d = get_document(path)
        if '手冊' in d['file_name']:
            specs = [(26, '單一人時成本=', '單一人時成本公式一致性', 'A', ['budget.fixed_total', 'budget.hourly_cost', 'course.enrollment', 'course.declared_hours'], 'hourly_formula', '以原式精確比较；不假設四捨五入容差，不一致仍須人工核對計價精度。'),
                     (6, '一日上課總時數', '每日與時段訓練時數', 'B', ['sessions'], 'manual', '有專案例外；時段分組與核准附件須人工確認。'),
                     (6, '室外教學', '室外教學時數比例', 'C', ['sessions'], 'manual', 'Excel 未提供室外教學標記，不能把空白視為否。'),
                     (6, '同一講師', '同一講師授課時數', 'C', ['sessions', 'instructors'], 'manual', '教師身分空白，且有專案例外。'),
                     (27, '行政管理費', '行政管理費支用比例', 'C', ['budget'], 'manual', '缺各項支用明細；預算不等於實際支用。')]
        elif d['document_type'] == '計畫':
            specs = [(4, '核定補助人數', '核定補助人數與例外', 'C', ['course.enrollment'], 'manual', '計畫訓練人數不是核定補助人數，缺核定資料與例外附件。'),
                     (4, '訓練時數應達', '班次時數與開課期間', 'B', ['course.declared_hours', 'course.start_date', 'course.end_date'], 'manual', '原則、學分班及適用前提須人工判讀，不能任意以天數代替月份。'),
                     (4, '開訓日期', '年度期別與開訓日期', 'B', ['course.start_date', 'plan'], 'manual', '有另行公告例外，版本與公告需人工確認。'),
                     (4, '訓練班次地點', '訓練地點與服務區域', 'C', ['facilities'], 'manual', '缺核定服務轄區、立案及例外附件。')]
        else:
            specs = [(1 if '原則' in d['file_name'] else 10, '師資', '師資佐證與課程關聯', 'B', ['instructors'], 'manual', '須原文脈絡、職類適用範圍與附件人工判讀；師資目前空白。')]
        for page, needle, name, grade, fields, method, note in specs:
            matches = [s for s in d['sections'] if s['page_start'] == page and compact(needle) in compact(s['text'])]
            if not matches:
                raise ValueError((path.name, page, needle))
            s = matches[0]
            source = {'document_id': d['document_id'], 'sha256': d['sha256'], 'file_name': d['file_name'], 'section_id': s['section_id'], 'page': page, 'text': s['text'], 'source_path': d['source_path'], 'archived_source_path': d['archived_source_path']}
            if '原則' in d['file_name']:
                name = '民俗調理／推拿整復師資與技檢認列'
                note = '僅來源表格【05-02】條件候選，不適用所有職類；需目的事業主管機關師資資格與考照資料人工核對。'
            thresholds = {'核定補助人數與例外': '四十人；百分之二十（核定資料及專案例外）',
                '班次時數與開課期間': '十六至一百四十四小時；四個月（原文前提與例外保留）',
                '每日與時段訓練時數': '單一時段四小時；一日八小時；休息一小時（專案例外）',
                '室外教學時數比例': '總時數五分之一', '同一講師授課時數': '五十四小時（專案例外）',
                '行政管理費支用比例': '前列各項費用百分之九'}
            rules.append(dict(rule_id=f'REV-{len(rules)+1:03}', rule_name=name, category=grade, description=name,
                rule_type='arithmetic' if method != 'manual' else 'manual', severity='提示', applicable_plan_types=[d['plan_type']],
                required_case_fields=fields, evaluation_method=method, parameters={}, source_documents=[source],
                source_sections=[s['section_id']], source_pages=[page], source_text=s['text'], version='2B.1',
                status='enabled' if grade == 'A' else 'candidate_rule', created_from='本地 PDF 原文人工整理候選，待承辦人確認',
                created_at='2026-09-11', requires_human_confirmation=True, notes=note,
                fully_programmable=grade == 'A', requires_human_interpretation=grade != 'A', numeric_threshold=thresholds.get(name),
                data_sufficiency='依案件執行時檢查' if grade == 'A' else note))
    (ROOT/'candidate_rules.json').write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding='utf-8')
    return rules

if __name__ == '__main__':
    from collections import Counter
    r = build()
    print(len(r), Counter(x['category'] for x in r))
