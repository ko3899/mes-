"""阶段码管理蓝图"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete, gen_no

stage_bp = Blueprint('stage', __name__)


# ==================== 阶段码定义 ====================
@stage_bp.route('/api/stage/code/list')
@login_required
def stage_code_list():
    db = get_db()
    rows = db.execute("SELECT * FROM base_stage_code ORDER BY sort_order ASC, id ASC").fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@stage_bp.route('/api/stage/code/add', methods=['POST'])
@login_required
def stage_code_add():
    d = request.json
    db = get_db()
    # 自动排序
    max_order = db.execute("SELECT COALESCE(MAX(sort_order), 0) as m FROM base_stage_code").fetchone()['m']
    d['sort_order'] = max_order + 1
    keys = [k for k in d.keys() if k != 'id']
    vals = [d[k] for k in keys]
    placeholders = ','.join(['?'] * len(keys))
    columns = ','.join(keys)
    try:
        cursor = db.execute(f"INSERT INTO base_stage_code ({columns}) VALUES ({placeholders})", vals)
        db.commit()
        return jsonify({'code': 0, 'data': {'id': cursor.lastrowid}, 'message': '添加成功'})
    except Exception as e:
        return jsonify({'code': 400, 'message': str(e)})


@stage_bp.route('/api/stage/code/update', methods=['POST'])
@login_required
def stage_code_update():
    return jsonify(crud_update('base_stage_code', request.json))


@stage_bp.route('/api/stage/code/delete', methods=['POST'])
@login_required
def stage_code_delete():
    return jsonify(crud_delete('base_stage_code', request.json.get('id')))


@stage_bp.route('/api/stage/code/reorder', methods=['POST'])
@login_required
def stage_code_reorder():
    """阶段码调序"""
    d = request.json
    stage_id = d.get('id')
    direction = d.get('direction')
    
    if not stage_id or direction not in ('up', 'down'):
        return jsonify({'code': 400, 'message': '参数错误'})
    
    db = get_db()
    current = db.execute("SELECT * FROM base_stage_code WHERE id=?", (stage_id,)).fetchone()
    if not current:
        return jsonify({'code': 404, 'message': '阶段码不存在'})
    
    current_order = current['sort_order']
    
    if direction == 'up':
        prev = db.execute("SELECT * FROM base_stage_code WHERE sort_order < ? ORDER BY sort_order DESC LIMIT 1", (current_order,)).fetchone()
        if prev:
            db.execute("UPDATE base_stage_code SET sort_order=? WHERE id=?", (prev['sort_order'], stage_id))
            db.execute("UPDATE base_stage_code SET sort_order=? WHERE id=?", (current_order, prev['id']))
            db.commit()
            return jsonify({'code': 0, 'message': '上移成功'})
    else:
        next_stage = db.execute("SELECT * FROM base_stage_code WHERE sort_order > ? ORDER BY sort_order ASC LIMIT 1", (current_order,)).fetchone()
        if next_stage:
            db.execute("UPDATE base_stage_code SET sort_order=? WHERE id=?", (next_stage['sort_order'], stage_id))
            db.execute("UPDATE base_stage_code SET sort_order=? WHERE id=?", (current_order, next_stage['id']))
            db.commit()
            return jsonify({'code': 0, 'message': '下移成功'})
    
    return jsonify({'code': 0, 'message': '已在边界位置'})


# ==================== 阶段记录 ====================
@stage_bp.route('/api/stage/record/list')
@login_required
def stage_record_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM prod_stage_record").fetchone()['cnt']
    rows = db.execute('''SELECT r.*, w.order_no as workorder_no, p.product_name, u.real_name
        FROM prod_stage_record r
        LEFT JOIN prod_workorder w ON r.workorder_id=w.id
        LEFT JOIN base_product p ON r.product_id=p.id
        LEFT JOIN sys_user u ON r.operator=u.id
        ORDER BY r.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@stage_bp.route('/api/stage/record/add', methods=['POST'])
@login_required
def stage_record_add():
    d = request.json
    d['operator'] = session.get('user_id')
    return jsonify(crud_add('prod_stage_record', d))


@stage_bp.route('/api/stage/record/update', methods=['POST'])
@login_required
def stage_record_update():
    return jsonify(crud_update('prod_stage_record', request.json))


@stage_bp.route('/api/stage/record/complete', methods=['POST'])
@login_required
def stage_record_complete():
    """完成阶段"""
    import datetime
    d = request.json
    record_id = d.get('id')
    db = get_db()
    record = db.execute("SELECT * FROM prod_stage_record WHERE id=?", (record_id,)).fetchone()
    if not record:
        return jsonify({'code': 404, 'message': '记录不存在'})
    
    now = datetime.datetime.now()
    start = record['start_time']
    if start:
        try:
            start_dt = datetime.datetime.fromisoformat(str(start))
            duration = (now - start_dt).total_seconds() / 60
        except:
            duration = 0
    else:
        duration = 0
    
    db.execute("UPDATE prod_stage_record SET end_time=?, duration=?, remark=? WHERE id=?",
               (now, round(duration, 2), d.get('remark', ''), record_id))
    db.commit()
    return jsonify({'code': 0, 'message': '阶段完成'})


@stage_bp.route('/api/stage/statistics')
@login_required
def stage_statistics():
    """阶段统计"""
    db = get_db()
    
    # 各阶段数量
    stage_counts = db.execute('''SELECT stage_code, COUNT(*) as count, SUM(quantity) as total_qty
        FROM prod_stage_record GROUP BY stage_code ORDER BY count DESC''').fetchall()
    
    # 今日阶段记录
    import datetime
    today = datetime.date.today().strftime('%Y-%m-%d')
    today_records = db.execute('''SELECT COUNT(*) as c FROM prod_stage_record WHERE DATE(created_at)=?''', (today,)).fetchone()['c']
    
    # 平均阶段时长
    avg_duration = db.execute("SELECT COALESCE(AVG(duration), 0) as avg_d FROM prod_stage_record WHERE duration > 0").fetchone()['avg_d']
    
    return jsonify({'code': 0, 'data': {
        'stage_counts': [dict(r) for r in stage_counts],
        'today_records': today_records,
        'avg_duration': round(avg_duration, 2)
    }})
