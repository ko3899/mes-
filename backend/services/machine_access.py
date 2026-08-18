"""AIM机台生产准入与检测报告业务。"""
from datetime import datetime
import csv
import hashlib
import io
import os
from pathlib import Path
import time
import uuid
import logging

from services.machine_protocol import AccessDecision
from services.aim_event_bridge import (
    aim_report_event, enqueue_aim_event, dispatch_aim_event, next_aim_sequence,
)
from services.quality_disposition import (
    QUALITY_HOLD,
    QUALITY_REWORK,
    QUALITY_SCRAPPED,
    access_context,
    create_ng_disposition,
)


logger = logging.getLogger(__name__)


ALLOWED_WORKORDER_STATUSES = {1, 2}
REQUIRED_CSV_HEADERS = ('2D Barcode', 'Date', 'Time', 'OK(1)/NG(0)')


def _default_event_sink(db):
    """Select the safe local sink for legacy AIM reports."""
    if os.environ.get('MES_AIM_EVENT_MODE', 'central').strip().lower() == 'edge':
        from edge_gateway.event_store import EdgeEventStore
        edge_db = os.environ.get('MES_EDGE_DB')
        if not edge_db:
            raise RuntimeError('MES_EDGE_DB is required when MES_AIM_EVENT_MODE=edge')
        store = EdgeEventStore(edge_db)
        return store.append
    if db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='iot_device_event'"
    ).fetchone():
        from services.device_event_ingest import ingest_device_event
        return lambda item: ingest_device_event(db, item)
    return None


def _value(row, key, default=None):
    try:
        value = row[key]
    except (KeyError, TypeError, IndexError):
        value = default
    return default if value is None else value


def _decision_from_row(row):
    return AccessDecision(
        row['decision'], row['reason_code'], row['reason_message'] or '',
        row['laser_template'] or '', row['inspection_template'] or '',
    )


