"""设备台账、维修和保养业务。"""
import calendar
import datetime

from flask import Blueprint, jsonify, request, session

from utils.database import get_db
from utils.helpers import crud_add, crud_list, gen_no_in_transaction, login_required


equipment_bp = Blueprint('equipment', __name__)
MAINTENANCE_FREQUENCIES = {'日', '周', '月', '季', '年'}


def _error(message, status=400):
    return jsonify({'code': status, 'message': message}), status


def _positive_int(value, name):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f'{name}格式错误')
    if parsed <= 0:
        raise ValueError(f'{name}必须大于0')
    return parsed


def _parse_date(value, name='日期', required=False):
    text = str(value or '').strip()
    if not text and not required:
        return ''
    try:
        return datetime.date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError(f'{name}格式必须为YYYY-MM-DD') from exc


def _add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


def _next_maintenance_date(completed_on, frequency):
    if frequency == '日':
        return completed_on + datetime.timedelta(days=1)
    if frequency == '周':
        return completed_on + datetime.timedelta(weeks=1)
    if frequency == '月':
        return _add_months(completed_on, 1)
    if frequency == '季':
        return _add_months(completed_on, 3)
    if frequency == '年':
        return _add_months(completed_on, 12)
    raise ValueError('保养周期无效')


@equipment_bp.route('/api/eqp/type/list')
@login_required
def eqp_type_list():
    return jsonify(crud_list('eqp_type', request.args))


@equipment_bp.route('/api/eqp/type/add', methods=['POST'])
@login_required
def eqp_type_add():
    return jsonify(crud_add('eqp_type', request.get_json(silent=True)))


@equipment_bp.route('/api/eqp/ledger/list')
@login_required
def eqp_ledger_list():
    db = get_db()
    rows = db.execute(
        '''SELECT el.*,et.type_name,ws.workshop_name
           FROM eqp_ledger el
           LEFT JOIN eqp_type et ON el.type_id=et.id
           LEFT JOIN base_workshop ws ON el.workshop_id=ws.id
           ORDER BY el.id DESC'''
    ).fetchall()
    return jsonify({'code': 0, 'data': [dict(row) for row in rows]})


@equipment_bp.route('/api/eqp/ledger/add', methods=['POST'])
@login_required
def eqp_ledger_add():
    data = request.get_json(silent=True) or {}
    if not str(data.get('equipment_name') or '').strip() or not str(data.get('code') or '').strip():
        return _error('设备名称和编码不能为空')
    data['equipment_name'] = str(data['equipment_name']).strip()
    data['code'] = str(data['code']).strip()
    data['status'] = 1
    return jsonify(crud_add('eqp_ledger', data))


@equipment_bp.route('/api/eqp/ledger/update', methods=['POST'])
@login_required
def eqp_ledger_update():
    data = request.get_json(silent=True) or {}
    try:
        equipment_id = _positive_int(data.get('id'), '设备ID')
    except ValueError as exc:
        return _error(str(exc))
    db = get_db()
    current = db.execute('SELECT * FROM eqp_ledger WHERE id=?', (equipment_id,)).fetchone()
    if not current:
        return _error('设备不存在', 404)
    if 'status' in data and int(data['status']) != current['status']:
        return _error('设备状态由维修流程维护，不能直接修改', 409)
    fields = ['equipment_name', 'code', 'type_id', 'model', 'manufacturer',
              'purchase_date', 'workshop_id', 'location', 'remark']
    updates = {field: data[field] for field in fields if field in data}
    if not updates:
        return _error('无可修改字段')
    if 'equipment_name' in updates and not str(updates['equipment_name'] or '').strip():
        return _error('设备名称不能为空')
    if 'code' in updates and not str(updates['code'] or '').strip():
        return _error('设备编码不能为空')
    try:
        db.execute(
            'UPDATE eqp_ledger SET ' + ','.join(f'{key}=?' for key in updates) + ' WHERE id=?',
            list(updates.values()) + [equipment_id],
        )
        db.commit()
    except Exception:
        db.rollback()
        return _error('设备编码已存在或数据格式错误', 409)
    return jsonify({'code': 0, 'message': '修改成功'})


