"""SQLite repository. Monetary values are serialized as decimal strings."""
from contextlib import contextmanager
from dataclasses import asdict, fields
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import json
import os
import sqlite3

from .domain import ETFKey, ETF, DailyPrice, NavPoint, Distribution, CorporateAction, FundFact, Transaction, now, decimal

SCHEMA_VERSION = 1
TABLES = ('etfs', 'daily_prices', 'daily_navs', 'distributions', 'corporate_actions',
          'fund_facts', 'transactions', 'import_batches', 'alerts', 'sync_runs',
          'watchlist', 'settings', 'coverage')

def data_dir():
    return Path(os.environ.get('TWETF_DATA_DIR', str(Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'TWETF')))

def encode(value):
    return json.dumps(asdict(value) if hasattr(value, '__dataclass_fields__') else value,
                      default=lambda v: str(v), ensure_ascii=False, sort_keys=True)

def decode(cls, raw):
    data = json.loads(raw) if isinstance(raw, str) else dict(raw)
    if 'key' in data:
        data['key'] = ETFKey(**data['key'])
    dates = {'day', 'listing_date', 'source_date', 'ex_date', 'pay_date', 'effective_date', 'trade_date'}
    decimals = {'close','turnover','value','amount','unit_ratio','units','unit_price','fee','tax','cash_amount'}
    for name in data:
        if name in dates and data[name] is not None:
            data[name] = date.fromisoformat(data[name])
        if name in decimals:
            data[name] = Decimal(data[name])
    return cls(**data)

def open_db(path=None):
    path = Path(path or data_dir() / 'etf.db')
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    version = conn.execute('PRAGMA user_version').fetchone()[0]
    if version not in (0, SCHEMA_VERSION):
        conn.close()
        raise ValueError('資料庫版本不支援')
    conn.execute('PRAGMA journal_mode=DELETE')
    conn.execute('PRAGMA foreign_keys=ON')
    for table in TABLES:
        conn.execute(f'CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY, exchange TEXT, code TEXT, day TEXT, data TEXT NOT NULL)')
        conn.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_key ON {table}(exchange,code,day)')
    conn.execute('CREATE TABLE IF NOT EXISTS source_revisions (id INTEGER PRIMARY KEY, entity TEXT, exchange TEXT, code TEXT, day TEXT, old_value TEXT, new_value TEXT, retrieved_at TEXT)')
    conn.execute(f'PRAGMA user_version={SCHEMA_VERSION}')
    return conn

