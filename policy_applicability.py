"""Transparent document-level applicability hints; no legal adjudication."""
from datetime import date
from policy_parser import UNKNOWN, PLANS

LABELS = {"applicable": "適用", "possibly_applicable": "可能適用", "not_applicable": "不適用", "unknown": "無法判斷"}


def case_context(case_data):
    """Adapter only. Does not modify Phase 1 case_data or its parser."""
    p = case_data.get("plan", {})
    kind = p.get("plan_type")
    if kind is None:
        matches = [v for k,v in PLANS.items() if k in (p.get("name") or "")]
        kind = matches[0] if len(matches) == 1 else UNKNOWN
    return {"plan_type": PLANS.get(kind, kind), "roc_year": p.get("roc_year", p.get("year_roc", UNKNOWN)), "period": p.get("period", p.get("term", UNKNOWN))}


def applicability(document, context):
    evidence = document.get("metadata_evidence", {})
    notes = list(document.get("applicability_notes", []))
    def result(status, reason):
        return {"status": status, "label": LABELS[status], "reason": reason, "case_context": dict(context),
                "document_id": document["document_id"], "evidence": evidence, "notes": notes,
                "method_version": "applicability-2A.1"}
    def trusted(key):
        return evidence.get(key, {}).get("kind") == "document_text"
    if document["parse_report"]["status"] != "success":
        return result("unknown", "文件未完整取得文字，無法可靠判斷整份文件適用性。")
    kind = PLANS.get(context.get("plan_type"), context.get("plan_type", UNKNOWN))
    doc_kind = document.get("plan_type", UNKNOWN)
    if kind not in ("industrial", "self_learning"):
        return result("unknown", "案件計畫別不明。")
    if trusted("plan_type") and doc_kind in ("industrial", "self_learning") and doc_kind != kind:
        return result("not_applicable", "正文標題確認的計畫別與案件不同。")
    if not trusted("plan_type") or doc_kind not in (kind, "both"):
        return result("unknown", "文件計畫別無明確正文證據；檔名或『方案』字樣不能代表適用所有計畫。")
    year, period = context.get("roc_year"), context.get("period")
    if not isinstance(year, int) or isinstance(year, bool) or period not in ("上半年", "下半年"):
        return result("unknown", "案件年度／期別不完整。")
    dy, dp = document.get("roc_year"), document.get("period")
    period_match = False
    if trusted("roc_year") and trusted("period") and dy != UNKNOWN and dp != UNKNOWN:
        if (year, period) != (dy, dp):
            return result("not_applicable", "正文明示的適用年度／期別與案件不同。")
        hints = document.get("filename_hints", {})
        if hints.get("roc_year", dy) != dy or hints.get("period", dp) != dp:
            return result("unknown", "正文期間與檔名版本提示相互矛盾，須先確認版本。")
        period_match = True
    if trusted("effective_from") and trusted("effective_to"):
        try:
            start, end = date.fromisoformat(document["effective_from"]), date.fromisoformat(document["effective_to"])
            case_start = date(year + 1911, 1 if period == "上半年" else 7, 1)
            case_end = date(year + 1911, 6 if period == "上半年" else 12, 30 if period == "上半年" else 31)
            if end < start:
                return result("unknown", "適用期間起訖順序矛盾。")
            if end < case_start or start > case_end:
                return result("not_applicable", "明示適用期間與案件期別無交集。")
            if start <= case_start and end >= case_end:
                return result("applicable", "明示期間涵蓋案件整個期別；僅為文件範圍提示。")
            return result("possibly_applicable", "明示期間只涵蓋案件部分期別，需人工確認案件實際適用日期。")
        except (ValueError, TypeError):
            return result("unknown", "文件適用期間無法解析。")
    if period_match:
        return result("applicable", "正文明示的計畫別與適用年度／期別相符；僅為文件層級範圍提示。")
    hints = document.get("filename_hints", {})
    conflict = hints.get("roc_year") not in (None, year) or hints.get("period") not in (None, period)
    return result("unknown", "未取得正文適用期間。" + ("檔名另標示不同年度／期別，不可直接套用本案。" if conflict else "發布／修訂日期不代表有效期間，需確認後才能引用。"))
