"""成本核算蓝图"""
from flask import Blueprint, request, jsonify
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_delete, permission_required

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
@permission_required('cost:write')
def cost_add():
    return jsonify(crud_add('prod_cost', request.json))


@cost_bp.route('/api/cost/delete', methods=['POST'])
@permission_required('cost:write')
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


@cost_bp.route('/api/cost/variance')
@login_required
def cost_variance():
    """成本差异分析"""
    db = get_db()
    
    # 获取各工单的标准成本和实际成本
    rows = db.execute('''SELECT w.order_no, p.product_name,
        w.planned_qty, w.completed_qty,
        COALESCE(sc.material_cost, 0) as std_material,
        COALESCE(sc.labor_cost, 0) as std_labor,
        COALESCE(sc.overhead_cost, 0) as std_overhead,
        COALESCE(SUM(c.amount), 0) as actual_cost
        FROM prod_workorder w
        LEFT JOIN base_product p ON w.product_id=p.id
        LEFT JOIN base_standard_cost sc ON w.product_id=sc.product_id
        LEFT JOIN prod_cost c ON w.id=c.workorder_id
        GROUP BY w.id
        ORDER BY w.id DESC LIMIT 20''').fetchall()
    
    result = []
    for row in rows:
        std_total = (row['std_material'] + row['std_labor'] + row['std_overhead']) * row['completed_qty']
        actual = row['actual_cost']
        variance = actual - std_total
        variance_rate = round(variance / std_total * 100, 2) if std_total > 0 else 0
        
        result.append({
            'order_no': row['order_no'],
            'product_name': row['product_name'],
            'completed_qty': row['completed_qty'],
            'standard_cost': round(std_total, 2),
            'actual_cost': round(actual, 2),
            'variance': round(variance, 2),
            'variance_rate': variance_rate
        })
    
    return jsonify({'code': 0, 'data': result})
