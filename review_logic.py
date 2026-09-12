"""單一案件的狀態與固定範本草稿邏輯；不呼叫 AI API。"""
from datetime import datetime
from zoneinfo import ZoneInfo
from demo_data import BANNER, CHECKS, COURSE, ORG, RULE_VERSION, RULE_WARNING, HISTORY, STAGES

DECISIONS = ["尚未確認", "確認符合", "列為補件事項", "保留待確認"]


def now():
    return datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y-%m-%d %H:%M:%S")


def new_case():
    return dict(loaded=False, analysis_started=False, stage=0, error=None,
                reviews={c["id"]: {"decision": "尚未確認", "note": ""} for c in CHECKS},
                revision=0, draft=None, draft_revision=None, saved=None,
                versions=[], confirmed_at=None, preview=False)


def reviewed_count(case):
    return sum(r["decision"] != "尚未確認" for r in case["reviews"].values())


def pending_review_ids(case):
    return [c["id"] for c in CHECKS if case["reviews"][c["id"]]["decision"] == "尚未確認"]


def analysis_completed(case):
    return case["stage"] == len(STAGES) and case["error"] is None


def start_analysis(case):
    case.update(analysis_started=True, stage=0, error=None)


def advance_analysis(case):
    if case["analysis_started"] and not case["error"] and case["stage"] < len(STAGES):
        case["stage"] += 1


def analysis_snapshot(case):
    """總進度與各階段只從同一已完成階段數推導。"""
    completed = case["stage"]
    states = []
    for i in range(len(STAGES)):
        if i < completed:
            state = "已完成"
        elif i == completed and case["error"]:
            state = "處理失敗"
        elif i == completed and case["analysis_started"]:
            state = "處理中"
        else:
            state = "尚未開始"
        states.append(state)
    return dict(completed=completed, total=len(STAGES), progress=completed / len(STAGES),
                states=states, finished=analysis_completed(case))


def stale(case):
    return case["draft"] is not None and case["draft_revision"] != case["revision"]


def save_review(case, rule_id, decision, note):
    if decision not in DECISIONS:
        raise ValueError("未知確認結果")
    value = dict(decision=decision, note=note.strip())
    if case["reviews"][rule_id] != value:
        case["reviews"][rule_id] = value
        case["revision"] += 1
        case["confirmed_at"] = None
        return True
    return False


def edit_draft(case, text):
    if case["draft"] != text:
        case["draft"] = text
        case["confirmed_at"] = None


def archive_draft(case):
    if case["draft"] is not None:
        case["versions"].append(dict(time=now(), text=case["draft"], revision=case["draft_revision"]))
        case["saved"] = case["draft"]


def generate_draft(case):
    archive_draft(case)
    lines = [BANNER, RULE_WARNING, "", "AI 幕僚初審意見草稿（固定範本模擬產生）", "", "一、課程摘要",
             f"案件 DEMO-001｜{COURSE}｜{ORG}",
             "計畫摘要 36 小時，課表合计 42 小時；所列經費合計 68,000 元。", f"檢核依據：{RULE_VERSION}。", "", "二、AI 初步檢核結果"]
    lines += [f"• {c['name']}：{c['finding']}（{c['id']}）" for c in CHECKS if c["status"] == "符合"]
    lines += ["", "三、待確認與疑似異常"]
    lines += [f"• [{c['status']}] {c['name']}：{c['finding']}（{c['id']}：{c['rule']}）" for c in CHECKS if c["status"] != "符合"]
    lines += ["", "承辦人處理結果可與 AI 初步判斷不同，以人工確認結果為準。", "", "四、承辦人確認與處理結果"]
    for c in CHECKS:
        r = case["reviews"][c["id"]]
        lines.append(f"• {c['id']} {c['name']}｜承辦人：{r['decision']}。")
        if r["decision"] != "確認符合":
            lines.append(f"  建議：{c['suggestion']}")
        if r["note"]:
            lines.append(f"  承辦人備註：{r['note']}")
    pending = pending_review_ids(case)
    lines += ["", "五、歷史案例參考（不作為本案核准依據）"]
    lines += [f"• {h['id']} {h['name']}：{h['reason']} 差異：{h['difference']} 歷史處理：{h['outcome']}" for h in HISTORY]
    lines += ["", "六、承辦人後續處理建議", f"尚未完成檢視：{'、'.join(pending) if pending else '無'}。",
              "請依上列逐項處理結果辦理補件或後續確認；本意見僅為初審幕僚意見，不代表課程核定或審查通過。"]
    case["draft"] = "\n".join(lines).replace("合计", "合計")
    case["draft_revision"] = case["revision"]
    case["confirmed_at"] = None


def confirmation_issues(case):
    issues = []
    if not analysis_completed(case):
        issues.append("尚未完成分析。")
    if not case["draft"] or not case["draft"].strip():
        issues.append("請先產生並填寫初審意見。")
    if stale(case):
        issues.append("檢核內容已變更，請先重新產生草稿。")
    remaining = len(pending_review_ids(case))
    if remaining:
        issues.append(f"尚有 {remaining} 項未檢視，請逐項選擇處理結果。")
    if case["draft"]:
        for c in CHECKS:
            if case["reviews"][c["id"]]["decision"] in ("列為補件事項", "保留待確認") and c["id"] not in case["draft"]:
                issues.append(f"請在意見中保留未決事項 {c['id']} 的編號與處理說明。")
    return issues


def confirm(case, acknowledged):
    issues = confirmation_issues(case)
    if not acknowledged:
        issues.append("請先勾選承辦人確認聲明。")
    if issues:
        return issues
    archive_draft(case)
    case["confirmed_at"] = now()
    return []


def case_status(case):
    if case["confirmed_at"]:
        return "初審意見已確認"
    if stale(case):
        return "意見草稿・內容待更新"
    if case["draft"] is not None:
        return "意見草稿"
    if analysis_completed(case):
        return "待承辦人檢視"
    if case["error"]:
        return "分析暫停"
    if case["analysis_started"]:
        return "分析中"
    return "尚未分析"
