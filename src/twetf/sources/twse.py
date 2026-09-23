from html.parser import HTMLParser
import re
from ..domain import ETF, ETFKey, DailyPrice, decimal, now
from .base import SourceBatch, parse_date, fetch_text, fetch_json

CATALOG_URL='https://isin.twse.com.tw/isin/C_public.jsp?strMode=2'
PRICE_URL='https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL'

class TableReader(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows=[]; self.row=[]; self.cell=None
    def handle_starttag(self, tag, attrs):
        if tag=='tr': self.row=[]
        if tag in ('td','th'): self.cell=''
    def handle_data(self, data):
        if self.cell is not None: self.cell+=data
    def handle_endtag(self, tag):
        if tag in ('td','th') and self.cell is not None:
            self.row.append(self.cell.strip()); self.cell=None
        if tag=='tr' and self.row: self.rows.append(self.row)

def parse_catalog(html, exchange):
    parser=TableReader(); parser.feed(html)
    result=[]; group=''; source=CATALOG_URL if exchange=='TWSE' else CATALOG_URL.replace('=2','=4')
    for row in parser.rows:
        if len(row)==1:
            group=row[0]; continue
        if 'ETF' not in group.upper() or 'ETN' in group.upper(): continue
        match=re.match(r'^(\d[0-9A-Z]{3,7})\s+(.+)$', row[0])
        if not match or len(row)<6: continue
        code,name=match.groups()
        # Membership comes from the ETF section. Official suffix rules identify
        # foreign-currency share classes; do not confuse USD underlying bonds
        # with the currency used to trade their TWD ETF units.
        currency='FOREIGN' if code[-1] in 'CKMV' else 'TWD'
        if code=='00687C': currency='USD'
        category='待核實'
        suffix_types={'L':'槓桿','R':'反向','U':'期貨','B':'債券型','D':'主動債券型','A':'主動股票型','T':'多資產型'}
        category=suffix_types.get(code[-1],category)
        for needle, value in [('槓桿','槓桿'),('反向','反向'),('期貨','期貨')]:
            if needle in group or needle in name: category=value
        result.append(ETF(ETFKey(exchange,code),name,category,currency,parse_date(row[2]),source=source))
    if not result: raise ValueError('官方 ETF 名錄格式改變或無 ETF 分類')
    return result

def enrich_catalog(catalog, facts):
    by_code={x['基金代號']:x for x in facts}
    from dataclasses import replace
    result=[]
    for etf in catalog:
        fact=by_code.get(etf.key.code)
        if fact:
            category=fact['基金類型']
            if etf.key.code[-1] in ('B','D') and '債券' not in category: category+='（債券型）'
            region='海外' if fact.get('是否包含國外成分股')=='是' or '國外' in category else '臺灣'
            if any(x in etf.category for x in ('槓桿','反向','期貨')): category=etf.category
            etf=replace(etf,category=category,region=region,source_date=parse_date(fact['出表日期']))
        result.append(etf)
    return result

def parse_prices(payload, day, catalog, exchange, names, url):
    if not isinstance(payload,list) or not payload: raise ValueError('行情格式錯誤／尚未公布')
    code,close,volume,turnover=names
    records=[]; errors=[]
    for row in payload:
        if not all(k in row for k in ('Date',code,close,volume,turnover)):
            raise ValueError('官方行情 schema 欄位改變')
        key=ETFKey(exchange,row[code])
        if key not in catalog: continue
        try:
            actual=parse_date(row['Date'])
            if actual != day: raise ValueError(f'來源日期 {actual} 不等於要求日期 {day}')
            records.append(DailyPrice(key,actual,decimal(row[close]),int(decimal(row[volume])),decimal(row[turnover]),url))
        except ValueError as exc: errors.append(f'{key.code} 收盤價／日期：{exc}')
    return SourceBatch(exchange,day,now(),url,records,errors)

def parse_twse_prices(payload, day, catalog):
    return parse_prices(payload,day,catalog,'TWSE',('Code','ClosingPrice','TradeVolume','TradeValue'),PRICE_URL)

class TWSESource:
    source_id='TWSE'
    def __init__(self, catalog=(), client=fetch_json): self.catalog=set(catalog); self.client=client
    def fetch_catalog(self):
        items=parse_catalog(fetch_text(CATALOG_URL,'cp950'),'TWSE')
        items=enrich_catalog(items,self.client('https://openapi.twse.com.tw/v1/opendata/t187ap47_L'))
        self.catalog={e.key for e in items}
        return SourceBatch(self.source_id,None,now(),CATALOG_URL,items)
    def fetch_prices(self, day): return parse_twse_prices(self.client(PRICE_URL),day,self.catalog)
