"""仓库管理增强蓝图 - 三级库位/库存事务/到货通知"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete, gen_no

warehouse_bp = Blueprint('warehouse', __name__)


# ==================== 三级库位 ====================
@warehouse_bp.route('/api/warehouse/list')
@login_required
def warehouse_list():
    return jsonify(crud_list('inv_warehouse', request.args))


@warehouse_bp.route('/api/warehouse/add', methods=['POST'])
@login_required
def warehouse_add():
    return jsonify(crud_add('inv_warehouse', request.json))


@warehouse_bp.route('/api/warehouse/update', methods=['POST'])
@login_required
def warehouse_update():
    return jsonify(crud_update('inv_warehouse', request.json))


@warehouse_bp.route('/api/warehouse/delete', methods=['POST'])
@login_required
def warehouse_delete():
    return jsonify(crud_delete('inv_warehouse', request.json.get('id')))


@warehouse_bp.route('/api/area/list')
@login_required
def area_list():
    db = get_db()
    rows = db.execute('''SELECT a.*, w.warehouse_name 
        FROM inv_area a LEFT JOIN inv_warehouse w ON a.warehouse_id=w.id 
        ORDER BY a.id''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@warehouse_bp.route('/api/area/add', methods=['POST'])
@login_required
def area_add():
    return jsonify(crud_add('inv_area', request.json))


@warehouse_bp.route('/api/location/list')
@login_required
def location_list():
    db = get_db()
    rows = db.execute('''SELECT l.*, a.area_name, w.warehouse_name 
        FROM inv_location l 
        LEFT JOIN inv_area a ON l.area_id=a.id
        LEFT JOIN inv_warehouse w ON a.warehouse_id=w.id
        ORDER BY l.id''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@warehouse_bp.route('/api/location/add', methods=['POST'])
@login_required
def location_add():
    return jsonify(crud_add('inv_location', request.json))


# ==================== 库存事务 ====================
@warehouse_bp.route('/api/transaction/list')
@login_required
def transaction_list():
    return jsonify(crud_list('inv_transaction_log', request.args))


@warehouse_bp.route('/api/transaction/add', methods=['POST'])
@login_required
def transaction_add():
    d = request.json
    d['operator'] = session.get('user_id')
    return jsonify(crud_add('inv_transaction_log', d))


# ==================== 到货通知 ====================
@warehouse_bp.route('/api/arrival/list')
@login_required
def arrival_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as c FROM inv_arrival_notice").fetchone()['c']
    rows = db.execute('''SELECT a.*, s.supplier_name 
        FROM inv_arrival_notice a 
        LEFT JOIN base_supplier s ON a.supplier_id=s.id
        ORDER BY a.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@warehouse_bp.route('/api/arrival/add', methods=['POST'])
@login_required
def arrival_add():
    d = request.json
    d['notice_no'] = gen_no('AN')
    return jsonify(crud_add('inv_arrival_notice', d))


@warehouse_bp.route('/api/arrival/update', methods=['POST'])
@login_required
def arrival_update():
    return jsonify(crud_update('inv_arrival_notice', request.json))