@equipment_bp.route('/api/eqp/ledger/delete', methods=['POST'])
@login_required
def eqp_ledger_delete():
    data = request.get_json(silent=True) or {}
    try:
        equipment_id = _positive_int(data.get('id'), '设备ID')
    except ValueError as exc:
        return _error(str(exc))
    db = get_db()
    if not db.execute('SELECT 1 FROM eqp_ledger WHERE id=?', (equipment_id,)).fetchone():
        return _error('设备不存在', 404)
    references = (
        ('eqp_repair_order', '维修记录'),
        ('eqp_maintenance_plan', '保养计划'),
        ('iot_machine_endpoint', '机台通讯配置'),
    )
    for table, label in references:
        if db.execute(f'SELECT 1 FROM {table} WHERE equipment_id=? LIMIT 1', (equipment_id,)).fetchone():
            return _error(f'设备已有{label}，不能删除；可停用或保留台账', 409)
    db.execute('DELETE FROM eqp_ledger WHERE id=?', (equipment_id,))
    db.commit()
    return jsonify({'code': 0, 'message': '删除成功'})


@equipment_bp.route('/api/eqp/repair/list')
@login_required
def eqp_repair_list():
    db = get_db()
    rows = db.execute(
        '''SELECT er.*,el.equipment_name,el.code AS eqp_code,
                  u1.real_name AS reporter_name,u2.real_name AS repairer_name
           FROM eqp_repair_order er
           LEFT JOIN eqp_ledger el ON er.equipment_id=el.id
           LEFT JOIN sys_user u1 ON er.reporter=u1.id
           LEFT JOIN sys_user u2 ON er.repairer=u2.id
           ORDER BY er.id DESC'''
    ).fetchall()
    return jsonify({'code': 0, 'data': [dict(row) for row in rows]})


@equipment_bp.route('/api/eqp/repair/add', methods=['POST'])
@login_required
def eqp_repair_add():
    data = request.get_json(silent=True) or {}
    try:
        equipment_id = _positive_int(data.get('equipment_id'), '设备ID')
    except ValueError as exc:
        return _error(str(exc))
    fault_desc = str(data.get('fault_desc') or '').strip()
    if not fault_desc:
        return _error('故障描述不能为空')
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        equipment = db.execute('SELECT status FROM eqp_ledger WHERE id=?', (equipment_id,)).fetchone()
        if not equipment:
            db.rollback()
            return _error('设备不存在', 404)
        if db.execute(
            'SELECT 1 FROM eqp_repair_order WHERE equipment_id=? AND status IN (0,1) LIMIT 1',
            (equipment_id,),
        ).fetchone():
            db.rollback()
            return _error('该设备已有未完成维修单', 409)
        repair_no = gen_no_in_transaction(db, 'WX')
        cursor = db.execute(
            '''INSERT INTO eqp_repair_order
               (repair_no,equipment_id,fault_desc,reporter,status,remark)
               VALUES (?,?,?,?,0,?)''',
            (repair_no, equipment_id, fault_desc, session.get('user_id'),
             str(data.get('remark') or '').strip()),
        )
        db.execute('UPDATE eqp_ledger SET status=2 WHERE id=?', (equipment_id,))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return jsonify({'code': 0, 'data': {'id': cursor.lastrowid}, 'message': '维修单已创建'})


@equipment_bp.route('/api/eqp/repair/<int:repair_id>/start', methods=['POST'])
@login_required
def eqp_repair_start(repair_id):
    db = get_db()
    cursor = db.execute(
        '''UPDATE eqp_repair_order SET status=1,repairer=?
           WHERE id=? AND status=0''',
        (session.get('user_id'), repair_id),
    )
    if cursor.rowcount != 1:
        db.rollback()
        return _error('维修单不存在或已开始处理', 409)
    db.commit()
    return jsonify({'code': 0, 'message': '维修已开始'})


@equipment_bp.route('/api/eqp/repair/<int:repair_id>/complete', methods=['POST'])
@login_required
def eqp_repair_complete(repair_id):
    data = request.get_json(silent=True) or {}
    repair_desc = str(data.get('repair_desc') or '').strip()
    if not repair_desc:
        return _error('维修结果不能为空')
    db = get_db()
    repair = db.execute(
        'SELECT equipment_id,status FROM eqp_repair_order WHERE id=?', (repair_id,)
    ).fetchone()
    if not repair or repair['status'] != 1:
        return _error('维修单不存在、尚未开始或已完成', 409)
    db.execute(
        '''UPDATE eqp_repair_order SET status=2,repair_desc=?,
           repairer=COALESCE(repairer,?),repair_time=CURRENT_TIMESTAMP
           WHERE id=? AND status=1''',
        (repair_desc, session.get('user_id'), repair_id),
    )
    other_open = db.execute(
        '''SELECT 1 FROM eqp_repair_order
           WHERE equipment_id=? AND status IN (0,1) AND id<>? LIMIT 1''',
        (repair['equipment_id'], repair_id),
    ).fetchone()
    if not other_open:
        db.execute('UPDATE eqp_ledger SET status=1 WHERE id=?', (repair['equipment_id'],))
    db.commit()
    return jsonify({'code': 0, 'message': '维修已完成'})


