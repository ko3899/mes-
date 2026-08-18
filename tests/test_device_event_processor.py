import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from device_platform.contracts import DeviceEvent  # noqa: E402
from services.device_event_ingest import create_device_event_tables, ingest_device_event  # noqa: E402
from services.device_event_processor import (  # noqa: E402
    create_event_processing_tables, process_pending_events,
)


def make_event(event_id='E1'):
    return DeviceEvent.from_dict({
        'schema_version': '1.0', 'event_id': event_id, 'customer_code': 'C',
        'factory_code': 'F1', 'gateway_code': 'GW1', 'device_code': 'D1',
        'event_type': 'device.connected', 'occurred_at': '2026-08-16T10:00:00+08:00',
        'received_at': None, 'sequence': 1, 'correlation_id': None,
        'payload': {'port': 1}, 'raw_reference': None,
    })


def test_pending_event_is_claimed_processed_and_idempotent():
    db = sqlite3.connect(':memory:'); db.row_factory = sqlite3.Row
    create_device_event_tables(db); create_event_processing_tables(db)
    ingest_device_event(db, make_event())
    seen = []
    assert process_pending_events(db, lambda event: seen.append(event.event_id)) == {
        'claimed': 1, 'processed': 1, 'failed': 0,
    }
    assert process_pending_events(db, lambda event: seen.append(event.event_id)) == {
        'claimed': 0, 'processed': 0, 'failed': 0,
    }
    assert seen == ['E1']
    assert db.execute('SELECT processing_status FROM iot_device_event').fetchone()[0] == 'processed'


def test_failed_event_remains_retryable_with_error():
    db = sqlite3.connect(':memory:'); db.row_factory = sqlite3.Row
    create_device_event_tables(db); create_event_processing_tables(db)
    ingest_device_event(db, make_event())
    assert process_pending_events(db, lambda event: (_ for _ in ()).throw(RuntimeError('down'))) == {
        'claimed': 1, 'processed': 0, 'failed': 1,
    }
    row = db.execute('SELECT processing_status,last_processing_error FROM iot_device_event').fetchone()
    assert tuple(row) == ('failed', 'down')
