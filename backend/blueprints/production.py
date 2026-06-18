"""生产管理蓝图"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete, gen_no

production_bp = Blueprint('production', __name__)


@production_bp.route('/api/prod/sales/list')
@login_required
def prod_sales_list():
    return jsonify(crud_list('prod_sales_order', request.args))


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
    return jsonify(crud_list('prod_plan', request.args))


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
    total = db.execute("SELECT COUNT(*) as cnt FROM prod_workorder").fetchone()['cnt']
    rows = db.execute('''SELECT w.*, p.product_name, p.code as product_code,
        ws.workshop_name
        FROM prod_workorder w
        LEFT JOIN base_product p ON w.product_id=p.id
        LEFT JOIN base_workshop ws ON w.workshop_id=ws.id
        ORDER BY w.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
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
    total = db.execute("SELECT COUNT(*) as cnt FROM prod_task").fetchone()['cnt']
    rows = db.execute('''SELECT t.*, w.order_no as workorder_no, pr.process_name,
        u.real_name as assigned_name
        FROM prod_task t
        LEFT JOIN prod_workorder w ON t.workorder_id=w.id
        LEFT JOIN base_process pr ON t.process_id=pr.id
        LEFT JOIN sys_user u ON t.assigned_to=u.id
        ORDER BY t.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
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
    total = db.execute("SELECT COUNT(*) as cnt FROM prod_report").fetchone()['cnt']
    rows = db.execute('''SELECT r.*, t.task_no, w.order_no as workorder_no,
        pr.process_name, u.real_name
        FROM prod_report r
        LEFT JOIN prod_task t ON r.task_id=t.id
        LEFT JOIN prod_workorder w ON r.workorder_id=w.id
        LEFT JOIN base_process pr ON r.process_id=pr.id
        LEFT JOIN sys_user u ON r.user_id=u.id
        ORDER BY r.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@production_bp.route('/api/prod/report/add', methods=['POST'])
@login_required
def prod_report_add():
    data = request.json
    data['report_no'] = gen_no('BR')
    data['user_id'] = session.get('user_id')
    return jsonify(crud_add('prod_report', data))


@production_bp.route('/api/prod/report/delete', methods=['POST'])
@login_required
def prod_report_delete():
    return jsonify(crud_delete('prod_report', request.json.get('id')))
