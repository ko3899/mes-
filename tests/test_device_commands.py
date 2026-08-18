import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from device_platform.contracts import DeviceCommand  # noqa: E402
from services.device_commands import (  # noqa: E402
    create_command_tables, enqueue_command, claim_commands, acknowledge_command,
)


def command(command_id='C1', idem='I1'):
    return DeviceCommand.from_dict({
        'schema_version': '1.0', 'command_id': command_id, 'factory_code': 'F1',
        'gateway_code': 'GW1', 'device_code': 'D1', 'command_type': 'task.control',
        'created_at': '2026-08-16T10:00:00+08:00', 'expires_at': '2026-08-16T23:00:00+08:00',
        'idempotency_key': idem, 'config_version': 'v1', 'payload': {'action': 'pause'},
    })


def test_command_queue_is_idempotent_claimable_and_acknowledgeable():
    db = sqlite3.connect(':memory:'); db.row_factory = sqlite3.Row
    create_command_tables(db)
    first = enqueue_command(db, command())
    duplicate = enqueue_command(db, command('C2', 'I1'))
    assert first.command_id == duplicate.command_id == 'C1'
    claimed = claim_commands(db, 'GW1', 'worker-1')
    assert [item.command_id for item in claimed] == ['C1']
    assert acknowledge_command(db, 'C1', 'worker-1', 'acknowledged', 'wrong') is False
    assert acknowledge_command(db, 'C1', 'worker-1', 'acknowledged', claimed[0].lease_token) is True
    assert db.execute('SELECT status FROM iot_device_command').fetchone()[0] == 'acknowledged'


def test_command_is_claimed_by_only_one_worker():
    db = sqlite3.connect(':memory:'); db.row_factory = sqlite3.Row
    create_command_tables(db)
    enqueue_command(db, command())
    first = claim_commands(db, 'GW1', 'worker-1')
    second = claim_commands(db, 'GW1', 'worker-2')
    assert len(first) == 1
    assert second == []
