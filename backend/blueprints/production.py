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
    crud_update,
    crud_delete,
    gen_no_in_transaction,
    permission_required,
)
from services.production_flow import (
    BusinessError,
    save_batch,
    save_plan,
    save_sales_order,
    save_workorder,
    release_workorder,
    generate_tasks,
    generate_material_requirements,
    post_report,
    task_availability,
    transition_status,
)

production_bp = Blueprint('production', __name__)

_sales_write = permission_required('prod:sales:write')
_sales_read = permission_required('prod:sales:read')
_plan_write = permission_required('prod:plan:write')
_plan_read = permission_required('prod:plan:read')
_batch_write = permission_required('prod:batch:write')
_batch_read = permission_required('prod:batch:read')
_workorder_write = permission_required('prod:workorder:write')
_workorder_read = permission_required('prod:workorder:read')
_task_write = permission_required('prod:task:write')
_task_read = permission_required('prod:task:read')
_report_create = permission_required('prod:report:create')
_report_read = permission_required('prod:report:read')
_report_review = permission_required('prod:report:review')
_report_post = permission_required('prod:report:post')

_QUANTITY_QUANTUM = Decimal('0.000001')


def _guard_legacy_mutation(table, record_id, allowed_statuses, message):
    row = get_db().execute(
        f'SELECT status FROM {table} WHERE id=?', (record_id,)
    ).fetchone()
    if not row:
        return jsonify({'code': 404, 'message': '记录不存在'}), 404
    if row['status'] not in allowed_statuses:
        return jsonify({'code': 400, 'message': message}), 400
    return None


def _legacy_write_disabled(message):
    return jsonify({
        'code': 410,
        'message': message,
        'data': {'use': 'save'},
    }), 410


def _legacy_safe_update(table, data, allowed_fields, allowed_statuses, blocked_message):
    blocked = _guard_legacy_mutation(table, data.get('id'), allowed_statuses, blocked_message)
    if blocked:
        return blocked
    unknown = set(data) - ({'id'} | set(allowed_fields))
    if unknown:
        return jsonify({'code': 400, 'message': '旧接口禁止修改关联、数量或系统计算字段'}), 400
    if not (set(data) & set(allowed_fields)):
        return jsonify({'code': 400, 'message': '没有可修改的业务字段'}), 400
    payload = {'id': data['id']}
    payload.update({field: data[field] for field in allowed_fields if field in data})
    return jsonify(crud_update(table, payload))


def _legacy_safe_delete(table, record_id, allowed_statuses, blocked_message, dependencies=()):
    blocked = _guard_legacy_mutation(table, record_id, allowed_statuses, blocked_message)
    if blocked:
        return blocked
    db = get_db()
    for sql, message in dependencies:
        if db.execute(sql, (record_id,)).fetchone():
            return jsonify({'code': 409, 'message': message}), 409
    return jsonify(crud_delete(table, record_id))


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
@_sales_read
def prod_sales_list():
    db = get_db()
    page, size = int(request.args.get('page', 1)), int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute('SELECT COUNT(*) FROM prod_sales_order').fetchone()[0]
    sales_sort_fields = {
        'id': 's.id', 'order_no': 's.order_no', 'customer_name': 'COALESCE(c.customer_name,s.customer)',
        'total_amount': 's.total_amount', 'delivery_date': 's.delivery_date',
        'status': 's.status', 'created_at': 's.created_at',
    }
    order_by = _manual_or_field_sort(request.args, sales_sort_fields, 's', 'prod/sales')
    rows = db.execute(
        '''SELECT s.*,COALESCE(c.customer_name,s.customer) AS customer_name,
                  COUNT(i.id) AS line_count
           FROM prod_sales_order s
           LEFT JOIN base_customer c ON c.id=s.customer_id
           LEFT JOIN prod_sales_order_item i ON i.order_id=s.id
           GROUP BY s.id ORDER BY {order_by} LIMIT ? OFFSET ?'''.format(order_by=order_by), (size, offset)
    ).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(row) for row in rows], 'total': total}})