def _persist_decision(db, endpoint, request, decision, context, started, session_id=None):
    dedupe_key = f"{_value(endpoint, 'id')}:{request.request_no}"
    elapsed_ms = max(0, int((time.perf_counter() - started) * 1000))
    try:
        db.execute(
            '''INSERT INTO iot_machine_request
               (endpoint_id,session_id,request_no,protocol_version,station_code,cavity_code,sn,
                workorder_id,task_id,route_step_id,decision,reason_code,reason_message,
                laser_template,inspection_template,elapsed_ms,dedupe_key,report_status)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (_value(endpoint, 'id'), session_id, request.request_no, request.protocol_version,
             request.station_code, request.cavity_code, request.sn,
             context.get('workorder_id'), context.get('task_id'), context.get('route_step_id'),
             decision.decision, decision.reason_code, decision.reason_message,
             decision.laser_template, decision.inspection_template, elapsed_ms,
             dedupe_key, 'pending' if decision.decision == 'L1' else 'not_required'),
        )
        db.commit()
    except Exception:
        db.rollback()
        existing = db.execute(
            'SELECT * FROM iot_machine_request WHERE dedupe_key=?', (dedupe_key,)
        ).fetchone()
        if not existing and decision.decision == 'L1' and context.get('route_step_id'):
            existing = db.execute(
                '''SELECT * FROM iot_machine_request
                   WHERE endpoint_id=? AND sn=? AND route_step_id=?
                     AND decision='L1' AND report_status='pending'
                   ORDER BY id DESC LIMIT 1''',
                (_value(endpoint, 'id'), request.sn, context['route_step_id']),
            ).fetchone()
        if existing:
            return _decision_from_row(existing)
        raise
    return decision


def _consume_request_nonce(db, endpoint, request):
    """Record a secure V2 nonce and reject a second use."""
    nonce = getattr(request, 'request_nonce', None)
    if not nonce or not bool(int(_value(endpoint, 'require_request_nonce', 0) or 0)):
        return True
    nonce = str(nonce)
    if len(nonce) > 256:
        return False
    db.execute('''CREATE TABLE IF NOT EXISTS iot_machine_request_nonce (
        endpoint_id INTEGER NOT NULL,
        nonce TEXT NOT NULL,
        request_no TEXT NOT NULL,
        used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(endpoint_id, nonce)
    )''')
    # Keep the replay guard bounded and make the check-and-insert one write.
    db.execute("DELETE FROM iot_machine_request_nonce WHERE used_at < datetime('now','-10 minutes')")
    inserted = db.execute(
        'INSERT OR IGNORE INTO iot_machine_request_nonce(endpoint_id,nonce,request_no) VALUES(?,?,?)',
        (_value(endpoint, 'id'), nonce, request.request_no),
    ).rowcount
    db.commit()
    return inserted == 1


def evaluate_access(db, endpoint, request, now=None, session_id=None):
    """判定SN能否在指定机台工序开始加工，并持久化幂等判定。"""
    started = time.perf_counter()
    if not _consume_request_nonce(db, endpoint, request):
        return AccessDecision.reject('REQUEST_REPLAY', 'V2请求重复使用')
    dedupe_key = f"{_value(endpoint, 'id')}:{request.request_no}"
    existing = db.execute(
        'SELECT * FROM iot_machine_request WHERE dedupe_key=?', (dedupe_key,)
    ).fetchone()
    if existing:
        return _decision_from_row(existing)
    context = {}

    def reject(code, message):
        return _persist_decision(
            db, endpoint, request, AccessDecision.reject(code, message), context, started,
            session_id=session_id,
        )

    if request.sn.casefold() == 'noread':
        return reject('NO_READ', '读码失败')
    if int(_value(endpoint, 'enabled', 0)) != 1:
        return reject('ENDPOINT_DISABLED', '通讯端点未启用')
    if int(_value(endpoint, 'equipment_status', 0)) != 1:
        return reject('EQUIPMENT_UNAVAILABLE', '设备停用或维修中')

    serial = db.execute(
        'SELECT * FROM prod_serial WHERE serial_no=?', (request.sn,)
    ).fetchone()
    if not serial:
        return reject('UNKNOWN_SN', 'SN不存在')
    if int(_value(serial, 'status', 0)) != 0:
        return reject('SN_UNAVAILABLE', 'SN处于冻结、报废或异常状态')
    workorder = db.execute(
        'SELECT * FROM prod_workorder WHERE id=?', (serial['workorder_id'],)
    ).fetchone()
    if not workorder:
        return reject('WORKORDER_NOT_FOUND', 'SN未关联有效工单')
    context['workorder_id'] = workorder['id']
    if int(workorder['status']) not in ALLOWED_WORKORDER_STATUSES:
        return reject('WORKORDER_UNAVAILABLE', '工单状态不允许生产')
    if int(workorder['product_id']) != int(serial['product_id']):
        return reject('PRODUCT_MISMATCH', 'SN产品与工单产品不一致')

    steps = db.execute(
        '''SELECT s.* FROM prod_workorder_route_step s
           JOIN prod_workorder_route_snapshot h ON h.id=s.snapshot_id
           WHERE h.workorder_id=? ORDER BY s.step_no''',
        (workorder['id'],),
    ).fetchall()
    if not steps:
        return reject('ROUTE_NOT_RELEASED', '工单没有冻结工艺路线')

    current = None
    for step in steps:
        passed = db.execute(
            '''SELECT 1 FROM prod_station_record
               WHERE sn=? AND route_step_id=? AND action='过站' AND result='PASS'
               LIMIT 1''',
            (request.sn, step['id']),
        ).fetchone()
        if not passed:
            current = step
            break
    if not current:
        return reject('ROUTE_COMPLETED', 'SN已完成全部工序')
    context['route_step_id'] = current['id']
    if int(current['process_id']) != int(_value(endpoint, 'process_id', 0)):
        return reject('WRONG_STEP', f"当前应执行工序：{current['process_name']}")

    quality = access_context(db, request.sn, current['id'])
    if quality['quality_status'] == QUALITY_HOLD:
        return reject('QUALITY_HOLD', 'SN处于质量冻结，等待质量处置')
    if quality['quality_status'] == QUALITY_SCRAPPED:
        return reject('SN_SCRAPPED', 'SN已报废')
    if quality['quality_status'] == QUALITY_REWORK:
        task = quality['rework_task']
        if not task or int(_value(task, 'status', 0)) == 0:
            return reject('REWORK_TASK_NOT_STARTED', '返工任务尚未启动')
    else:
        task_columns = {row[1] for row in db.execute('PRAGMA table_info(prod_task)')}
        normal_filter = " AND COALESCE(task_type,'normal')='normal'" if 'task_type' in task_columns else ''
        task = db.execute(
            '''SELECT * FROM prod_task
               WHERE workorder_id=? AND route_step_id=?%s ORDER BY id LIMIT 1''' % normal_filter,
            (workorder['id'], current['id']),
        ).fetchone()
    if not task:
        return reject('TASK_NOT_FOUND', '当前工序没有生产任务')
    context['task_id'] = task['id']
    if int(_value(task, 'status', 0)) != 1:
        return reject('TASK_UNAVAILABLE', '当前任务不可生产')

    laser = str(_value(endpoint, 'laser_template', ''))
    inspection = str(_value(endpoint, 'inspection_template', ''))
    if request.protocol_version == 2 and (not laser or not inspection):
        return reject('TEMPLATE_MISSING', '机台加工或检测模板未配置')
    outstanding = db.execute(
        '''SELECT * FROM iot_machine_request
           WHERE endpoint_id=? AND sn=? AND route_step_id=?
             AND decision='L1' AND report_status='pending'
           ORDER BY id DESC LIMIT 1''',
        (_value(endpoint, 'id'), request.sn, current['id']),
    ).fetchone()
    if outstanding:
        return _decision_from_row(outstanding)
    decision = AccessDecision.allow(laser, inspection, '允许加工')
    return _persist_decision(
        db, endpoint, request, decision, context, started, session_id=session_id
    )


def _decode_csv(payload):
    for encoding in ('utf-8-sig', 'utf-8', 'gbk'):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError('CSV编码无法识别')


def _parse_inspected_at(date_text, time_text):
    value = f'{date_text.strip()} {time_text.strip()}'
    for pattern in ('%Y/%m/%d %H:%M:%S', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(value, pattern).strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue
    raise ValueError('CSV日期或时间格式错误')


def _normalize_result(value):
    normalized = str(value).strip().upper()
    if normalized in ('OK', '1'):
        return 'OK'
    if normalized in ('NG', '0'):
        return 'NG'
    raise ValueError('检测结果必须是OK/NG或1/0')


def _failure_request_id(db, endpoint, file_hash, sn='UNKNOWN'):
    dedupe_key = f"{_value(endpoint, 'id')}:file-failure:{file_hash}"
    existing = db.execute(
        'SELECT id FROM iot_machine_request WHERE dedupe_key=?', (dedupe_key,)
    ).fetchone()
    if existing:
        return existing[0]
    return db.execute(
        '''INSERT INTO iot_machine_request
           (endpoint_id,request_no,protocol_version,station_code,cavity_code,sn,
            decision,reason_code,reason_message,elapsed_ms,dedupe_key,report_status)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
        (_value(endpoint, 'id'), f'FILE-{file_hash[:20]}',
         int(_value(endpoint, 'protocol_version', 1)),
         str(_value(endpoint, 'station_code', 'UNKNOWN')),
         str(_value(endpoint, 'cavity_code', 'UNKNOWN')), sn or 'UNKNOWN',
         'L3', 'REPORT_IMPORT_FAILED', '检测报告导入失败', 0, dedupe_key,
         'not_required'),
    ).lastrowid


