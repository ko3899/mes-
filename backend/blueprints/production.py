"""生产管理蓝图"""
import math
from decimal import Decimal, ROUND_HALF_UP

from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import (
    login_required,
    crud_list,
    crud_add,
    crud_update,
    crud_delete,
    gen_no,
    gen_no_in_transaction,
)

production_bp = Blueprint('production', __name__)

_QUANTITY_QUANTUM = Decimal('0.000001')


@production_bp.route('/api/prod/sales/list')
@login_required
def prod_sales_list():
    return jsonify(crud_list('prod_sales_order', request.args))


@production_bp.route('/api/prod/sales/add', methods=['POST'])
@login_required
def prod_sales_add():
    data = request.json
    data['order_no'] = gen_no('SO')
    data['created_by'] = session.get('user_id')
    return jsonify(crud_add('prod_sales_order', data))


@production_bp.route('/api/prod/sales/update', methods=['POST'])
@login_required
def prod_sales_update():
    return jsonify(crud_update('prod_sales_order', request.json))


@production_bp.route('/api/prod/sales/delete', methods=['POST'])
@login_required
def prod_sales_delete():
    return jsonify(crud_delete('prod_sales_order', request.json.get('id')))


@production_bp.route('/api/prod/plan/list')
@login_required
def prod_plan_list():
    return jsonify(crud_list('prod_plan', request.args))


@production_bp.route('/api/prod/plan/add', methods=['POST'])
@login_required
def prod_plan_add():
    data = request.json
    data['plan_no'] = gen_no('PP')
    data['created_by'] = session.get('user_id')
    return jsonify(crud_add('prod_plan', data))


@production_bp.route('/api/prod/plan/update', methods=['POST'])
@login_required
def prod_plan_update():
    return jsonify(crud_update('prod_plan', request.json))


@production_bp.route('/api/prod/plan/delete', methods=['POST'])
@login_required
def prod_plan_delete():
    return jsonify(crud_delete('prod_plan', request.json.get('id')))


@production_bp.route('/api/prod/workorder/list')
@login_required
def prod_workorder_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    keyword = request.args.get('keyword', '').strip()
    where = ""
    params = []
    if keyword:
        where = """ WHERE (
            w.order_no LIKE ? OR p.product_name LIKE ? OR p.code LIKE ?
        )"""
        params = [f"%{keyword}%"] * 3
    total = db.execute(
        f'''SELECT COUNT(*) as cnt
            FROM prod_workorder w
            LEFT JOIN base_product p ON w.product_id=p.id
            LEFT JOIN base_workshop ws ON w.workshop_id=ws.id
            {where}''',
        params,
    ).fetchone()['cnt']
    rows = db.execute(f'''SELECT w.*, p.product_name, p.code as product_code,
        ws.workshop_name
        FROM prod_workorder w
        LEFT JOIN base_product p ON w.product_id=p.id
        LEFT JOIN base_workshop ws ON w.workshop_id=ws.id
        {where}
        ORDER BY w.id DESC LIMIT ? OFFSET ?''',
        params + [size, offset],
    ).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@production_bp.route('/api/prod/workorder/add', methods=['POST'])
@login_required
def prod_workorder_add():
    data = request.json
    data['order_no'] = gen_no('WO')
    data['created_by'] = session.get('user_id')
    return jsonify(crud_add('prod_workorder', data))


@production_bp.route('/api/prod/workorder/update', methods=['POST'])
@login_required
def prod_workorder_update():
    return jsonify(crud_update('prod_workorder', request.json))


@production_bp.route('/api/prod/workorder/delete', methods=['POST'])
@login_required
def prod_workorder_delete():
    return jsonify(crud_delete('prod_workorder', request.json.get('id')))