@production_bp.route('/api/prod/sales/<int:order_id>')
@_sales_read
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
@_sales_write
def prod_sales_save():
    try:
        result = save_sales_order(get_db(), request.get_json(silent=True) or {}, session.get('user_id'))
        return jsonify({'code': 0, 'data': result, 'message': '保存成功'})
    except BusinessError as exc:
        return jsonify({'code': exc.status, 'message': str(exc), 'data': exc.details}), exc.status


@production_bp.route('/api/prod/sales/add', methods=['POST'])
@_sales_write
def prod_sales_add():
    return _legacy_write_disabled('旧销售订单新增接口已停用，请使用 /api/prod/sales/save 提交订单及明细')


@production_bp.route('/api/prod/sales/update', methods=['POST'])
@_sales_write
def prod_sales_update():
    data = request.get_json(silent=True) or {}
    if 'status' in data:
        try:
            return jsonify({'code': 0, 'data': transition_status(get_db(), 'sales', data.get('id'), data.get('status'), session.get('user_id'))})
        except BusinessError as exc:
            return jsonify({'code': exc.status, 'message': str(exc)}), exc.status
    return _legacy_safe_update('prod_sales_order', data,
        {'customer', 'contact', 'phone', 'delivery_date', 'remark'}, {0},
        '已确认或已执行的销售订单不可修改')


@production_bp.route('/api/prod/sales/delete', methods=['POST'])
@_sales_write
def prod_sales_delete():
    record_id = (request.get_json(silent=True) or {}).get('id')
    return _legacy_safe_delete('prod_sales_order', record_id, {0}, '只有草稿销售订单可以删除', (
        ('SELECT 1 FROM prod_sales_order_item WHERE order_id=? LIMIT 1', '销售订单已有明细，不能直接删除'),
        ('SELECT 1 FROM prod_plan WHERE sales_order_id=? LIMIT 1', '销售订单已有生产计划，不能删除'),
    ))


@production_bp.route('/api/prod/plan/list')
@_plan_read
def prod_plan_list():
    db = get_db()
    page, size = int(request.args.get('page', 1)), int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute('SELECT COUNT(*) FROM prod_plan').fetchone()[0]
    plan_sort_fields = {
        'id': 'p.id', 'plan_no': 'p.plan_no', 'sales_order_no': 's.order_no',
        'plan_type': 'p.plan_type', 'status': 'p.status', 'created_at': 'p.created_at',
    }
    order_by = _manual_or_field_sort(request.args, plan_sort_fields, 'p', 'prod/plan')
    rows = db.execute(
        '''SELECT p.*,s.order_no AS sales_order_no,COUNT(i.id) AS line_count
           FROM prod_plan p LEFT JOIN prod_sales_order s ON s.id=p.sales_order_id
           LEFT JOIN prod_plan_item i ON i.plan_id=p.id
           GROUP BY p.id ORDER BY {order_by} LIMIT ? OFFSET ?'''.format(order_by=order_by), (size, offset)
    ).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(row) for row in rows], 'total': total}})


@production_bp.route('/api/prod/plan/<int:plan_id>')
@_plan_read
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
@_plan_read
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
@_plan_write
def prod_plan_save():
    try:
        result = save_plan(get_db(), request.get_json(silent=True) or {}, session.get('user_id'))
        return jsonify({'code': 0, 'data': result, 'message': '保存成功'})
    except BusinessError as exc:
        return jsonify({'code': exc.status, 'message': str(exc), 'data': exc.details}), exc.status


