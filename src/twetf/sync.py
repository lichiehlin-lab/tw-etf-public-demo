from dataclasses import dataclass,asdict
from datetime import datetime
import time
import urllib.error
from .domain import now,TZ
from .quality import validate_batch
from .calendar import TradingCalendar,sync_target
from .sources.base import fetch_json
from .sources.twse import TWSESource
from .sources.tpex import TPExSource

@dataclass
class SyncReport:
    source: str
    day: object
    status: str
    saved: int = 0
    error: str = ''
    completed_at: str = ''

class SyncService:
    def __init__(self,repo,calendar,sources,sleep=time.sleep):
        self.repo=repo; self.calendar=calendar; self.sources=sources; self.sleep=sleep

    def sync(self,day,force=False):
        reports={}
        for source in self.sources:
            identity=f'{source.source_id}:{day}'
            old=self.repo.get('sync_runs',identity)
            if old and old['status']=='CURRENT' and not force:
                reports[source.source_id]=SyncReport(**old); continue
            report=SyncReport(source.source_id,day,'UNAVAILABLE',completed_at=now())
            try:
                if self.calendar and not self.calendar.is_trading(day):
                    report.status='CURRENT'; report.error='休市日，無收盤行情'
                else:
                    for attempt in range(3):
                        try:
                            batch=source.fetch_prices(day); break
                        except (TimeoutError,urllib.error.URLError,ConnectionError) as exc:
                            if isinstance(exc,urllib.error.HTTPError) and exc.code<500 and exc.code!=429: raise
                            if attempt==2: raise
                            self.sleep(1+attempt)
                    valid,errors=validate_batch(batch,self.repo)
                    if not valid: raise ValueError('尚未公布要求日期的有效 ETF 行情')
                    with self.repo.transaction():
                        for price in valid: self.repo.upsert_price(price)
                    report.saved=len(valid); report.status='REVIEW_REQUIRED' if errors else 'CURRENT'
                    report.error='; '.join(errors[:12])
            except ValueError as exc:
                report.status='REVIEW_REQUIRED'; report.error=str(exc)
            except Exception as exc:
                report.error=f'{type(exc).__name__}: {exc}'
            self.repo.put('sync_runs',identity,asdict(report),day=day)
            reports[source.source_id]=report
        return reports

def load_calendar(repo,year=None):
    payload=repo.setting(f'calendar_{year}') if year else repo.setting('calendar')
    if payload is None and year:
        fallback=repo.setting('calendar')
        if fallback and TradingCalendar.from_payload(fallback).year==year: payload=fallback
    return TradingCalendar.from_payload(payload) if payload else None

def save_catalog(repo,source_id,records):
    from dataclasses import replace
    if not records or any(e.key.exchange!=source_id for e in records): raise ValueError('名錄市場不符或為空')
    seen={e.key for e in records}
    with repo.transaction():
        for old in repo.etfs():
            if old.key.exchange==source_id and old.key not in seen:
                repo.upsert_etf(replace(old,status='REVIEW_REQUIRED'))
        for etf in records: repo.upsert_etf(etf)

def update_official(repo,day=None,force=False):
    """Shared UI/CLI entry point; failures preserve the last verified catalog."""
    current=datetime.now(TZ); notes=[]
    try:
        payload=fetch_json(f'https://www.twse.com.tw/holidaySchedule/holidaySchedule?response=json&queryYear={current.year-1911}')
        calendar=TradingCalendar.from_payload(payload)
        repo.set_setting('calendar',payload)
        repo.set_setting(f'calendar_{calendar.year}',payload)
        for year in (current.year-1,current.year-2):
            if not load_calendar(repo,year):
                try:
                    historical=fetch_json(f'https://www.twse.com.tw/holidaySchedule/holidaySchedule?response=json&queryYear={year-1911}')
                    if TradingCalendar.from_payload(historical).year!=year: raise ValueError('日曆年份不符')
                    repo.set_setting(f'calendar_{year}',historical)
                except Exception as exc: notes.append(f'{year} 年日曆未確認：{exc}')
    except Exception as exc:
        calendar=load_calendar(repo); notes.append(f'日曆同步失敗：{exc}')
    sources=[]
    for cls in (TWSESource,TPExSource):
        source=cls([e.key for e in repo.etfs() if e.key.exchange==cls.source_id and e.currency=='TWD'])
        try:
            batch=source.fetch_catalog()
            save_catalog(repo,source.source_id,batch.records)
            source.catalog={e.key for e in batch.records if e.currency=='TWD'}
        except Exception as exc: notes.append(f'{source.source_id} 名錄同步失敗：{exc}')
        sources.append(source)
    if day is None:
        try: day=sync_target(current,calendar)
        except (ValueError,AttributeError):
            return {},notes+['交易日曆未確認，請指定同步日期']
    return SyncService(repo,calendar,sources).sync(day,force),notes
