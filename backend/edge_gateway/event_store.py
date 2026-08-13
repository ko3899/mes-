"""Durable SQLite outbox used before acknowledging a device event."""

import json
from pathlib import Path
import sqlite3

from device_platform.contracts import DeviceEvent


class EdgeEventStore:
    """Persist immutable device events until the central platform confirms them."""

    def __init__(self, database_path):
        path = Path(database_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.database_path = str(path)
        self._initialize()

    def _connect(self):
        db = sqlite3.connect(self.database_path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA busy_timeout=5000')
        db.execute('PRAGMA foreign_keys=ON')
        return db

    def _initialize(self):
        db = self._connect()
        try:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('PRAGMA synchronous=FULL')
            db.execute(
                '''CREATE TABLE IF NOT EXISTS edge_event_outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    device_code TEXT NOT NULL,
                    sequence INTEGER NOT NULL CHECK(sequence > 0),
                    envelope_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK(status IN ('pending','acknowledged')),
                    attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0),
                    last_error TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    acknowledged_at TIMESTAMP
                )'''
            )
            db.execute(
                '''CREATE INDEX IF NOT EXISTS idx_edge_outbox_pending
                   ON edge_event_outbox(status,device_code,sequence,id)'''
            )
            db.commit()
        finally:
            db.close()

    def append(self, event):
        if not isinstance(event, DeviceEvent):
            raise TypeError('event must be a DeviceEvent')
        envelope = json.dumps(
            event.to_dict(), ensure_ascii=False, sort_keys=True,
            separators=(',', ':'), allow_nan=False,
        )
        db = self._connect()
        try:
            cursor = db.execute(
                '''INSERT OR IGNORE INTO edge_event_outbox
                   (event_id,device_code,sequence,envelope_json)
                   VALUES(?,?,?,?)''',
                (event.event_id, event.device_code, event.sequence, envelope),
            )
            db.commit()
            return cursor.rowcount == 1
        finally:
            db.close()

    def pending(self, limit=100):
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError('limit must be a positive integer')
        db = self._connect()
        try:
            rows = db.execute(
                '''SELECT envelope_json FROM edge_event_outbox
                   WHERE status='pending'
                   ORDER BY device_code,sequence,id LIMIT ?''',
                (limit,),
            ).fetchall()
            return [DeviceEvent.from_dict(json.loads(row['envelope_json'])) for row in rows]
        finally:
            db.close()

    def ack(self, event_id):
        db = self._connect()
        try:
            cursor = db.execute(
                '''UPDATE edge_event_outbox
                   SET status='acknowledged',acknowledged_at=CURRENT_TIMESTAMP,last_error=NULL
                   WHERE event_id=? AND status='pending' ''',
                (str(event_id),),
            )
            db.commit()
            return cursor.rowcount == 1
        finally:
            db.close()

    def fail(self, event_id, error):
        db = self._connect()
        try:
            cursor = db.execute(
                '''UPDATE edge_event_outbox
                   SET attempts=attempts+1,last_error=?
                   WHERE event_id=? AND status='pending' ''',
                (str(error)[:1000], str(event_id)),
            )
            db.commit()
            return cursor.rowcount == 1
        finally:
            db.close()

    def stats(self):
        db = self._connect()
        try:
            row = db.execute(
                '''SELECT
                     SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending,
                     SUM(CASE WHEN status='acknowledged' THEN 1 ELSE 0 END) AS acknowledged,
                     COALESCE(SUM(attempts),0) AS attempts,
                     SUM(CASE WHEN status='pending' AND last_error IS NOT NULL THEN 1 ELSE 0 END) AS failed
                   FROM edge_event_outbox'''
            ).fetchone()
            return {
                'pending': int(row['pending'] or 0),
                'acknowledged': int(row['acknowledged'] or 0),
                'attempts': int(row['attempts'] or 0),
                'failed': int(row['failed'] or 0),
            }
        finally:
            db.close()
