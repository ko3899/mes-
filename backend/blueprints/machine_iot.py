"""AIM机台通讯配置、监控和检测报告API。"""
import os
import sqlite3
import ipaddress
from pathlib import Path
import hashlib
import uuid

from flask import Blueprint, jsonify, request, session

from services.machine_access import (
    import_inspection_report,
    record_failed_inspection,
    retry_inspection_report,
)
from utils.database import get_db
from utils.helpers import admin_required, login_required
from utils.db_errors import INTEGRITY_ERRORS


machine_iot_bp = Blueprint('machine_iot', __name__)


def _public_endpoint(row):
    data = dict(row)
    data.pop('shared_secret', None)
    data['shared_secret_configured'] = bool(row['shared_secret'])
    data['csv_directory_exists'] = bool(data.get('csv_input_dir') and Path(data['csv_input_dir']).is_dir())
    if session.get('username') != 'admin':
        data.pop('csv_input_dir', None)
    return data


def _validate_remote_allowlist(value):
    for item in str(value or '').split(','):
        item = item.strip()
        if not item:
            continue
        try:
            ipaddress.ip_network(item, strict=False)
        except ValueError:
            raise ValueError('机台来源IP白名单必须是IP、CIDR或逗号分隔列表')


def _page():
    try:
        page = max(1, int(request.args.get('page', 1)))
        size = min(200, max(1, int(request.args.get('size', 20))))
    except (TypeError, ValueError):
        page, size = 1, 20
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
    return jsonify({'code': 0, 'data': {'list': [_public_endpoint(row) for row in rows], 'total': len(rows)}})


