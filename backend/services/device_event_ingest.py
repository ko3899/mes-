"""Transactional, idempotent ingestion of standard device events."""

from dataclasses import dataclass
import json
import sqlite3

from device_platform.contracts import DeviceEvent


@dataclass(frozen=True)
class IngestResult:
    accepted: bool
    duplicate: bool = False
    gap_expected: int = None
    gap_actual: int = None
    sequence_conflict: bool = False


def create_device_event_tables(db):
    db.execute(
        '''CREATE TABLE IF NOT EXISTS iot_device_event (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            schema_version TEXT NOT NULL,
            customer_code TEXT NOT NULL,
            factory_code TEXT NOT NULL,
            gateway_code TEXT NOT NULL,
            device_code TEXT NOT NULL,
            event_type TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            received_at TEXT,
            sequence INTEGER NOT NULL CHECK(sequence > 0),
            correlation_id TEXT,
            payload_json TEXT NOT NULL,
            raw_reference TEXT,
            processing_status TEXT NOT NULL DEFAULT 'pending',
            ingested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )'''
    )
    db.execute(
        '''CREATE TABLE IF NOT EXISTS iot_device_cursor (
            factory_code TEXT NOT NULL,
            device_code TEXT NOT NULL,
            last_sequence INTEGER NOT NULL CHECK(last_sequence > 0),
            last_event_id TEXT NOT NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(factory_code,device_code)
        )'''
    )
    db.execute(
        '''CREATE TABLE IF NOT EXISTS iot_device_sequence_gap (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factory_code TEXT NOT NULL,
            device_code TEXT NOT NULL,
            missing_from INTEGER NOT NULL,
            missing_to INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'open'
                CHECK(status IN ('open','resolved')),
            detected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            UNIQUE(factory_code,device_code,missing_from,missing_to)
        )'''
    )
    db.execute(
        '''CREATE INDEX IF NOT EXISTS idx_iot_device_event_identity_sequence
           ON iot_device_event(factory_code,device_code,sequence)'''
    )
    db.execute(
        '''CREATE INDEX IF NOT EXISTS idx_iot_device_event_status
           ON iot_device_event(processing_status,ingested_at)'''
    )
    db.execute(
        '''CREATE INDEX IF NOT EXISTS idx_iot_device_gap_status
           ON iot_device_sequence_gap(status,factory_code,device_code)'''
    )
    db.commit()


def ingest_device_event(db, event):
    if not isinstance(event, DeviceEvent):
        raise TypeError('event must be a DeviceEvent')
    existing = db.execute(
        'SELECT id FROM iot_device_event WHERE event_id=?', (event.event_id,)
    ).fetchone()
    if existing:
        return IngestResult(accepted=True, duplicate=True)

    payload_json = json.dumps(
        event.to_dict()['payload'], ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False,
    )
    db.execute('SAVEPOINT ingest_device_event')
    try:
        conflict = db.execute(
            '''SELECT 1 FROM iot_device_event
               WHERE factory_code=? AND device_code=? AND sequence=? LIMIT 1''',
            (event.factory_code, event.device_code, event.sequence),
        ).fetchone() is not None
        try:
            db.execute(
                '''INSERT INTO iot_device_event
                   (event_id,schema_version,customer_code,factory_code,gateway_code,
                    device_code,event_type,occurred_at,received_at,sequence,
                    correlation_id,payload_json,raw_reference)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (event.event_id, event.schema_version, event.customer_code,
                 event.factory_code, event.gateway_code, event.device_code,
                 event.event_type, event.occurred_at, event.received_at,
                 event.sequence, event.correlation_id, payload_json,
                 event.raw_reference),
            )
        except sqlite3.IntegrityError:
            duplicate = db.execute(
                'SELECT 1 FROM iot_device_event WHERE event_id=?', (event.event_id,)
            ).fetchone()
            if duplicate:
                db.execute('ROLLBACK TO SAVEPOINT ingest_device_event')
                db.execute('RELEASE SAVEPOINT ingest_device_event')
                return IngestResult(accepted=True, duplicate=True)
            raise

        cursor = db.execute(
            '''SELECT last_sequence FROM iot_device_cursor
               WHERE factory_code=? AND device_code=?''',
            (event.factory_code, event.device_code),
        ).fetchone()
        last_sequence = int(cursor[0]) if cursor else 0
        gap_expected = None
        gap_actual = None
        if event.sequence > last_sequence + 1:
            gap_expected = last_sequence + 1
            gap_actual = event.sequence
            db.execute(
                '''INSERT OR IGNORE INTO iot_device_sequence_gap
                   (factory_code,device_code,missing_from,missing_to)
                   VALUES(?,?,?,?)''',
                (event.factory_code, event.device_code,
                 gap_expected, event.sequence - 1),
            )
        if event.sequence > last_sequence:
            db.execute(
                '''INSERT INTO iot_device_cursor
                   (factory_code,device_code,last_sequence,last_event_id)
                   VALUES(?,?,?,?)
                   ON CONFLICT(factory_code,device_code) DO UPDATE SET
                     last_sequence=excluded.last_sequence,
                     last_event_id=excluded.last_event_id,
                     updated_at=CURRENT_TIMESTAMP''',
                (event.factory_code, event.device_code,
                 event.sequence, event.event_id),
            )

        db.execute(
            '''UPDATE iot_device_sequence_gap
               SET status='resolved',resolved_at=CURRENT_TIMESTAMP
               WHERE factory_code=? AND device_code=? AND status='open'
                 AND NOT EXISTS (
                   SELECT 1 FROM (
                     WITH RECURSIVE missing(n) AS (
                       SELECT iot_device_sequence_gap.missing_from
                       UNION ALL SELECT n+1 FROM missing
                         WHERE n < iot_device_sequence_gap.missing_to
                     ) SELECT n FROM missing
                   ) m WHERE NOT EXISTS (
                     SELECT 1 FROM iot_device_event e
                     WHERE e.factory_code=iot_device_sequence_gap.factory_code
                       AND e.device_code=iot_device_sequence_gap.device_code
                       AND e.sequence=m.n
                   )
                 )''',
            (event.factory_code, event.device_code),
        )
        db.execute('RELEASE SAVEPOINT ingest_device_event')
        db.commit()
        return IngestResult(
            accepted=True,
            gap_expected=gap_expected,
            gap_actual=gap_actual,
            sequence_conflict=conflict,
        )
    except Exception:
        try:
            db.execute('ROLLBACK TO SAVEPOINT ingest_device_event')
            db.execute('RELEASE SAVEPOINT ingest_device_event')
        except sqlite3.Error:
            pass
        db.rollback()
        raise
