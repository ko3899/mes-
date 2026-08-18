"""Reliable central processing worker for standard device events."""

from dataclasses import dataclass
import json
import sqlite3
import time
import uuid

from device_platform.contracts import DeviceEvent


def create_event_processing_tables(db):
    columns = {row[1] for row in db.execute('PRAGMA table_info(iot_device_event)')}
    additions = {
        'processing_attempts': 'INTEGER NOT NULL DEFAULT 0',
        'last_processing_error': 'TEXT',
        'next_processing_at': 'INTEGER NOT NULL DEFAULT 0',
        'processing_lease_owner': 'TEXT',
        'processing_lease_until': 'INTEGER',
        'processing_lease_token': 'TEXT',
        'processed_at': 'TIMESTAMP',
    }
    for name, definition in additions.items():
        if name not in columns:
            db.execute(f'ALTER TABLE iot_device_event ADD COLUMN {name} {definition}')
    db.execute('CREATE INDEX IF NOT EXISTS idx_iot_event_processing_queue ON iot_device_event(processing_status,next_processing_at,ingested_at)')
    db.execute('''CREATE TABLE IF NOT EXISTS iot_device_event_effect (
        event_id TEXT PRIMARY KEY,
        effect_type TEXT NOT NULL,
        effect_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS iot_device_state (
        factory_code TEXT NOT NULL, device_code TEXT NOT NULL, lifecycle_id TEXT NOT NULL,
        state TEXT NOT NULL, payload_json TEXT NOT NULL, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(factory_code,device_code,lifecycle_id)
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS iot_device_alarm (
        event_id TEXT PRIMARY KEY, factory_code TEXT NOT NULL, device_code TEXT NOT NULL,
        lifecycle_id TEXT NOT NULL, status TEXT NOT NULL, payload_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS iot_device_measurement (
        event_id TEXT PRIMARY KEY, factory_code TEXT NOT NULL, device_code TEXT NOT NULL,
        lifecycle_id TEXT NOT NULL, event_type TEXT NOT NULL, payload_json TEXT NOT NULL,
        occurred_at TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    db.commit()


def apply_standard_event(db, event):
    """Record the idempotent MES-side effect for a validated standard event.

    Device-specific production mutations remain in their domain services; this
    ledger prevents a retried transport event from applying the integration
    effect twice and gives operators a concrete processing result.
    """
    create_event_processing_tables(db)
    payload = event.to_dict()['payload']
    existing_effect = db.execute(
        'SELECT 1 FROM iot_device_event_effect WHERE event_id=?', (event.event_id,)
    ).fetchone()
    if existing_effect:
        return
    if event.event_type == 'quality.completed':
        result = str(payload.get('result') or '').upper()
        if result not in ('OK', 'NG') or not str(payload.get('sn') or '').strip():
            raise ValueError('quality.completed requires sn and result OK/NG')
        # AIM CSV import already creates the draft prod_report and links it to
        # the inspection row.  The standard event is the durable integration
        # record; never create a second report for the same imported result.
        if event.event_id.startswith('AIM:'):
            try:
                inspection_id = int(event.event_id.rsplit(':', 1)[-1])
            except ValueError:
                inspection_id = 0
            linked = None
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='iot_inspection_report'").fetchone():
                linked = db.execute(
                    'SELECT prod_report_id FROM iot_inspection_report WHERE id=?',
                    (inspection_id,),
                ).fetchone()
            if linked and linked['prod_report_id']:
                return
        _apply_quality_completed(db, event, payload, result)
    elif event.event_type in ('device.connected', 'device.disconnected', 'device.state.changed'):
        state = str(payload.get('state') or event.event_type.rsplit('.', 1)[-1])
        db.execute('''INSERT INTO iot_device_state
            (factory_code,device_code,lifecycle_id,state,payload_json)
            VALUES(?,?,?,?,?) ON CONFLICT(factory_code,device_code,lifecycle_id) DO UPDATE SET
            state=excluded.state,payload_json=excluded.payload_json,updated_at=CURRENT_TIMESTAMP''',
            (event.factory_code, event.device_code, event.lifecycle_id or 'legacy',
             state, json.dumps(payload, ensure_ascii=False, sort_keys=True)))
    elif event.event_type in ('alarm.raised', 'alarm.cleared'):
        db.execute('''INSERT OR IGNORE INTO iot_device_alarm
            (event_id,factory_code,device_code,lifecycle_id,status,payload_json)
            VALUES(?,?,?,?,?,?)''',
            (event.event_id, event.factory_code, event.device_code,
             event.lifecycle_id or 'legacy', event.event_type.rsplit('.', 1)[-1],
             json.dumps(payload, ensure_ascii=False, sort_keys=True)))
    elif event.event_type in ('measurement.sampled', 'energy.sampled', 'count.changed'):
        db.execute('''INSERT OR IGNORE INTO iot_device_measurement
            (event_id,factory_code,device_code,lifecycle_id,event_type,payload_json,occurred_at)
            VALUES(?,?,?,?,?,?,?)''',
            (event.event_id, event.factory_code, event.device_code,
             event.lifecycle_id or 'legacy', event.event_type,
             json.dumps(payload, ensure_ascii=False, sort_keys=True), event.occurred_at))
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    db.execute('''INSERT OR IGNORE INTO iot_device_event_effect
        (event_id,effect_type,effect_json) VALUES(?,?,?)''',
        (event.event_id, event.event_type, encoded))
    db.commit()


def _apply_quality_completed(db, event, payload, result):
    """Turn a machine quality event into the normal approved/posting path."""
    task_id = payload.get('task_id')
    workorder_id = payload.get('workorder_id')
    process_id = payload.get('process_id')
    if not task_id:
        raise ValueError('quality.completed requires task_id')
    task = db.execute('SELECT id,workorder_id,process_id,planned_qty FROM prod_task WHERE id=?',
                      (task_id,)).fetchone()
    if not task:
        raise ValueError('quality.completed task does not exist')
    workorder_id = workorder_id or task['workorder_id']
    process_id = process_id or task['process_id']
    if int(task['workorder_id']) != int(workorder_id):
        raise ValueError('quality.completed task/workorder does not match')
    if db.execute('SELECT 1 FROM prod_report WHERE client_operation_id=? AND user_id=0',
                  (event.event_id,)).fetchone():
        return
    qualified = float(payload.get('qualified_qty', 1 if result == 'OK' else 0) or 0)
    defect = float(payload.get('defect_qty', 1 if result == 'NG' else 0) or 0)
    if qualified < 0 or defect < 0 or qualified + defect <= 0:
        raise ValueError('quality.completed quantities must be positive')
    db.execute('SAVEPOINT quality_event_effect')
    try:
        report_no = 'IOT-' + event.event_id.replace(':', '-')
        report_id = db.execute('''INSERT INTO prod_report
            (report_no,task_id,workorder_id,process_id,user_id,qualified_qty,defect_qty,
             approval_status,posted_at,remark,client_operation_id)
            VALUES(?,?,?,?,?,?,?,1,NULL,?,?)''',
            (report_no, int(task_id), int(workorder_id), int(process_id), 0,
             qualified, defect, '设备标准事件', event.event_id)).lastrowid
        from services.production_flow import post_report
        post_report(db, report_id, 0, '设备标准事件自动记账')
        db.execute('RELEASE SAVEPOINT quality_event_effect')
    except Exception:
        db.execute('ROLLBACK TO SAVEPOINT quality_event_effect')
        db.execute('RELEASE SAVEPOINT quality_event_effect')
        raise


@dataclass(frozen=True)
class EventClaim:
    event: DeviceEvent
    lease_token: str


def _event_from_row(row):
    return DeviceEvent.from_dict({
        'schema_version': row['schema_version'], 'event_id': row['event_id'],
        'customer_code': row['customer_code'], 'factory_code': row['factory_code'],
        'gateway_code': row['gateway_code'], 'device_code': row['device_code'],
        'event_type': row['event_type'], 'occurred_at': row['occurred_at'],
        'received_at': row['received_at'], 'sequence': row['sequence'],
        'correlation_id': row['correlation_id'], 'payload': json.loads(row['payload_json']),
        'raw_reference': row['raw_reference'], 'lifecycle_id': row['lifecycle_id'],
    })


def process_pending_events(db, handler, limit=100, worker_id='processor', lease_seconds=30,
                           backoff_seconds=2):
    create_event_processing_tables(db)
    now = int(time.time())
    db.execute('''UPDATE iot_device_event SET processing_status='pending',
        processing_lease_owner=NULL,processing_lease_until=NULL,processing_lease_token=NULL
        WHERE processing_status='processing' AND processing_lease_until IS NOT NULL
          AND processing_lease_until <= ?''', (now,))
    db.commit()
    rows = db.execute('''SELECT * FROM iot_device_event
        WHERE processing_status IN ('pending','failed') AND next_processing_at <= ?
        ORDER BY ingested_at,id LIMIT ?''', (now, int(limit))).fetchall()
    claimed = processed = failed = 0
    for row in rows:
        token = uuid.uuid4().hex
        updated = db.execute('''UPDATE iot_device_event SET processing_status='processing',
            processing_lease_owner=?,processing_lease_until=?,processing_lease_token=?
            WHERE id=? AND processing_status IN ('pending','failed')''',
            (str(worker_id), now + int(lease_seconds), token, row['id'])).rowcount
        db.commit()
        if not updated:
            continue
        claimed += 1
        event = _event_from_row(row)
        try:
            handler(event)
            db.execute('''UPDATE iot_device_event SET processing_status='processed',
                processed_at=CURRENT_TIMESTAMP,last_processing_error=NULL,
                processing_lease_owner=NULL,processing_lease_until=NULL,processing_lease_token=NULL
                WHERE id=? AND processing_lease_owner=? AND processing_lease_token=?''',
                (row['id'], str(worker_id), token))
            db.commit(); processed += 1
        except Exception as exc:
            db.execute('''UPDATE iot_device_event SET processing_status='failed',
                processing_attempts=processing_attempts+1,last_processing_error=?,
                next_processing_at=?,processing_lease_owner=NULL,processing_lease_until=NULL,processing_lease_token=NULL
                WHERE id=? AND processing_lease_owner=? AND processing_lease_token=?''',
                (str(exc)[:1000], now + max(0, int(backoff_seconds)), row['id'], str(worker_id), token))
            db.commit(); failed += 1
    return {'claimed': claimed, 'processed': processed, 'failed': failed}
