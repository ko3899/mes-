"""基础数据蓝图"""
from flask import Blueprint, request, jsonify
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete

base_data_bp = Blueprint('base_data', __name__)


@base_data_bp.route('/api/base/workshop/list')
@login_required
def base_workshop_list():
    return jsonify(crud_list('base_workshop', request.args))


@base_data_bp.route('/api/base/workshop/add', methods=['POST'])
@login_required
def base_workshop_add():
    return jsonify(crud_add('base_workshop', request.json))


@base_data_bp.route('/api/base/workshop/update', methods=['POST'])
@login_required
def base_workshop_update():
    return jsonify(crud_update('base_workshop', request.json))


@base_data_bp.route('/api/base/workshop/delete', methods=['POST'])
@login_required
def base_workshop_delete():
    return jsonify(crud_delete('base_workshop', request.json.get('id')))


@base_data_bp.route('/api/base/process/list')
@login_required
def base_process_list():
    db = get_db()
    rows = db.execute("SELECT p.*, ws.workshop_name FROM base_process p LEFT JOIN base_workshop ws ON p.workshop_id=ws.id ORDER BY p.sort_order ASC, p.id ASC").fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@base_data_bp.route('/api/base/process/add', methods=['POST'])
@login_required
def base_process_add():
    d = request.json
    db = get_db()
    # 自动排序：获取当前最大排序号
    max_order = db.execute("SELECT COALESCE(MAX(sort_order), 0) as max_order FROM base_process").fetchone()['max_order']
    d['sort_order'] = max_order + 1
    # 添加到 crud_add
    keys = [k for k in d.keys() if k != 'id']
    vals = [d[k] for k in keys]
    placeholders = ','.join(['?'] * len(keys))
    columns = ','.join(keys)
    try:
        cursor = db.execute(f"INSERT INTO base_process ({columns}) VALUES ({placeholders})", vals)
        db.commit()
        return jsonify({'code': 0, 'data': {'id': cursor.lastrowid}, 'message': '添加成功'})
    except Exception as e:
        return jsonify({'code': 400, 'message': str(e)})


@base_data_bp.route('/api/base/process/update', methods=['POST'])
@login_required
def base_process_update():
    return jsonify(crud_update('base_process', request.json))


@base_data_bp.route('/api/base/process/delete', methods=['POST'])
@login_required
def base_process_delete():
    return jsonify(crud_delete('base_process', request.json.get('id')))


@base_data_bp.route('/api/base/process/reorder', methods=['POST'])
@login_required
def base_process_reorder():
    """工序调序"""
    d = request.json
    process_id = d.get('id')
    direction = d.get('direction')  # 'up' 或 'down'
    
    if not process_id or direction not in ('up', 'down'):
        return jsonify({'code': 400, 'message': '参数错误'})
    
    db = get_db()
    current = db.execute("SELECT * FROM base_process WHERE id=?", (process_id,)).fetchone()
    if not current:
        return jsonify({'code': 404, 'message': '工序不存在'})
    
    current_order = current['sort_order']
    
    if direction == 'up':
        # 找到上一个工序
        prev = db.execute("SELECT * FROM base_process WHERE sort_order < ? ORDER BY sort_order DESC LIMIT 1", (current_order,)).fetchone()
        if prev:
            # 交换排序号
            db.execute("UPDATE base_process SET sort_order=? WHERE id=?", (prev['sort_order'], process_id))
            db.execute("UPDATE base_process SET sort_order=? WHERE id=?", (current_order, prev['id']))
            db.commit()
            return jsonify({'code': 0, 'message': '上移成功'})
    else:
        # 找到下一个工序
        next_proc = db.execute("SELECT * FROM base_process WHERE sort_order > ? ORDER BY sort_order ASC LIMIT 1", (current_order,)).fetchone()
        if next_proc:
            # 交换排序号
            db.execute("UPDATE base_process SET sort_order=? WHERE id=?", (next_proc['sort_order'], process_id))
            db.execute("UPDATE base_process SET sort_order=? WHERE id=?", (current_order, next_proc['id']))
            db.commit()
            return jsonify({'code': 0, 'message': '下移成功'})
    
    return jsonify({'code': 0, 'message': '已在边界位置'})