@production_bp.route('/api/prod/task/list')
@login_required
def prod_task_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    keyword = request.args.get('keyword', '').strip()
    where = ""
    params = []
    if keyword:
        where = """ WHERE (
            t.task_no LIKE ? OR w.order_no LIKE ? OR pr.process_name LIKE ?
        )"""
        params = [f"%{keyword}%"] * 3
    total = db.execute(
        f'''SELECT COUNT(*) as cnt
            FROM prod_task t
            LEFT JOIN prod_workorder w ON t.workorder_id=w.id
            LEFT JOIN base_process pr ON t.process_id=pr.id
            LEFT JOIN sys_user u ON t.assigned_to=u.id
            {where}''',
        params,
    ).fetchone()['cnt']
    rows = db.execute(f'''SELECT t.*, w.order_no as workorder_no, pr.process_name,
        u.real_name as assigned_name
        FROM prod_task t
        LEFT JOIN prod_workorder w ON t.workorder_id=w.id
        LEFT JOIN base_process pr ON t.process_id=pr.id
        LEFT JOIN sys_user u ON t.assigned_to=u.id
        {where}
        ORDER BY t.id DESC LIMIT ? OFFSET ?''',
        params + [size, offset],
    ).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@production_bp.route('/api/prod/task/add', methods=['POST'])
@login_required
def prod_task_add():
    data = request.json
    data['task_no'] = gen_no('TK')
    return jsonify(crud_add('prod_task', data))


@production_bp.route('/api/prod/task/update', methods=['POST'])
@login_required
def prod_task_update():
    return jsonify(crud_update('prod_task', request.json))


@production_bp.route('/api/prod/task/delete', methods=['POST'])
@login_required
def prod_task_delete():
    return jsonify(crud_delete('prod_task', request.json.get('id')))


