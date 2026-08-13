"""Durable SQLite outbox used before acknowledging a device event."""

import json
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import time
import uuid

from device_platform.contracts import DeviceEvent


@dataclass(frozen=True)
class EventClaim:
    event: DeviceEvent
    lease_token: str

    def __getattr__(self, name):
        return getattr(self.event, name)


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
                    lease_owner TEXT,
                    lease_until TIMESTAMP,
                    lease_token TEXT,
                    next_attempt_at INTEGER NOT NULL DEFAULT 0,
                    dead_lettered_at TIMESTAMP,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    acknowledged_at TIMESTAMP
                )'''
            )
            columns = {row[1] for row in db.execute('PRAGMA table_info(edge_event_outbox)')}
            if 'lease_owner' not in columns:
                db.execute('ALTER TABLE edge_event_outbox ADD COLUMN lease_owner TEXT')
            if 'lease_until' not in columns:
                db.execute('ALTER TABLE edge_event_outbox ADD COLUMN lease_until TIMESTAMP')
            if 'lease_token' not in columns:
                db.execute('ALTER TABLE edge_event_outbox ADD COLUMN lease_token TEXT')
            if 'next_attempt_at' not in columns:
                db.execute('ALTER TABLE edge_event_outbox ADD COLUMN next_attempt_at INTEGER NOT NULL DEFAULT 0')
            if 'dead_lettered_at' not in columns:
                db.execute('ALTER TABLE edge_event_outbox ADD COLUMN dead_lettered_at TIMESTAMP')
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
                     AND dead_lettered_at IS NULL
                   ORDER BY device_code,sequence,id LIMIT ?''',
                (limit,),
            ).fetchall()
            return [DeviceEvent.from_dict(json.loads(row['envelope_json'])) for row in rows]
        finally:
            db.close()

    def claim_pending(self, worker_id, limit=100, lease_seconds=30, now=None):
        if not str(worker_id).strip():
            raise ValueError('worker_id is required')
        if not isinstance(limit, int) or limit < 1 or not isinstance(lease_seconds, int) or lease_seconds < 1:
            raise ValueError('limit and lease_seconds must be positive integers')
        now = int(time.time()) if now is None else int(now)
        db = self._connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            rows = db.execute(
                '''SELECT o.id,o.event_id,o.envelope_json FROM edge_event_outbox o
                   WHERE o.status='pending'
                     AND o.dead_lettered_at IS NULL AND o.next_attempt_at <= ?
                     AND (o.lease_until IS NULL OR typeof(o.lease_until)!='integer' OR o.lease_until <= ?)
                     AND NOT EXISTS (
                       SELECT 1 FROM edge_event_outbox earlier
                       WHERE earlier.device_code=o.device_code AND earlier.status='pending'
                         AND earlier.dead_lettered_at IS NULL
                         AND earlier.sequence < o.sequence
                     )
                   ORDER BY o.device_code,o.sequence,o.id LIMIT ?''', (now, now, limit)
            ).fetchall()
            claims = []
            for row in rows:
                token = uuid.uuid4().hex
                db.execute(
                    '''UPDATE edge_event_outbox SET lease_owner=?,lease_token=?,
                       lease_until=?
                       WHERE id=?''',
                    (str(worker_id), token, now + lease_seconds, row['id']),
                )
                claims.append(EventClaim(
                    DeviceEvent.from_dict(json.loads(row['envelope_json'])), token
                ))
            db.commit()
            return claims
        finally:
            db.close()

    def ack(self, event_id, worker_id=None, lease_token=None):
        db = self._connect()
        try:
            cursor = db.execute(
                '''UPDATE edge_event_outbox
                   SET status='acknowledged',acknowledged_at=CURRENT_TIMESTAMP,last_error=NULL
                   WHERE event_id=? AND status='pending'
                     AND (? IS NULL OR (lease_owner=? AND lease_token=?))''',
                (str(event_id), worker_id, worker_id, lease_token),
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

    def release(self, event_id, worker_id, lease_token, error, now=None,
                backoff_seconds=2, max_attempts=10, permanent=False):
        now = int(time.time()) if now is None else int(now)
        db = self._connect()
        try:
            row = db.execute(
                '''SELECT attempts FROM edge_event_outbox
                   WHERE event_id=? AND status='pending' AND lease_owner=? AND lease_token=?''',
                (str(event_id), str(worker_id), str(lease_token)),
            ).fetchone()
            if row is None:
                return False
            delay = max(0, int(backoff_seconds)) * (2 ** min(int(row['attempts']), 8))
            cursor = db.execute(
                '''UPDATE edge_event_outbox
                   SET attempts=attempts+1,last_error=?,lease_owner=NULL,lease_until=NULL,
                       lease_token=NULL,next_attempt_at=?,
                       dead_lettered_at=CASE WHEN ? OR attempts+1>=?
                                            THEN CURRENT_TIMESTAMP ELSE NULL END
                   WHERE event_id=? AND status='pending'
                     AND lease_owner=? AND lease_token=?''',
                (str(error)[:1000], now + delay,
                 1 if permanent else 0, int(max_attempts), str(event_id),
                 str(worker_id), str(lease_token)),
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
                     SUM(CASE WHEN status='pending' AND dead_lettered_at IS NULL THEN 1 ELSE 0 END) AS pending,
                     SUM(CASE WHEN status='acknowledged' THEN 1 ELSE 0 END) AS acknowledged,
                     COALESCE(SUM(attempts),0) AS attempts,
                     SUM(CASE WHEN status='pending' AND dead_lettered_at IS NULL
                               AND last_error IS NOT NULL THEN 1 ELSE 0 END) AS failed
                     ,SUM(CASE WHEN dead_lettered_at IS NOT NULL THEN 1 ELSE 0 END) AS dead_letter
                   FROM edge_event_outbox'''
            ).fetchone()
            return {
                'pending': int(row['pending'] or 0),
                'acknowledged': int(row['acknowledged'] or 0),
                'attempts': int(row['attempts'] or 0),
                'failed': int(row['failed'] or 0),
                'dead_letter': int(row['dead_letter'] or 0),
            }
        finally:
            db.close()
