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


def create_device_event_tables(db, commit=True):
    db.execute('''CREATE TABLE IF NOT EXISTS iot_device_event (
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
        lifecycle_id TEXT NOT NULL DEFAULT 'legacy',
        processing_status TEXT NOT NULL DEFAULT 'pending',
        ingested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )''')
    columns = {row[1] for row in db.execute('PRAGMA table_info(iot_device_event)')}
    if 'lifecycle_id' not in columns:
        db.execute("ALTER TABLE iot_device_event ADD COLUMN lifecycle_id TEXT NOT NULL DEFAULT 'legacy'")
    db.execute('''CREATE TABLE IF NOT EXISTS iot_device_cursor (
        factory_code TEXT NOT NULL, device_code TEXT NOT NULL,
        last_sequence INTEGER NOT NULL CHECK(last_sequence > 0),
        last_event_id TEXT NOT NULL, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(factory_code,device_code)
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS iot_device_sequence_gap (
        id INTEGER PRIMARY KEY AUTOINCREMENT, factory_code TEXT NOT NULL,
        device_code TEXT NOT NULL, missing_from INTEGER NOT NULL, missing_to INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','resolved')),
        detected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, resolved_at TIMESTAMP,
        UNIQUE(factory_code,device_code,missing_from,missing_to)
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS iot_device_cursor_v2 (
        factory_code TEXT NOT NULL, device_code TEXT NOT NULL, lifecycle_id TEXT NOT NULL,
        last_sequence INTEGER NOT NULL CHECK(last_sequence > 0), last_event_id TEXT NOT NULL,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(factory_code,device_code,lifecycle_id)
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS iot_device_sequence_gap_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT, factory_code TEXT NOT NULL,
        device_code TEXT NOT NULL, lifecycle_id TEXT NOT NULL,
        missing_from INTEGER NOT NULL, missing_to INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','resolved')),
        detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, resolved_at TIMESTAMP,
        UNIQUE(factory_code,device_code,lifecycle_id,missing_from,missing_to)
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS iot_device_event_conflict (
        id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL,
        factory_code TEXT NOT NULL, device_code TEXT NOT NULL, lifecycle_id TEXT NOT NULL,
        sequence INTEGER NOT NULL, payload_json TEXT NOT NULL, reason TEXT NOT NULL,
        quarantined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(event_id,reason)
    )''')
    db.execute('CREATE INDEX IF NOT EXISTS idx_iot_device_event_identity_sequence ON iot_device_event(factory_code,device_code,lifecycle_id,sequence)')
    # A unique constraint is the final concurrency guard.  Older installations
    # may already contain duplicates; leave those rows intact and let the
    # transactional conflict path quarantine all new collisions.
    duplicate = db.execute('''SELECT 1 FROM iot_device_event
        GROUP BY factory_code,device_code,lifecycle_id,sequence HAVING COUNT(*)>1 LIMIT 1''').fetchone()
    if duplicate is None:
        db.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_iot_device_event_identity_sequence_uq
            ON iot_device_event(factory_code,device_code,lifecycle_id,sequence)''')
    db.execute('CREATE INDEX IF NOT EXISTS idx_iot_device_event_status ON iot_device_event(processing_status,ingested_at)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_iot_device_gap_status ON iot_device_sequence_gap(status,factory_code,device_code)')
    if commit:
        db.commit()


def _quarantine(db, event, payload_json, reason):
    db.execute('''INSERT OR IGNORE INTO iot_device_event_conflict
        (event_id,factory_code,device_code,lifecycle_id,sequence,payload_json,reason)
        VALUES(?,?,?,?,?,?,?)''', (
        event.event_id, event.factory_code, event.device_code,
        event.lifecycle_id or 'legacy', event.sequence, payload_json, reason,
    ))


def ingest_device_event(db, event):
    if not isinstance(event, DeviceEvent):
        raise TypeError('event must be a DeviceEvent')
    existing_transaction = db.in_transaction
    create_device_event_tables(db, commit=not existing_transaction)
    own_transaction = not existing_transaction
    if own_transaction:
        db.execute('BEGIN IMMEDIATE')
    lifecycle_id = event.lifecycle_id or 'legacy'
    payload_json = json.dumps(event.to_dict()['payload'], ensure_ascii=False,
                              sort_keys=True, separators=(',', ':'), allow_nan=False)
    existing = db.execute(
        'SELECT factory_code,device_code,event_type,sequence,payload_json,lifecycle_id FROM iot_device_event WHERE event_id=?',
        (event.event_id,),
    ).fetchone()
    if existing:
        same = tuple(existing) == (event.factory_code, event.device_code,
                                   event.event_type, event.sequence, payload_json,
                                   lifecycle_id)
        if same:
            if own_transaction:
                db.commit()
            return IngestResult(accepted=True, duplicate=True)
        _quarantine(db, event, payload_json, 'event_id_payload_mismatch')
        if own_transaction:
            db.commit()
        return IngestResult(accepted=False, sequence_conflict=True)

    db.execute('SAVEPOINT ingest_device_event')
    try:
        conflict = db.execute(
            '''SELECT 1 FROM iot_device_event
               WHERE factory_code=? AND device_code=? AND lifecycle_id=? AND sequence=? LIMIT 1''',
            (event.factory_code, event.device_code, lifecycle_id, event.sequence),
        ).fetchone() is not None
        if conflict:
            db.execute('RELEASE SAVEPOINT ingest_device_event')
            if own_transaction:
                db.commit()
            _quarantine(db, event, payload_json, 'device_sequence_conflict')
            return IngestResult(accepted=False, sequence_conflict=True)
        db.execute('''INSERT INTO iot_device_event
            (event_id,schema_version,customer_code,factory_code,gateway_code,device_code,
             event_type,occurred_at,received_at,sequence,correlation_id,payload_json,
             raw_reference,lifecycle_id)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
            event.event_id, event.schema_version, event.customer_code, event.factory_code,
            event.gateway_code, event.device_code, event.event_type, event.occurred_at,
            event.received_at, event.sequence, event.correlation_id, payload_json,
            event.raw_reference, lifecycle_id,
        ))
        cursor_table = 'iot_device_cursor' if lifecycle_id == 'legacy' else 'iot_device_cursor_v2'
        gap_table = 'iot_device_sequence_gap' if lifecycle_id == 'legacy' else 'iot_device_sequence_gap_v2'
        cursor = db.execute(
            f'''SELECT last_sequence FROM {cursor_table}
                WHERE factory_code=? AND device_code=?'''
            + ('' if lifecycle_id == 'legacy' else ' AND lifecycle_id=?'),
            (event.factory_code, event.device_code) if lifecycle_id == 'legacy'
            else (event.factory_code, event.device_code, lifecycle_id),
        ).fetchone()
        last_sequence = int(cursor[0]) if cursor else 0
        gap_expected = gap_actual = None
        if event.sequence > last_sequence + 1:
            gap_expected, gap_actual = last_sequence + 1, event.sequence
            if lifecycle_id == 'legacy':
                db.execute('INSERT OR IGNORE INTO iot_device_sequence_gap(factory_code,device_code,missing_from,missing_to) VALUES(?,?,?,?)',
                           (event.factory_code, event.device_code, gap_expected, event.sequence - 1))
            else:
                db.execute('INSERT OR IGNORE INTO iot_device_sequence_gap_v2(factory_code,device_code,lifecycle_id,missing_from,missing_to) VALUES(?,?,?,?,?)',
                           (event.factory_code, event.device_code, lifecycle_id, gap_expected, event.sequence - 1))
        if event.sequence > last_sequence:
            if lifecycle_id == 'legacy':
                db.execute('''INSERT INTO iot_device_cursor(factory_code,device_code,last_sequence,last_event_id)
                    VALUES(?,?,?,?) ON CONFLICT(factory_code,device_code) DO UPDATE SET
                    last_sequence=excluded.last_sequence,last_event_id=excluded.last_event_id,updated_at=CURRENT_TIMESTAMP''',
                    (event.factory_code, event.device_code, event.sequence, event.event_id))
            else:
                db.execute('''INSERT INTO iot_device_cursor_v2(factory_code,device_code,lifecycle_id,last_sequence,last_event_id)
                    VALUES(?,?,?,?,?) ON CONFLICT(factory_code,device_code,lifecycle_id) DO UPDATE SET
                    last_sequence=excluded.last_sequence,last_event_id=excluded.last_event_id,updated_at=CURRENT_TIMESTAMP''',
                    (event.factory_code, event.device_code, lifecycle_id, event.sequence, event.event_id))
        if lifecycle_id == 'legacy':
            db.execute('''UPDATE iot_device_sequence_gap SET status='resolved',resolved_at=CURRENT_TIMESTAMP
                WHERE factory_code=? AND device_code=? AND status='open' AND NOT EXISTS (
                  SELECT 1 FROM (WITH RECURSIVE missing(n) AS (
                    SELECT iot_device_sequence_gap.missing_from UNION ALL SELECT n+1 FROM missing
                    WHERE n < iot_device_sequence_gap.missing_to) SELECT n FROM missing) m
                  WHERE NOT EXISTS (SELECT 1 FROM iot_device_event e WHERE e.factory_code=iot_device_sequence_gap.factory_code
                    AND e.device_code=iot_device_sequence_gap.device_code AND e.lifecycle_id='legacy' AND e.sequence=m.n))''',
                (event.factory_code, event.device_code))
        else:
            db.execute('''UPDATE iot_device_sequence_gap_v2 SET status='resolved',resolved_at=CURRENT_TIMESTAMP
                WHERE factory_code=? AND device_code=? AND lifecycle_id=? AND status='open' AND NOT EXISTS (
                  SELECT 1 FROM (WITH RECURSIVE missing(n) AS (
                    SELECT iot_device_sequence_gap_v2.missing_from UNION ALL SELECT n+1 FROM missing
                    WHERE n < iot_device_sequence_gap_v2.missing_to) SELECT n FROM missing) m
                  WHERE NOT EXISTS (SELECT 1 FROM iot_device_event e WHERE e.factory_code=iot_device_sequence_gap_v2.factory_code
                    AND e.device_code=iot_device_sequence_gap_v2.device_code AND e.lifecycle_id=iot_device_sequence_gap_v2.lifecycle_id AND e.sequence=m.n))''',
                (event.factory_code, event.device_code, lifecycle_id))
        db.execute('RELEASE SAVEPOINT ingest_device_event')
        db.commit()
        return IngestResult(True, False, gap_expected, gap_actual, False)
    except Exception:
        try:
            db.execute('ROLLBACK TO SAVEPOINT ingest_device_event')
            db.execute('RELEASE SAVEPOINT ingest_device_event')
        except sqlite3.Error:
            pass
        db.rollback()
        raise
