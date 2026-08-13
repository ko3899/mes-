import os
import sqlite3
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from device_platform.contracts import DeviceEvent  # noqa: E402
from services.device_event_ingest import (  # noqa: E402
    create_device_event_tables,
    ingest_device_event,
)


def event(device, sequence, event_id, factory='F01'):
    return DeviceEvent.from_dict({
        'schema_version': '1.0',
        'event_id': event_id,
        'customer_code': 'CUSTOMER-A',
        'factory_code': factory,
        'gateway_code': f'GW-{factory}-A',
        'device_code': device,
        'event_type': 'measurement.sampled',
        'occurred_at': '2026-08-13T10:30:18+08:00',
        'received_at': None,
        'sequence': sequence,
        'correlation_id': None,
        'payload': {'value': sequence},
        'raw_reference': None,
    })


def build_db():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    create_device_event_tables(db)
    return db


def test_ingestion_is_idempotent_and_records_sequence_gap():
    db = build_db()
    first = ingest_device_event(db, event('D1', 1, 'E1'))
    duplicate = ingest_device_event(db, event('D1', 1, 'E1'))
    gap = ingest_device_event(db, event('D1', 3, 'E3'))

    assert first.accepted is True and first.duplicate is False
    assert duplicate.accepted is True and duplicate.duplicate is True
    assert (gap.gap_expected, gap.gap_actual) == (2, 3)
    assert db.execute('SELECT COUNT(*) FROM iot_device_event').fetchone()[0] == 2
    assert db.execute('SELECT last_sequence FROM iot_device_cursor').fetchone()[0] == 3
    row = db.execute(
        'SELECT missing_from,missing_to,status FROM iot_device_sequence_gap'
    ).fetchone()
    assert tuple(row) == (2, 2, 'open')


def test_late_event_closes_single_sequence_gap_without_rewinding_cursor():
    db = build_db()
    ingest_device_event(db, event('D1', 1, 'E1'))
    ingest_device_event(db, event('D1', 3, 'E3'))
    late = ingest_device_event(db, event('D1', 2, 'E2'))

    assert late.accepted and not late.duplicate
    assert db.execute('SELECT last_sequence FROM iot_device_cursor').fetchone()[0] == 3
    assert db.execute('SELECT status FROM iot_device_sequence_gap').fetchone()[0] == 'resolved'


def test_late_events_shrink_and_eventually_close_range_gap():
    db = build_db()
    ingest_device_event(db, event('D1', 1, 'E1'))
    ingest_device_event(db, event('D1', 5, 'E5'))
    for sequence in (3, 2, 4):
        ingest_device_event(db, event('D1', sequence, f'E{sequence}'))
    assert db.execute(
        "SELECT COUNT(*) FROM iot_device_sequence_gap WHERE status='open'"
    ).fetchone()[0] == 0


def test_same_sequence_with_different_event_id_is_kept_and_flagged():
    db = build_db()
    ingest_device_event(db, event('D1', 1, 'E1'))
    result = ingest_device_event(db, event('D1', 1, 'E1-OTHER'))

    assert result.accepted is True
    assert result.duplicate is False
    assert result.sequence_conflict is True
    assert db.execute('SELECT COUNT(*) FROM iot_device_event').fetchone()[0] == 2


def test_device_cursor_is_scoped_by_factory_and_device():
    db = build_db()
    ingest_device_event(db, event('D1', 1, 'F01-E1', factory='F01'))
    ingest_device_event(db, event('D1', 5, 'F02-E5', factory='F02'))
    cursors = db.execute(
        'SELECT factory_code,last_sequence FROM iot_device_cursor ORDER BY factory_code'
    ).fetchall()
    assert [tuple(row) for row in cursors] == [('F01', 1), ('F02', 5)]


def test_tables_and_indexes_are_created_idempotently():
    db = sqlite3.connect(':memory:')
    create_device_event_tables(db)
    create_device_event_tables(db)
    names = {row[0] for row in db.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','index')"
    )}
    assert {
        'iot_device_event', 'iot_device_cursor', 'iot_device_sequence_gap',
        'idx_iot_device_event_identity_sequence', 'idx_iot_device_gap_status',
    } <= names
