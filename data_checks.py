"""Phase 1 arithmetic and presence checks, NOT legal compliance rules."""
from decimal import Decimal

STATUSES = ("資料一致", "資料不一致", "資料未提供", "無法解析", "待人工確認")
CHECK_VERSION = "DATA-2.0.1"
CORE = ("organization.name", "course.name", "course.occupation", "plan.name",
        "plan.year_roc", "plan.term", "course.enrollment", "course.declared_hours",
        "course.start_date", "course.end_date")


def value(data, key):
    current = data
    for part in key.split("."):
        current = current[int(part)] if isinstance(current, list) else current.get(part)
        if current is None:
            return None
    return current


def source_errors(data, keys):
    errors = [e["field"] for e in data["parse_report"]["errors"]]
    return [e for e in errors if e == "workbook" or any(e == k or e.startswith(k + ".") for k in keys)]


def make_result(data, ident, title, status, finding, keys, method, details=None):
    refs = []
    for key in keys:
        refs.extend(data["field_sources"].get(key, []))
    return {"id": ident, "name": title, "status": status, "finding": finding,
            "method": method, "check_version": CHECK_VERSION, "input_fields": keys,
            "evidence": refs, "details": details or [],
            "suggestion": "請核對原計畫表與相關佐證；資料未提供不等於不符合，仍由承辦人判斷。"}


def arithmetic(data, ident, title, equations):
    keys = list(dict.fromkeys(k for left, right, operation in equations for k in left + [right]))
    if source_errors(data, keys):
        status, finding, details = "無法解析", "計算所需欄位含解析錯誤，未進行完整比較。", []
    elif any(value(data, k) is None for k in keys) or not equations:
        status, finding, details = "資料未提供", "計算所需資料未完整提供，沒有將空白補成 0。", []
    else:
        details = []
        for left, right, operation in equations:
            vals = [Decimal(value(data, k)) for k in left]
            calculated = sum(vals, Decimal(0)) if operation == "sum" else vals[0] * vals[1]
            recorded = Decimal(value(data, right))
            expression = (f"{len(vals)} 筆課表時數加總" if len(vals) > 3 else " + ".join(map(str, vals))) if operation == "sum" else " × ".join(map(str, vals))
            details.append({"計算式": expression,
                            "計算值": str(calculated), "原表值": str(recorded),
                            "差額": str(calculated - recorded)})
        status = "資料一致" if all(Decimal(x["差額"]) == 0 for x in details) else "資料不一致"
        finding = "數值相符；僅代表本項資料內部一致。" if status == "資料一致" else "計算值與原表值不同，請釐清差異。"
    return make_result(data, ident, title, status, finding, keys, "十進位精確加總／乘法與原表數值比較，不判定法規符合性。", details)


def run_checks(data):
    session_keys = [f"sessions.{i}.hours" for i in range(len(data["sessions"]))]
    results = [arithmetic(data, "DATA-01", "課表時數與計畫時數", [(session_keys, "course.declared_hours", "sum")] if session_keys else [])]
    for ident, basis, title in (("DATA-02", "per_class", "每班補助＋自付與總計"), ("DATA-03", "per_person", "每人補助＋自付與總計")):
        results.append(arithmetic(data, ident, title, [([f"budget.{basis}.subsidy", f"budget.{basis}.self_paid"], f"budget.{basis}.total", "sum")]))
    results.append(arithmetic(data, "DATA-04", "每人金額 × 人數與每班金額", [([f"budget.per_person.{k}", "course.enrollment"], f"budget.per_class.{k}", "multiply") for k in ("subsidy", "self_paid", "total")]))
    results.append(arithmetic(data, "DATA-05", "固定費用＋材料費與總計", [(["budget.fixed_total", "budget.materials_total"], "budget.per_class.total", "sum")]))
    missing = [k for k in CORE if value(data, k) is None or value(data, k) == ""]
    status = "無法解析" if source_errors(data, CORE) else "資料未提供" if missing else "資料一致"
    results.append(make_result(data, "DATA-06", "核心欄位完整性", status,
                               "未提供：" + "、".join(missing) if missing else "核心欄位已取得；內容合理性仍需人工核對。", list(CORE), "只檢查是否有值及可解析，不推論內容正確性。"))
    staff_status = "無法解析" if source_errors(data, ["instructors"]) else "待人工確認" if data["instructors"] else "資料未提供"
    results.append(make_result(data, "DATA-07", "師資資料是否提供", staff_status,
                               "已提供師資內容，資格是否適合尚未判讀。" if data["instructors"] else "原表師資區未提供實際師資資料，無法判斷師資資格。",
                               ["instructors"] + [k for k in data["field_sources"] if k.startswith("instructors.")], "只檢查實際師資內容是否存在，忽略空白及資格範本提示。"))
    staff_keys = [f"sessions.{i}.{k}" for i in range(len(data["sessions"])) for k in ("teacher", "assistant")]
    blanks = [k for k in staff_keys if value(data, k) is None or value(data, k) == ""]
    status = "無法解析" if source_errors(data, staff_keys) else "資料未提供" if blanks or not staff_keys else "待人工確認"
    results.append(make_result(data, "DATA-08", "課表教師／助教資料是否提供", status,
                               f"{len(blanks)} 個教師／助教欄位未提供；是否需要助教仍待人工確認。" if blanks else "已取得指派文字；人員資格與適用性待人工確認。",
                               staff_keys, "檢查欄位提供情形；空白不代表否，也不代表不符合。"))
    if data["parse_report"]["status"] == "failed":
        for item in results:
            item.update(status="無法解析", finding="Excel 解析失敗，未完成本項檢查。")
    return results
