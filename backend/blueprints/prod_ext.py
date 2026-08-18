"""生产增强蓝图 - 工序转移、领料、委外、序列号、工时、包装"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete, gen_no, permission_required
from services.production_flow import (
    BusinessError, create_transfer, issue_material, receive_material,
    request_material, return_material,
)

prod_ext_bp = Blueprint('prod_ext', __name__)
_prod_ext_write = permission_required('prod:extension:write')
_prod_ext_read = permission_required('prod:extension:read')


def _legacy_ext_write_disabled():
    """Reject the former generic CRUD endpoints until domain services exist.

    These tables affect stock, supplier settlement and production traceability;
    accepting arbitrary columns here would bypass the validated action APIs.
    """
    return jsonify({
        'code': 410,
        'message': '该写入入口已停用，请使用受控业务操作',
        'data': {'use': 'domain_service'},
    }), 410


def _ext_order(args, fields, alias, table_key):
    requested = args.get('sort', '')
    direction = str(args.get('order', 'DESC')).upper()
    if requested in fields:
        return f"{fields[requested]} {'ASC' if direction == 'ASC' else 'DESC'}"
    return f'''CASE WHEN (SELECT position FROM sys_table_order
                    WHERE table_key='{table_key}' AND record_id={alias}.id) IS NULL THEN 1 ELSE 0 END,
                (SELECT position FROM sys_table_order
                    WHERE table_key='{table_key}' AND record_id={alias}.id) ASC,
                {alias}.id DESC'''


# ==================== 工序转移单 ====================
@prod_ext_bp.route('/api/prod/transfer/list')
@_prod_ext_read
def transfer_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM prod_transfer").fetchone()['cnt']
    order_by = _ext_order(request.args, {'id': 't.id', 'transfer_no': 't.transfer_no', 'workorder_no': 'w.order_no', 'quantity': 't.quantity', 'status': 't.status'}, 't', 'prod/transfer')
    rows = db.execute('''SELECT t.*, w.order_no as workorder_no,
        p1.process_name as from_process, p2.process_name as to_process
        FROM prod_transfer t
        LEFT JOIN prod_workorder w ON t.workorder_id=w.id
        LEFT JOIN base_process p1 ON t.from_process_id=p1.id
        LEFT JOIN base_process p2 ON t.to_process_id=p2.id
        ORDER BY {order_by} LIMIT ? OFFSET ?'''.format(order_by=order_by), (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@prod_ext_bp.route('/api/prod/transfer/add', methods=['POST'])
@_prod_ext_write
def transfer_add():
    try:
        result = create_transfer(get_db(), request.get_json(silent=True) or {}, session.get('user_id'))
        return jsonify({'code': 0, 'data': result, 'message': '工序转移成功'})
    except BusinessError as exc:
        return jsonify({'code': exc.status, 'message': str(exc), 'data': exc.details}), exc.status


# ==================== 生产领料 ====================
@prod_ext_bp.route('/api/prod/material/list')
@_prod_ext_read
def material_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM prod_material_req").fetchone()['cnt']
    order_by = _ext_order(request.args, {'id': 'm.id', 'req_no': 'm.req_no', 'workorder_no': 'w.order_no', 'product_name': 'p.product_name', 'required_qty': 'm.required_qty', 'status': 'm.status'}, 'm', 'prod/material')
    rows = db.execute('''SELECT m.*, w.order_no as workorder_no, p.product_name
        FROM prod_material_req m
        LEFT JOIN prod_workorder w ON m.workorder_id=w.id
        LEFT JOIN base_product p ON m.product_id=p.id
        ORDER BY {order_by} LIMIT ? OFFSET ?'''.format(order_by=order_by), (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@prod_ext_bp.route('/api/prod/material/add', methods=['POST'])
@_prod_ext_write
def material_add():
    return _legacy_ext_write_disabled()


@prod_ext_bp.route('/api/prod/material/update', methods=['POST'])
@_prod_ext_write
def material_update():
    return _legacy_ext_write_disabled()


def _material_action_result(action):
    try:
        return jsonify({'code': 0, 'data': action(), 'message': '操作成功'})
    except BusinessError as exc:
        return jsonify({'code': exc.status, 'message': str(exc), 'data': exc.details}), exc.status


@prod_ext_bp.route('/api/prod/material/<int:request_id>/request', methods=['POST'])
@_prod_ext_write
def material_request_action(request_id):
    data = request.get_json(silent=True) or {}
    return _material_action_result(lambda: request_material(
        get_db(), request_id, data.get('quantity'), session.get('user_id')
    ))


@prod_ext_bp.route('/api/prod/material/<int:request_id>/issue', methods=['POST'])
@_prod_ext_write
def material_issue_action(request_id):
    data = request.get_json(silent=True) or {}
    return _material_action_result(lambda: issue_material(
        get_db(), request_id, data.get('quantity'), data.get('warehouse_id'),
        data.get('location_id'), data.get('batch_no'), session.get('user_id')
    ))


@prod_ext_bp.route('/api/prod/material/<int:request_id>/receive', methods=['POST'])
@_prod_ext_write
def material_receive_action(request_id):
    data = request.get_json(silent=True) or {}
    return _material_action_result(lambda: receive_material(
        get_db(), request_id, data.get('quantity'), session.get('user_id')
    ))


@prod_ext_bp.route('/api/prod/material/<int:request_id>/return', methods=['POST'])
@_prod_ext_write
def material_return_action(request_id):
    data = request.get_json(silent=True) or {}
    return _material_action_result(lambda: return_material(
        get_db(), request_id, data.get('quantity'), session.get('user_id')
    ))


# ==================== 委外加工 ====================
@prod_ext_bp.route('/api/prod/outsource/list')
@_prod_ext_read
def outsource_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM prod_outsource").fetchone()['cnt']
    order_by = _ext_order(request.args, {'id': 'o.id', 'outsource_no': 'o.outsource_no', 'supplier_name': 's.supplier_name', 'product_name': 'p.product_name', 'status': 'o.status'}, 'o', 'prod/outsource')
    rows = db.execute('''SELECT o.*, s.supplier_name, p.product_name
        FROM prod_outsource o
        LEFT JOIN base_supplier s ON o.supplier_id=s.id
        LEFT JOIN base_product p ON o.product_id=p.id
        ORDER BY {order_by} LIMIT ? OFFSET ?'''.format(order_by=order_by), (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@prod_ext_bp.route('/api/prod/outsource/add', methods=['POST'])
@_prod_ext_write
def outsource_add():
    return _legacy_ext_write_disabled()


@prod_ext_bp.route('/api/prod/outsource/update', methods=['POST'])
@_prod_ext_write
def outsource_update():
    return _legacy_ext_write_disabled()


# ==================== 产品序列号 ====================
@prod_ext_bp.route('/api/prod/serial/list')
@_prod_ext_read
def serial_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    keyword = request.args.get('keyword', '')
    offset = (page - 1) * size
    order_by = _ext_order(request.args, {'id': 's.id', 'serial_no': 's.serial_no', 'product_name': 'p.product_name'}, 's', 'prod/serial')
    if keyword:
        total = db.execute("SELECT COUNT(*) as cnt FROM prod_serial WHERE serial_no LIKE ?", (f'%{keyword}%',)).fetchone()['cnt']
        rows = db.execute('''SELECT s.*, p.product_name FROM prod_serial s
            LEFT JOIN base_product p ON s.product_id=p.id
            WHERE s.serial_no LIKE ? ORDER BY {order_by} LIMIT ? OFFSET ?'''.format(order_by=order_by),
            (f'%{keyword}%', size, offset)).fetchall()
    else:
        total = db.execute("SELECT COUNT(*) as cnt FROM prod_serial").fetchone()['cnt']
        rows = db.execute('''SELECT s.*, p.product_name FROM prod_serial s
            LEFT JOIN base_product p ON s.product_id=p.id
            ORDER BY {order_by} LIMIT ? OFFSET ?'''.format(order_by=order_by), (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@prod_ext_bp.route('/api/prod/serial/generate', methods=['POST'])
@_prod_ext_write
def serial_generate():
    d = request.json
    product_id = d.get('product_id')
    workorder_id = d.get('workorder_id')
    count = int(d.get('count', 1))
    db = get_db()
    generated = []
    import datetime
    prefix = f"SN{datetime.datetime.now().strftime('%Y%m%d')}"
    for i in range(count):
        row = db.execute("SELECT MAX(id) as max_id FROM prod_serial").fetchone()
        seq = (row['max_id'] or 0) + 1
        serial_no = f"{prefix}{str(seq).zfill(6)}"
        db.execute("INSERT INTO prod_serial (serial_no, product_id, workorder_id) VALUES (?,?,?)",
                   (serial_no, product_id, workorder_id))
        generated.append(serial_no)
    db.commit()
    return jsonify({'code': 0, 'data': {'serials': generated}})


# ==================== 工时记录 ====================
@prod_ext_bp.route('/api/prod/labor/list')
@_prod_ext_read
def labor_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM prod_labor_time").fetchone()['cnt']
    order_by = _ext_order(request.args, {'id': 'l.id', 'real_name': 'u.real_name', 'task_no': 't.task_no', 'workorder_no': 'w.order_no', 'duration': 'l.duration'}, 'l', 'prod/labor')
    rows = db.execute('''SELECT l.*, u.real_name, t.task_no, w.order_no as workorder_no
        FROM prod_labor_time l
        LEFT JOIN sys_user u ON l.user_id=u.id
        LEFT JOIN prod_task t ON l.task_id=t.id
        LEFT JOIN prod_workorder w ON l.workorder_id=w.id
        ORDER BY {order_by} LIMIT ? OFFSET ?'''.format(order_by=order_by), (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@prod_ext_bp.route('/api/prod/labor/add', methods=['POST'])
@_prod_ext_write
def labor_add():
    return _legacy_ext_write_disabled()


@prod_ext_bp.route('/api/prod/labor/summary')
@_prod_ext_read
def labor_summary():
    db = get_db()
    rows = db.execute('''SELECT u.real_name, SUM(l.duration) as total_hours,
        SUM(l.overtime) as overtime_hours, COUNT(*) as task_count
        FROM prod_labor_time l
        LEFT JOIN sys_user u ON l.user_id=u.id
        GROUP BY l.user_id ORDER BY total_hours DESC''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


# ==================== 包装管理 ====================
@prod_ext_bp.route('/api/prod/packing/list')
@_prod_ext_read
def packing_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM prod_packing").fetchone()['cnt']
    order_by = _ext_order(request.args, {'id': 'p.id', 'packing_no': 'p.packing_no', 'workorder_no': 'w.order_no', 'status': 'p.status'}, 'p', 'prod/packing')
    rows = db.execute('''SELECT p.*, w.order_no as workorder_no
        FROM prod_packing p
        LEFT JOIN prod_workorder w ON p.workorder_id=w.id
        ORDER BY {order_by} LIMIT ? OFFSET ?'''.format(order_by=order_by), (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@prod_ext_bp.route('/api/prod/packing/add', methods=['POST'])
@_prod_ext_write
def packing_add():
    return _legacy_ext_write_disabled()
