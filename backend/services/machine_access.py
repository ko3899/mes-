"""AIM机台生产准入与检测报告业务。"""
from datetime import datetime
import csv
import hashlib
import io
import os
from pathlib import Path
import time
import uuid

from services.machine_protocol import AccessDecision


ALLOWED_WORKORDER_STATUSES = {1, 2}
REQUIRED_CSV_HEADERS = ('2D Barcode', 'Date', 'Time', 'OK(1)/NG(0)')


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


def _persist_decision(db, endpoint, request, decision, context, started):
    dedupe_key = f"{_value(endpoint, 'id')}:{request.request_no}"
    elapsed_ms = max(0, int((time.perf_counter() - started) * 1000))
    try:
        db.execute(
            '''INSERT INTO iot_machine_request
               (endpoint_id,request_no,protocol_version,station_code,cavity_code,sn,
                workorder_id,task_id,route_step_id,decision,reason_code,reason_message,
                laser_template,inspection_template,elapsed_ms,dedupe_key,report_status)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (_value(endpoint, 'id'), request.request_no, request.protocol_version,
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
        if existing:
            return _decision_from_row(existing)
        raise
    return decision


def evaluate_access(db, endpoint, request, now=None):
    """判定SN能否在指定机台工序开始加工，并持久化幂等判定。"""
    started = time.perf_counter()
    dedupe_key = f"{_value(endpoint, 'id')}:{request.request_no}"
    existing = db.execute(
        'SELECT * FROM iot_machine_request WHERE dedupe_key=?', (dedupe_key,)
    ).fetchone()
    if existing:
        return _decision_from_row(existing)

    context = {}

    def reject(code, message):
        return _persist_decision(
            db, endpoint, request, AccessDecision.reject(code, message), context, started
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
               WHERE sn=? AND process_name=? AND action='过站' AND result='PASS'
               LIMIT 1''',
            (request.sn, step['process_name']),
        ).fetchone()
        if not passed:
            current = step
            break
    if not current:
        return reject('ROUTE_COMPLETED', 'SN已完成全部工序')
    context['route_step_id'] = current['id']
    if int(current['process_id']) != int(_value(endpoint, 'process_id', 0)):
        return reject('WRONG_STEP', f"当前应执行工序：{current['process_name']}")

    task = db.execute(
        '''SELECT * FROM prod_task
           WHERE workorder_id=? AND route_step_id=? ORDER BY id LIMIT 1''',
        (workorder['id'], current['id']),
    ).fetchone()
    if not task:
        return reject('TASK_NOT_FOUND', '当前工序没有生产任务')
    context['task_id'] = task['id']
    if int(_value(task, 'status', 0)) in (3, 4, 5, 6):
        return reject('TASK_UNAVAILABLE', '当前任务不可生产')

    laser = str(_value(endpoint, 'laser_template', ''))
    inspection = str(_value(endpoint, 'inspection_template', ''))
    decision = AccessDecision.allow(laser, inspection, '允许加工')
    return _persist_decision(db, endpoint, request, decision, context, started)


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


def import_inspection_report(db, endpoint, csv_bytes, filename, archive_root, now=None):
    """验证、归档和导入单件AIM检测报告。"""
    if not csv_bytes:
        raise ValueError('CSV文件为空')
    file_hash = hashlib.sha256(csv_bytes).hexdigest()
    existing = db.execute(
        '''SELECT * FROM iot_inspection_report
           WHERE endpoint_id=? AND file_hash=?''',
        (_value(endpoint, 'id'), file_hash),
    ).fetchone()
    if existing:
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

    date_path = datetime.strptime(inspected_at, '%Y-%m-%d %H:%M:%S')
    target_dir = Path(archive_root) / date_path.strftime('%Y') / date_path.strftime('%m') / date_path.strftime('%d')
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = ''.join(char for char in os.path.basename(filename) if char not in '\\/:*?"<>|')
    safe_name = safe_name or f'{sn}.csv'
    target = target_dir / f'{file_hash[:12]}_{safe_name}'
    temporary = target.with_suffix(target.suffix + '.tmp')
    temporary.write_bytes(csv_bytes)
    os.replace(temporary, target)

    try:
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
        if result == 'OK':
            flow = db.execute(
                'SELECT * FROM prod_station_flow WHERE sn=? ORDER BY id DESC LIMIT 1', (sn,)
            ).fetchone()
            if not flow:
                flow_id = db.execute(
                    '''INSERT INTO prod_station_flow
                       (flow_no,sn,product_id,workorder_id,current_station,current_process,status)
                       VALUES(?,?,?,?,?,?,0)''',
                    (f'SF{uuid.uuid4().hex[:16]}', sn,
                     db.execute('SELECT product_id FROM prod_workorder WHERE id=?', (request_row['workorder_id'],)).fetchone()[0],
                     request_row['workorder_id'], request_row['station_code'],
                     db.execute('SELECT process_name FROM prod_workorder_route_step WHERE id=?', (request_row['route_step_id'],)).fetchone()[0]),
                ).lastrowid
            else:
                flow_id = flow['id']
            process_name = db.execute(
                'SELECT process_name FROM prod_workorder_route_step WHERE id=?',
                (request_row['route_step_id'],),
            ).fetchone()[0]
            db.execute(
                '''INSERT INTO prod_station_record
                   (flow_id,sn,station,process_name,action,operator,result,remark)
                   VALUES(?,?,?,?,?,?,?,?)''',
                (flow_id, sn, request_row['station_code'], process_name, '过站', 1,
                 'PASS', f'AIM报告#{report_id}'),
            )
        db.execute(
            "UPDATE iot_machine_request SET report_status='received' WHERE id=?",
            (request_row['id'],),
        )
        db.commit()
    except Exception:
        db.rollback()
        try:
            target.unlink()
        except OSError:
            pass
        raise
    row = dict(db.execute('SELECT * FROM iot_inspection_report WHERE id=?', (report_id,)).fetchone())
    row['archive_path'] = str(target)
    return row

