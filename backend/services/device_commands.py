"""Durable, idempotent command queue shared by MES and edge gateways."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import sqlite3
import time
import uuid

from device_platform.contracts import DeviceCommand, DeviceEvent


@dataclass(frozen=True)
class CommandClaim:
    command: DeviceCommand
    lease_token: str

    def __getattr__(self, name):
        return getattr(self.command, name)


def create_command_tables(db):
    db.execute('''CREATE TABLE IF NOT EXISTS iot_device_command (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        command_id TEXT NOT NULL UNIQUE,
        factory_code TEXT NOT NULL,
        gateway_code TEXT NOT NULL,
        device_code TEXT NOT NULL,
        command_type TEXT NOT NULL,
        command_json TEXT NOT NULL,
        idempotency_key TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'queued'
          CHECK(status IN ('queued','leased','acknowledged','failed','expired')),
        attempts INTEGER NOT NULL DEFAULT 0,
        lease_owner TEXT, lease_token TEXT, lease_until INTEGER,
        last_error TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        acknowledged_at TIMESTAMP
    )''')
    db.execute('CREATE INDEX IF NOT EXISTS idx_iot_command_queue ON iot_device_command(gateway_code,device_code,status,created_at)')
    db.commit()


def enqueue_command(db, command):
    if not isinstance(command, DeviceCommand):
        raise TypeError('command must be a DeviceCommand')
    create_command_tables(db)
    encoded = json.dumps(command.to_dict(), ensure_ascii=False, sort_keys=True)
    try:
        db.execute('''INSERT INTO iot_device_command
            (command_id,factory_code,gateway_code,device_code,command_type,command_json,idempotency_key)
            VALUES(?,?,?,?,?,?,?)''', (command.command_id, command.factory_code,
            command.gateway_code, command.device_code, command.command_type, encoded,
            command.idempotency_key))
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
    row = db.execute('SELECT command_json FROM iot_device_command WHERE idempotency_key=?',
                     (command.idempotency_key,)).fetchone()
    return DeviceCommand.from_dict(json.loads(row['command_json']))


def claim_commands(db, gateway_code, worker_id, device_code=None, limit=50, lease_seconds=30):
    create_command_tables(db)
    now = int(time.time())
    if not str(worker_id).strip():
        raise ValueError('worker_id is required')
    if isinstance(limit, bool) or int(limit) < 1 or int(lease_seconds) < 1:
        raise ValueError('limit and lease_seconds must be positive integers')
    # Claiming is a single SQLite write transaction.  Without IMMEDIATE two
    # gateway workers can SELECT the same queued command before either UPDATE.
    db.execute('BEGIN IMMEDIATE')
    try:
        db.execute('''UPDATE iot_device_command SET status='queued',lease_owner=NULL,lease_token=NULL,lease_until=NULL
                      WHERE status='leased' AND lease_until IS NOT NULL AND lease_until<=?''', (now,))
        clauses = "gateway_code=? AND status='queued'"
        params = [str(gateway_code)]
        if device_code:
            clauses += ' AND device_code=?'; params.append(str(device_code))
        rows = db.execute(f'''SELECT * FROM iot_device_command WHERE {clauses}
                              ORDER BY created_at,id LIMIT ?''', params + [int(limit)]).fetchall()
        result = []
        for row in rows:
            decoded = json.loads(row['command_json'])
            command = DeviceCommand.from_dict(decoded)
            if command.is_expired(datetime.now(timezone.utc)):
                db.execute("UPDATE iot_device_command SET status='expired' WHERE id=? AND status='queued'", (row['id'],))
                continue
            token = uuid.uuid4().hex
            updated = db.execute('''UPDATE iot_device_command SET status='leased',lease_owner=?,lease_token=?,
                          lease_until=?,attempts=attempts+1 WHERE id=? AND status='queued' ''',
                       (str(worker_id), token, now + int(lease_seconds), row['id'])).rowcount
            if updated == 1:
                result.append(CommandClaim(command, token))
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def acknowledge_command(db, command_id, worker_id, status, lease_token, error=None):
    if status not in ('acknowledged', 'failed', 'expired'):
        raise ValueError('invalid command status')
    create_command_tables(db)
    # Create the event tables before changing command state.  The helper can
    # preserve the caller transaction so an ACK and its audit event commit or
    # roll back together.
    from services.device_event_ingest import create_device_event_tables, ingest_device_event
    create_device_event_tables(db, commit=False)
    row = db.execute('SELECT command_json FROM iot_device_command WHERE command_id=?',
                     (str(command_id),)).fetchone()
    rowcount = db.execute('''UPDATE iot_device_command SET status=?,last_error=?,
        acknowledged_at=CASE WHEN ?='acknowledged' THEN CURRENT_TIMESTAMP ELSE acknowledged_at END,
        lease_owner=NULL,lease_token=NULL,lease_until=NULL
        WHERE command_id=? AND status='leased' AND lease_owner=? AND lease_token=?''',
        (status, str(error)[:1000] if error else None, status, str(command_id),
         str(worker_id), str(lease_token))).rowcount
    if rowcount == 1 and row:
        command = DeviceCommand.from_dict(json.loads(row['command_json']))
        timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
        next_sequence = db.execute(
            '''SELECT COALESCE(MAX(sequence),0)+1 FROM iot_device_event
               WHERE factory_code=? AND device_code=? AND lifecycle_id='command' ''',
            (command.factory_code, command.device_code),
        ).fetchone()[0]
        event_type = 'command.acknowledged' if status == 'acknowledged' else 'command.failed'
        event = DeviceEvent.from_dict({
            'schema_version': '1.0',
            'event_id': f'CMD:{command.command_id}:{status}',
            'customer_code': 'SYSTEM', 'factory_code': command.factory_code,
            'gateway_code': command.gateway_code, 'device_code': command.device_code,
            'event_type': event_type, 'occurred_at': timestamp,
            'received_at': timestamp, 'sequence': int(next_sequence),
            'correlation_id': command.command_id,
            'payload': {'command_type': command.command_type, 'error': error},
            'raw_reference': None, 'lifecycle_id': 'command',
        })
        ingest_device_event(db, event)
    db.commit()
    return rowcount == 1
