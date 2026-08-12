"""AIM机台通讯配置、监控和检测报告API。"""
import os
import sqlite3

from flask import Blueprint, jsonify, request

from services.machine_access import import_inspection_report
from utils.database import get_db
from utils.helpers import login_required


machine_iot_bp = Blueprint('machine_iot', __name__)


def _page():
    page = max(1, int(request.args.get('page', 1)))
    size = min(200, max(1, int(request.args.get('size', 20))))
    return page, size


def _endpoint(db, endpoint_id):
    return db.execute(
        '''SELECT e.*,q.code AS device_code,q.status AS equipment_status,
                  q.equipment_name,p.process_name
           FROM iot_machine_endpoint e
           JOIN eqp_ledger q ON q.id=e.equipment_id
           JOIN base_process p ON p.id=e.process_id WHERE e.id=?''',
        (endpoint_id,),
    ).fetchone()


@machine_iot_bp.route('/api/iot/machine/endpoints')
@login_required
def endpoint_list():
    db = get_db()
    rows = db.execute(
        '''SELECT e.*,q.code AS device_code,q.status AS equipment_status,
                  q.equipment_name,p.process_name
           FROM iot_machine_endpoint e
           JOIN eqp_ledger q ON q.id=e.equipment_id
           JOIN base_process p ON p.id=e.process_id ORDER BY e.id DESC'''
    ).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(row) for row in rows], 'total': len(rows)}})


