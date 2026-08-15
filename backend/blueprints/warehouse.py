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
    page = max(1, int(request.args.get('page', 1)))
    size = max(1, int(request.args.get('size', 20)))
    offset = (page - 1) * size
    where = ' WHERE 1=1'
    params = []
    keyword = request.args.get('keyword', '').strip()
    warehouse_id = request.args.get('warehouse_id')
    if warehouse_id:
        where += ' AND a.warehouse_id=?'
        params.append(warehouse_id)
    if keyword:
        where += ''' AND (
            a.area_name LIKE ? OR a.code LIKE ? OR w.warehouse_name LIKE ?
        )'''
        like = f'%{keyword}%'
        params.extend([like, like, like])
    sort_columns = {
        'id': 'a.id',
        'warehouse_id': 'a.warehouse_id',
        'area_name': 'a.area_name',
        'code': 'a.code',
        'status': 'a.status',
        'created_at': 'a.created_at',
        'warehouse_name': 'w.warehouse_name',
    }
    sort = sort_columns.get(request.args.get('sort'), 'a.id')
    order = request.args.get('order', 'DESC').upper()
    if order not in ('ASC', 'DESC'):
        order = 'DESC'
    total = db.execute(
        '''SELECT COUNT(*) AS cnt FROM inv_area a
        LEFT JOIN inv_warehouse w ON a.warehouse_id=w.id''' + where,
        params,
    ).fetchone()['cnt']
    rows = db.execute('''SELECT a.*, w.warehouse_name 
        FROM inv_area a LEFT JOIN inv_warehouse w ON a.warehouse_id=w.id'''
        + where + f' ORDER BY {sort} {order} LIMIT ? OFFSET ?',
        params + [size, offset],
    ).fetchall()
    return jsonify({'code': 0, 'data': {
        'list': [dict(r) for r in rows],
        'total': total,
        'page': page,
        'size': size,
    }})


@warehouse_bp.route('/api/area/add', methods=['POST'])
@login_required
def area_add():
    return jsonify(crud_add('inv_area', request.json))


@warehouse_bp.route('/api/area/update', methods=['POST'])
@login_required
def area_update():
    return jsonify(crud_update('inv_area', request.json))


@warehouse_bp.route('/api/area/delete', methods=['POST'])
@login_required
def area_delete():
    return jsonify(crud_delete('inv_area', request.json.get('id')))


@warehouse_bp.route('/api/location/list')
@login_required
def location_list():
    db = get_db()
    page = max(1, int(request.args.get('page', 1)))
    size = max(1, int(request.args.get('size', 20)))
    offset = (page - 1) * size
    where = ' WHERE 1=1'
    params = []
    keyword = request.args.get('keyword', '').strip()
    area_id = request.args.get('area_id')
    if area_id:
        where += ' AND l.area_id=?'
        params.append(area_id)
    if keyword:
        where += ''' AND (
            l.location_name LIKE ? OR l.code LIKE ?
            OR a.area_name LIKE ? OR w.warehouse_name LIKE ?
        )'''
        like = f'%{keyword}%'
        params.extend([like, like, like, like])
    sort_columns = {
        'id': 'l.id',
        'area_id': 'l.area_id',
        'location_name': 'l.location_name',
        'code': 'l.code',
        'status': 'l.status',
        'created_at': 'l.created_at',
        'area_name': 'a.area_name',
        'warehouse_name': 'w.warehouse_name',
    }
    sort = sort_columns.get(request.args.get('sort'), 'l.id')
    order = request.args.get('order', 'DESC').upper()
    if order not in ('ASC', 'DESC'):
        order = 'DESC'
    from_clause = ''' FROM inv_location l
        LEFT JOIN inv_area a ON l.area_id=a.id
        LEFT JOIN inv_warehouse w ON a.warehouse_id=w.id'''
    total = db.execute(
        'SELECT COUNT(*) AS cnt' + from_clause + where,
        params,
    ).fetchone()['cnt']
    rows = db.execute('''SELECT l.*, a.area_name, w.warehouse_name
        ''' + from_clause + where
        + f' ORDER BY {sort} {order} LIMIT ? OFFSET ?',
        params + [size, offset],
    ).fetchall()
    return jsonify({'code': 0, 'data': {
        'list': [dict(r) for r in rows],
        'total': total,
        'page': page,
        'size': size,
    }})


@warehouse_bp.route('/api/location/add', methods=['POST'])
@login_required
def location_add():
    return jsonify(crud_add('inv_location', request.json))


@warehouse_bp.route('/api/location/update', methods=['POST'])
@login_required
def location_update():
    return jsonify(crud_update('inv_location', request.json))


@warehouse_bp.route('/api/location/delete', methods=['POST'])
@login_required
def location_delete():
    return jsonify(crud_delete('inv_location', request.json.get('id')))


# ==================== 库存事务 ====================
@warehouse_bp.route('/api/transaction/list')
@login_required
def transaction_list():
    return jsonify(crud_list('inv_transaction_log', request.args))


@warehouse_bp.route('/api/transaction/add', methods=['POST'])
@login_required
def transaction_add():
    return jsonify({
        'code': 409,
        'message': '库存流水只能由入库、出库、领料或退料过账生成',
    }), 409


# ==================== 到货通知 ====================
@warehouse_bp.route('/api/arrival/list')
@login_required
def arrival_list():
    db = get_db()
    page = max(1, int(request.args.get('page', 1)))
    size = max(1, int(request.args.get('size', 20)))
    offset = (page - 1) * size
    where = ' WHERE 1=1'
    params = []
    keyword = request.args.get('keyword', '').strip()
    if keyword:
        where += ''' AND (
            a.notice_no LIKE ? OR a.expected_date LIKE ?
            OR a.remark LIKE ? OR s.supplier_name LIKE ?
        )'''
        like = f'%{keyword}%'
        params.extend([like, like, like, like])
    sort_columns = {
        'id': 'a.id',
        'notice_no': 'a.notice_no',
        'supplier_id': 'a.supplier_id',
        'supplier_name': 's.supplier_name',
        'expected_date': 'a.expected_date',
        'status': 'a.status',
        'remark': 'a.remark',
        'created_at': 'a.created_at',
    }
    sort = sort_columns.get(request.args.get('sort'), 'a.id')
    order = request.args.get('order', 'DESC').upper()
    if order not in ('ASC', 'DESC'):
        order = 'DESC'
    from_clause = ''' FROM inv_arrival_notice a
        LEFT JOIN base_supplier s ON a.supplier_id=s.id'''
    total = db.execute(
        'SELECT COUNT(*) AS c' + from_clause + where,
        params,
    ).fetchone()['c']
    rows = db.execute(
        'SELECT a.*, s.supplier_name' + from_clause + where
        + f' ORDER BY {sort} {order} LIMIT ? OFFSET ?',
        params + [size, offset],
    ).fetchall()
    return jsonify({'code': 0, 'data': {
        'list': [dict(r) for r in rows],
        'total': total,
        'page': page,
        'size': size,
    }})


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


@warehouse_bp.route('/api/arrival/delete', methods=['POST'])
@login_required
def arrival_delete():
    return jsonify(crud_delete('inv_arrival_notice', request.json.get('id')))
