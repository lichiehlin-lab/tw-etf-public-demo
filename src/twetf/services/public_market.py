"""Public-only market cache. Never opens or exports the personal database."""
from datetime import datetime
from pathlib import Path
import json
import os
import sqlite3
import tempfile
import threading
import time

from ..db import Repository, open_db, decode
from ..domain import ETF, DailyPrice, TZ
from ..sync import update_official

SEED = Path(__file__).resolve().parents[3] / 'public_data' / 'market.json'
REFRESH_SECONDS = 3600
_locks = {}
_locks_guard = threading.Lock()

def public_data_path():
    root = Path(os.environ.get('TWETF_PUBLIC_DATA_DIR', str(Path(tempfile.gettempdir()) / 'twetf-public-demo')))
    return root / 'market-public.db'

class PublicMarketStore:
    def __init__(self, path, updater=update_official):
        self.path = Path(path).resolve()
        self.updater = updater
        self._ready = False
        self._worker = None
        self._worker_guard = threading.Lock()
        with _locks_guard:
            self.lock = _locks.setdefault(str(self.path), threading.Lock())

    def start_refresh(self, offline=False):
        """Seed locally, then update without blocking visitor page rendering."""
        with self._worker_guard:
            if not self._ready:
                self.refresh(offline=True)
                self._ready = True
            if not offline and (self._worker is None or not self._worker.is_alive()):
                self._worker = threading.Thread(target=self.refresh, daemon=True)
                self._worker.start()

    def refresh(self, offline=False):
        with self.lock:
            repo = Repository(open_db(self.path))
            try:
                if not repo.etfs():
                    payload = json.loads(SEED.read_text(encoding='utf8'))
                    if payload['schema_version'] != 1:
                        raise ValueError('公開資料快照版本不支援')
                    with repo.transaction():
                        for item in payload['etfs']: repo.upsert_etf(decode(ETF, item))
                        for item in payload['prices']: repo.upsert_price(decode(DailyPrice, item))
                        for year, calendar in payload['calendars'].items():
                            repo.set_setting(f'calendar_{year}', calendar)
                        if payload['calendars']:
                            repo.set_setting('calendar', payload['calendars'][max(payload['calendars'])])
                        repo.set_setting('public_snapshot_day', payload['snapshot_day'])
                last = repo.setting('public_refresh', {})
                if offline or time.time() - last.get('attempt_epoch', 0) < REFRESH_SECONDS:
                    return last
                # Persist the attempt before network I/O so failures also back off.
                status = {'attempt_epoch': time.time(), 'attempt_at': datetime.now(TZ).isoformat(), 'state': '更新中', 'notes': []}
                repo.set_setting('public_refresh', status)
                try:
                    reports, notes = self.updater(repo)
                    status['state'] = '已更新' if reports and all(r.status == 'CURRENT' for r in reports.values()) else '部分資料待核對'
                    status['notes'] = notes
                except Exception as exc:
                    status['state'] = '更新失敗，保留原資料'
                    status['notes'] = [f'{type(exc).__name__}: {exc}']
                repo.set_setting('public_refresh', status)
                return status
            finally:
                repo.conn.close()

    def reader(self):
        conn = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA query_only=ON')
        return Repository(conn)