def record_failed_inspection(db, endpoint, csv_bytes, filename, failure_path, reason):
    """持久化隔离文件；同一端点相同内容只保留一条失败记录。"""
    file_hash = hashlib.sha256(csv_bytes).hexdigest()
    existing = db.execute(
        'SELECT * FROM iot_inspection_report WHERE endpoint_id=? AND file_hash=?',
        (_value(endpoint, 'id'), file_hash),
    ).fetchone()
    if existing:
        return dict(existing)
    sn, inspected_at, result = 'UNKNOWN', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'UNKNOWN'
    try:
        rows = list(csv.reader(io.StringIO(_decode_csv(csv_bytes))))
        if (len(rows) > 1 and len(rows[0]) >= 4
                and tuple(cell.strip() for cell in rows[0][:4]) == REQUIRED_CSV_HEADERS):
            values = rows[1]
            sn = values[0].strip() or sn
            if len(values) > 2:
                inspected_at = _parse_inspected_at(values[1], values[2])
            if len(values) > 3:
                result = _normalize_result(values[3])
    except (ValueError, IndexError):
        pass
    try:
        request_id = _failure_request_id(db, endpoint, file_hash, sn)
        report_id = db.execute(
            '''INSERT INTO iot_inspection_report
               (request_id,endpoint_id,sn,inspected_at,result,original_filename,
                archive_path,file_hash,import_status,failure_reason)
               VALUES(?,?,?,?,?,?,?,?,?,?)''',
            (request_id, _value(endpoint, 'id'), sn, inspected_at, result,
             os.path.basename(filename), str(Path(failure_path).resolve()), file_hash,
             'failed', str(reason)[:1000]),
        ).lastrowid
        db.commit()
    except Exception:
        db.rollback()
        raise
    return dict(db.execute(
        'SELECT * FROM iot_inspection_report WHERE id=?', (report_id,)
    ).fetchone())