@production_bp.route('/api/prod/batch/list')
@_batch_read
def prod_batch_list():
    db = get_db()
    page, size = int(request.args.get('page', 1)), int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute('SELECT COUNT(*) FROM prod_batch').fetchone()[0]
    batch_sort_fields = {
        'id': 'b.id', 'batch_no': 'b.batch_no', 'plan_no': 'pl.plan_no',
        'product_name': 'p.product_name', 'workshop_name': 'w.workshop_name',
        'planned_qty': 'b.planned_qty', 'status': 'b.status', 'created_at': 'b.created_at',
    }
    order_by = _manual_or_field_sort(request.args, batch_sort_fields, 'b', 'prod/batch')
    rows = db.execute(
        '''SELECT b.*,pl.plan_no,p.product_name,w.workshop_name,s.order_no AS sales_order_no
           FROM prod_batch b LEFT JOIN prod_plan pl ON pl.id=b.plan_id
           LEFT JOIN base_product p ON p.id=b.product_id
           LEFT JOIN base_workshop w ON w.id=b.workshop_id
           LEFT JOIN prod_sales_order s ON s.id=b.sales_order_id
           ORDER BY {order_by} LIMIT ? OFFSET ?'''.format(order_by=order_by), (size, offset)
    ).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(row) for row in rows], 'total': total}})


@production_bp.route('/api/prod/batch/save', methods=['POST'])
@_batch_write
def prod_batch_save():
    try:
        result = save_batch(get_db(), request.get_json(silent=True) or {}, session.get('user_id'))
        return jsonify({'code': 0, 'data': result, 'message': '保存成功'})
    except BusinessError as exc:
        return jsonify({'code': exc.status, 'message': str(exc), 'data': exc.details}), exc.status


@production_bp.route('/api/prod/batch/status', methods=['POST'])
@_batch_write
def prod_batch_status():
    data = request.get_json(silent=True) or {}
    try:
        result = transition_status(get_db(), 'batch', data.get('id'), data.get('status'),
                                   session.get('user_id'), data.get('remark') or '')
        return jsonify({'code': 0, 'data': result})
    except BusinessError as exc:
        return jsonify({'code': exc.status, 'message': str(exc), 'data': exc.details}), exc.status


@production_bp.route('/api/prod/plan/add', methods=['POST'])
@_plan_write
def prod_plan_add():
    return _legacy_write_disabled('旧生产计划新增接口已停用，请使用 /api/prod/plan/save 提交计划及明细')


@production_bp.route('/api/prod/plan/update', methods=['POST'])
@_plan_write
def prod_plan_update():
    data = request.get_json(silent=True) or {}
    if 'status' in data:
        try:
            return jsonify({'code': 0, 'data': transition_status(get_db(), 'plan', data.get('id'), data.get('status'), session.get('user_id'))})
        except BusinessError as exc:
            return jsonify({'code': exc.status, 'message': str(exc)}), exc.status
    return _legacy_safe_update('prod_plan', data,
        {'plan_type', 'start_date', 'end_date', 'remark'}, {0},
        '已发布或已执行的生产计划不可修改')


@production_bp.route('/api/prod/plan/delete', methods=['POST'])
@_plan_write
def prod_plan_delete():
    record_id = (request.get_json(silent=True) or {}).get('id')
    return _legacy_safe_delete('prod_plan', record_id, {0}, '只有草稿生产计划可以删除', (
        ('SELECT 1 FROM prod_plan_item WHERE plan_id=? LIMIT 1', '生产计划已有明细，不能直接删除'),
        ('SELECT 1 FROM prod_batch WHERE plan_id=? LIMIT 1', '生产计划已有生产批次，不能删除'),
    ))


