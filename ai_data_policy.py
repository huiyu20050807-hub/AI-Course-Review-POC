"""Local minimization/redaction. External transmission is disabled, not certified safe."""
import re

class DataPolicyError(ValueError): pass

PATTERNS = [
    ('Email',r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'),
    ('身分證／居留證',r'(?i)(?<![A-Z0-9])[A-Z][12A-D89]\d{8}(?!\d)'),
    ('電話',r'(?<!\d)(?:\+886[-\s]?[0-9][\d\s-]{7,12}|09\d{2}[-\s]?\d{3}[-\s]?\d{3}|0[2-8][\d-]{7,11})(?!\d)'),
    ('姓名',r'(?:姓名|聯絡人|授課教師|講師|老師|教師|助教)\s*[:：]?\s*[\u4e00-\u9fff]{2,4}(?=[\s，,。；;：:]|$)'),
    ('姓名',r'[\u4e00-\u9fff]{2,4}(?:老師|教授|先生|小姐|女士)'),
    ('地址',r'(?:地址|住址|通訊地址)\s*[:：]\s*[^\n，;；]{3,100}'),
    ('地址',r'[\u4e00-\u9fff]{2,3}[縣市][^\n，;；]{1,60}[路街巷][^\n，;；]{0,30}[號樓]'),
    ('識別資料',r'(?:護照號碼|帳號|學號|員工編號|病歷號)\s*[:：]\s*[A-Za-z0-9-]+'),
]

def sanitize(payload):
    """Does not log matched personal data. Retains null; accepts JSON-like input only."""
    findings=[]
    def visit(v,path):
        if isinstance(v,str):
            for kind,pattern in PATTERNS:
                v,n=re.subn(pattern,'[已遮罩：'+kind+']',v)
                if n: findings.append({'field':path,'type':kind,'count':n})
            return v
        if v is None or isinstance(v,(int,float,bool)):return v
        if isinstance(v,list):return [visit(x,f'{path}.{i}') for i,x in enumerate(v)]
        if isinstance(v,dict):
            if any(not isinstance(k,str) for k in v):raise DataPolicyError('資料鍵值必須為文字')
            return {k:visit(x,path+'.'+k) for k,x in v.items()}
        raise DataPolicyError('不得傳入檔案、bytes 或非白名單資料型態')
    cleaned=visit(payload,'input')
    return cleaned,{'redactions':findings,'external_allowed':False,
        'limitations':'規則遮罩不能保證辨識所有姓名或間接識別資訊；本階段外部傳輸一律停用。'}

def require_local(provider):
    if provider!='mock':raise DataPolicyError('本階段只允許本機 mock；外部 AI 傳輸尚未授權及實作。')
