"""Literal keyword matching only; whitespace-normalized, no AI or embeddings."""
from policy_parser import compact
from policy_applicability import applicability


def search_documents(documents, query, context, scope="all"):
    query = compact(query.strip())
    if not query:
        return []
    results = []
    for doc in documents:
        status = applicability(doc, context)
        title_hit = query in compact(doc["title"]) or query in compact(doc["file_name"])
        for section in doc["sections"]:
            fields = []
            if scope in ("all", "title") and title_hit:
                fields.append("文件名稱")
            if scope in ("all", "heading") and section["heading"] != "unknown" and query in compact(section["heading"]):
                fields.append("章節標題")
            if scope in ("all", "text") and query in compact(section["text"]):
                fields.append("段落全文")
            if fields:
                results.append({"document_id": doc["document_id"], "title": doc["title"], "file_name": doc["file_name"],
                                "section_id": section["section_id"], "heading": section["heading"],
                                "page_start": section["page_start"], "page_end": section["page_end"],
                                "text": section["source_excerpt"], "matched_fields": fields, "applicability": status})
    return results
