"""生产管理蓝图"""
import datetime
import math
import sqlite3
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
from services.production_flow import (
    BusinessError,
    save_batch,
    save_plan,
    save_sales_order,
    transition_status,
)

production_bp = Blueprint('production', __name__)

_QUANTITY_QUANTUM = Decimal('0.000001')


def _safe_sort(args, fields, default):
    """Return a validated SQL ORDER BY fragment for paginated production lists."""
    requested = args.get('sort', '')
    direction = str(args.get('order', 'DESC')).upper()
    column = fields.get(requested, default)
    if direction not in ('ASC', 'DESC'):
        direction = 'DESC'
    return f'{column} {direction}'


def _manual_or_field_sort(args, fields, alias, table_key):
    if args.get('sort'):
        return _safe_sort(args, fields, f'{alias}.id')
    return f'''CASE WHEN (
        SELECT position FROM sys_table_order
        WHERE table_key='{table_key}' AND record_id={alias}.id
    ) IS NULL THEN 1 ELSE 0 END,
    (SELECT position FROM sys_table_order
     WHERE table_key='{table_key}' AND record_id={alias}.id) ASC,
    {alias}.id DESC'''


@production_bp.route('/api/prod/sales/list')
@login_required
def prod_sales_list():
    db = get_db()
    page, size = int(request.args.get('page', 1)), int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute('SELECT COUNT(*) FROM prod_sales_order').fetchone()[0]
    rows = db.execute(
        '''SELECT s.*,COALESCE(c.customer_name,s.customer) AS customer_name,
                  COUNT(i.id) AS line_count
           FROM prod_sales_order s
           LEFT JOIN base_customer c ON c.id=s.customer_id
           LEFT JOIN prod_sales_order_item i ON i.order_id=s.id
           GROUP BY s.id ORDER BY s.id DESC LIMIT ? OFFSET ?''', (size, offset)
    ).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(row) for row in rows], 'total': total}})


@production_bp.route('/api/prod/sales/<int:order_id>')
@login_required
def prod_sales_detail(order_id):
    db = get_db()
    header = db.execute(
        '''SELECT s.*,COALESCE(c.customer_name,s.customer) AS customer_name
           FROM prod_sales_order s LEFT JOIN base_customer c ON c.id=s.customer_id
           WHERE s.id=?''', (order_id,)
    ).fetchone()
    if not header:
        return jsonify({'code': 404, 'message': '销售订单不存在'}), 404
    items = db.execute(
        '''SELECT i.*,p.product_name,p.code AS product_code,p.unit
           FROM prod_sales_order_item i JOIN base_product p ON p.id=i.product_id
           WHERE i.order_id=? ORDER BY i.id''', (order_id,)
    ).fetchall()
    return jsonify({'code': 0, 'data': {'header': dict(header), 'items': [dict(row) for row in items]}})


@production_bp.route('/api/prod/sales/save', methods=['POST'])
@login_required
def prod_sales_save():
    try:
        result = save_sales_order(get_db(), request.get_json(silent=True) or {}, session.get('user_id'))
        return jsonify({'code': 0, 'data': result, 'message': '保存成功'})
    except BusinessError as exc:
        return jsonify({'code': exc.status, 'message': str(exc), 'data': exc.details}), exc.status


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
    db = get_db()
    page, size = int(request.args.get('page', 1)), int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute('SELECT COUNT(*) FROM prod_plan').fetchone()[0]
    rows = db.execute(
        '''SELECT p.*,s.order_no AS sales_order_no,COUNT(i.id) AS line_count
           FROM prod_plan p LEFT JOIN prod_sales_order s ON s.id=p.sales_order_id
           LEFT JOIN prod_plan_item i ON i.plan_id=p.id
           GROUP BY p.id ORDER BY p.id DESC LIMIT ? OFFSET ?''', (size, offset)
    ).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(row) for row in rows], 'total': total}})


@production_bp.route('/api/prod/plan/<int:plan_id>')
@login_required
def prod_plan_detail(plan_id):
    db = get_db()
    header = db.execute(
        '''SELECT p.*,s.order_no AS sales_order_no FROM prod_plan p
           LEFT JOIN prod_sales_order s ON s.id=p.sales_order_id WHERE p.id=?''', (plan_id,)
    ).fetchone()
    if not header:
        return jsonify({'code': 404, 'message': '生产计划不存在'}), 404
    items = db.execute(
        '''SELECT i.*,p.product_name,p.code AS product_code,w.workshop_name
           FROM prod_plan_item i JOIN base_product p ON p.id=i.product_id
           LEFT JOIN base_workshop w ON w.id=i.workshop_id
           WHERE i.plan_id=? ORDER BY i.id''', (plan_id,)
    ).fetchall()
    return jsonify({'code': 0, 'data': {'header': dict(header), 'items': [dict(row) for row in items]}})


