"""Read-only resource lookup using the existing PDF parser and literal search."""
from pathlib import Path
import os
from policy_parser import scan_pdfs,get_document
from policy_search import search_documents

ROOT=Path(__file__).parent
DEFAULT=ROOT.parent/'AI_Course_Review_POC'/'補助資源查詢系統'

def catalogue(folder=None):
    folder=Path(folder or os.environ.get('WORKSHOP_RESOURCE_DIR',str(DEFAULT)))
    docs=[]
    for path in scan_pdfs(folder):
        doc=get_document(path,ROOT/'resource_cache')
        doc['resource_category']=str(path.parent.relative_to(folder)) if path.parent!=folder else '補助資源查詢系統（未分子資料夾）'
        doc['resource_name']=path.stem
        docs.append(doc)
    return docs

def search(docs,query):
    lookup={d['document_id']:d for d in docs}
    hits=search_documents(docs,query,{'plan_type':'unknown','roc_year':'unknown','period':'unknown'})
    # Applicability is intentionally not exposed or used to decide eligibility.
    for hit in hits:
        hit.pop('applicability',None)
        doc=lookup[hit['document_id']]
        hit.update(resource_name=doc['resource_name'],category=doc['resource_category'],source_path=doc['archived_source_path'])
    return hits
