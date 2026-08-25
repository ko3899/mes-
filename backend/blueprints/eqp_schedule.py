"""设备点检和排班日历蓝图"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete, permission_required

eqp_schedule_bp = Blueprint('eqp_schedule', __name__)


# ==================== 设备点检项目 ====================
@eqp_schedule_bp.route('/api/eqp/check-project/list')
@login_required
def check_project_list():
    return jsonify(crud_list('eqp_check_project', request.args))


@eqp_schedule_bp.route('/api/eqp/check-project/add', methods=['POST'])
@permission_required('eqp:write')
def check_project_add():
    return jsonify(crud_add('eqp_check_project', request.json))


@eqp_schedule_bp.route('/api/eqp/check-project/update', methods=['POST'])
@permission_required('eqp:write')
def check_project_update():
    return jsonify(crud_update('eqp_check_project', request.json))


@eqp_schedule_bp.route('/api/eqp/check-project/delete', methods=['POST'])
@permission_required('eqp:write')
def check_project_delete():
    return jsonify(crud_delete('eqp_check_project', request.json.get('id')))


# ==================== 排班日历 ====================
@eqp_schedule_bp.route('/api/sched/calendar/list')
@login_required
def calendar_list():
    db = get_db()
    page = max(1, int(request.args.get('page', 1)))
    size = max(1, int(request.args.get('size', 20)))
    offset = (page - 1) * size
    plan_id = request.args.get('plan_id')
    where = ' WHERE 1=1'
    params = []
    if plan_id:
        where += ' AND c.plan_id=?'
        params.append(int(plan_id))
    keyword = request.args.get('keyword', '').strip()
    if keyword:
        where += ''' AND (
            c.work_date LIKE ? OR c.shift_type LIKE ?
            OR c.user_ids LIKE ? OR sp.plan_name LIKE ?
        )'''
        like = f'%{keyword}%'
        params.extend([like, like, like, like])
    sort_columns = {
        'id': 'c.id',
        'plan_id': 'c.plan_id',
        'work_date': 'c.work_date',
        'shift_type': 'c.shift_type',
        'user_ids': 'c.user_ids',
        'created_at': 'c.created_at',
        'plan_name': 'sp.plan_name',
    }
    sort = sort_columns.get(request.args.get('sort'), 'c.work_date')
    order = request.args.get('order', 'DESC').upper()
    if order not in ('ASC', 'DESC'):
        order = 'DESC'
    from_clause = ''' FROM sched_calendar c
        LEFT JOIN sched_plan sp ON c.plan_id=sp.id'''
    total = db.execute(
        'SELECT COUNT(*) AS cnt' + from_clause + where,
        params,
    ).fetchone()['cnt']
    rows = db.execute(f'''SELECT c.*, sp.plan_name
        {from_clause} {where}
        ORDER BY {sort} {order} LIMIT ? OFFSET ?''',
        params + [size, offset],
    ).fetchall()
    return jsonify({'code': 0, 'data': {
        'list': [dict(r) for r in rows],
        'total': total,
        'page': page,
        'size': size,
    }})


@eqp_schedule_bp.route('/api/sched/calendar/add', methods=['POST'])
@permission_required('sched:write')
def calendar_add():
    return jsonify(crud_add('sched_calendar', request.json))


@eqp_schedule_bp.route('/api/sched/calendar/update', methods=['POST'])
@permission_required('sched:write')
def calendar_update():
    return jsonify(crud_update('sched_calendar', request.json))


@eqp_schedule_bp.route('/api/sched/calendar/delete', methods=['POST'])
@permission_required('sched:write')
def calendar_delete():
    return jsonify(crud_delete('sched_calendar', request.json.get('id')))


# ==================== 质检方案模板 ====================
@eqp_schedule_bp.route('/api/qm/template/list')
@login_required
def qm_template_list():
    return jsonify(crud_list('qm_inspect_template', request.args))


@eqp_schedule_bp.route('/api/qm/template/add', methods=['POST'])
@permission_required('quality:write')
def qm_template_add():
    return jsonify(crud_add('qm_inspect_template', request.json))


@eqp_schedule_bp.route('/api/qm/template/update', methods=['POST'])
@permission_required('quality:write')
def qm_template_update():
    return jsonify(crud_update('qm_inspect_template', request.json))


@eqp_schedule_bp.route('/api/qm/template/delete', methods=['POST'])
@permission_required('quality:write')
def qm_template_delete():
    return jsonify(crud_delete('qm_inspect_template', request.json.get('id')))


# ==================== 工序流转卡 ====================
@eqp_schedule_bp.route('/api/routing-card/list')
@login_required
def routing_card_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as c FROM prod_routing_card").fetchone()['c']
    rows = db.execute('''SELECT rc.*, w.order_no as workorder_no, p.product_name
        FROM prod_routing_card rc
        LEFT JOIN prod_workorder w ON rc.workorder_id=w.id
        LEFT JOIN base_product p ON rc.product_id=p.id
        ORDER BY rc.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@eqp_schedule_bp.route('/api/routing-card/generate', methods=['POST'])
@permission_required('prod:extension:write')
def routing_card_generate():
    d = request.json
    workorder_id = d.get('workorder_id')
    db = get_db()
    
    # 获取工单信息
    wo = db.execute("SELECT * FROM prod_workorder WHERE id=?", (workorder_id,)).fetchone()
    if not wo:
        return jsonify({'code': 404, 'message': '工单不存在'})
    
    # 获取工序步骤
    steps = db.execute('''SELECT p.process_name FROM base_process p 
        WHERE p.workshop_id=? ORDER BY p.sort_order''', (wo['workshop_id'],)).fetchall()
    
    import datetime
    card_no = f"RC{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    db.execute('''INSERT INTO prod_routing_card 
        (card_no, workorder_id, product_id, total_steps, status) 
        VALUES (?,?,?,?,0)''',
        (card_no, workorder_id, wo['product_id'], len(steps)))
    card_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    
    for i, step in enumerate(steps):
        db.execute('''INSERT INTO prod_routing_card_step 
            (card_id, step_no, process_name) VALUES (?,?,?)''',
            (card_id, i+1, step['process_name']))
    
    db.commit()
    return jsonify({'code': 0, 'data': {'card_no': card_no, 'steps': len(steps)}})
