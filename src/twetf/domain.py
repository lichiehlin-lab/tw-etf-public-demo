from dataclasses import dataclass, field
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
import re

TZ = timezone(timedelta(hours=8))
ZERO = Decimal('0')

def now():
    return datetime.now(TZ).isoformat()

def decimal(value):
    try:
        result = Decimal(str(value).replace(',', '').strip())
        if not result.is_finite():
            raise ValueError('數字不可為 NaN 或無限值')
        return result
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f'無效數值：{value}') from exc

@dataclass(frozen=True, order=True)
class ETFKey:
    exchange: str
    code: str

    def __post_init__(self):
        if self.exchange not in ('TWSE', 'TPEx') or not isinstance(self.code, str) or not re.fullmatch(r'[0-9A-Z]{4,8}', self.code):
            raise ValueError('交易所或證券代碼無效')

@dataclass(frozen=True)
class ETF:
    key: ETFKey
    name: str
    category: str = '待核實'
    currency: str = 'TWD'
    listing_date: date | None = None
    region: str = '待核實'
    manager: str = ''
    status: str = 'ACTIVE'
    source: str = ''
    source_date: date | None = None
    retrieved_at: str = field(default_factory=now)

    @property
    def eligible(self):
        return self.status == 'ACTIVE' and self.currency == 'TWD' and not any(x in self.category for x in ('槓桿', '反向', '期貨', 'ETN'))

@dataclass(frozen=True)
class DailyPrice:
    key: ETFKey
    day: date
    close: Decimal
    volume: int
    turnover: Decimal
    source: str
    currency: str = 'TWD'
    status: str = 'CURRENT'
    retrieved_at: str = field(default_factory=now)

    def __post_init__(self):
        if decimal(self.close) <= 0 or self.volume < 0 or decimal(self.turnover) < 0:
            raise ValueError('價格必須大於零，成交量值不可為負')

@dataclass(frozen=True)
class NavPoint:
    key: ETFKey
    day: date
    value: Decimal
    currency: str
    source: str
    formal: bool = True
    status: str = 'CURRENT'

@dataclass(frozen=True)
class Distribution:
    key: ETFKey
    ex_date: date
    pay_date: date | None
    amount: Decimal
    status: str
    source: str
    announcement_id: str = ''

@dataclass(frozen=True)
class CorporateAction:
    key: ETFKey
    effective_date: date
    unit_ratio: Decimal
    source: str

    def __post_init__(self):
        if decimal(self.unit_ratio) <= 0:
            raise ValueError('拆分比率必須大於零')

@dataclass(frozen=True)
class FundFact:
    key: ETFKey
    effective_date: date
    metric: str
    value: Decimal
    definition: str
    source: str

@dataclass(frozen=True)
class Transaction:
    key: ETFKey
    trade_date: date
    type: str
    units: Decimal = ZERO
    unit_price: Decimal = ZERO
    fee: Decimal = ZERO
    tax: Decimal = ZERO
    cash_amount: Decimal = ZERO
    status: str = 'RECEIVED'
    external_ref: str = ''
    transaction_id: str = ''

    def __post_init__(self):
        if self.type not in ('BUY', 'SELL', 'DIVIDEND', 'FEE'):
            raise ValueError('交易類型無效')
        for v in (self.units, self.unit_price, self.fee, self.tax, self.cash_amount):
            if decimal(v) < 0:
                raise ValueError('交易數值不可為負')
        if self.type in ('BUY', 'SELL') and (self.units <= 0 or self.unit_price <= 0):
            raise ValueError('買賣單位與價格須大於零')
        if self.type == 'BUY' and self.tax:
            raise ValueError('買入不接受賣出稅費；另記獨立費用')
        if self.type in ('DIVIDEND', 'FEE') and (self.units or self.unit_price or self.fee or self.tax):
            raise ValueError('配息與獨立費用只填現金金額')
        if self.status not in ('RECEIVED', 'PENDING'):
            raise ValueError('收款狀態無效')

@dataclass(frozen=True)
class Metric:
    value: Decimal | None
    start_day: date | None = None
    end_day: date | None = None
    source: str | None = None
    status: str = 'UNAVAILABLE'
    missing_reason: str | None = None

DataStatus = str