class Repository:
    def __init__(self, conn):
        self.conn = conn
        self._depth = 0

    @contextmanager
    def transaction(self):
        name = f'tx_{self._depth}'
        self.conn.execute(f'SAVEPOINT {name}')
        self._depth += 1
        try:
            yield
            self.conn.execute(f'RELEASE SAVEPOINT {name}')
        except BaseException:
            self.conn.execute(f'ROLLBACK TO SAVEPOINT {name}')
            self.conn.execute(f'RELEASE SAVEPOINT {name}')
            raise
        finally:
            self._depth -= 1

    def put(self, table, identity, value, key=None, day=None, audit=False):
        if table not in TABLES:
            raise ValueError('未知資料表')
        raw = encode(value)
        old = self.conn.execute(f'SELECT data FROM {table} WHERE id=?', (identity,)).fetchone()
        with self.transaction():
            if audit and old:
                a, b = json.loads(old[0]), json.loads(raw)
                a.pop('retrieved_at', None); b.pop('retrieved_at', None)
                if a != b:
                    self.conn.execute('INSERT INTO source_revisions(entity,exchange,code,day,old_value,new_value,retrieved_at) VALUES (?,?,?,?,?,?,?)',
                                      (table, key.exchange, key.code, str(day), old[0], raw, now()))
            self.conn.execute(f'INSERT INTO {table} VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET exchange=excluded.exchange,code=excluded.code,day=excluded.day,data=excluded.data',
                              (identity, key.exchange if key else None, key.code if key else None, str(day) if day else None, raw))
        return old[0] if old else None

    def rows(self, table, key=None):
        if table not in TABLES: raise ValueError('未知資料表')
        sql, args = f'SELECT data FROM {table}', ()
        if key: sql += ' WHERE exchange=? AND code=?'; args = (key.exchange, key.code)
        return [json.loads(r[0]) for r in self.conn.execute(sql + ' ORDER BY day,id', args)]

    def get(self, table, identity):
        if table not in TABLES: raise ValueError('未知資料表')
        row = self.conn.execute(f'SELECT data FROM {table} WHERE id=?', (identity,)).fetchone()
        return json.loads(row[0]) if row else None

    @staticmethod
    def key_id(key): return f'{key.exchange}:{key.code}'

    def upsert_etf(self, etf): self.put('etfs', self.key_id(etf.key), etf, etf.key, etf.source_date, True)
    def get_etf(self, key):
        item = self.get('etfs', self.key_id(key))
        return decode(ETF, item) if item else None
    def etfs(self): return [decode(ETF, x) for x in self.rows('etfs')]
    def upsert_price(self, p): self.put('daily_prices', f'{self.key_id(p.key)}:{p.day}', p, p.key, p.day, True)
    def prices(self, key): return [decode(DailyPrice, x) for x in self.rows('daily_prices', key)]
    def get_price(self, key, day):
        item = self.get('daily_prices', f'{self.key_id(key)}:{day}')
        return decode(DailyPrice, item) if item else None
    def latest_price(self, key):
        items = self.prices(key)
        return items[-1] if items else None
    def count_prices(self, key, day): return int(self.get_price(key, day) is not None)
    def revisions_for(self, key):
        return [SimpleNamespace(**dict(x)) for x in self.conn.execute('SELECT * FROM source_revisions WHERE exchange=? AND code=? ORDER BY id', (key.exchange,key.code))]
    def setting(self, name, default=None):
        obj = self.get('settings', name)
        return obj['value'] if obj else default
    def set_setting(self, name, value): self.put('settings', name, {'value': value})
    def add_to_watchlist(self, key):
        if not self.get_etf(key): raise ValueError('無效 ETF')
        self.put('watchlist', self.key_id(key), {'exchange':key.exchange,'code':key.code}, key)
    def remove_from_watchlist(self, key): self.conn.execute('DELETE FROM watchlist WHERE id=?', (self.key_id(key),))

    def distribution_coverage(self,key):
        obj=self.get('coverage',self.key_id(key))
        return date.fromisoformat(obj['start']) if obj else None
    def set_coverage(self,key,start,end,source):
        if start>end or not source.startswith('https://'): raise ValueError('完整性證明需要有效期間與來源')
        self.put('coverage',self.key_id(key),{'start':str(start),'end':str(end),'source':source},key)
    def coverage_contains(self,key,start,end):
        obj=self.get('coverage',self.key_id(key))
        return bool(obj and obj['start']<=str(start) and obj['end']>=str(end))
    def distributions(self,key): return [decode(Distribution,x) for x in self.rows('distributions',key)]
    def actions(self,key=None): return [decode(CorporateAction,x) for x in self.rows('corporate_actions',key)]
    def navs(self,key): return [decode(NavPoint,x) for x in self.rows('daily_navs',key)]
    def facts(self,key): return [decode(FundFact,x) for x in self.rows('fund_facts',key)]
    def upsert_disclosure(self,record):
        if not self.get_etf(record.key): raise ValueError('無效 ETF')
        if not record.source.startswith('https://'): raise ValueError('需填寫公告 HTTPS 來源')
        if isinstance(record,Distribution):
            if decimal(record.amount)<0 or record.status not in ('CONFIRMED','ANNOUNCED'): raise ValueError('配息金額或公告狀態無效')
            table,day,tail='distributions',record.ex_date,record.announcement_id or record.source
        elif isinstance(record,NavPoint):
            if decimal(record.value)<=0: raise ValueError('NAV 須大於零')
            table,day,tail='daily_navs',record.day,record.currency+':'+str(record.formal)
        elif isinstance(record,CorporateAction): table,day,tail='corporate_actions',record.effective_date,''
        elif isinstance(record,FundFact):
            if decimal(record.value)<0 or not record.definition: raise ValueError('費用需非負數與揭露定義')
            table,day,tail='fund_facts',record.effective_date,record.metric+':'+record.definition
        else: raise ValueError('公告型別不支援')
        identity=f'{self.key_id(record.key)}:{day}:{tail}'
        if isinstance(record,Distribution) and record.announcement_id:
            identity=f'{self.key_id(record.key)}:announcement:{record.announcement_id}'
        with self.transaction():
            old=self.put(table,identity,record,record.key,day,True)
            if isinstance(record,CorporateAction): self.validate_transactions()
        affected=day
        if old and isinstance(record,Distribution): affected=min(day,date.fromisoformat(json.loads(old)['ex_date']))
        return SimpleNamespace(recompute_from=affected if old!=encode(record) else None)

    def transactions(self):
        return [decode(Transaction,x[0]) for x in self.conn.execute('SELECT data FROM transactions ORDER BY day,rowid')]
    def count_transactions(self): return len(self.transactions())
    def validate_transactions(self):
        from .analytics.portfolio import calculate_portfolio
        calculate_portfolio(self.transactions(),{},self.actions())
    def _check_transaction(self,tx):
        etf=self.get_etf(tx.key)
        if not etf or etf.status!='ACTIVE': raise ValueError('無效或已下市 ETF')
        if etf.currency!='TWD': raise ValueError('持倉僅支援新臺幣 ETF')
    def add_transaction(self,tx):
        from dataclasses import replace
        from uuid import uuid4
        self._check_transaction(tx)
        identity=tx.transaction_id or str(uuid4())
        if self.get('transactions',identity): raise ValueError('交易 ID 已存在')
        tx=replace(tx,transaction_id=identity)
        with self.transaction():
            self.put('transactions',identity,tx,tx.key,tx.trade_date)
            self.validate_transactions()
        return identity
    def update_transaction(self,identity,tx):
        from dataclasses import replace
        self._check_transaction(tx)
        if not self.get('transactions',identity): raise ValueError('交易不存在')
        with self.transaction():
            tx=replace(tx,transaction_id=identity)
            self.put('transactions',identity,tx,tx.key,tx.trade_date)
            self.validate_transactions()
    def delete_transaction(self,identity):
        with self.transaction():
            self.conn.execute('DELETE FROM transactions WHERE id=?',(identity,))
            self.validate_transactions()