def import_inspection_report(db, endpoint, csv_bytes, filename, archive_root, now=None,
                             _retry_report_id=None, event_sink=None):
    """验证、归档和导入单件AIM检测报告。"""
    if not csv_bytes:
        raise ValueError('CSV文件为空')
    file_hash = hashlib.sha256(csv_bytes).hexdigest()
    existing = db.execute(
        '''SELECT * FROM iot_inspection_report
           WHERE endpoint_id=? AND file_hash=?''',
        (_value(endpoint, 'id'), file_hash),
    ).fetchone()
    if existing and int(existing['id']) != int(_retry_report_id or 0):
        event_id = f"AIM:{_value(endpoint, 'id')}:REPORT:{existing['id']}"
        try:
            if event_sink is not None:
                dispatch_aim_event(db, event_id, event_sink)
            else:
                sink = _default_event_sink(db)
                if sink is not None:
                    dispatch_aim_event(db, event_id, sink)
        except Exception:
            logger.exception('AIM report %s standard event retry failed', existing['id'])
        return dict(existing)

    rows = list(csv.reader(io.StringIO(_decode_csv(csv_bytes))))
    if len(rows) < 2 or len(rows[0]) < 4:
        raise ValueError('CSV表头或数据行不完整')
    headers = [cell.strip() for cell in rows[0]]
    if tuple(headers[:4]) != REQUIRED_CSV_HEADERS:
        raise ValueError('CSV表头不符合AIM规范')
    values = rows[1]
    if len(values) < len(headers):
        values += [''] * (len(headers) - len(values))
    sn = values[0].strip()
    inspected_at = _parse_inspected_at(values[1], values[2])
    result = _normalize_result(values[3])
    request_row = db.execute(
        '''SELECT * FROM iot_machine_request
           WHERE endpoint_id=? AND sn=? AND decision='L1' AND report_status='pending'
           ORDER BY id DESC LIMIT 1''',
        (_value(endpoint, 'id'), sn),
    ).fetchone()
    if not request_row:
        another = db.execute(
            '''SELECT 1 FROM iot_machine_request
               WHERE endpoint_id=? AND decision='L1' AND report_status='pending' LIMIT 1''',
            (_value(endpoint, 'id'),),
        ).fetchone()
        if another:
            raise ValueError('CSV中的SN与待报告准入请求不一致')
        raise ValueError('没有对应的L1准入请求')

    request_row = dict(request_row)
    if request_row.get('process_id') is None and request_row.get('route_step_id'):
        step = db.execute(
            'SELECT process_id FROM prod_workorder_route_step WHERE id=?',
            (request_row['route_step_id'],),
        ).fetchone()
        if step:
            request_row['process_id'] = step['process_id']

    date_path = datetime.strptime(inspected_at, '%Y-%m-%d %H:%M:%S')
    target_dir = Path(archive_root) / date_path.strftime('%Y') / date_path.strftime('%m') / date_path.strftime('%d')
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = ''.join(char for char in os.path.basename(filename) if char not in '\\/:*?"<>|')
    safe_name = safe_name or f'{sn}.csv'
    target = target_dir / f'{file_hash[:12]}_{safe_name}'
    temporary = target.with_suffix(target.suffix + f'.{uuid.uuid4().hex}.tmp')
    temporary.write_bytes(csv_bytes)
    db.execute('BEGIN IMMEDIATE')
    concurrent = db.execute(
        '''SELECT * FROM iot_inspection_report
           WHERE endpoint_id=? AND file_hash=? AND id<>?''',
        (_value(endpoint, 'id'), file_hash, int(_retry_report_id or 0)),
    ).fetchone()
    if concurrent:
        db.commit()
        temporary.unlink(missing_ok=True)
        return dict(concurrent)

    try:
        if _retry_report_id:
            report_id = int(_retry_report_id)
            db.execute('DELETE FROM iot_inspection_value WHERE report_id=?', (report_id,))
            db.execute(
                '''UPDATE iot_inspection_report SET request_id=?,sn=?,inspected_at=?,result=?,
                   original_filename=?,archive_path=?,file_hash=?,import_status='imported',
                   failure_reason=NULL,retry_count=retry_count+1 WHERE id=?''',
                (request_row['id'], sn, inspected_at, result, os.path.basename(filename),
                 str(target), file_hash, report_id),
            )
        else:
            report_id = db.execute(
                '''INSERT INTO iot_inspection_report
                   (request_id,endpoint_id,sn,inspected_at,result,original_filename,
                    archive_path,file_hash,import_status)
                   VALUES(?,?,?,?,?,?,?,?,?)''',
                (request_row['id'], _value(endpoint, 'id'), sn, inspected_at, result,
                 os.path.basename(filename), str(target), file_hash, 'imported'),
            ).lastrowid
        for item_code, measured_value in zip(headers[4:], values[4:]):
            db.execute(
                '''INSERT INTO iot_inspection_value
                   (report_id,item_code,item_name,measured_value,result)
                   VALUES(?,?,?,?,?)''',
                (report_id, item_code, item_code, measured_value.strip(), result),
            )
        report_no = f'MR{datetime.now().strftime("%Y%m%d%H%M%S")}{uuid.uuid4().hex[:6]}'
        client_operation_id = f'machine-report:{report_id}'
        prod_report_id = db.execute(
            '''INSERT INTO prod_report
               (report_no,task_id,workorder_id,process_id,user_id,qualified_qty,
                defect_qty,approval_status,remark,client_operation_id)
               VALUES(?,?,?,?,?,?,?,?,?,?)''',
            (report_no, request_row['task_id'], request_row['workorder_id'],
             db.execute('SELECT process_id FROM prod_task WHERE id=?', (request_row['task_id'],)).fetchone()[0],
             1, 1 if result == 'OK' else 0, 1 if result == 'NG' else 0, 0,
             f'AIM机台检测 {sn} {result}', client_operation_id),
        ).lastrowid
        db.execute(
            'UPDATE iot_inspection_report SET prod_report_id=? WHERE id=?',
            (prod_report_id, report_id),
        )
        flow = db.execute(
            'SELECT * FROM prod_station_flow WHERE sn=? ORDER BY id DESC LIMIT 1', (sn,)
        ).fetchone()
        process_name = db.execute(
            'SELECT process_name FROM prod_workorder_route_step WHERE id=?',
            (request_row['route_step_id'],),
        ).fetchone()[0]
        if not flow:
            flow_id = db.execute(
                '''INSERT INTO prod_station_flow
                   (flow_no,sn,product_id,workorder_id,current_station,current_process,status)
                   VALUES(?,?,?,?,?,?,0)''',
                (f'SF{uuid.uuid4().hex[:16]}', sn,
                 db.execute('SELECT product_id FROM prod_workorder WHERE id=?', (request_row['workorder_id'],)).fetchone()[0],
                 request_row['workorder_id'], request_row['station_code'], process_name),
            ).lastrowid
        else:
            flow_id = flow['id']
        db.execute(
            '''INSERT INTO prod_station_record
               (flow_id,sn,station,process_name,action,operator,result,remark,
                route_step_id,machine_request_id)
               VALUES(?,?,?,?,?,?,?,?,?,?)''',
            (flow_id, sn, request_row['station_code'], process_name,
             '过站' if result == 'OK' else '检测不良', 1,
             'PASS' if result == 'OK' else 'FAIL', f'AIM报告#{report_id}',
             request_row['route_step_id'], request_row['id']),
        )
        db.execute(
            "UPDATE iot_machine_request SET report_status='received' WHERE id=?",
            (request_row['id'],),
        )
        report_task = db.execute(
            'SELECT task_type FROM prod_task WHERE id=?', (request_row['task_id'],)
        ).fetchone()
        if result == 'NG':
            if report_task and report_task['task_type'] == 'rework':
                # Fail closed immediately. The next disposition cycle is created
                # when this approved NG report is posted, but the SN must not be
                # admitted again during the approval window.
                db.execute(
                    "UPDATE prod_serial SET quality_status='quality_hold' WHERE serial_no=?",
                    (sn,),
                )
            else:
                create_ng_disposition(
                    db, endpoint, request_row, report_id, prod_report_id,
                    reason='AIM机台检测NG',
                )
        os.replace(temporary, target)
        db.commit()
    except Exception:
        db.rollback()
        temporary.unlink(missing_ok=True)
        raise
    row = dict(db.execute('SELECT * FROM iot_inspection_report WHERE id=?', (report_id,)).fetchone())
    row['archive_path'] = str(target)
    measurement_map = {
        item_code: measured_value.strip()
        for item_code, measured_value in zip(headers[4:], values[4:])
    }
    try:
        lifecycle_id = str(_value(endpoint, 'lifecycle_id', 'legacy'))
        # Sequence allocation and outbox insertion must commit together.  A
        # process crash between those operations would otherwise leave a
        # permanent sequence gap with no event to retry.
        db.execute('BEGIN IMMEDIATE')
        sequence = next_aim_sequence(db, endpoint, lifecycle_id)
        standard_event = aim_report_event(
            endpoint, request_row, row, measurement_map,
            sequence=sequence, lifecycle_id=lifecycle_id,
        )
        enqueue_aim_event(db, standard_event)
        db.commit()
        if event_sink is not None:
            dispatch_aim_event(db, standard_event.event_id, event_sink)
        else:
            sink = _default_event_sink(db)
            if sink is not None:
                dispatch_aim_event(db, standard_event.event_id, sink)
    except Exception:
        logger.exception('AIM report %s was imported but its standard event is pending retry', report_id)
    return row