@production_bp.route('/api/prod/report/list')
@login_required
def prod_report_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM prod_report").fetchone()['cnt']
    rows = db.execute('''SELECT r.*, t.task_no, w.order_no as workorder_no,
        pr.process_name, u.real_name
        FROM prod_report r
        LEFT JOIN prod_task t ON r.task_id=t.id
        LEFT JOIN prod_workorder w ON r.workorder_id=w.id
        LEFT JOIN base_process pr ON r.process_id=pr.id
        LEFT JOIN sys_user u ON r.user_id=u.id
        ORDER BY r.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@production_bp.route('/api/prod/report/add', methods=['POST'])
@login_required
def prod_report_add():
    result = _create_report(
        request.get_json(silent=True) or {},
        session.get('user_id'),
    )
    status = result['code'] if result.get('code', 0) >= 400 else 200
    return jsonify(result), status


@production_bp.route('/api/prod/report/gps', methods=['POST'])
@login_required
def prod_report_gps():
    """GPS定位报工"""
    data = dict(request.get_json(silent=True) or {})
    lat = data.pop('latitude', '')
    lng = data.pop('longitude', '')
    data['remark'] = f"GPS: {lat},{lng}"
    result = _create_report(data, session.get('user_id'))
    status = result['code'] if result.get('code', 0) >= 400 else 200
    return jsonify(result), status


def _progress_status(completed, defect, planned):
    completed = _normalize_quantity(completed)
    defect = _normalize_quantity(defect)
    planned = _normalize_quantity(planned)
    if completed >= planned:
        return 3
    if completed > 0 or defect > 0:
        return 1
    return 0


def _normalize_quantity(value):
    """按 MES 业务数量的 6 位小数精度进行归一化。"""
    return Decimal(str(value or 0)).quantize(
        _QUANTITY_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


def _report_totals(db, column, row_id):
    assert column in ('task_id', 'workorder_id')
    row = db.execute(
        f"""SELECT COALESCE(SUM(qualified_qty), 0) AS completed,
                   COALESCE(SUM(defect_qty), 0) AS defect
            FROM prod_report WHERE {column}=?""",
        (row_id,),
    ).fetchone()
    return {
        'completed': _normalize_quantity(row['completed']),
        'defect': _normalize_quantity(row['defect']),
    }


def _recalculate_task_and_workorder(db, task_id, workorder_id):
    task = db.execute(
        "SELECT planned_qty FROM prod_task WHERE id=?",
        (task_id,),
    ).fetchone()
    task_totals = _report_totals(db, 'task_id', task_id)
    task_status = _progress_status(
        task_totals['completed'],
        task_totals['defect'],
        task['planned_qty'],
    )
    db.execute(
        """UPDATE prod_task
           SET completed_qty=?, defect_qty=?, status=?,
               start_time=CASE
                   WHEN ? > 0 THEN COALESCE(start_time, CURRENT_TIMESTAMP)
                   ELSE start_time
               END,
               end_time=CASE
                   WHEN ? = 3 THEN COALESCE(end_time, CURRENT_TIMESTAMP)
                   ELSE NULL
               END
           WHERE id=?""",
        (
            float(task_totals['completed']),
            float(task_totals['defect']),
            task_status,
            float(task_totals['completed'] + task_totals['defect']),
            task_status,
            task_id,
        ),
    )

    workorder_totals = _report_totals(db, 'workorder_id', workorder_id)
    task_counts = db.execute(
        """SELECT COUNT(*) AS total,
                  COALESCE(SUM(CASE WHEN status=3 THEN 1 ELSE 0 END), 0)
                      AS finished
           FROM prod_task WHERE workorder_id=?""",
        (workorder_id,),
    ).fetchone()
    has_progress = (
        workorder_totals['completed'] > 0
        or workorder_totals['defect'] > 0
    )
    workorder_status = (
        3
        if task_counts['total'] > 0
        and task_counts['finished'] == task_counts['total']
        else 1 if has_progress else 0
    )
    db.execute(
        """UPDATE prod_workorder
           SET completed_qty=?, defect_qty=?, status=?,
               updated_at=CURRENT_TIMESTAMP
           WHERE id=?""",
        (
            float(workorder_totals['completed']),
            float(workorder_totals['defect']),
            workorder_status,
            workorder_id,
        ),
    )


def _create_report(data, user_id):
    db = get_db()
    try:
        task_id = int(data.get('task_id'))
        workorder_id = int(data.get('workorder_id'))
        process_id = int(data.get('process_id'))
        qualified = float(data.get('qualified_qty') or 0)
        defect = float(data.get('defect_qty') or 0)
    except (TypeError, ValueError):
        return {'code': 400, 'message': '报工参数不合法'}
    if not math.isfinite(qualified) or not math.isfinite(defect):
        return {'code': 400, 'message': '报工数量不合法'}
    qualified = _normalize_quantity(qualified)
    defect = _normalize_quantity(defect)
    if qualified <= 0 or defect < 0:
        return {'code': 400, 'message': '报工数量不合法'}

    try:
        db.execute("BEGIN IMMEDIATE")
        task = db.execute(
            "SELECT * FROM prod_task WHERE id=?",
            (task_id,),
        ).fetchone()
        if not task:
            db.rollback()
            return {'code': 404, 'message': '任务不存在'}
        if int(task['workorder_id']) != workorder_id:
            db.rollback()
            return {'code': 400, 'message': '任务与工单不匹配'}
        if int(task['process_id']) != process_id:
            db.rollback()
            return {'code': 400, 'message': '任务与工序不匹配'}

        report_no = gen_no_in_transaction(db, 'BR')
        cursor = db.execute(
            """INSERT INTO prod_report
               (report_no, task_id, workorder_id, process_id, user_id,
                qualified_qty, defect_qty, remark)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                report_no,
                task_id,
                workorder_id,
                process_id,
                user_id,
                float(qualified),
                float(defect),
                data.get('remark'),
            ),
        )
        _recalculate_task_and_workorder(db, task_id, workorder_id)
        db.commit()
        return {
            'code': 0,
            'data': {'id': cursor.lastrowid},
            'message': '报工成功',
        }
    except Exception:
        db.rollback()
        raise


def _delete_report(report_id):
    db = get_db()
    try:
        report_id = int(report_id)
    except (TypeError, ValueError):
        return {'code': 400, 'message': '报工记录参数不合法'}

    try:
        db.execute("BEGIN IMMEDIATE")
        report = db.execute(
            """SELECT task_id, workorder_id
               FROM prod_report WHERE id=?""",
            (report_id,),
        ).fetchone()
        if not report:
            db.rollback()
            return {'code': 404, 'message': '报工记录不存在'}

        db.execute("DELETE FROM prod_report WHERE id=?", (report_id,))
        _recalculate_task_and_workorder(
            db,
            report['task_id'],
            report['workorder_id'],
        )
        db.commit()
        return {'code': 0, 'message': '删除成功'}
    except Exception:
        db.rollback()
        raise


@production_bp.route('/api/prod/report/delete', methods=['POST'])
@login_required
def prod_report_delete():
    data = request.get_json(silent=True) or {}
    result = _delete_report(data.get('id'))
    status = result['code'] if result.get('code', 0) >= 400 else 200
    return jsonify(result), status
