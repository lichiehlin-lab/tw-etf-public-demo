from dataclasses import dataclass
from datetime import date, datetime, timedelta, time
from .domain import TZ
from .sources.base import parse_date

@dataclass
class TradingCalendar:
    year: int
    closed: set
    source: str = 'https://www.twse.com.tw/holidaySchedule/holidaySchedule'

    @classmethod
    def from_payload(cls,payload):
        if payload.get('stat','').lower()!='ok' or payload.get('fields')!=['日期','名稱','說明']:
            raise ValueError('日曆格式未核實')
        year=parse_date(payload['date']).year
        closed=set()
        for raw,name,description in payload['data']:
            if '開始交易' in name or '最後交易' in name: continue
            closed.add(parse_date(raw))
        return cls(year,closed)

    def is_trading(self,day):
        if day.year!=self.year: raise ValueError('交易日曆未確認')
        return day.weekday()<5 and day not in self.closed

    def previous(self,day):
        while not self.is_trading(day): day-=timedelta(days=1)
        return day

    def next(self,day):
        day+=timedelta(days=1)
        while not self.is_trading(day): day+=timedelta(days=1)
        return day

def market_status(now,calendar,latest_day):
    if not calendar or not latest_day: return 'UNAVAILABLE'
    today=now.astimezone(TZ).date()
    try:
        target=calendar.previous(today)
        if latest_day>=target: return 'CURRENT'
        missing=calendar.next(latest_day)
        deadline=datetime.combine(calendar.next(missing),time(18),TZ)
        return 'STALE' if now>=deadline else 'PENDING'
    except ValueError: return 'UNAVAILABLE'

def sync_target(now,calendar):
    today=now.astimezone(TZ).date()
    if now.astimezone(TZ).hour<18: today-=timedelta(days=1)
    return calendar.previous(today)
