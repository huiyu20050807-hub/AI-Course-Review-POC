"""Local PDF text-layer extraction. Metadata evidence is distinct from filename hints."""
from datetime import date
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
import re
from pypdf import PdfReader

PARSER_VERSION = "policy-2A.2"
SCHEMA_VERSION = "policy_document-1"
ROOT = Path(__file__).parent
POLICY_FOLDER = ROOT / "產投規定及審查原則"
STORE = ROOT / "policy_store"
UNKNOWN = "unknown"
PLANS = {"產業人才投資計畫": "industrial", "提升勞工自主學習計畫": "self_learning"}


def compact(text):
    return re.sub(r"\s+", "", str(text)).casefold()


def scan_pdfs(folder=POLICY_FOLDER):
    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"找不到規定來源資料夾：{folder}")
    return sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf")


def iso_date(y, m, d):
    year = int(y)
    return date(year + 1911 if year < 1911 else year, int(m), int(d)).isoformat()


def metadata(document):
    first = document["pages"][0]["text"] if document["pages"] else ""
    lines = [line.strip() for line in first.splitlines() if line.strip()]
    joined = compact(first)
    evidence = document["metadata_evidence"]

    def assign(key, value, excerpt):
        document[key] = value
        evidence[key] = {"kind": "document_text", "page": 1, "excerpt": excerpt}

    title_line = next((line for line in lines if re.search(r"產業人才投資方案.*審查標準作業(?:原則|程序)", compact(line))), None)
    if title_line:
        title = re.sub(r"\s+", "", title_line)
        assign("title", title, title_line)
        assign("document_type", "審查標準作業原則" if title.endswith("原則") else "審查標準作業程序", title_line)
        # The procedure explicitly states both plans; an umbrella title alone does not.
        if all(name in joined for name in PLANS) and "二計畫" in joined:
            assign("plan_type", "both", first)
    else:
        main_plan = next((name for line in lines[:12] for name in PLANS if compact(line) == name), None)
        if main_plan:
            handbook = any(compact(line) == "作業手冊" for line in lines[:12])
            assign("title", main_plan + ("作業手冊" if handbook else ""), first)
            assign("document_type", "作業手冊" if handbook else "計畫", first)
            assign("plan_type", PLANS[main_plan], first)

    # Periods are accepted only when explicitly attached to applicability or the title.
    for line in lines:
        m = re.search(r"(\d{3})年度?\s*(上半年|下半年)", line)
        if m and ("適用" in line or (document["title"] != UNKNOWN and document["title"] in compact(line))):
            assign("roc_year", int(m[1]), line)
            assign("period", m[2], line)
            break
    date_pattern = r"(\d{3,4})\s*[年/.]\s*(\d{1,2})\s*[月/.]\s*(\d{1,2})\s*日?"
    for line in lines:
        m = re.search(date_pattern, line)
        if m:
            try:
                parsed = iso_date(*m.groups())
            except ValueError:
                continue
            if re.search(r"修正|修訂", line):
                assign("revision_date", parsed, line)
            if "發布" in line:
                assign("publication_date", parsed, line)
            if document["document_date"] == UNKNOWN:
                assign("document_date", parsed, line)
        if "適用期間" in line:
            matches = list(re.finditer(date_pattern, line))
            if len(matches) == 2 and re.search(r"至|到|～|~", line):
                try:
                    start, end = [iso_date(*x.groups()) for x in matches]
                    if start <= end:
                        assign("effective_from", start, line)
                        assign("effective_to", end, line)
                except ValueError:
                    pass

    filename = document["file_name"]
    hint = re.search(r"(\d{3})年度?(上半年|下半年)", filename)
    if hint:
        document["filename_hints"].update(roc_year=int(hint[1]), period=hint[2])
        document["applicability_notes"].append("檔名有年度期別提示；不得取代正文適用期間證據。")
    tail_date = re.search(r"(\d{3})(\d{2})(\d{2})(?=\.pdf$)", filename, re.I)
    if tail_date:
        try:
            document["filename_hints"]["date"] = iso_date(*tail_date.groups())
        except ValueError:
            pass
    if document["filename_hints"].get("date") and document["document_date"] != UNKNOWN and document["filename_hints"]["date"] != document["document_date"]:
        document["applicability_notes"].append("檔名日期與正文日期不同；正文日期未必是發布／修訂日期，不自動消除差異。")
    if document["roc_year"] == UNKNOWN and document["effective_from"] == UNKNOWN:
        document["applicability_notes"].append("未辨識明確適用年度／期間；修訂日期不等於生效日期，也不證明持續有效。")


