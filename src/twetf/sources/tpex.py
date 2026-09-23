from ..domain import now
from .base import SourceBatch, fetch_json, fetch_text
from .twse import parse_catalog, parse_prices

CATALOG_URL='https://isin.twse.com.tw/isin/C_public.jsp?strMode=4'
PRICE_URL='https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes'

def parse_tpex_prices(payload,day,catalog):
    return parse_prices(payload,day,catalog,'TPEx',('SecuritiesCompanyCode','Close','TradingShares','TransactionAmount'),PRICE_URL)

class TPExSource:
    source_id='TPEx'
    def __init__(self,catalog=(),client=fetch_json): self.catalog=set(catalog); self.client=client
    def fetch_catalog(self):
        items=parse_catalog(fetch_text(CATALOG_URL,'cp950'),'TPEx')
        self.catalog={e.key for e in items}
        return SourceBatch(self.source_id,None,now(),CATALOG_URL,items)
    def fetch_prices(self,day): return parse_tpex_prices(self.client(PRICE_URL),day,self.catalog)