@machine_iot_bp.route('/api/iot/machine/endpoints/save', methods=['POST'])
@admin_required
def endpoint_save():
    data = request.get_json(silent=True) or {}
    try:
        equipment_id = int(data.get('equipment_id'))
        process_id = int(data.get('process_id'))
        protocol = int(data.get('protocol_version', 1))
        transport_mode = str(data.get('transport_mode', 'server')).strip().lower()
        port = int(data.get('listen_port'))
        reader_port = int(data.get('reader_port', 2002))
        reader_frame_idle_ms = int(data.get('reader_frame_idle_ms', 80))
        timeout_ms = int(data.get('timeout_ms', 1000))
        heartbeat = int(data.get('heartbeat_seconds', 30))
        csv_stable_seconds = int(data.get('csv_stable_seconds', 2))
        enabled = 1 if int(data.get('enabled', 1)) else 0
        endpoint_id = int(data.get('id') or 0)
    except (TypeError, ValueError):
        return jsonify({'code': 400, 'message': '设备、工序、端口和数值参数不合法'}), 400
    bind_ip = str(data.get('bind_ip', '')).strip()
    reader_ip = str(data.get('reader_ip', '')).strip() or None
    allowed_remote_ip = str(data.get('allowed_remote_ip', '')).strip() or None
    station = str(data.get('station_code', '')).strip()
    cavity = str(data.get('cavity_code', '1')).strip()
    encoding = str(data.get('encoding', 'utf-8')).lower().strip()
    lifecycle_id = str(data.get('lifecycle_id') or 'legacy').strip()
    try:
        default_nonce = 1 if (protocol == 2 and not endpoint_id) else 0
        require_request_nonce = 1 if int(data.get('require_request_nonce', default_nonce)) else 0
    except (TypeError, ValueError):
        return jsonify({'code': 400, 'message': 'V2防重放配置不合法'}), 400
    raw_csv_dir = str(data.get('csv_input_dir', '')).strip()
    if raw_csv_dir and not Path(raw_csv_dir).is_absolute():
        return jsonify({'code': 400, 'message': 'CSV输入目录必须是绝对路径'}), 400
    csv_input_dir = str(Path(raw_csv_dir).resolve()) if raw_csv_dir else None
    if protocol not in (1, 2) or transport_mode not in ('server', 'reader_client') or not (1 <= port <= 65535):
        return jsonify({'code': 400, 'message': '协议版本或监听端口不合法'}), 400
    if not bind_ip or not station or not cavity or not lifecycle_id or encoding not in ('utf-8', 'gbk'):
        return jsonify({'code': 400, 'message': 'IP、工站、穴位或编码不合法'}), 400
    if not (1 <= reader_port <= 65535) or not (20 <= reader_frame_idle_ms <= 2000):
        return jsonify({'code': 400, 'message': '读码器端口或无结束符切帧参数不合法'}), 400
    if transport_mode == 'reader_client':
        if protocol != 1:
            return jsonify({'code': 400, 'message': '海康直连读码器模式使用V1纯条码协议'}), 400
        if not reader_ip:
            return jsonify({'code': 400, 'message': '直连读码器模式必须配置读码器IP'}), 400
        try:
            ipaddress.ip_address(reader_ip)
        except ValueError:
            return jsonify({'code': 400, 'message': '读码器IP格式不合法'}), 400
    if not (500 <= timeout_ms <= 5000) or not (5 <= heartbeat <= 3600):
        return jsonify({'code': 400, 'message': '超时或心跳参数超出范围'}), 400
    if not (1 <= csv_stable_seconds <= 60):
        return jsonify({'code': 400, 'message': 'CSV稳定秒数必须在1到60之间'}), 400
    try:
        ipaddress.ip_address(bind_ip)
        if allowed_remote_ip:
            _validate_remote_allowlist(allowed_remote_ip)
    except ValueError:
        return jsonify({'code': 400, 'message': '监听IP或机台来源IP格式不合法'}), 400
    if transport_mode == 'server' and protocol == 1 and enabled and not allowed_remote_ip:
        return jsonify({'code': 400, 'message': 'V1端点必须配置机台来源IP白名单'}), 400
    db = get_db()
    if endpoint_id and not db.execute(
        'SELECT 1 FROM iot_machine_endpoint WHERE id=?', (endpoint_id,)
    ).fetchone():
        return jsonify({'code': 404, 'message': '通讯端点不存在'}), 404
    equipment = db.execute('SELECT code FROM eqp_ledger WHERE id=?', (equipment_id,)).fetchone()
    process = db.execute('SELECT id FROM base_process WHERE id=?', (process_id,)).fetchone()
    if not equipment or not process:
        return jsonify({'code': 400, 'message': '设备或工序不存在'}), 400
    conflict = db.execute(
        '''SELECT id FROM iot_machine_endpoint WHERE listen_port=?
           AND (bind_ip=? OR bind_ip='0.0.0.0' OR ?='0.0.0.0') AND id<>?''',
        (port, bind_ip, bind_ip, endpoint_id)
    ).fetchone()
    if conflict:
        return jsonify({'code': 409, 'message': '该监听IP和端口已被其他通讯端点占用'}), 409
    if csv_input_dir and enabled:
        directory_conflict = db.execute(
            '''SELECT id FROM iot_machine_endpoint
               WHERE enabled=1 AND csv_input_dir=? COLLATE NOCASE AND id<>?''',
            (csv_input_dir, endpoint_id),
        ).fetchone()
        if directory_conflict:
            return jsonify({'code': 409, 'message': '该CSV输入目录已绑定其他启用端点'}), 409
    laser_template = str(data.get('laser_template') or '').strip() or None
    inspection_template = str(data.get('inspection_template') or '').strip() or None
    shared_secret = data.get('shared_secret')
    if endpoint_id and not shared_secret:
        current = db.execute(
            'SELECT shared_secret FROM iot_machine_endpoint WHERE id=?',
            (endpoint_id,),
        ).fetchone()
        if not current:
            return jsonify({'code': 404, 'message': '通讯端点不存在'}), 404
        shared_secret = current['shared_secret']
    if protocol == 2 and enabled and not shared_secret:
        return jsonify({'code': 400, 'message': 'V2端点必须配置共享密钥'}), 400
    if protocol == 2 and enabled and (not laser_template or not inspection_template):
        return jsonify({'code': 400, 'message': 'V2端点必须配置加工模板和检测模板'}), 400
    values = (equipment_id, protocol, transport_mode, bind_ip, allowed_remote_ip, port,
              reader_ip, reader_port, reader_frame_idle_ms, station, process_id, cavity,
              encoding, timeout_ms, heartbeat, laser_template,
              inspection_template, shared_secret, csv_input_dir,
               csv_stable_seconds, enabled, lifecycle_id, require_request_nonce)
    try:
        if endpoint_id:
            db.execute(
                '''UPDATE iot_machine_endpoint SET equipment_id=?,protocol_version=?,transport_mode=?,
                   bind_ip=?,allowed_remote_ip=?,listen_port=?,reader_ip=?,reader_port=?,reader_frame_idle_ms=?,
                   station_code=?,process_id=?,cavity_code=?,
                   encoding=?,timeout_ms=?,heartbeat_seconds=?,laser_template=?,
                    inspection_template=?,shared_secret=?,csv_input_dir=?,csv_stable_seconds=?,
                    enabled=?,lifecycle_id=?,require_request_nonce=?,updated_at=CURRENT_TIMESTAMP
                   WHERE id=?''', values + (endpoint_id,))
        else:
            endpoint_id = db.execute(
                '''INSERT INTO iot_machine_endpoint
                   (equipment_id,protocol_version,transport_mode,bind_ip,allowed_remote_ip,listen_port,
                    reader_ip,reader_port,reader_frame_idle_ms,station_code,process_id,cavity_code,
                    encoding,timeout_ms,heartbeat_seconds,
                    laser_template,inspection_template,shared_secret,csv_input_dir,
                    csv_stable_seconds,enabled,lifecycle_id,require_request_nonce)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', values
            ).lastrowid
        db.commit()
    except INTEGRITY_ERRORS:
        db.rollback()
        return jsonify({'code': 409, 'message': '该IP、端口、工站和穴位已被占用'}), 409
    return jsonify({'code': 0, 'data': _public_endpoint(_endpoint(db, endpoint_id))})


@machine_iot_bp.route('/api/iot/machine/endpoints/<int:endpoint_id>/toggle', methods=['POST'])
@admin_required
def endpoint_toggle(endpoint_id):
    try:
        enabled = 1 if int((request.get_json(silent=True) or {}).get('enabled', 0)) else 0
    except (TypeError, ValueError):
        return jsonify({'code': 400, 'message': '启停状态不合法'}), 400
    db = get_db()
    current = _endpoint(db, endpoint_id)
    if not current:
        return jsonify({'code': 404, 'message': '通讯端点不存在'}), 404
    if enabled and str(current['transport_mode'] or 'server') == 'server' and int(current['protocol_version']) == 1 and not current['allowed_remote_ip']:
        return jsonify({'code': 400, 'message': 'V1端点必须配置机台来源IP白名单'}), 400
    if enabled and str(current['transport_mode'] or 'server') == 'reader_client':
        if int(current['protocol_version']) != 1:
            return jsonify({'code': 400, 'message': '海康直连读码器模式使用V1纯条码协议'}), 400
        if not current['reader_ip'] or not current['reader_port']:
            return jsonify({'code': 400, 'message': '直连读码器端点必须配置读码器IP和端口'}), 400
    if enabled and int(current['protocol_version']) == 2:
        if not current['shared_secret']:
            return jsonify({'code': 400, 'message': 'V2端点必须配置共享密钥'}), 400
        if not current['laser_template'] or not current['inspection_template']:
            return jsonify({'code': 400, 'message': 'V2端点必须配置加工模板和检测模板'}), 400
    if enabled and current['csv_input_dir']:
        conflict = db.execute(
            '''SELECT id FROM iot_machine_endpoint
               WHERE enabled=1 AND csv_input_dir=? COLLATE NOCASE AND id<>?''',
            (current['csv_input_dir'], endpoint_id),
        ).fetchone()
        if conflict:
            return jsonify({'code': 409, 'message': '该CSV输入目录已绑定其他启用端点'}), 409
    db.execute('UPDATE iot_machine_endpoint SET enabled=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
               (enabled, endpoint_id))
    db.commit()
    row = _endpoint(db, endpoint_id)
    if not row:
        return jsonify({'code': 404, 'message': '通讯端点不存在'}), 404
    return jsonify({'code': 0, 'data': _public_endpoint(row)})


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
    data = _log_list(
        'iot_inspection_report',
        '''LEFT JOIN iot_machine_endpoint e ON e.id=t.endpoint_id
           LEFT JOIN eqp_ledger q ON q.id=e.equipment_id
           LEFT JOIN prod_quality_disposition d ON d.inspection_report_id=t.id''',
        't.*,q.code AS device_code,d.disposition_no,d.status AS disposition_status',
        (('result', 't.result'), ('import_status', 't.import_status'), ('sn', 't.sn')),
    )
    if session.get('username') != 'admin':
        for row in data['list']:
            row.pop('archive_path', None)
    return jsonify({'code': 0, 'data': data})


@machine_iot_bp.route('/api/iot/machine/reports/upload', methods=['POST'])
@admin_required
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
        archive_root = Path(os.environ.get(
            'MES_MACHINE_ARCHIVE_DIR', os.path.join(os.getcwd(), 'machine_archive')
        )).resolve()
        failed_dir = archive_root / '_failed' / f'endpoint_{endpoint_id}'
        failed_dir.mkdir(parents=True, exist_ok=True)
        safe_name = os.path.basename(uploaded.filename).replace('/', '_').replace('\\', '_') or 'failed.csv'
        failed_path = failed_dir / f'{hashlib.sha256(payload).hexdigest()[:12]}_{uuid.uuid4().hex[:8]}_{safe_name}'
        failed_path.write_bytes(payload)
        try:
            record_failed_inspection(
                db, endpoint, payload, uploaded.filename, failed_path, exc,
            )
        except Exception:
            try:
                failed_path.unlink()
            except OSError:
                pass
            raise
        return jsonify({'code': 400, 'message': str(exc)}), 400
    return jsonify({'code': 0, 'data': result})


@machine_iot_bp.route('/api/iot/machine/reports/<int:report_id>/retry', methods=['POST'])
@admin_required
def report_retry(report_id):
    db = get_db()
    report = db.execute(
        'SELECT endpoint_id FROM iot_inspection_report WHERE id=?', (report_id,)
    ).fetchone()
    if not report:
        return jsonify({'code': 404, 'message': '失败报告不存在'}), 404
    endpoint = _endpoint(db, report['endpoint_id'])
    try:
        result = retry_inspection_report(
            db, endpoint, report_id,
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
    listening = db.execute(
        "SELECT COUNT(*) FROM iot_machine_endpoint WHERE enabled=1 AND listener_status='listening'"
    ).fetchone()[0]
    listener_errors = db.execute(
        "SELECT COUNT(*) FROM iot_machine_endpoint WHERE enabled=1 AND listener_status='error'"
    ).fetchone()[0]
    online = db.execute(
        '''SELECT COUNT(*) FROM iot_machine_session s
           JOIN iot_machine_endpoint e ON e.id=s.endpoint_id
           WHERE s.status='online' AND e.listener_status='listening'
             AND s.last_heartbeat_at >= datetime('now','-' || (e.heartbeat_seconds * 2) || ' seconds')'''
    ).fetchone()[0]
    pending = db.execute("SELECT COUNT(*) FROM iot_machine_request WHERE decision='L1' AND report_status='pending'").fetchone()[0]
    failures = db.execute("SELECT COUNT(*) FROM iot_inspection_report WHERE import_status='failed'").fetchone()[0]
    directories = db.execute(
        "SELECT csv_input_dir,csv_last_scan_at,csv_last_error FROM iot_machine_endpoint WHERE enabled=1 AND TRIM(COALESCE(csv_input_dir,''))<>''"
    ).fetchall()
    missing = sum(1 for row in directories if not Path(row['csv_input_dir']).is_dir())
    unstable = 0
    for row in directories:
        directory = Path(row['csv_input_dir'])
        if directory.is_dir():
            try:
                unstable += sum(
                    1 for item in directory.iterdir()
                    if item.is_file() and not item.name.startswith('.') and item.suffix.lower() == '.csv'
                )
            except OSError:
                missing += 1
    last_collection = max(
        (row['csv_last_scan_at'] for row in directories if row['csv_last_scan_at']), default=None
    )
    collector = db.execute(
        '''SELECT *,CASE WHEN heartbeat_at >= datetime('now','-30 seconds')
                  THEN 1 ELSE 0 END AS heartbeat_fresh
           FROM iot_machine_runtime WHERE component='csv_collector' '''
    ).fetchone()
    collector_status = (
        collector['status'] if collector and collector['heartbeat_fresh'] else 'stopped'
    )
    return jsonify({'code': 0, 'data': {'enabled_endpoints': enabled, 'online_sessions': online,
                                        'listening_endpoints': listening,
                                        'listener_errors': listener_errors,
                                        'pending_reports': pending, 'failed_reports': failures,
                                        'collector_directories': len(directories),
                                        'missing_directories': missing,
                                        'unstable_files': unstable,
                                        'collector_status': collector_status,
                                        'last_collection_at': last_collection}})
