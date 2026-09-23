from dataclasses import dataclass, field
from datetime import date
import json
import urllib.request
from ..domain import now

@dataclass
class SourceBatch:
    source_id: str
    requested_day: date | None
    retrieved_at: str
    source_url: str
    records: list
    errors: list = field(default_factory=list)

def fetch_text(url, encoding='utf-8'):
    req = urllib.request.Request(url, headers={'User-Agent':'TWETF-Local/1.0', 'Accept':'application/json,text/html'})
    with urllib.request.urlopen(req, timeout=20) as response:
        return response.read().decode(encoding)

def fetch_json(url): return json.loads(fetch_text(url))

def parse_date(raw):
    s=str(raw).strip().replace('/','').replace('-','')
    if len(s)==7: s=str(int(s[:3])+1911)+s[3:]
    if len(s)!=8: raise ValueError(f'無效日期 {raw}')
    return date(int(s[:4]),int(s[4:6]),int(s[6:8]))