def split_sections(document):
    """Page-local paragraphs preserve exact offsets. No fabricated legal numbering."""
    heading = UNKNOWN
    output = []
    for page in document["pages"]:
        text = page["text"]
        is_table = document["document_type"] == "審查標準作業原則"
        breaks = {0, len(text)}
        for m in re.finditer(r"\n[ \t]*\n", text):
            breaks.add(m.end())
        if not is_table:
            for m in re.finditer(r"(?m)^[ \t]*(?:[壹貳參肆伍陸柒捌玖拾]+、|第[一二三四五六七八九十百\d]+[章條]|[一二三四五六七八九十百]+、|[（(][一二三四五六七八九十百\d]+[）)])", text):
                breaks.add(m.start())
        positions = sorted(breaks)
        for start, end in zip(positions, positions[1:]):
            raw = text[start:end]
            if not raw.strip():
                continue
            stripped = raw.strip()
            line = stripped.splitlines()[0].strip()
            if re.fullmatch(r"\d+", stripped):
                continue
            chapter = re.match(r"(?:[壹貳參肆伍陸柒捌玖拾]+、|第[一二三四五六七八九十百\d]+章).+", line)
            if chapter:
                heading = line
            elif line.startswith("附件") and len(line) < 90:
                heading = line
            article = re.match(r"第[一二三四五六七八九十百\d]+條(?:之[一二三四五六七八九十\d]+)?", line) if not is_table else None
            item = re.match(r"(?:[一二三四五六七八九十百]+、|[（(][一二三四五六七八九十百\d]+[）)])", line) if not is_table else None
            local_heading = UNKNOWN if is_table else heading
            # A table chunk remains a paragraph, never assigned to a category whose row boundary is uncertain.
            output.append({"section_id": f"{document['document_id']}:p{page['page_number']}:s{len(output)+1}",
                           "heading": local_heading, "article_no": article[0] if article else UNKNOWN,
                           "item_no": item[0] if item else UNKNOWN, "text": raw,
                           "page_start": page["page_number"], "page_end": page["page_number"],
                           "source_excerpt": raw, "char_start": start, "char_end": end,
                           "structure_status": "table_paragraph_unclassified" if is_table else "explicit_marker" if article or item or chapter else "paragraph"})
    return output


def parse_policy_bytes(content, file_name, source_path):
    digest = sha256(content).hexdigest()
    document = {"schema_version": SCHEMA_VERSION, "parser_version": PARSER_VERSION,
                "document_id": "POL-" + digest, "source_path": str(source_path), "file_name": file_name,
                "sha256": digest, **{k: UNKNOWN for k in ("title", "document_type", "plan_type", "roc_year", "period", "effective_from", "effective_to", "revision_date", "publication_date", "document_date")},
                "status": "unverified", "applicability_notes": [], "metadata_evidence": {}, "filename_hints": {},
                "page_count": 0, "pages": [], "sections": [],
                "parse_report": {"status": "failed", "method": "pypdf_text_layer; layout_for_principles_table", "text_pages": 0, "errors": [], "warnings": []}}
    try:
        reader = PdfReader(BytesIO(content))
        document["page_count"] = len(reader.pages)
        table_layout = bool(reader.pages) and "產業人才投資方案各職類課程審查標準作業原則" in compact(reader.pages[0].extract_text() or "")
        for n, page in enumerate(reader.pages, 1):
            try:
                plain = page.extract_text() or ""
                text = (page.extract_text(extraction_mode="layout") or plain) if table_layout else plain
                usable = len(re.findall(r"[\w\u4e00-\u9fff]", text)) >= 10
                state = "text_available" if usable else "no_usable_text"
                if not usable:
                    document["parse_report"]["warnings"].append(f"PDF 第 {n} 頁未取得可用文字層；未執行 OCR。")
            except Exception as exc:
                text, plain, state = "", "", "extraction_failed"
                document["parse_report"]["errors"].append({"page": n, "message": str(exc)})
            document["pages"].append({"page_number": n, "text": text, "plain_text": plain, "text_status": state,
                                      "extraction_mode": "layout" if table_layout else "plain"})
        count = sum(p["text_status"] == "text_available" for p in document["pages"])
        document["parse_report"]["text_pages"] = count
        document["parse_report"]["status"] = "success" if count == document["page_count"] and count else "partial" if count else "failed"
        metadata(document)
        document["sections"] = split_sections(document)
        document["parse_report"]["warnings"].append("段落按實體 PDF 頁切分；跨頁條文未自動合併，unknown 條號不代表沒有條號。")
        if document["document_type"] == "審查標準作業原則":
            document["parse_report"]["warnings"].append("表格職類與條文關係尚未結構化；請回查原始 PDF，不依文字位置推定職類適用。")
    except Exception as exc:
        document["parse_report"]["errors"].append({"page": None, "message": f"{type(exc).__name__}: {exc}"})
    return document


def get_document(path, store=STORE):
    """Content-addressed immutable snapshots, separated by parser version."""
    path = Path(path)
    content = path.read_bytes()
    digest = sha256(content).hexdigest()
    # Include original path in the storage key so identical bytes at different paths retain provenance.
    location = sha256(str(path.resolve()).encode()).hexdigest()[:12]
    target = Path(store) / digest / f"{PARSER_VERSION}-{location}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    archive = target.parent / "source.pdf"
    if not archive.exists():
        try:
            with archive.open("xb") as out:
                out.write(content)
        except FileExistsError:
            pass
    if sha256(archive.read_bytes()).hexdigest() != digest:
        raise ValueError("原始 PDF 封存內容與雜湊不一致")
    if target.exists():
        document = json.loads(target.read_text(encoding="utf-8"))
        if document["sha256"] == digest and document["parser_version"] == PARSER_VERSION:
            document["archived_source_path"] = str(archive.resolve())
            return document
        raise ValueError("規定快照識別不一致，請檢查來源紀錄")
    document = parse_policy_bytes(content, path.name, path.resolve())
    document["archived_source_path"] = str(archive.resolve())
    try:
        with target.open("x", encoding="utf-8") as out:
            json.dump(document, out, ensure_ascii=False, indent=2)
    except FileExistsError:
        return json.loads(target.read_text(encoding="utf-8"))
    return document


if __name__ == "__main__":
    for path in scan_pdfs():
        d = get_document(path)
        print(json.dumps({k: d[k] for k in ("file_name", "title", "plan_type", "roc_year", "period", "revision_date", "document_date", "page_count")}, ensure_ascii=False), "sections", len(d["sections"]), d["parse_report"]["status"])