@base_data_bp.route('/api/base/product/list')
@login_required
def base_product_list():
    return jsonify(crud_list('base_product', request.args))


@base_data_bp.route('/api/base/product/add', methods=['POST'])
@login_required
def base_product_add():
    return jsonify(crud_add('base_product', request.json))


@base_data_bp.route('/api/base/product/update', methods=['POST'])
@login_required
def base_product_update():
    return jsonify(crud_update('base_product', request.json))


@base_data_bp.route('/api/base/product/delete', methods=['POST'])
@login_required
def base_product_delete():
    return jsonify(crud_delete('base_product', request.json.get('id')))


@base_data_bp.route('/api/base/product/all')
@login_required
def base_product_all():
    db = get_db()
    rows = db.execute("SELECT id, product_name, code FROM base_product WHERE status=1").fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@base_data_bp.route('/api/base/bom/list')
@login_required
def base_bom_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM base_bom").fetchone()['cnt']
    rows = db.execute('''SELECT b.*, p1.product_name, p1.code as product_code,
        p2.product_name as material_name, p2.code as material_code
        FROM base_bom b
        LEFT JOIN base_product p1 ON b.product_id=p1.id
        LEFT JOIN base_product p2 ON b.material_id=p2.id
        ORDER BY b.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@base_data_bp.route('/api/base/bom/add', methods=['POST'])
@login_required
def base_bom_add():
    return jsonify(crud_add('base_bom', request.json))


@base_data_bp.route('/api/base/bom/delete', methods=['POST'])
@login_required
def base_bom_delete():
    return jsonify(crud_delete('base_bom', request.json.get('id')))


@base_data_bp.route('/api/base/defect/list')
@login_required
def base_defect_list():
    return jsonify(crud_list('base_defect', request.args))


@base_data_bp.route('/api/base/defect/add', methods=['POST'])
@login_required
def base_defect_add():
    return jsonify(crud_add('base_defect', request.json))


@base_data_bp.route('/api/base/defect/update', methods=['POST'])
@login_required
def base_defect_update():
    return jsonify(crud_update('base_defect', request.json))


@base_data_bp.route('/api/base/defect/delete', methods=['POST'])
@login_required
def base_defect_delete():
    return jsonify(crud_delete('base_defect', request.json.get('id')))


@base_data_bp.route('/api/base/unit/list')
@login_required
def base_unit_list():
    return jsonify(crud_list('base_unit', request.args))


@base_data_bp.route('/api/base/unit/add', methods=['POST'])
@login_required
def base_unit_add():
    return jsonify(crud_add('base_unit', request.json))


@base_data_bp.route('/api/base/unit/update', methods=['POST'])
@login_required
def base_unit_update():
    return jsonify(crud_update('base_unit', request.json))


@base_data_bp.route('/api/base/unit/delete', methods=['POST'])
@login_required
def base_unit_delete():
    return jsonify(crud_delete('base_unit', request.json.get('id')))


@base_data_bp.route('/api/base/route/list')
@login_required
def base_route_list():
    db = get_db()
    rows = db.execute('''SELECT r.*, p.product_name, p.code as product_code
        FROM base_process_route r
        LEFT JOIN base_product p ON r.product_id=p.id
        ORDER BY r.id DESC''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@base_data_bp.route('/api/base/route/add', methods=['POST'])
@login_required
def base_route_add():
    return jsonify(crud_add('base_process_route', request.json))


@base_data_bp.route('/api/base/route/update', methods=['POST'])
@login_required
def base_route_update():
    return jsonify(crud_update('base_process_route', request.json))


@base_data_bp.route('/api/base/route/delete', methods=['POST'])
@login_required
def base_route_delete():
    return jsonify(crud_delete('base_process_route', request.json.get('id')))
