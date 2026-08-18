"""Authenticated management and development ingestion API for device events."""

import json

from flask import Blueprint, jsonify, request

from device_platform.contracts import ContractError, DeviceEvent, DeviceCommand
from services.device_event_ingest import ingest_device_event
from services.device_event_processor import process_pending_events, apply_standard_event
from services.device_commands import (
    create_command_tables, enqueue_command, claim_commands, acknowledge_command,
)
from services.gateway_auth import authenticate_gateway, GatewayAuthError
from utils.database import get_db
from utils.helpers import admin_required


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
@admin_required
def ingest_event():
    try:
        event = DeviceEvent.from_dict(request.get_json(silent=True) or {})
    except ContractError as exc:
        return jsonify({'code': 400, 'message': str(exc)}), 400
    result = ingest_device_event(get_db(), event)
    if not result.accepted:
        return jsonify({'code': 409, 'data': _result_data(result),
                        'message': '事件序列或事件内容冲突，已隔离'}), 409
    status = 200 if result.duplicate else 201
    return jsonify({'code': 0, 'data': _result_data(result)}), status


@device_platform_bp.route('/api/device-platform/gateway-events', methods=['POST'])
def ingest_gateway_event():
    body = request.get_data(cache=True)
    try:
        credential = authenticate_gateway(
            get_db(), request.headers.get('X-Gateway-Id', ''),
            request.headers.get('X-Gateway-Time', ''),
            request.headers.get('X-Gateway-Nonce', ''),
            request.headers.get('X-Gateway-Signature', ''), body,
        )
        event = DeviceEvent.from_dict(request.get_json(silent=True) or {})
        expected = (credential['customer_code'], credential['factory_code'],
                    credential['gateway_code'])
        actual = (event.customer_code, event.factory_code, event.gateway_code)
        if actual != expected:
            raise GatewayAuthError('event customer, factory or gateway identity mismatch')
    except (GatewayAuthError, ContractError) as exc:
        return jsonify({'code': 401, 'message': str(exc)}), 401
    result = ingest_device_event(get_db(), event)
    if not result.accepted:
        return jsonify({'code': 409, 'data': _result_data(result),
                        'message': '事件序列或事件内容冲突，已隔离'}), 409
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
@admin_required
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
@admin_required
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


@device_platform_bp.route('/api/device-platform/communications-health', methods=['GET'])
@admin_required
def communications_health():
    """Operational view for operators; keeps the legacy health contract stable."""
    db = get_db()

    def table_exists(name):
        return db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone() is not None

    def count(table, where='1=1'):
        if not table_exists(table):
            return 0
        return int(db.execute(f'SELECT COUNT(*) FROM {table} WHERE {where}').fetchone()[0] or 0)

    return jsonify({'code': 0, 'data': {
        'events': {
            'pending': count('iot_device_event', "processing_status='pending'"),
            'failed': count('iot_device_event', "processing_status='failed'"),
            'processed': count('iot_device_event', "processing_status='processed'"),
            'conflicts': count('iot_device_event_conflict'),
        },
        'aim_outbox': {
            'pending': count('iot_aim_event_outbox', "status='pending'"),
            'failed_attempts': int(db.execute(
                'SELECT COALESCE(SUM(attempts),0) FROM iot_aim_event_outbox'
            ).fetchone()[0] or 0) if table_exists('iot_aim_event_outbox') else 0,
        },
        'commands': {
            'queued': count('iot_device_command', "status='queued'"),
            'leased': count('iot_device_command', "status='leased'"),
            'failed': count('iot_device_command', "status='failed'"),
        },
        'machine_endpoints': {
            'listening': count('iot_machine_endpoint', "listener_status='listening'"),
            'error': count('iot_machine_endpoint', "listener_status='error'"),
            'enabled': count('iot_machine_endpoint', 'enabled=1'),
        },
    }})


@device_platform_bp.route('/api/device-platform/events/process', methods=['POST'])
@admin_required
def process_events():
    result = process_pending_events(get_db(), lambda event: apply_standard_event(get_db(), event))
    return jsonify({'code': 0, 'data': result})


@device_platform_bp.route('/api/device-platform/commands', methods=['POST'])
@admin_required
def create_command():
    try:
        command = DeviceCommand.from_dict(request.get_json(silent=True) or {})
        stored = enqueue_command(get_db(), command)
    except ContractError as exc:
        return jsonify({'code': 400, 'message': str(exc)}), 400
    return jsonify({'code': 0, 'data': stored.to_dict()}), 201


@device_platform_bp.route('/api/device-platform/gateway-commands/claim', methods=['POST'])
def gateway_claim_commands():
    body = request.get_data(cache=True)
    try:
        credential = authenticate_gateway(
            get_db(), request.headers.get('X-Gateway-Id', ''),
            request.headers.get('X-Gateway-Time', ''), request.headers.get('X-Gateway-Nonce', ''),
            request.headers.get('X-Gateway-Signature', ''), body,
        )
        data = request.get_json(silent=True) or {}
        if str(data.get('gateway_code') or '') != credential['gateway_code']:
            raise GatewayAuthError('gateway identity mismatch')
        worker_id = str(data.get('worker_id') or '').strip()
        if not worker_id:
            raise GatewayAuthError('worker_id is required')
        claims = claim_commands(get_db(), credential['gateway_code'], worker_id,
                                data.get('device_code'), int(data.get('limit') or 20))
    except (GatewayAuthError, ContractError, ValueError) as exc:
        return jsonify({'code': 401, 'message': str(exc)}), 401
    return jsonify({'code': 0, 'data': [
        {'command': claim.command.to_dict(), 'lease_token': claim.lease_token}
        for claim in claims
    ]})


@device_platform_bp.route('/api/device-platform/gateway-commands/<command_id>/ack', methods=['POST'])
def gateway_ack_command(command_id):
    body = request.get_data(cache=True)
    try:
        credential = authenticate_gateway(
            get_db(), request.headers.get('X-Gateway-Id', ''),
            request.headers.get('X-Gateway-Time', ''), request.headers.get('X-Gateway-Nonce', ''),
            request.headers.get('X-Gateway-Signature', ''), body,
        )
        data = request.get_json(silent=True) or {}
        row = get_db().execute(
            'SELECT gateway_code FROM iot_device_command WHERE command_id=?', (command_id,)
        ).fetchone()
        if not row or row['gateway_code'] != credential['gateway_code']:
            raise GatewayAuthError('command is outside gateway scope')
        if not acknowledge_command(get_db(), command_id, str(data.get('worker_id') or ''),
                                   str(data.get('status') or ''),
                                   str(data.get('lease_token') or ''), data.get('error')):
            return jsonify({'code': 409, 'message': '命令租约无效或已处理'}), 409
    except (GatewayAuthError, ContractError, ValueError) as exc:
        return jsonify({'code': 401, 'message': str(exc)}), 401
    return jsonify({'code': 0, 'message': 'command acknowledged'})