@equipment_bp.route('/api/eqp/repair/delete', methods=['POST'])
@login_required
def eqp_repair_delete():
    data = request.get_json(silent=True) or {}
    try:
        repair_id = _positive_int(data.get('id'), '维修单ID')
    except ValueError as exc:
        return _error(str(exc))
    db = get_db()
    repair = db.execute(
        'SELECT equipment_id,status FROM eqp_repair_order WHERE id=?', (repair_id,)
    ).fetchone()
    if not repair:
        return _error('维修单不存在', 404)
    if repair['status'] != 0:
        return _error('已开始或已完成的维修单不能删除', 409)
    db.execute('DELETE FROM eqp_repair_order WHERE id=?', (repair_id,))
    if not db.execute(
        'SELECT 1 FROM eqp_repair_order WHERE equipment_id=? AND status IN (0,1) LIMIT 1',
        (repair['equipment_id'],),
    ).fetchone():
        db.execute('UPDATE eqp_ledger SET status=1 WHERE id=?', (repair['equipment_id'],))
    db.commit()
    return jsonify({'code': 0, 'message': '删除成功'})


@equipment_bp.route('/api/eqp/maintenance/list')
@login_required
def eqp_maint_list():
    db = get_db()
    try:
        page = max(1, int(request.args.get('page', 1)))
        size = min(100, max(1, int(request.args.get('size', 15))))
    except (TypeError, ValueError):
        return _error('分页参数格式错误')
    total = db.execute('SELECT COUNT(*) AS count FROM eqp_maintenance_plan').fetchone()['count']
    rows = db.execute(
        '''SELECT m.*,e.equipment_name,e.code AS eqp_code
           FROM eqp_maintenance_plan m
           LEFT JOIN eqp_ledger e ON m.equipment_id=e.id
           ORDER BY m.id DESC LIMIT ? OFFSET ?''',
        (size, (page - 1) * size),
    ).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(row) for row in rows], 'total': total}})


def _validate_maintenance_payload(data, db):
    plan_name = str(data.get('plan_name') or '').strip()
    if not plan_name:
        raise ValueError('计划名称不能为空')
    equipment_id = _positive_int(data.get('equipment_id'), '设备ID')
    if not db.execute('SELECT 1 FROM eqp_ledger WHERE id=?', (equipment_id,)).fetchone():
        raise ValueError('设备不存在')
    frequency = str(data.get('frequency') or '').strip()
    if frequency not in MAINTENANCE_FREQUENCIES:
        raise ValueError('保养周期只能是日、周、月、季或年')
    next_date = _parse_date(data.get('next_date'), '下次保养日期', required=True)
    status = int(data.get('status', 1))
    if status not in (0, 1):
        raise ValueError('计划状态无效')
    return plan_name, equipment_id, frequency, next_date, status


@equipment_bp.route('/api/eqp/maintenance/add', methods=['POST'])
@login_required
def eqp_maint_add():
    data = request.get_json(silent=True) or {}
    db = get_db()
    try:
        plan_name, equipment_id, frequency, next_date, status = _validate_maintenance_payload(data, db)
    except (TypeError, ValueError) as exc:
        return _error(str(exc))
    cursor = db.execute(
        '''INSERT INTO eqp_maintenance_plan
           (plan_name,equipment_id,check_items,frequency,next_date,status)
           VALUES (?,?,?,?,?,?)''',
        (plan_name, equipment_id, str(data.get('check_items') or '').strip(),
         frequency, next_date, status),
    )
    db.commit()
    return jsonify({'code': 0, 'data': {'id': cursor.lastrowid}})


@equipment_bp.route('/api/eqp/maintenance/update', methods=['POST'])
@login_required
def eqp_maint_update():
    data = request.get_json(silent=True) or {}
    try:
        plan_id = _positive_int(data.get('id'), '计划ID')
    except ValueError as exc:
        return _error(str(exc))
    db = get_db()
    if not db.execute('SELECT 1 FROM eqp_maintenance_plan WHERE id=?', (plan_id,)).fetchone():
        return _error('维护计划不存在', 404)
    try:
        plan_name, equipment_id, frequency, next_date, status = _validate_maintenance_payload(data, db)
    except (TypeError, ValueError) as exc:
        return _error(str(exc))
    db.execute(
        '''UPDATE eqp_maintenance_plan SET plan_name=?,equipment_id=?,check_items=?,
           frequency=?,next_date=?,status=? WHERE id=?''',
        (plan_name, equipment_id, str(data.get('check_items') or '').strip(),
         frequency, next_date, status, plan_id),
    )
    db.commit()
    return jsonify({'code': 0})