@machine_iot_bp.route('/api/iot/machine/endpoints/save', methods=['POST'])
@login_required
def endpoint_save():
    data = request.get_json(silent=True) or {}
    try:
        equipment_id = int(data.get('equipment_id'))
        process_id = int(data.get('process_id'))
        protocol = int(data.get('protocol_version', 1))
        port = int(data.get('listen_port'))
        timeout_ms = int(data.get('timeout_ms', 1000))
        heartbeat = int(data.get('heartbeat_seconds', 30))
        enabled = 1 if int(data.get('enabled', 1)) else 0
    except (TypeError, ValueError):
        return jsonify({'code': 400, 'message': '设备、工序、端口和数值参数不合法'}), 400
    bind_ip = str(data.get('bind_ip', '')).strip()
    station = str(data.get('station_code', '')).strip()
    cavity = str(data.get('cavity_code', '1')).strip()
    encoding = str(data.get('encoding', 'utf-8')).lower().strip()
    if protocol not in (1, 2) or not (1 <= port <= 65535):
        return jsonify({'code': 400, 'message': '协议版本或监听端口不合法'}), 400
    if not bind_ip or not station or not cavity or encoding not in ('utf-8', 'gbk'):
        return jsonify({'code': 400, 'message': 'IP、工站、穴位或编码不合法'}), 400
    if not (500 <= timeout_ms <= 5000) or not (5 <= heartbeat <= 3600):
        return jsonify({'code': 400, 'message': '超时或心跳参数超出范围'}), 400
    db = get_db()
    equipment = db.execute('SELECT code FROM eqp_ledger WHERE id=?', (equipment_id,)).fetchone()
    process = db.execute('SELECT id FROM base_process WHERE id=?', (process_id,)).fetchone()
    if not equipment or not process:
        return jsonify({'code': 400, 'message': '设备或工序不存在'}), 400
    values = (equipment_id, protocol, bind_ip, port, station, process_id, cavity,
              encoding, timeout_ms, heartbeat, data.get('laser_template'),
              data.get('inspection_template'), data.get('shared_secret'), enabled)
    try:
        if data.get('id'):
            endpoint_id = int(data['id'])
            db.execute(
                '''UPDATE iot_machine_endpoint SET equipment_id=?,protocol_version=?,
                   bind_ip=?,listen_port=?,station_code=?,process_id=?,cavity_code=?,
                   encoding=?,timeout_ms=?,heartbeat_seconds=?,laser_template=?,
                   inspection_template=?,shared_secret=?,enabled=?,updated_at=CURRENT_TIMESTAMP
                   WHERE id=?''', values + (endpoint_id,))
        else:
            endpoint_id = db.execute(
                '''INSERT INTO iot_machine_endpoint
                   (equipment_id,protocol_version,bind_ip,listen_port,station_code,
                    process_id,cavity_code,encoding,timeout_ms,heartbeat_seconds,
                    laser_template,inspection_template,shared_secret,enabled)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', values
            ).lastrowid
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify({'code': 409, 'message': '该IP、端口、工站和穴位已被占用'}), 409
    return jsonify({'code': 0, 'data': dict(_endpoint(db, endpoint_id))})


@machine_iot_bp.route('/api/iot/machine/endpoints/<int:endpoint_id>/toggle', methods=['POST'])
@login_required
def endpoint_toggle(endpoint_id):
    enabled = 1 if int((request.get_json(silent=True) or {}).get('enabled', 0)) else 0
    db = get_db()
    db.execute('UPDATE iot_machine_endpoint SET enabled=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
               (enabled, endpoint_id))
    db.commit()
    row = _endpoint(db, endpoint_id)
    if not row:
        return jsonify({'code': 404, 'message': '通讯端点不存在'}), 404
    return jsonify({'code': 0, 'data': dict(row)})


def _log_list(table, joins='', fields='t.*', filters=()):
    db = get_db()
    page, size = _page()
    where, params = ['1=1'], []
    for arg_name, column in filters:
        value = request.args.get(arg_name)
        if value:
            where.append(f'{column}=?')
            params.append(value)
    clause = ' AND '.join(where)
    total = db.execute(f'SELECT COUNT(*) FROM {table} t {joins} WHERE {clause}', params).fetchone()[0]
    rows = db.execute(
        f'''SELECT {fields} FROM {table} t {joins} WHERE {clause}
            ORDER BY t.id DESC LIMIT ? OFFSET ?''', params + [size, (page - 1) * size]
    ).fetchall()
    return {'list': [dict(row) for row in rows], 'total': total, 'page': page, 'size': size}


@machine_iot_bp.route('/api/iot/machine/sessions')
@login_required
def session_list():
    return jsonify({'code': 0, 'data': _log_list(
        'iot_machine_session',
        'LEFT JOIN iot_machine_endpoint e ON e.id=t.endpoint_id LEFT JOIN eqp_ledger q ON q.id=e.equipment_id',
        't.*,q.code AS device_code,e.station_code,e.cavity_code',
        (('status', 't.status'),),
    )})


@machine_iot_bp.route('/api/iot/machine/requests')
@login_required
def request_list():
    return jsonify({'code': 0, 'data': _log_list(
        'iot_machine_request',
        'LEFT JOIN iot_machine_endpoint e ON e.id=t.endpoint_id LEFT JOIN eqp_ledger q ON q.id=e.equipment_id',
        't.*,q.code AS device_code',
        (('decision', 't.decision'), ('reason_code', 't.reason_code'), ('sn', 't.sn')),
    )})


@machine_iot_bp.route('/api/iot/machine/reports')
@login_required
def report_list():
    return jsonify({'code': 0, 'data': _log_list(
        'iot_inspection_report',
        'LEFT JOIN iot_machine_endpoint e ON e.id=t.endpoint_id LEFT JOIN eqp_ledger q ON q.id=e.equipment_id',
        't.*,q.code AS device_code',
        (('result', 't.result'), ('import_status', 't.import_status'), ('sn', 't.sn')),
    )})


@machine_iot_bp.route('/api/iot/machine/reports/upload', methods=['POST'])
@login_required
def report_upload():
    try:
        endpoint_id = int(request.form.get('endpoint_id'))
    except (TypeError, ValueError):
        return jsonify({'code': 400, 'message': 'endpoint_id不合法'}), 400
    uploaded = request.files.get('file')
    if not uploaded or not uploaded.filename:
        return jsonify({'code': 400, 'message': '请选择CSV文件'}), 400
    payload = uploaded.read(5 * 1024 * 1024 + 1)
    if len(payload) > 5 * 1024 * 1024:
        return jsonify({'code': 400, 'message': 'CSV文件不得超过5MB'}), 400
    db = get_db()
    endpoint = _endpoint(db, endpoint_id)
    if not endpoint:
        return jsonify({'code': 404, 'message': '通讯端点不存在'}), 404
    try:
        result = import_inspection_report(
            db, endpoint, payload, uploaded.filename,
            os.environ.get('MES_MACHINE_ARCHIVE_DIR', os.path.join(os.getcwd(), 'machine_archive')),
        )
    except ValueError as exc:
        return jsonify({'code': 400, 'message': str(exc)}), 400
    return jsonify({'code': 0, 'data': result})


@machine_iot_bp.route('/api/iot/machine/health')
@login_required
def health():
    db = get_db()
    enabled = db.execute('SELECT COUNT(*) FROM iot_machine_endpoint WHERE enabled=1').fetchone()[0]
    online = db.execute("SELECT COUNT(*) FROM iot_machine_session WHERE status='online'").fetchone()[0]
    pending = db.execute("SELECT COUNT(*) FROM iot_machine_request WHERE decision='L1' AND report_status='pending'").fetchone()[0]
    failures = db.execute("SELECT COUNT(*) FROM iot_inspection_report WHERE import_status='failed'").fetchone()[0]
    return jsonify({'code': 0, 'data': {'enabled_endpoints': enabled, 'online_sessions': online,
                                        'pending_reports': pending, 'failed_reports': failures}})

