"""Authenticated management and development ingestion API for device events."""

import json

from flask import Blueprint, jsonify, request

from device_platform.contracts import ContractError, DeviceEvent
from services.device_event_ingest import ingest_device_event
from utils.database import get_db
from utils.helpers import login_required


device_platform_bp = Blueprint('device_platform', __name__)


def _result_data(result):
    return {
        'accepted': result.accepted,
        'duplicate': result.duplicate,
        'gap_expected': result.gap_expected,
        'gap_actual': result.gap_actual,
        'sequence_conflict': result.sequence_conflict,
    }


@device_platform_bp.route('/api/device-platform/events', methods=['POST'])
@login_required
def ingest_event():
    try:
        event = DeviceEvent.from_dict(request.get_json(silent=True) or {})
    except ContractError as exc:
        return jsonify({'code': 400, 'message': str(exc)}), 400
    result = ingest_device_event(get_db(), event)
    status = 200 if result.duplicate else 201
    return jsonify({'code': 0, 'data': _result_data(result)}), status


def _pagination():
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
    except (TypeError, ValueError):
        raise ContractError('page and page_size must be integers')
    if page < 1 or not 1 <= page_size <= 500:
        raise ContractError('page must be positive and page_size must be between 1 and 500')
    return page, page_size


@device_platform_bp.route('/api/device-platform/events', methods=['GET'])
@login_required
def list_events():
    try:
        page, page_size = _pagination()
    except ContractError as exc:
        return jsonify({'code': 400, 'message': str(exc)}), 400
    where = []
    params = []
    for column in ('factory_code', 'gateway_code', 'device_code', 'event_type', 'processing_status'):
        value = str(request.args.get(column, '')).strip()
        if value:
            where.append(f'{column}=?')
            params.append(value)
    clause = (' WHERE ' + ' AND '.join(where)) if where else ''
    db = get_db()
    total = db.execute(
        f'SELECT COUNT(*) FROM iot_device_event{clause}', params
    ).fetchone()[0]
    rows = db.execute(
        f'''SELECT * FROM iot_device_event{clause}
            ORDER BY id DESC LIMIT ? OFFSET ?''',
        params + [page_size, (page - 1) * page_size],
    ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item['payload'] = json.loads(item.pop('payload_json'))
        items.append(item)
    return jsonify({'code': 0, 'data': {
        'list': items, 'total': int(total), 'page': page, 'page_size': page_size,
    }})


@device_platform_bp.route('/api/device-platform/health', methods=['GET'])
@login_required
def health():
    db = get_db()
    row = db.execute(
        '''SELECT COUNT(*) AS total,
                  SUM(CASE WHEN processing_status='pending' THEN 1 ELSE 0 END) AS pending,
                  COUNT(DISTINCT factory_code || ':' || device_code) AS devices
           FROM iot_device_event'''
    ).fetchone()
    gaps = db.execute(
        "SELECT COUNT(*) FROM iot_device_sequence_gap WHERE status='open'"
    ).fetchone()[0]
    return jsonify({'code': 0, 'data': {
        'total_events': int(row['total'] or 0),
        'pending_events': int(row['pending'] or 0),
        'open_sequence_gaps': int(gaps or 0),
        'devices_seen': int(row['devices'] or 0),
    }})