@production_bp.route('/api/prod/plan/source/<int:sales_order_id>')
@login_required
def prod_plan_source(sales_order_id):
    db = get_db()
    header = db.execute('SELECT * FROM prod_sales_order WHERE id=?', (sales_order_id,)).fetchone()
    if not header:
        return jsonify({'code': 404, 'message': '销售订单不存在'}), 404
    items = db.execute(
        '''SELECT i.*,p.product_name,p.code AS product_code,p.unit,
                  MAX(0,i.quantity-i.delivered_qty-COALESCE((
                    SELECT SUM(pi.planned_qty) FROM prod_plan_item pi
                    JOIN prod_plan pp ON pp.id=pi.plan_id
                    WHERE pi.sales_order_item_id=i.id AND pp.status<>4
                  ),0)) AS remaining_qty
           FROM prod_sales_order_item i JOIN base_product p ON p.id=i.product_id
           WHERE i.order_id=? ORDER BY i.id''', (sales_order_id,)
    ).fetchall()
    return jsonify({'code': 0, 'data': {'header': dict(header),
        'items': [dict(row) for row in items if row['remaining_qty'] > 0]}})


@production_bp.route('/api/prod/plan/save', methods=['POST'])
@login_required
def prod_plan_save():
    try:
        result = save_plan(get_db(), request.get_json(silent=True) or {}, session.get('user_id'))
        return jsonify({'code': 0, 'data': result, 'message': '保存成功'})
    except BusinessError as exc:
        return jsonify({'code': exc.status, 'message': str(exc), 'data': exc.details}), exc.status


@production_bp.route('/api/prod/batch/list')
@login_required
def prod_batch_list():
    db = get_db()
    page, size = int(request.args.get('page', 1)), int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute('SELECT COUNT(*) FROM prod_batch').fetchone()[0]
    rows = db.execute(
        '''SELECT b.*,pl.plan_no,p.product_name,w.workshop_name,s.order_no AS sales_order_no
           FROM prod_batch b LEFT JOIN prod_plan pl ON pl.id=b.plan_id
           LEFT JOIN base_product p ON p.id=b.product_id
           LEFT JOIN base_workshop w ON w.id=b.workshop_id
           LEFT JOIN prod_sales_order s ON s.id=b.sales_order_id
           ORDER BY b.id DESC LIMIT ? OFFSET ?''', (size, offset)
    ).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(row) for row in rows], 'total': total}})


@production_bp.route('/api/prod/batch/save', methods=['POST'])
@login_required
def prod_batch_save():
    try:
        result = save_batch(get_db(), request.get_json(silent=True) or {}, session.get('user_id'))
        return jsonify({'code': 0, 'data': result, 'message': '保存成功'})
    except BusinessError as exc:
        return jsonify({'code': exc.status, 'message': str(exc), 'data': exc.details}), exc.status


