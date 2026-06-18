"""成本核算蓝图"""
from flask import Blueprint, request, jsonify
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_delete

cost_bp = Blueprint('cost', __name__)


@cost_bp.route('/api/cost/list')
@login_required
def cost_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM prod_cost").fetchone()['cnt']
    rows = db.execute('''SELECT c.*, w.order_no as workorder_no
        FROM prod_cost c
        LEFT JOIN prod_workorder w ON c.workorder_id=w.id
        ORDER BY c.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@cost_bp.route('/api/cost/add', methods=['POST'])
@login_required
def cost_add():
    return jsonify(crud_add('prod_cost', request.json))


@cost_bp.route('/api/cost/delete', methods=['POST'])
@login_required
def cost_delete():
    return jsonify(crud_delete('prod_cost', request.json.get('id')))


@cost_bp.route('/api/cost/summary')
@login_required
def cost_summary():
    db = get_db()
    workorder_id = request.args.get('workorder_id')
    if workorder_id:
        rows = db.execute('''SELECT cost_type, SUM(amount) as total
            FROM prod_cost WHERE workorder_id=? GROUP BY cost_type''', (workorder_id,)).fetchall()
    else:
        rows = db.execute('''SELECT cost_type, SUM(amount) as total
            FROM prod_cost GROUP BY cost_type''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})
