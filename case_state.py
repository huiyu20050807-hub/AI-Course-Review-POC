"""Per-case review state. Parsed input is copied, never mutated by widgets."""
from copy import deepcopy
from datetime import datetime
from data_checks import run_checks

DECISIONS = ("尚未處理", "已核對資料", "請補充資料", "保留待人工確認")


def new_case(case_data):
    if case_data["parse_report"]["status"] == "failed" or not case_data["case_id"]:
        raise ValueError("解析失敗的案件不可載入審查")
    return {"case_id": case_data["case_id"], "case_data": deepcopy(case_data),
            "checks": [], "reviews": {}, "revision": 0, "checked": False}


def load_case(cases, data):
    ident = data["case_id"]
    if data["parse_report"]["status"] == "failed":
        raise ValueError("解析失敗的案件不可載入")
    if ident not in cases:
        cases[ident] = new_case(data)
    return ident


def execute_checks(case):
    if not case["checked"]:
        case["checks"] = run_checks(case["case_data"])
        case["reviews"] = {c["id"]: {"decision": "尚未處理", "note": "", "saved_at": None} for c in case["checks"]}
        case["checked"] = True


def save_review(case, check_id, decision, note):
    if decision not in DECISIONS or decision == "尚未處理":
        raise ValueError("請選擇處理結果後再儲存")
    previous = case["reviews"][check_id]
    note = note.strip()
    if previous["decision"] != decision or previous["note"] != note:
        case["reviews"][check_id] = {"decision": decision, "note": note, "saved_at": datetime.now().isoformat(timespec="seconds")}
        case["revision"] += 1


def review_counts(case):
    total = len(case["checks"])
    reviewed = sum(case["reviews"][c["id"]]["saved_at"] is not None for c in case["checks"])
    return reviewed, total - reviewed, total
