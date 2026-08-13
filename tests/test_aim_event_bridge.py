import os
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from services.aim_event_bridge import (  # noqa: E402
    aim_report_event, create_aim_event_outbox, enqueue_aim_event,
    dispatch_aim_event,
)


def test_ok_report_maps_to_deterministic_standard_quality_event():
    endpoint = {
        'id': 7, 'device_code': 'AIM-007', 'station_code': 'ST01',
        'customer_code': 'CUSTOMER-A', 'factory_code': 'F01',
        'gateway_code': 'GW-F01-A',
    }
    request_row = {'id': 20, 'request_no': 'REQ-20', 'sn': 'SN001', 'workorder_id': 9}
    report_row = {
        'id': 33, 'result': 'OK', 'inspected_at': '2026-08-13 10:30:18',
        'archive_path': 'archive/SN001.csv',
    }
    first = aim_report_event(endpoint, request_row, report_row, {'width': '12.52'})
    second = aim_report_event(endpoint, request_row, report_row, {'width': '12.52'})

    assert first.event_id == 'AIM:7:REPORT:33'
    assert first.event_id == second.event_id
    assert first.event_type == 'quality.completed'
    assert first.sequence == 33
    assert first.correlation_id == 'REQ-20'
    assert first.payload == {
        'sn': 'SN001', 'workorder_id': 9, 'station_code': 'ST01',
        'result': 'OK', 'measurements': {'width': '12.52'},
    }
    assert first.occurred_at == '2026-08-13T10:30:18+08:00'


def test_ng_report_uses_safe_legacy_identity_defaults():
    event = aim_report_event(
        {'id': 2, 'device_code': 'AIM002', 'station_code': 'CCD'},
        {'id': 4, 'request_no': 'R4', 'sn': 'SN-NG', 'workorder_id': None},
        {'id': 5, 'result': 'NG', 'inspected_at': '2026-08-13T02:30:18Z',
         'archive_path': None},
        {},
    )
    assert event.customer_code == 'LEGACY'
    assert event.factory_code == 'LEGACY'
    assert event.gateway_code == 'AIM-COMPAT'
    assert event.payload['result'] == 'NG'
    assert event.raw_reference is None


def test_failed_dispatch_remains_durable_and_can_retry():
    import sqlite3
    db = sqlite3.connect(':memory:'); db.row_factory = sqlite3.Row
    create_aim_event_outbox(db)
    event = aim_report_event(
        {'id': 2, 'device_code': 'AIM002', 'station_code': 'CCD'},
        {'id': 4, 'request_no': 'R4', 'sn': 'SN1', 'workorder_id': 1},
        {'id': 5, 'result': 'OK', 'inspected_at': '2026-08-13T02:30:18Z', 'archive_path': None}, {},
    )
    assert enqueue_aim_event(db, event) is True
    assert dispatch_aim_event(db, event.event_id, lambda _: (_ for _ in ()).throw(RuntimeError('offline'))) is False
    assert tuple(db.execute('SELECT status,attempts FROM iot_aim_event_outbox').fetchone()) == ('pending', 1)
    received = []
    assert dispatch_aim_event(db, event.event_id, received.append) is True
    assert received[0].event_id == event.event_id
    assert db.execute('SELECT status FROM iot_aim_event_outbox').fetchone()[0] == 'dispatched'
