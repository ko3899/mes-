"""Compatibility mapping from legacy AIM inspection rows to standard events."""

from datetime import datetime, timezone, timedelta
import json
import time
import uuid

from device_platform.contracts import DeviceEvent


CHINA_STANDARD_TIME = timezone(timedelta(hours=8))


def create_aim_event_outbox(db, commit=True):
    db.execute('''CREATE TABLE IF NOT EXISTS iot_aim_event_outbox (
        event_id TEXT PRIMARY KEY,
        envelope_json TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0,
        last_error TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        dispatched_at TIMESTAMP
    )''')
    columns = {row[1] for row in db.execute('PRAGMA table_info(iot_aim_event_outbox)')}
    if 'dispatch_owner' not in columns:
        db.execute('ALTER TABLE iot_aim_event_outbox ADD COLUMN dispatch_owner TEXT')
    if 'dispatch_until' not in columns:
        db.execute('ALTER TABLE iot_aim_event_outbox ADD COLUMN dispatch_until INTEGER')
    db.execute('''CREATE TABLE IF NOT EXISTS iot_aim_device_sequence (
        endpoint_id INTEGER NOT NULL,
        device_code TEXT NOT NULL,
        lifecycle_id TEXT NOT NULL,
        last_sequence INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(endpoint_id, device_code, lifecycle_id)
    )''')
    if commit:
        db.commit()


def enqueue_aim_event(db, event):
    in_transaction = db.in_transaction
    create_aim_event_outbox(db, commit=not in_transaction)
    row = db.execute(
        'INSERT OR IGNORE INTO iot_aim_event_outbox(event_id,envelope_json) VALUES(?,?)',
        (event.event_id, json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True)),
    )
    if not in_transaction:
        db.commit()
    return row.rowcount == 1


def dispatch_aim_event(db, event_id, sink):
    now = int(time.time())
    owner = uuid.uuid4().hex
    row = db.execute(
        "SELECT * FROM iot_aim_event_outbox WHERE event_id=? AND status='pending'",
        (event_id,),
    ).fetchone()
    if not row:
        return False
    claimed = db.execute(
        '''UPDATE iot_aim_event_outbox SET dispatch_owner=?,dispatch_until=?
           WHERE event_id=? AND status='pending'
             AND (dispatch_owner IS NULL OR dispatch_until IS NULL OR dispatch_until<=?)''',
        (owner, now + 60, event_id, now),
    ).rowcount
    db.commit()
    if claimed != 1:
        return False
    try:
        result = sink(DeviceEvent.from_dict(json.loads(row['envelope_json'])))
        if hasattr(result, 'accepted') and not result.accepted:
            raise RuntimeError('standard event sink rejected the event')
    except Exception as exc:
        db.execute(
            'UPDATE iot_aim_event_outbox SET attempts=attempts+1,last_error=?,dispatch_owner=NULL,dispatch_until=NULL WHERE event_id=? AND dispatch_owner=?',
            (str(exc)[:1000], event_id, owner),
        ); db.commit(); return False
    db.execute(
        "UPDATE iot_aim_event_outbox SET status='dispatched',dispatched_at=CURRENT_TIMESTAMP,last_error=NULL,dispatch_owner=NULL,dispatch_until=NULL WHERE event_id=? AND dispatch_owner=?",
        (event_id, owner),
    ); db.commit(); return True


def dispatch_pending_aim_events(db, sink, limit=100):
    """Retry all pending AIM events so transient failures are recoverable."""
    rows = db.execute(
        """SELECT event_id FROM iot_aim_event_outbox
           WHERE status='pending' ORDER BY created_at,event_id LIMIT ?""", (int(limit),)
    ).fetchall()
    attempted = dispatched = failed = 0
    for row in rows:
        attempted += 1
        if dispatch_aim_event(db, row['event_id'], sink):
            dispatched += 1
        else:
            failed += 1
    return {'attempted': attempted, 'dispatched': dispatched, 'failed': failed}


def next_aim_sequence(db, endpoint, lifecycle_id=None):
    """Allocate a sequence scoped to one AIM device lifecycle."""
    in_transaction = db.in_transaction
    create_aim_event_outbox(db, commit=not in_transaction)
    endpoint_id = int(_value(endpoint, 'id'))
    device_code = str(_value(endpoint, 'device_code', f'AIM-{endpoint_id}'))
    lifecycle = str(lifecycle_id or _value(endpoint, 'lifecycle_id', 'legacy'))
    if not in_transaction:
        db.execute('BEGIN IMMEDIATE')
    try:
        db.execute(
            '''INSERT OR IGNORE INTO iot_aim_device_sequence
               (endpoint_id,device_code,lifecycle_id,last_sequence) VALUES(?,?,?,0)''',
            (endpoint_id, device_code, lifecycle),
        )
        db.execute(
            '''UPDATE iot_aim_device_sequence SET last_sequence=last_sequence+1
               WHERE endpoint_id=? AND device_code=? AND lifecycle_id=?''',
            (endpoint_id, device_code, lifecycle),
        )
        value = db.execute(
            '''SELECT last_sequence FROM iot_aim_device_sequence
               WHERE endpoint_id=? AND device_code=? AND lifecycle_id=?''',
            (endpoint_id, device_code, lifecycle),
        ).fetchone()[0]
        if not in_transaction:
            db.commit()
        return int(value)
    except Exception:
        if not in_transaction:
            db.rollback()
        raise


def _value(row, key, default=None):
    try:
        value = row[key]
    except (KeyError, TypeError, IndexError):
        value = default
    return default if value is None else value


def _occurred_at(value):
    text = str(value or '').strip()
    if not text:
        return datetime.now(CHINA_STANDARD_TIME).isoformat(timespec='seconds')
    try:
        parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('AIM inspected_at is not a supported timestamp') from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=CHINA_STANDARD_TIME)
    return parsed.isoformat(timespec='seconds')


def aim_report_event(endpoint, request_row, report_row, measurements, sequence=None,
                     lifecycle_id=None):
    """Build the deterministic standard event representing one AIM report."""
    endpoint_id = int(_value(endpoint, 'id'))
    report_id = int(_value(report_row, 'id'))
    result = str(_value(report_row, 'result', '')).upper()
    payload = {
        'sn': str(_value(request_row, 'sn', '')),
        'workorder_id': _value(request_row, 'workorder_id'),
        'station_code': str(_value(endpoint, 'station_code', '')),
        'result': result,
        'measurements': dict(measurements or {}),
    }
    for optional_key in ('task_id', 'process_id', 'route_step_id'):
        optional_value = _value(request_row, optional_key)
        if optional_value is not None:
            payload[optional_key] = optional_value
    return DeviceEvent.from_dict({
        'schema_version': '1.0',
        'event_id': f'AIM:{endpoint_id}:REPORT:{report_id}',
        'customer_code': str(_value(endpoint, 'customer_code', 'LEGACY')),
        'factory_code': str(_value(endpoint, 'factory_code', 'LEGACY')),
        'gateway_code': str(_value(endpoint, 'gateway_code', 'AIM-COMPAT')),
        'device_code': str(_value(endpoint, 'device_code', f'AIM-{endpoint_id}')),
        'event_type': 'quality.completed',
        'occurred_at': _occurred_at(_value(report_row, 'inspected_at')),
        'received_at': None,
        'sequence': report_id if sequence is None else int(sequence),
        'correlation_id': str(_value(request_row, 'request_no', _value(request_row, 'id'))),
        'payload': payload,
        'raw_reference': _value(report_row, 'archive_path'),
        'lifecycle_id': lifecycle_id,
    })
