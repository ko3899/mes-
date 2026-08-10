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
    where, params = [], []
    if request.args.get('workshop_id'):
        where.append('p.workshop_id=?')
        params.append(request.args.get('workshop_id'))
    if request.args.get('status') not in (None, ''):
        where.append('p.status=?')
        params.append(request.args.get('status'))
    keyword = (request.args.get('keyword') or '').strip()
    if keyword:
        where.append('(p.process_name LIKE ? OR p.code LIKE ?)')
        params.extend([f'%{keyword}%', f'%{keyword}%'])
    clause = (' WHERE ' + ' AND '.join(where)) if where else ''
    rows = db.execute(
        '''SELECT p.*, ws.workshop_name FROM base_process p
           LEFT JOIN base_workshop ws ON p.workshop_id=ws.id'''
        + clause + ' ORDER BY p.sort_order ASC, p.id ASC', params
    ).fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@base_data_bp.route('/api/base/process/add', methods=['POST'])
@login_required
def base_process_add():
    d = dict(request.json or {})
    db = get_db()
    if not d.get('workshop_id'):
        return jsonify({'code': 400, 'message': '所属车间必填'}), 400
    if not db.execute('SELECT 1 FROM base_workshop WHERE id=? AND status=1', (d['workshop_id'],)).fetchone():
        return jsonify({'code': 400, 'message': '所属车间不存在或未启用'}), 400
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
    data = dict(request.json or {})
    if not data.get('workshop_id'):
        return jsonify({'code': 400, 'message': '所属车间必填'}), 400
    if not get_db().execute(
        'SELECT 1 FROM base_workshop WHERE id=? AND status=1', (data['workshop_id'],)
    ).fetchone():
        return jsonify({'code': 400, 'message': '所属车间不存在或未启用'}), 400
    return jsonify(crud_update('base_process', data))


@base_data_bp.route('/api/base/process/delete', methods=['POST'])
@login_required
def base_process_delete():
    process_id = (request.json or {}).get('id')
    if get_db().execute(
        'SELECT 1 FROM base_process_route_detail WHERE process_id=? LIMIT 1', (process_id,)
    ).fetchone():
        return jsonify({'code': 409, 'message': '工序已被工艺路线引用，只能停用'}), 409
    return jsonify(crud_delete('base_process', process_id))


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
    where, params = [], []
    if request.args.get('product_id'):
        where.append('r.product_id=?')
        params.append(request.args.get('product_id'))
    if request.args.get('workshop_id'):
        where.append('r.workshop_id=?')
        params.append(request.args.get('workshop_id'))
    if request.args.get('status') not in (None, ''):
        where.append('r.status=?')
        params.append(request.args.get('status'))
    clause = (' WHERE ' + ' AND '.join(where)) if where else ''
    rows = db.execute('''SELECT r.*, p.product_name, p.code as product_code,
                               ws.workshop_name
        FROM base_process_route r
        LEFT JOIN base_product p ON r.product_id=p.id
        LEFT JOIN base_workshop ws ON r.workshop_id=ws.id
        ''' + clause + ' ORDER BY r.id DESC', params).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        steps = db.execute(
            '''SELECT d.*,p.process_name,p.code AS process_code,
                      ws.workshop_name
               FROM base_process_route_detail d
               JOIN base_process p ON p.id=d.process_id
               LEFT JOIN base_workshop ws ON ws.id=d.workshop_id
               WHERE d.route_id=? ORDER BY d.step_no''', (row['id'],)
        ).fetchall()
        item['steps'] = [dict(step) for step in steps]
        result.append(item)
    return jsonify({'code': 0, 'data': result})


@base_data_bp.route('/api/base/route/save', methods=['POST'])
@login_required
def base_route_save():
    data = dict(request.json or {})
    required = [('route_name', '路线名称必填'), ('product_id', '适用产品必填'),
                ('workshop_id', '默认车间必填')]
    for field, message in required:
        if not data.get(field):
            return jsonify({'code': 400, 'message': message}), 400
    steps = data.get('steps') or []
    if not steps:
        return jsonify({'code': 400, 'message': '工艺路线至少需要一道工序'}), 400
    db = get_db()
    if not db.execute('SELECT 1 FROM base_product WHERE id=? AND status=1', (data['product_id'],)).fetchone():
        return jsonify({'code': 400, 'message': '适用产品不存在或未启用'}), 400
    if not db.execute('SELECT 1 FROM base_workshop WHERE id=? AND status=1', (data['workshop_id'],)).fetchone():
        return jsonify({'code': 400, 'message': '默认车间不存在或未启用'}), 400
    seen = set()
    validated = []
    for index, step in enumerate(steps, 1):
        process_id = step.get('process_id')
        step_workshop = step.get('workshop_id') or data['workshop_id']
        process = db.execute(
            'SELECT id,workshop_id,status FROM base_process WHERE id=?', (process_id,)
        ).fetchone()
        if not process or process['status'] != 1:
            return jsonify({'code': 400, 'message': f'第{index}道工序不存在或未启用'}), 400
        if process['workshop_id'] != int(step_workshop):
            return jsonify({'code': 400, 'message': f'第{index}道工序不属于路线车间（步骤车间）'}), 400
        if process_id in seen:
            return jsonify({'code': 400, 'message': '同一路线不能重复添加相同工序'}), 400
        seen.add(process_id)
        validated.append((process_id, step_workshop, step.get('standard_time'),
                          1 if step.get('is_inspection_point') else 0, step.get('description')))
    try:
        db.execute('BEGIN IMMEDIATE')
        route_id = data.get('id')
        if route_id:
            route = db.execute('SELECT id FROM base_process_route WHERE id=?', (route_id,)).fetchone()
            if not route:
                raise ValueError('工艺路线不存在')
            db.execute(
                '''UPDATE base_process_route SET route_name=?,product_id=?,workshop_id=?,
                   version=?,status=?,description=? WHERE id=?''',
                (data['route_name'], data['product_id'], data['workshop_id'],
                 int(data.get('version') or 1), int(data.get('status', 1)),
                 data.get('description'), route_id),
            )
            db.execute('DELETE FROM base_process_route_detail WHERE route_id=?', (route_id,))
        else:
            route_id = db.execute(
                '''INSERT INTO base_process_route
                   (route_name,product_id,workshop_id,version,status,description)
                   VALUES(?,?,?,?,?,?)''',
                (data['route_name'], data['product_id'], data['workshop_id'],
                 int(data.get('version') or 1), int(data.get('status', 1)), data.get('description')),
            ).lastrowid
        for step_no, step in enumerate(validated, 1):
            db.execute(
                '''INSERT INTO base_process_route_detail
                   (route_id,process_id,step_no,workshop_id,standard_time,is_inspection_point,description)
                   VALUES(?,?,?,?,?,?,?)''', (route_id, step[0], step_no, *step[1:])
            )
        db.commit()
        return jsonify({'code': 0, 'data': {'id': route_id}, 'message': '保存成功'})
    except Exception as exc:
        db.rollback()
        return jsonify({'code': 400, 'message': str(exc)}), 400


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
