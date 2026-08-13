from datetime import datetime, timedelta, timezone
import os
import sys

import pytest


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from device_platform.contracts import (  # noqa: E402
    ContractError,
    DeviceCommand,
    DeviceEvent,
)


def valid_event(**overrides):
    data = {
        'schema_version': '1.0',
        'event_id': 'EV-001',
        'customer_code': 'CUSTOMER-A',
        'factory_code': 'F01',
        'gateway_code': 'GW-F01-A',
        'device_code': 'AIM-028',
        'event_type': 'quality.completed',
        'occurred_at': '2026-08-13T10:30:18.235+08:00',
        'received_at': None,
        'sequence': 1,
        'correlation_id': 'REQ-001',
        'payload': {'sn': 'SN001', 'result': 'OK'},
        'raw_reference': 'archive/SN001.csv',
    }
    data.update(overrides)
    return data


def valid_command(**overrides):
    data = {
        'schema_version': '1.0',
        'command_id': 'CMD-001',
        'factory_code': 'F01',
        'gateway_code': 'GW-F01-A',
        'device_code': 'AIM-028',
        'command_type': 'production.authorize',
        'created_at': '2026-08-13T10:30:18+08:00',
        'expires_at': '2026-08-13T10:35:18+08:00',
        'idempotency_key': 'AUTH-SN001-STEP1',
        'config_version': 'cfg-7',
        'payload': {'sn': 'SN001', 'decision': 'L1'},
    }
    data.update(overrides)
    return data


def test_event_round_trip_is_canonical_and_does_not_alias_payload():
    source = valid_event()
    event = DeviceEvent.from_dict(source)
    source['payload']['result'] = 'NG'

    assert event.to_dict() == valid_event()
    exported = event.to_dict()
    exported['payload']['result'] = 'NG'
    assert event.payload['result'] == 'OK'


@pytest.mark.parametrize('field,value', [
    ('schema_version', '2.0'),
    ('event_id', ''),
    ('factory_code', ''),
    ('device_code', ''),
    ('event_type', 'vendor.unknown'),
    ('sequence', 0),
    ('sequence', True),
    ('payload', []),
    ('occurred_at', '2026-08-13 10:30:18'),
])
def test_event_rejects_invalid_required_values(field, value):
    with pytest.raises(ContractError):
        DeviceEvent.from_dict(valid_event(**{field: value}))


def test_event_accepts_zulu_time_and_rejects_unknown_fields():
    event = DeviceEvent.from_dict(valid_event(occurred_at='2026-08-13T02:30:18Z'))
    assert event.occurred_at == '2026-08-13T02:30:18Z'
    with pytest.raises(ContractError):
        DeviceEvent.from_dict({**valid_event(), 'secret': 'must-not-pass'})


def test_command_round_trip_and_expiry():
    command = DeviceCommand.from_dict(valid_command())
    assert command.to_dict() == valid_command()
    assert command.is_expired(datetime(2026, 8, 13, 2, 36, tzinfo=timezone.utc)) is True
    assert command.is_expired(datetime(2026, 8, 13, 2, 34, tzinfo=timezone.utc)) is False


def test_command_rejects_expiry_before_creation_and_naive_now():
    with pytest.raises(ContractError):
        DeviceCommand.from_dict(valid_command(expires_at='2026-08-13T10:20:18+08:00'))
    command = DeviceCommand.from_dict(valid_command())
    with pytest.raises(ContractError):
        command.is_expired(datetime.now())


def test_contract_values_are_immutable():
    event = DeviceEvent.from_dict(valid_event())
    command = DeviceCommand.from_dict(valid_command())
    with pytest.raises((AttributeError, TypeError)):
        event.event_id = 'changed'
    with pytest.raises((AttributeError, TypeError)):
        command.command_id = 'changed'
