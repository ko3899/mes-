"""Compatibility mapping from legacy AIM inspection rows to standard events."""

from datetime import datetime, timezone, timedelta

from device_platform.contracts import DeviceEvent


CHINA_STANDARD_TIME = timezone(timedelta(hours=8))


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


def aim_report_event(endpoint, request_row, report_row, measurements):
    """Build the deterministic standard event representing one AIM report."""
    endpoint_id = int(_value(endpoint, 'id'))
    report_id = int(_value(report_row, 'id'))
    result = str(_value(report_row, 'result', '')).upper()
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
        'sequence': report_id,
        'correlation_id': str(_value(request_row, 'request_no', _value(request_row, 'id'))),
        'payload': {
            'sn': str(_value(request_row, 'sn', '')),
            'workorder_id': _value(request_row, 'workorder_id'),
            'station_code': str(_value(endpoint, 'station_code', '')),
            'result': result,
            'measurements': dict(measurements or {}),
        },
        'raw_reference': _value(report_row, 'archive_path'),
    })