@production_bp.route('/api/prod/workorder/list')
@_workorder_read
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
        ws.workshop_name,pl.plan_no,s.order_no AS sales_order_no,
        b.batch_no,r.route_name
        FROM prod_workorder w
        LEFT JOIN base_product p ON w.product_id=p.id
        LEFT JOIN base_workshop ws ON w.workshop_id=ws.id
        LEFT JOIN prod_plan pl ON w.plan_id=pl.id
        LEFT JOIN prod_sales_order s ON w.sales_order_id=s.id
        LEFT JOIN prod_batch b ON w.production_batch_id=b.id
        LEFT JOIN base_process_route r ON w.route_id=r.id
        {where}
        ORDER BY {order_by} LIMIT ? OFFSET ?''',
        params + [size, offset],
    ).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@production_bp.route('/api/prod/workorder/options')
@_workorder_read
def prod_workorder_options():
    db = get_db()
    plan_item_id = request.args.get('plan_item_id')
    batch_id = request.args.get('batch_id')
    if batch_id:
        source = db.execute(
            '''SELECT b.plan_item_id,b.plan_id,b.sales_order_id,b.product_id,b.workshop_id,
                      b.planned_qty AS remaining_qty,b.id AS production_batch_id,b.batch_no
               FROM prod_batch b WHERE b.id=? AND b.status<>4''', (batch_id,)
        ).fetchone()
    else:
        source = db.execute(
            '''SELECT i.id AS plan_item_id,i.plan_id,p.sales_order_id,i.product_id,i.workshop_id,
                      MAX(0,i.planned_qty-COALESCE((SELECT SUM(b.planned_qty) FROM prod_batch b
                        WHERE b.plan_item_id=i.id AND b.status<>4),0)) AS remaining_qty,
                      NULL AS production_batch_id,NULL AS batch_no
               FROM prod_plan_item i JOIN prod_plan p ON p.id=i.plan_id WHERE i.id=?''',
            (plan_item_id,),
        ).fetchone()
    if not source:
        return jsonify({'code': 404, 'message': '生产计划明细或批次不存在'}), 404
    routes = db.execute(
        '''SELECT id,route_name,version,workshop_id FROM base_process_route
           WHERE product_id=? AND workshop_id=? AND status=1 ORDER BY version DESC,id DESC''',
        (source['product_id'], source['workshop_id']),
    ).fetchall()
    result = dict(source)
    result['routes'] = [dict(route) for route in routes]
    return jsonify({'code': 0, 'data': result})


@production_bp.route('/api/prod/workorder/save', methods=['POST'])
@_workorder_write
def prod_workorder_save():
    try:
        result = save_workorder(get_db(), request.get_json(silent=True) or {}, session.get('user_id'))
        return jsonify({'code': 0, 'data': result, 'message': '保存成功'})
    except BusinessError as exc:
        return jsonify({'code': exc.status, 'message': str(exc), 'data': exc.details}), exc.status


@production_bp.route('/api/prod/workorder/<int:workorder_id>/release', methods=['POST'])
@_workorder_write
def prod_workorder_release(workorder_id):
    data = request.get_json(silent=True) or {}
    try:
        result = release_workorder(get_db(), workorder_id, session.get('user_id'), data.get('remark') or '')
        return jsonify({'code': 0, 'data': result, 'message': '工单已下达并冻结路线与BOM'})
    except BusinessError as exc:
        return jsonify({'code': exc.status, 'message': str(exc), 'data': exc.details}), exc.status


@production_bp.route('/api/prod/workorder/<int:workorder_id>/generate-tasks', methods=['POST'])
@_workorder_write
def prod_workorder_generate_tasks(workorder_id):
    try:
        result = generate_tasks(get_db(), workorder_id, session.get('user_id'))
        return jsonify({'code': 0, 'data': result, 'message': '任务已按冻结路线生成'})
    except BusinessError as exc:
        return jsonify({'code': exc.status, 'message': str(exc), 'data': exc.details}), exc.status


@production_bp.route('/api/prod/workorder/<int:workorder_id>/generate-materials', methods=['POST'])
@_workorder_write
def prod_workorder_generate_materials(workorder_id):
    try:
        result = generate_material_requirements(get_db(), workorder_id, session.get('user_id'))
        return jsonify({'code': 0, 'data': result, 'message': '领料需求已按冻结BOM生成'})
    except BusinessError as exc:
        return jsonify({'code': exc.status, 'message': str(exc), 'data': exc.details}), exc.status


@production_bp.route('/api/prod/workorder/<int:workorder_id>/executable-steps')
@_workorder_read
def prod_workorder_executable_steps(workorder_id):
    db = get_db()
    workorder = db.execute('SELECT planned_qty FROM prod_workorder WHERE id=?', (workorder_id,)).fetchone()
    if not workorder:
        return jsonify({'code': 404, 'message': '工单不存在'}), 404
    rows = db.execute(
        '''SELECT s.*,t.id AS task_id,COALESCE(t.completed_qty,0) AS reported_qty,
                  COALESCE(t.defect_qty,0) AS defect_qty
           FROM prod_workorder_route_step s
           JOIN prod_workorder_route_snapshot h ON h.id=s.snapshot_id
           LEFT JOIN prod_task t ON t.route_step_id=s.id
           WHERE h.workorder_id=? ORDER BY s.step_no''', (workorder_id,)
    ).fetchall()
    result, previous = [], float(workorder['planned_qty'])
    for row in rows:
        item = dict(row)
        item['upstream_qty'] = previous
        item['available_qty'] = max(0, previous - float(row['reported_qty']) - float(row['defect_qty']))
        previous = float(row['reported_qty'])
        result.append(item)
    return jsonify({'code': 0, 'data': result})


@production_bp.route('/api/prod/workorder/add', methods=['POST'])
@_workorder_write
def prod_workorder_add():
    return _legacy_write_disabled('旧工单新增接口已停用，请使用 /api/prod/workorder/save 创建冻结快照工单')


@production_bp.route('/api/prod/workorder/update', methods=['POST'])
@_workorder_write
def prod_workorder_update():
    data = request.get_json(silent=True) or {}
    if 'status' in data:
        try:
            return jsonify({'code': 0, 'data': transition_status(get_db(), 'workorder', data.get('id'), data.get('status'), session.get('user_id'))})
        except BusinessError as exc:
            return jsonify({'code': exc.status, 'message': str(exc)}), exc.status
    return _legacy_safe_update('prod_workorder', data,
        {'priority', 'start_date', 'end_date', 'remark'}, {0},
        '已下达工单不可修改，请新建工单')


@production_bp.route('/api/prod/workorder/delete', methods=['POST'])
@_workorder_write
def prod_workorder_delete():
    record_id = (request.get_json(silent=True) or {}).get('id')
    return _legacy_safe_delete('prod_workorder', record_id, {0}, '只有草稿工单可以删除', (
        ('SELECT 1 FROM prod_task WHERE workorder_id=? LIMIT 1', '工单已有任务，不能直接删除'),
        ('SELECT 1 FROM prod_report WHERE workorder_id=? LIMIT 1', '工单已有报工，不能删除'),
        ('SELECT 1 FROM prod_material_req WHERE workorder_id=? LIMIT 1', '工单已有领料需求，不能删除'),
    ))


@production_bp.route('/api/prod/task/list')
@_task_read
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
@_task_write
def prod_task_add():
    return _legacy_write_disabled('旧任务新增接口已停用，请使用工单生成任务接口')


@production_bp.route('/api/prod/task/update', methods=['POST'])
@_task_write
def prod_task_update():
    data = request.get_json(silent=True) or {}
    if 'status' in data:
        try:
            return jsonify({'code': 0, 'data': transition_status(get_db(), 'task', data.get('id'), data.get('status'), session.get('user_id'))})
        except BusinessError as exc:
            return jsonify({'code': exc.status, 'message': str(exc)}), exc.status
    return _legacy_safe_update('prod_task', data,
        {'assigned_to', 'start_time', 'end_time', 'remark'}, {0},
        '已执行任务不可修改')


@production_bp.route('/api/prod/task/delete', methods=['POST'])
@_task_write
def prod_task_delete():
    record_id = (request.get_json(silent=True) or {}).get('id')
    return _legacy_safe_delete('prod_task', record_id, {0}, '只有待执行任务可以删除', (
        ('SELECT 1 FROM prod_report WHERE task_id=? LIMIT 1', '任务已有报工，不能删除'),
    ))


@production_bp.route('/api/prod/report/list')
@_report_read
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
@_report_create
def prod_report_add():
    result = _create_report(
        request.get_json(silent=True) or {},
        session.get('user_id'),
    )
    status = result['code'] if result.get('code', 0) >= 400 else 200
    return jsonify(result), status


@production_bp.route('/api/prod/report/gps', methods=['POST'])
@_report_create
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
            FROM prod_report WHERE {column}=? AND approval_status=2""",
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
    if data.get('controlled') is not True:
        return {'code': 400, 'message': '报工必须通过受控流程提交（controlled=true）'}
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

        controlled = True
        if controlled:
            availability = task_availability(db, task_id)
            requested_total = float(qualified + defect)
            if requested_total > availability['available_qty']:
                db.rollback()
                available = availability['available_qty']
                return {'code': 409, 'message': f'当前任务可执行数量为 {available:g}',
                        'data': availability}

        report_no = gen_no_in_transaction(db, 'BR')
        cursor = db.execute(
            """INSERT INTO prod_report
               (report_no, task_id, workorder_id, process_id, user_id,
                qualified_qty, defect_qty, approval_status, posted_at, remark, client_operation_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                report_no,
                task_id,
                workorder_id,
                process_id,
                user_id,
                float(qualified),
                float(defect),
                0 if controlled else 2,
                None if controlled else datetime.datetime.now().isoformat(sep=' ', timespec='seconds'),
                data.get('remark'),
                client_operation_id,
            ),
        )
        if not controlled:
            _recalculate_task_and_workorder(db, task_id, workorder_id)
        db.commit()
        return {
            'code': 0,
            'data': {'id': cursor.lastrowid, 'duplicate': False},
            'message': '报工已提交，等待审核' if controlled else '报工成功',
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
            """SELECT task_id, workorder_id, approval_status
               FROM prod_report WHERE id=?""",
            (report_id,),
        ).fetchone()
        if not report:
            db.rollback()
            return {'code': 404, 'message': '报工记录不存在'}
        if report['approval_status'] not in (0, 3):
            db.rollback()
            return {'code': 400, 'message': '只有待审核或已驳回的报工可以删除'}

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
@_report_review
def prod_report_delete():
    data = request.get_json(silent=True) or {}
    result = _delete_report(data.get('id'))
    status = result['code'] if result.get('code', 0) >= 400 else 200
    return jsonify(result), status


@production_bp.route('/api/prod/report/<int:report_id>/approve', methods=['POST'])
@_report_review
def prod_report_approve(report_id):
    try:
        result = transition_status(get_db(), 'report', report_id, 1, session.get('user_id'), '报工审核通过')
        return jsonify({'code': 0, 'data': result})
    except BusinessError as exc:
        return jsonify({'code': exc.status, 'message': str(exc), 'data': exc.details}), exc.status


@production_bp.route('/api/prod/report/<int:report_id>/post', methods=['POST'])
@_report_post
def prod_report_post(report_id):
    try:
        result = post_report(get_db(), report_id, session.get('user_id'), '报工记账')
        return jsonify({'code': 0, 'data': result})
    except BusinessError as exc:
        return jsonify({'code': exc.status, 'message': str(exc), 'data': exc.details}), exc.status


@production_bp.route('/api/prod/report/<int:report_id>/reject', methods=['POST'])
@_report_review
def prod_report_reject(report_id):
    try:
        result = transition_status(get_db(), 'report', report_id, 3, session.get('user_id'),
                                   (request.get_json(silent=True) or {}).get('remark') or '报工驳回')
        return jsonify({'code': 0, 'data': result})
    except BusinessError as exc:
        return jsonify({'code': exc.status, 'message': str(exc), 'data': exc.details}), exc.status


@production_bp.route('/api/prod/task/<int:task_id>/availability')
@login_required
def prod_task_availability(task_id):
    try:
        return jsonify({'code': 0, 'data': task_availability(get_db(), task_id)})
    except BusinessError as exc:
        return jsonify({'code': exc.status, 'message': str(exc), 'data': exc.details}), exc.status