def retry_inspection_report(db, endpoint, report_id, archive_root):
    """使用服务器保存的隔离路径重试，成功后更新原失败记录。"""
    db.execute('BEGIN IMMEDIATE')
    claimed = db.execute(
        '''UPDATE iot_inspection_report SET import_status='retrying'
           WHERE id=? AND endpoint_id=? AND import_status='failed' ''',
        (int(report_id), _value(endpoint, 'id')),
    ).rowcount
    if not claimed:
        db.rollback()
        raise ValueError('失败报告不存在或状态不可重试')
    row = db.execute('SELECT * FROM iot_inspection_report WHERE id=?', (int(report_id),)).fetchone()
    db.commit()
    source = Path(row['archive_path']).resolve()
    input_dir = Path(str(_value(endpoint, 'csv_input_dir', ''))).resolve()
    failed_root = (input_dir / '_failed').resolve()
    archive_resolved = Path(archive_root).resolve()
    def is_within(path, root):
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    if not (is_within(source, failed_root) or is_within(source, archive_resolved)):
        db.execute("UPDATE iot_inspection_report SET import_status='failed' WHERE id=?", (row['id'],)); db.commit()
        raise ValueError('失败报告路径不在允许目录内')
    if not source.is_file():
        db.execute("UPDATE iot_inspection_report SET import_status='failed' WHERE id=?", (row['id'],)); db.commit()
        raise ValueError('失败报告原文件不存在')
    payload = source.read_bytes()
    try:
        result = import_inspection_report(
            db, endpoint, payload, row['original_filename'], archive_root,
            _retry_report_id=row['id'],
        )
    except Exception as exc:
        db.rollback()
        db.execute(
            '''UPDATE iot_inspection_report SET import_status='failed',retry_count=retry_count+1,
               failure_reason=? WHERE id=? AND import_status='retrying' ''', (str(exc)[:1000], row['id']),
        )
        db.commit()
        raise
    try:
        if source != Path(result['archive_path']).resolve():
            source.unlink()
    except OSError:
        pass
    return result