@equipment_bp.route('/api/eqp/maintenance/delete', methods=['POST'])
@login_required
def eqp_maint_delete():
    data = request.get_json(silent=True) or {}
    try:
        plan_id = _positive_int(data.get('id'), '计划ID')
    except ValueError as exc:
        return _error(str(exc))
    db = get_db()
    if not db.execute('SELECT 1 FROM eqp_maintenance_plan WHERE id=?', (plan_id,)).fetchone():
        return _error('维护计划不存在', 404)
    if db.execute('SELECT 1 FROM eqp_check_workorder WHERE plan_id=? LIMIT 1', (plan_id,)).fetchone():
        return _error('计划已有保养记录，不能删除；可改为停用', 409)
    db.execute('DELETE FROM eqp_maintenance_plan WHERE id=?', (plan_id,))
    db.commit()
    return jsonify({'code': 0})


@equipment_bp.route('/api/eqp/maintenance/overdue')
@login_required
def eqp_maint_overdue():
    db = get_db()
    today = datetime.date.today().isoformat()
    rows = db.execute(
        '''SELECT m.*,e.equipment_name FROM eqp_maintenance_plan m
           JOIN eqp_ledger e ON m.equipment_id=e.id
           WHERE m.next_date<? AND m.status=1 ORDER BY m.next_date''',
        (today,),
    ).fetchall()
    return jsonify({'code': 0, 'data': [dict(row) for row in rows]})


@equipment_bp.route('/api/eqp/check/add', methods=['POST'])
@login_required
def eqp_check_add():
    data = request.get_json(silent=True) or {}
    try:
        plan_id = _positive_int(data.get('plan_id'), '维护计划ID')
    except ValueError as exc:
        return _error(str(exc))
    result = str(data.get('check_result') or '').strip()
    if result not in ('正常', '异常'):
        return _error('保养结果只能是正常或异常')
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        plan = db.execute(
            'SELECT * FROM eqp_maintenance_plan WHERE id=? AND status=1', (plan_id,)
        ).fetchone()
        if not plan:
            db.rollback()
            return _error('维护计划不存在或已停用', 404)
        if data.get('equipment_id') not in (None, '', plan['equipment_id'], str(plan['equipment_id'])):
            db.rollback()
            return _error('维护计划与设备不匹配', 409)
        next_date = _next_maintenance_date(datetime.date.today(), plan['frequency'])
        workorder_no = gen_no_in_transaction(db, 'BY')
        cursor = db.execute(
            '''INSERT INTO eqp_check_workorder
               (workorder_no,plan_id,equipment_id,check_result,status,assigned_to,check_time,remark)
               VALUES (?,?,?,?,1,?,CURRENT_TIMESTAMP,?)''',
            (workorder_no, plan_id, plan['equipment_id'], result,
             session.get('user_id'), str(data.get('remark') or '').strip()),
        )
        db.execute(
            'UPDATE eqp_maintenance_plan SET next_date=? WHERE id=? AND status=1',
            (next_date.isoformat(), plan_id),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return jsonify({'code': 0, 'data': {'id': cursor.lastrowid, 'next_date': next_date.isoformat()}})


@equipment_bp.route('/api/eqp/check/list')
@login_required
def eqp_check_list():
    db = get_db()
    try:
        page = max(1, int(request.args.get('page', 1)))
        size = min(100, max(1, int(request.args.get('size', 15))))
    except (TypeError, ValueError):
        return _error('分页参数格式错误')
    total = db.execute('SELECT COUNT(*) AS count FROM eqp_check_workorder').fetchone()['count']
    rows = db.execute(
        '''SELECT c.*,e.equipment_name,m.plan_name
           FROM eqp_check_workorder c
           LEFT JOIN eqp_ledger e ON c.equipment_id=e.id
           LEFT JOIN eqp_maintenance_plan m ON c.plan_id=m.id
           ORDER BY c.id DESC LIMIT ? OFFSET ?''',
        (size, (page - 1) * size),
    ).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(row) for row in rows], 'total': total}})
