import os
import sqlite3
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from device_platform.contracts import DeviceEvent  # noqa: E402
from edge_gateway.event_store import EdgeEventStore  # noqa: E402


def event(device, sequence, event_id):
    return DeviceEvent.from_dict({
        'schema_version': '1.0',
        'event_id': event_id,
        'customer_code': 'CUSTOMER-A',
        'factory_code': 'F01',
        'gateway_code': 'GW-F01-A',
        'device_code': device,
        'event_type': 'measurement.sampled',
        'occurred_at': '2026-08-13T10:30:18+08:00',
        'received_at': None,
        'sequence': sequence,
        'correlation_id': None,
        'payload': {'value': sequence},
        'raw_reference': None,
    })


def test_outbox_is_durable_idempotent_and_device_ordered(tmp_path):
    path = tmp_path / 'edge.db'
    store = EdgeEventStore(path)
    assert store.append(event('D2', 2, 'E2')) is True
    assert store.append(event('D1', 1, 'E1')) is True
    assert store.append(event('D1', 1, 'E1')) is False

    restarted = EdgeEventStore(path)
    assert [item.event_id for item in restarted.pending()] == ['E1', 'E2']
    assert restarted.stats() == {
        'pending': 2, 'acknowledged': 0, 'attempts': 0, 'failed': 0,
    }


def test_ack_is_idempotent_and_removes_event_from_pending(tmp_path):
    store = EdgeEventStore(tmp_path / 'edge.db')
    store.append(event('D1', 1, 'E1'))
    assert store.ack('E1') is True
    assert store.ack('E1') is False
    assert store.ack('missing') is False
    assert store.pending() == []
    assert store.stats()['acknowledged'] == 1


def test_failure_keeps_event_pending_and_records_attempt(tmp_path):
    store = EdgeEventStore(tmp_path / 'edge.db')
    store.append(event('D1', 1, 'E1'))
    assert store.fail('E1', 'central offline') is True
    assert store.fail('missing', 'ignored') is False

    assert [item.event_id for item in store.pending()] == ['E1']
    assert store.stats() == {
        'pending': 1, 'acknowledged': 0, 'attempts': 1, 'failed': 1,
    }
    db = sqlite3.connect(tmp_path / 'edge.db')
    row = db.execute(
        'SELECT attempts,last_error FROM edge_event_outbox WHERE event_id=?', ('E1',)
    ).fetchone()
    assert row == (1, 'central offline')


def test_pending_respects_limit_and_never_returns_acknowledged(tmp_path):
    store = EdgeEventStore(tmp_path / 'edge.db')
    for sequence in range(1, 4):
        store.append(event('D1', sequence, f'E{sequence}'))
    store.ack('E1')

    assert [item.event_id for item in store.pending(limit=1)] == ['E2']
    assert [item.event_id for item in store.pending(limit=10)] == ['E2', 'E3']


def test_database_enables_wal_and_foreign_keys(tmp_path):
    store = EdgeEventStore(tmp_path / 'edge.db')
    assert store.database_path == str((tmp_path / 'edge.db').resolve())
    db = sqlite3.connect(store.database_path)
    assert db.execute('PRAGMA journal_mode').fetchone()[0].lower() == 'wal'


def test_claim_allows_only_one_inflight_event_per_device(tmp_path):
    store = EdgeEventStore(tmp_path / 'edge.db')
    store.append(event('D1', 1, 'D1-E1'))
    store.append(event('D1', 2, 'D1-E2'))
    store.append(event('D2', 1, 'D2-E1'))
    first = store.claim_pending('worker-a', limit=10, lease_seconds=30)
    second = store.claim_pending('worker-b', limit=10, lease_seconds=30)
    assert [item.event_id for item in first] == ['D1-E1', 'D2-E1']
    assert second == []
    assert store.ack('D1-E1', worker_id='worker-b') is False
    assert store.ack('D1-E1', worker_id='worker-a') is True
    assert [item.event_id for item in store.claim_pending('worker-b')] == ['D1-E2']


def test_existing_outbox_is_migrated_with_lease_columns(tmp_path):
    path = tmp_path / 'legacy-edge.db'
    db = sqlite3.connect(path)
    db.execute('''CREATE TABLE edge_event_outbox (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT NOT NULL UNIQUE,
        device_code TEXT NOT NULL,
        sequence INTEGER NOT NULL,
        envelope_json TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0,
        last_error TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        acknowledged_at TIMESTAMP
    )''')
    db.commit(); db.close()
    EdgeEventStore(path)
    db = sqlite3.connect(path)
    columns = {row[1] for row in db.execute('PRAGMA table_info(edge_event_outbox)')}
    assert {'lease_owner', 'lease_until'} <= columns