@production_bp.route('/api/prod/batch/status', methods=['POST'])
@login_required
def prod_batch_status():
    data = request.get_json(silent=True) or {}
    try:
        result = transition_status(get_db(), 'batch', data.get('id'), data.get('status'),
                                   session.get('user_id'), data.get('remark') or '')
        return jsonify({'code': 0, 'data': result})
    except BusinessError as exc:
        return jsonify({'code': exc.status, 'message': str(exc), 'data': exc.details}), exc.status


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
    workorder_sort_fields = {
        'id': 'w.id', 'order_no': 'w.order_no', 'product_name': 'p.product_name',
        'planned_qty': 'w.planned_qty', 'completed_qty': 'w.completed_qty',
        'status': 'w.status', 'priority': 'w.priority', 'created_at': 'w.created_at',
    }
    order_by = _manual_or_field_sort(
        request.args, workorder_sort_fields, 'w', 'prod/workorder'
    )
    rows = db.execute(f'''SELECT w.*, p.product_name, p.code as product_code,
        ws.workshop_name
        FROM prod_workorder w
        LEFT JOIN base_product p ON w.product_id=p.id
        LEFT JOIN base_workshop ws ON w.workshop_id=ws.id
        {where}
        ORDER BY {order_by} LIMIT ? OFFSET ?''',
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
    clauses = []
    params = []
    if keyword:
        clauses.append("""(
            t.task_no LIKE ? OR w.order_no LIKE ? OR pr.process_name LIKE ?
        )""")
        params = [f"%{keyword}%"] * 3
    if request.args.get('mine') == '1':
        clauses.append("t.assigned_to=?")
        params.append(session.get('user_id'))
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    total = db.execute(
        f'''SELECT COUNT(*) as cnt
            FROM prod_task t
            LEFT JOIN prod_workorder w ON t.workorder_id=w.id
            LEFT JOIN base_process pr ON t.process_id=pr.id
            LEFT JOIN sys_user u ON t.assigned_to=u.id
            {where}''',
        params,
    ).fetchone()['cnt']
    task_sort_fields = {
        'id': 't.id', 'task_no': 't.task_no', 'workorder_no': 'w.order_no',
        'process_name': 'pr.process_name', 'planned_qty': 't.planned_qty',
        'completed_qty': 't.completed_qty', 'status': 't.status',
        'priority': 't.priority', 'created_at': 't.created_at',
    }
    order_by = _manual_or_field_sort(
        request.args, task_sort_fields, 't', 'prod/task'
    )
    rows = db.execute(f'''SELECT t.*, w.order_no as workorder_no, pr.process_name,
        u.real_name as assigned_name
        FROM prod_task t
        LEFT JOIN prod_workorder w ON t.workorder_id=w.id
        LEFT JOIN base_process pr ON t.process_id=pr.id
        LEFT JOIN sys_user u ON t.assigned_to=u.id
        {where}
        ORDER BY {order_by} LIMIT ? OFFSET ?''',
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
    clauses = []
    params = []
    if request.args.get('mine') == '1':
        clauses.append("r.user_id=?")
        params.append(session.get('user_id'))
    if request.args.get('date') == 'today':
        clauses.append("DATE(r.report_time)=?")
        params.append(datetime.date.today().isoformat())
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    total = db.execute(
        f"SELECT COUNT(*) as cnt FROM prod_report r{where}",
        params,
    ).fetchone()['cnt']
    report_sort_fields = {
        'id': 'r.id', 'report_time': 'r.report_time', 'workorder_no': 'w.order_no',
        'task_no': 't.task_no', 'process_name': 'pr.process_name',
        'report_qty': 'r.report_qty', 'qualified_qty': 'r.qualified_qty',
        'defect_qty': 'r.defect_qty', 'created_at': 'r.created_at',
    }
    order_by = _manual_or_field_sort(
        request.args, report_sort_fields, 'r', 'prod/report'
    )
    rows = db.execute(f'''SELECT r.*, t.task_no, w.order_no as workorder_no,
        pr.process_name, u.real_name
        FROM prod_report r
        LEFT JOIN prod_task t ON r.task_id=t.id
        LEFT JOIN prod_workorder w ON r.workorder_id=w.id
        LEFT JOIN base_process pr ON r.process_id=pr.id
        LEFT JOIN sys_user u ON r.user_id=u.id
        {where}
        ORDER BY {order_by} LIMIT ? OFFSET ?''', params + [size, offset]).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@production_bp.route('/api/collector/summary')
@login_required
def collector_summary():
    """Return current-user, current-day metrics for the collector home page."""
    db = get_db()
    user_id = session.get('user_id')
    today = datetime.date.today().isoformat()
    pending_tasks = db.execute(
        """SELECT COUNT(*) AS count FROM prod_task
           WHERE assigned_to=? AND status<3""",
        (user_id,),
    ).fetchone()['count']
    today_reports = db.execute(
        """SELECT COUNT(*) AS count FROM prod_report
           WHERE user_id=? AND DATE(report_time)=?""",
        (user_id, today),
    ).fetchone()['count']
    pending_inspections = db.execute(
        "SELECT COUNT(*) AS count FROM qm_incoming_inspection WHERE status=0"
    ).fetchone()['count']
    return jsonify({'code': 0, 'data': {
        'pending_tasks': pending_tasks,
        'today_reports': today_reports,
        'pending_inspections': pending_inspections,
    }})


def _collector_tasks_for_workorder(db, workorder_id, user_id):
    rows = db.execute(
        """SELECT t.*, w.order_no AS workorder_no, p.product_name,
                  p.code AS product_code, pr.process_name
           FROM prod_task t
           JOIN prod_workorder w ON t.workorder_id=w.id
           LEFT JOIN base_product p ON w.product_id=p.id
           LEFT JOIN base_process pr ON t.process_id=pr.id
           WHERE t.workorder_id=? AND t.assigned_to=? AND t.status<3
           ORDER BY t.id""",
        (workorder_id, user_id),
    ).fetchall()
    return [dict(row) for row in rows]


@production_bp.route('/api/collector/barcode/<path:code>')
@login_required
def collector_barcode(code):
    """Resolve exact workorder, task, or product codes for collector scans."""
    normalized = (code or '').strip()
    if not normalized:
        return jsonify({'code': 400, 'message': '条码不能为空'}), 400

    db = get_db()
    user_id = session.get('user_id')
    workorder = db.execute(
        """SELECT w.*, p.product_name, p.code AS product_code,
                  ws.workshop_name
           FROM prod_workorder w
           LEFT JOIN base_product p ON w.product_id=p.id
           LEFT JOIN base_workshop ws ON w.workshop_id=ws.id
           WHERE UPPER(w.order_no)=UPPER(?)""",
        (normalized,),
    ).fetchone()
    if workorder:
        return jsonify({'code': 0, 'data': {
            'kind': 'workorder',
            'entity': dict(workorder),
            'tasks': _collector_tasks_for_workorder(db, workorder['id'], user_id),
        }})

    task = db.execute(
        """SELECT t.*, w.order_no AS workorder_no, p.product_name,
                  p.code AS product_code, pr.process_name
           FROM prod_task t
           JOIN prod_workorder w ON t.workorder_id=w.id
           LEFT JOIN base_product p ON w.product_id=p.id
           LEFT JOIN base_process pr ON t.process_id=pr.id
           WHERE UPPER(t.task_no)=UPPER(?) AND t.assigned_to=?""",
        (normalized, user_id),
    ).fetchone()
    if task:
        return jsonify({'code': 0, 'data': {
            'kind': 'task',
            'entity': dict(task),
            'tasks': [dict(task)] if task['status'] < 3 else [],
        }})

    product = db.execute(
        "SELECT * FROM base_product WHERE UPPER(code)=UPPER(?)",
        (normalized,),
    ).fetchone()
    if product:
        rows = db.execute(
            """SELECT DISTINCT w.id FROM prod_workorder w
               WHERE w.product_id=? AND w.status<3 ORDER BY w.id""",
            (product['id'],),
        ).fetchall()
        tasks = []
        for row in rows:
            tasks.extend(_collector_tasks_for_workorder(db, row['id'], user_id))
        return jsonify({'code': 0, 'data': {
            'kind': 'product',
            'entity': dict(product),
            'tasks': tasks,
        }})

    return jsonify({'code': 404, 'message': '未找到对应的工单、任务或产品'}), 404


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
    client_operation_id = data.get('client_operation_id')
    if client_operation_id is not None:
        if not isinstance(client_operation_id, str):
            return {'code': 400, 'message': '客户端操作编号不合法'}
        client_operation_id = client_operation_id.strip()
        if not client_operation_id or len(client_operation_id) > 80:
            return {'code': 400, 'message': '客户端操作编号不合法'}
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
        if client_operation_id:
            existing = db.execute(
                """SELECT id FROM prod_report
                   WHERE user_id=? AND client_operation_id=?""",
                (user_id, client_operation_id),
            ).fetchone()
            if existing:
                db.commit()
                return {
                    'code': 0,
                    'data': {'id': existing['id'], 'duplicate': True},
                    'message': '报工已同步',
                }
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
                qualified_qty, defect_qty, remark, client_operation_id)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                report_no,
                task_id,
                workorder_id,
                process_id,
                user_id,
                float(qualified),
                float(defect),
                data.get('remark'),
                client_operation_id,
            ),
        )
        _recalculate_task_and_workorder(db, task_id, workorder_id)
        db.commit()
        return {
            'code': 0,
            'data': {'id': cursor.lastrowid, 'duplicate': False},
            'message': '报工成功',
        }
    except sqlite3.IntegrityError:
        db.rollback()
        if client_operation_id:
            existing = db.execute(
                """SELECT id FROM prod_report
                   WHERE user_id=? AND client_operation_id=?""",
                (user_id, client_operation_id),
            ).fetchone()
            if existing:
                return {
                    'code': 0,
                    'data': {'id': existing['id'], 'duplicate': True},
                    'message': '报工已同步',
                }
        raise
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
