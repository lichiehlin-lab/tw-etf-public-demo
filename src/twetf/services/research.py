from dataclasses import dataclass
from datetime import datetime,date
from decimal import Decimal as D
from ..domain import Metric,TZ
from ..analytics.returns import total_return_series,premium,volatility_252,max_drawdown
from ..analytics.ranking import RankInput,rank_cohort,BALANCED
from ..calendar import market_status
from ..sync import load_calendar

WINDOWS={1:21,3:63,6:126,12:252,24:504}

@dataclass
class ETFView:
    etf: object
    latest_price: Metric
    premium: Metric
    returns: dict
    return_basis: dict
    volatility: Metric
    drawdown: Metric
    liquidity: Metric
    expense: Metric
    expense_definition: str

@dataclass
class Comparison:
    items: list
    end_day: date | None

class ResearchService:
    def __init__(self,repo): self.repo=repo

    def search_etfs(self,query='',filters=None):
        filters=filters or {}; result=[]
        for etf in self.repo.etfs():
            if query.lower() not in (etf.key.code+' '+etf.name).lower(): continue
            if filters.get('ordinary',True) and not etf.eligible: continue
            if any(filters.get(k) and getattr(etf,k)!=filters[k] for k in ('category','region')): continue
            if filters.get('exchange') and etf.key.exchange!=filters['exchange']: continue
            price=self.repo.latest_price(etf.key)
            if filters.get('price_max') is not None and (not price or price.close>filters['price_max']): continue
            if filters.get('min_age_days') and (not etf.listing_date or (date.today()-etf.listing_date).days<filters['min_age_days']): continue
            if filters.get('distributing') and not self.repo.distributions(etf.key): continue
            if filters.get('min_turnover'):
                prices=self.repo.prices(etf.key)
                if len(prices)<20 or sum(p.turnover for p in prices[-20:])/20<filters['min_turnover']: continue
            result.append(etf)
        return result

    def details(self,key,end_day=None):
        etf=self.repo.get_etf(key)
        if not etf: raise ValueError('無效 ETF 代碼')
        prices=[p for p in self.repo.prices(key) if not end_day or p.day<=end_day]
        price=prices[-1] if prices else None
        calendar=load_calendar(self.repo)
        status=market_status(datetime.now(TZ),calendar,price.day if price else None)
        def metric(value,start=None,end=None,reason=None,source=None):
            return Metric(value,start,end,source or (price.source if price else etf.source),status if value is not None else 'UNAVAILABLE',reason)
        latest=metric(price.close if price else None,price.day if price else None,price.day if price else None,'尚無成交價' if not price else None)
        nav=next((n for n in reversed(self.repo.navs(key)) if price and n.day==price.day and n.currency==price.currency and n.formal),None)
        pv=premium(price,nav)
        pm=metric(pv,price.day if price else None,price.day if price else None,'沒有同日同幣別正式 NAV' if pv is None else None,nav.source if nav else None)
        distributions=self.repo.distributions(key); actions=self.repo.actions(key)
        returns={}; basis={}; series12=None
        for month,n in WINDOWS.items():
            subset=prices[-n-1:]
            why=None; value=None; start=subset[0].day if subset else None; end=subset[-1].day if subset else None
            covered=bool(subset and self.repo.coverage_contains(key,start,end))
            basis[month]='含息報酬' if covered else '價格報酬（配息史完整性未確認）'
            if etf.currency!='TWD': why='外幣計價商品不支援報酬比較'
            elif len(subset)<n+1: why=f'資料不足：需要 {n+1} 筆收盤價，目前 {len(subset)} 筆'
            elif end_day and end!=end_day: why='缺少共同比較截至日行情'
            elif any(p.status!='CURRENT' for p in subset): why='價格待核對'
            else:
                # Do not bridge missing expected trading dates when calendar is known.
                gaps=False
                calendars={year:load_calendar(self.repo,year) for year in range(start.year,end.year+1)}
                unknown=any(c is None for c in calendars.values())
                if not unknown:
                    from datetime import timedelta
                    cursor=start
                    available={p.day for p in subset}
                    while cursor<=end:
                        if calendars[cursor.year].is_trading(cursor) != (cursor in available): gaps=True
                        cursor+=timedelta(days=1)
                if unknown: why='期間涵蓋年度的交易日曆未確認'
                elif gaps: why='期間交易日價格缺漏或包含非交易日'
                else:
                    points=total_return_series(subset,distributions if covered else [],actions)
                    value=points[-1].wealth-1
                    if month==12 and covered: series12=points
            returns[month]=metric(value,start,end,why)
        risk_reason='需要完整 252 日含息報酬及配息史'
        volatility=metric(volatility_252(series12) if series12 else None,returns[12].start_day,returns[12].end_day,None if series12 else risk_reason)
        drawdown=metric(max_drawdown(series12) if series12 else None,returns[12].start_day,returns[12].end_day,None if series12 else risk_reason)
        liquidity=metric(sum(p.turnover for p in prices[-20:])/20 if len(prices)>=20 else None,prices[-20].day if len(prices)>=20 else None,price.day if price else None,'需要 20 日成交金額' if len(prices)<20 else None)
        facts=[f for f in self.repo.facts(key) if f.metric=='expense_ratio' and (not end_day or f.effective_date<=end_day)]
        fact=facts[-1] if facts else None
        expense=metric(fact.value if fact else None,fact.effective_date if fact else None,fact.effective_date if fact else None,'缺少可核實年度費用' if not fact else None,fact.source if fact else None)
        return ETFView(etf,latest,pm,returns,basis,volatility,drawdown,liquidity,expense,fact.definition if fact else '')

    def compare(self,keys):
        if not 2<=len(set(keys))<=5 or len(set(keys))!=len(keys): raise ValueError('比較需選取 2–5 檔不同 ETF')
        for k in keys:
            e=self.repo.get_etf(k)
            if not e or e.currency!='TWD': raise ValueError('只支援名錄內新臺幣 ETF 比較')
        dates=[{p.day for p in self.repo.prices(k)} for k in keys]
        common=set.intersection(*dates)
        end=max(common) if common else None
        items=[self.details(k,end) for k in keys]
        if end is None:
            from dataclasses import replace
            for item in items:
                item.returns={m:replace(v,value=None,status='UNAVAILABLE',missing_reason='沒有共同交易日') for m,v in item.returns.items()}
        return Comparison(items,end)

    def rankings(self,weights=None):
        etfs=[e for e in self.repo.etfs() if e.eligible]
        inputs=[]
        for e in etfs:
            v=self.details(e.key)
            inputs.append(RankInput(self.repo.key_id(e.key),e.category+' / '+e.region,v.latest_price.end_day,252 if v.volatility.value is not None else 0,v.expense_definition,v.returns[12].value,v.drawdown.value,v.volatility.value,v.liquidity.value,v.expense.value,v.returns[12].start_day))
        return rank_cohort(inputs,weights or BALANCED)

    def add_to_watchlist(self,key): self.repo.add_to_watchlist(key)
    def remove_from_watchlist(self,key): self.repo.remove_from_watchlist(key)
