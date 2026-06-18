"""生产增强蓝图 - 工序转移、领料、委外、序列号、工时、包装"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete, gen_no

prod_ext_bp = Blueprint('prod_ext', __name__)


# ==================== 工序转移单 ====================
@prod_ext_bp.route('/api/prod/transfer/list')
@login_required
def transfer_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM prod_transfer").fetchone()['cnt']
    rows = db.execute('''SELECT t.*, w.order_no as workorder_no,
        p1.process_name as from_process, p2.process_name as to_process
        FROM prod_transfer t
        LEFT JOIN prod_workorder w ON t.workorder_id=w.id
        LEFT JOIN base_process p1 ON t.from_process_id=p1.id
        LEFT JOIN base_process p2 ON t.to_process_id=p2.id
        ORDER BY t.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@prod_ext_bp.route('/api/prod/transfer/add', methods=['POST'])
@login_required
def transfer_add():
    data = request.json
    data['transfer_no'] = gen_no('TR')
    data['operator'] = session.get('user_id')
    return jsonify(crud_add('prod_transfer', data))


# ==================== 生产领料 ====================
@prod_ext_bp.route('/api/prod/material/list')
@login_required
def material_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM prod_material_req").fetchone()['cnt']
    rows = db.execute('''SELECT m.*, w.order_no as workorder_no, p.product_name
        FROM prod_material_req m
        LEFT JOIN prod_workorder w ON m.workorder_id=w.id
        LEFT JOIN base_product p ON m.product_id=p.id
        ORDER BY m.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@prod_ext_bp.route('/api/prod/material/add', methods=['POST'])
@login_required
def material_add():
    data = request.json
    data['req_no'] = gen_no('MR')
    data['operator'] = session.get('user_id')
    return jsonify(crud_add('prod_material_req', data))


@prod_ext_bp.route('/api/prod/material/update', methods=['POST'])
@login_required
def material_update():
    return jsonify(crud_update('prod_material_req', request.json))


# ==================== 委外加工 ====================
@prod_ext_bp.route('/api/prod/outsource/list')
@login_required
def outsource_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM prod_outsource").fetchone()['cnt']
    rows = db.execute('''SELECT o.*, s.supplier_name, p.product_name
        FROM prod_outsource o
        LEFT JOIN base_supplier s ON o.supplier_id=s.id
        LEFT JOIN base_product p ON o.product_id=p.id
        ORDER BY o.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@prod_ext_bp.route('/api/prod/outsource/add', methods=['POST'])
@login_required
def outsource_add():
    data = request.json
    data['outsource_no'] = gen_no('OS')
    return jsonify(crud_add('prod_outsource', data))


@prod_ext_bp.route('/api/prod/outsource/update', methods=['POST'])
@login_required
def outsource_update():
    return jsonify(crud_update('prod_outsource', request.json))


# ==================== 产品序列号 ====================
@prod_ext_bp.route('/api/prod/serial/list')
@login_required
def serial_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    keyword = request.args.get('keyword', '')
    offset = (page - 1) * size
    if keyword:
        total = db.execute("SELECT COUNT(*) as cnt FROM prod_serial WHERE serial_no LIKE ?", (f'%{keyword}%',)).fetchone()['cnt']
        rows = db.execute('''SELECT s.*, p.product_name FROM prod_serial s
            LEFT JOIN base_product p ON s.product_id=p.id
            WHERE s.serial_no LIKE ? ORDER BY s.id DESC LIMIT ? OFFSET ?''',
            (f'%{keyword}%', size, offset)).fetchall()
    else:
        total = db.execute("SELECT COUNT(*) as cnt FROM prod_serial").fetchone()['cnt']
        rows = db.execute('''SELECT s.*, p.product_name FROM prod_serial s
            LEFT JOIN base_product p ON s.product_id=p.id
            ORDER BY s.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@prod_ext_bp.route('/api/prod/serial/generate', methods=['POST'])
@login_required
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
@login_required
def labor_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM prod_labor_time").fetchone()['cnt']
    rows = db.execute('''SELECT l.*, u.real_name, t.task_no, w.order_no as workorder_no
        FROM prod_labor_time l
        LEFT JOIN sys_user u ON l.user_id=u.id
        LEFT JOIN prod_task t ON l.task_id=t.id
        LEFT JOIN prod_workorder w ON l.workorder_id=w.id
        ORDER BY l.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@prod_ext_bp.route('/api/prod/labor/add', methods=['POST'])
@login_required
def labor_add():
    data = request.json
    data['user_id'] = session.get('user_id')
    return jsonify(crud_add('prod_labor_time', data))


@prod_ext_bp.route('/api/prod/labor/summary')
@login_required
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
@login_required
def packing_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM prod_packing").fetchone()['cnt']
    rows = db.execute('''SELECT p.*, w.order_no as workorder_no
        FROM prod_packing p
        LEFT JOIN prod_workorder w ON p.workorder_id=w.id
        ORDER BY p.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@prod_ext_bp.route('/api/prod/packing/add', methods=['POST'])
@login_required
def packing_add():
    data = request.json
    data['packing_no'] = gen_no('PK')
    data['total_quantity'] = float(data.get('box_count', 0)) * float(data.get('quantity_per_box', 0))
    return jsonify(crud_add('prod_packing', data))
