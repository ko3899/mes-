"""全局搜索和数据查询蓝图"""
from flask import Blueprint, request, jsonify
from utils.database import get_db
from utils.helpers import login_required

search_bp = Blueprint('search', __name__)


@search_bp.route('/api/search/global')
@login_required
def global_search():
    """全局搜索"""
    keyword = request.args.get('q', '').strip()
    if not keyword or len(keyword) < 2:
        return jsonify({'code': 0, 'data': []})
    
    db = get_db()
    results = []
    like = f'%{keyword}%'
    
    # 搜索产品
    rows = db.execute("SELECT id, product_name as name, code, 'product' as type FROM base_product WHERE product_name LIKE ? OR code LIKE ? LIMIT 5", (like, like)).fetchall()
    results.extend([dict(r) for r in rows])
    
    # 搜索工单
    rows = db.execute("SELECT id, order_no as name, 'workorder' as type FROM prod_workorder WHERE order_no LIKE ? LIMIT 5", (like,)).fetchall()
    results.extend([dict(r) for r in rows])
    
    # 搜索任务
    rows = db.execute("SELECT id, task_no as name, 'task' as type FROM prod_task WHERE task_no LIKE ? LIMIT 5", (like,)).fetchall()
    results.extend([dict(r) for r in rows])
    
    # 搜索客户
    rows = db.execute("SELECT id, customer_name as name, code, 'customer' as type FROM base_customer WHERE customer_name LIKE ? OR code LIKE ? LIMIT 5", (like, like)).fetchall()
    results.extend([dict(r) for r in rows])
    
    # 搜索供应商
    rows = db.execute("SELECT id, supplier_name as name, code, 'supplier' as type FROM base_supplier WHERE supplier_name LIKE ? OR code LIKE ? LIMIT 5", (like, like)).fetchall()
    results.extend([dict(r) for r in rows])
    
    # 搜索设备
    rows = db.execute("SELECT id, equipment_name as name, code, 'equipment' as type FROM eqp_ledger WHERE equipment_name LIKE ? OR code LIKE ? LIMIT 5", (like, like)).fetchall()
    results.extend([dict(r) for r in rows])
    
    # 搜索用户
    rows = db.execute("SELECT id, real_name as name, username as code, 'user' as type FROM sys_user WHERE real_name LIKE ? OR username LIKE ? LIMIT 5", (like, like)).fetchall()
    results.extend([dict(r) for r in rows])
    
    return jsonify({'code': 0, 'data': results})


@search_bp.route('/api/query/production')
@login_required
def query_production():
    """生产数据查询"""
    db = get_db()
    
    # 查询参数
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    workshop_id = request.args.get('workshop_id', '')
    product_id = request.args.get('product_id', '')
    status = request.args.get('status', '')
    
    where = "WHERE 1=1"
    params = []
    
    if start_date:
        where += " AND w.created_at >= ?"
        params.append(start_date)
    if end_date:
        where += " AND w.created_at <= ?"
        params.append(end_date + ' 23:59:59')
    if workshop_id:
        where += " AND w.workshop_id = ?"
        params.append(int(workshop_id))
    if product_id:
        where += " AND w.product_id = ?"
        params.append(int(product_id))
    if status:
        where += " AND w.status = ?"
        params.append(int(status))
    
    rows = db.execute(f'''SELECT w.*, p.product_name, p.code as product_code, ws.workshop_name
        FROM prod_workorder w
        LEFT JOIN base_product p ON w.product_id=p.id
        LEFT JOIN base_workshop ws ON w.workshop_id=ws.id
        {where}
        ORDER BY w.id DESC LIMIT 200''', params).fetchall()
    
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@search_bp.route('/api/query/inventory')
@login_required
def query_inventory():
    """库存数据查询"""
    db = get_db()
    
    keyword = request.args.get('keyword', '')
    product_type = request.args.get('product_type', '')
    min_qty = request.args.get('min_qty', '')
    max_qty = request.args.get('max_qty', '')
    
    where = "WHERE 1=1"
    params = []
    
    if keyword:
        where += " AND (p.product_name LIKE ? OR p.code LIKE ?)"
        like = f'%{keyword}%'
        params.extend([like, like])
    if product_type:
        where += " AND p.product_type = ?"
        params.append(product_type)
    if min_qty:
        where += " AND b.quantity >= ?"
        params.append(float(min_qty))
    if max_qty:
        where += " AND b.quantity <= ?"
        params.append(float(max_qty))
    
    rows = db.execute(f'''SELECT b.*, p.product_name, p.code, p.unit, p.product_type
        FROM inv_balance b
        LEFT JOIN base_product p ON b.product_id=p.id
        {where}
        ORDER BY b.quantity ASC''', params).fetchall()
    
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@search_bp.route('/api/query/quality')
@login_required
def query_quality():
    """质量数据查询"""
    db = get_db()
    
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    inspect_type = request.args.get('inspect_type', 'incoming')
    result_filter = request.args.get('result', '')
    
    table_map = {
        'incoming': 'qm_incoming_inspection',
        'process': 'qm_process_inspection',
        'outgoing': 'qm_outgoing_inspection'
    }
    table = table_map.get(inspect_type, 'qm_incoming_inspection')
    
    where = "WHERE 1=1"
    params = []
    
    if start_date:
        where += " AND created_at >= ?"
        params.append(start_date)
    if end_date:
        where += " AND created_at <= ?"
        params.append(end_date + ' 23:59:59')
    if result_filter:
        where += " AND result = ?"
        params.append(result_filter)
    
    rows = db.execute(f'''SELECT * FROM {table} {where} ORDER BY id DESC LIMIT 200''', params).fetchall()
    
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@search_bp.route('/api/query/equipment')
@login_required
def query_equipment():
    """设备数据查询"""
    db = get_db()
    
    keyword = request.args.get('keyword', '')
    status = request.args.get('status', '')
    workshop_id = request.args.get('workshop_id', '')
    
    where = "WHERE 1=1"
    params = []
    
    if keyword:
        where += " AND (el.equipment_name LIKE ? OR el.code LIKE ?)"
        like = f'%{keyword}%'
        params.extend([like, like])
    if status:
        where += " AND el.status = ?"
        params.append(int(status))
    if workshop_id:
        where += " AND el.workshop_id = ?"
        params.append(int(workshop_id))
    
    rows = db.execute(f'''SELECT el.*, et.type_name, ws.workshop_name
        FROM eqp_ledger el
        LEFT JOIN eqp_type et ON el.type_id=et.id
        LEFT JOIN base_workshop ws ON el.workshop_id=ws.id
        {where}
        ORDER BY el.id DESC''', params).fetchall()
    
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@search_bp.route('/api/query/employee')
@login_required
def query_employee():
    """员工数据查询"""
    db = get_db()
    
    keyword = request.args.get('keyword', '')
    dept_id = request.args.get('dept_id', '')
    
    where = "WHERE 1=1"
    params = []
    
    if keyword:
        where += " AND (u.real_name LIKE ? OR u.username LIKE ? OR u.phone LIKE ?)"
        like = f'%{keyword}%'
        params.extend([like, like, like])
    if dept_id:
        where += " AND u.dept_id = ?"
        params.append(int(dept_id))
    
    rows = db.execute(f'''SELECT u.id, u.username, u.real_name, u.phone, u.email, u.status,
        d.dept_name, r.role_name
        FROM sys_user u
        LEFT JOIN sys_dept d ON u.dept_id=d.id
        LEFT JOIN sys_role r ON u.role_id=r.id
        {where}
        ORDER BY u.id''', params).fetchall()
    
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@search_bp.route('/api/query/statistics')
@login_required
def query_statistics():
    """综合统计查询"""
    db = get_db()
    
    # 生产统计
    total_orders = db.execute("SELECT COUNT(*) as c FROM prod_workorder").fetchone()['c']
    completed_orders = db.execute("SELECT COUNT(*) as c FROM prod_workorder WHERE status=2").fetchone()['c']
    total_output = db.execute("SELECT COALESCE(SUM(completed_qty),0) as t FROM prod_workorder").fetchone()['t']
    total_defect = db.execute("SELECT COALESCE(SUM(defect_qty),0) as t FROM prod_workorder").fetchone()['t']
    
    # 库存统计
    total_products = db.execute("SELECT COUNT(*) as c FROM base_product WHERE status=1").fetchone()['c']
    total_stock = db.execute("SELECT COALESCE(SUM(quantity),0) as q FROM inv_balance").fetchone()['q']
    
    # 设备统计
    total_eqp = db.execute("SELECT COUNT(*) as c FROM eqp_ledger").fetchone()['c']
    running_eqp = db.execute("SELECT COUNT(*) as c FROM eqp_ledger WHERE status=1").fetchone()['c']
    
    # 人员统计
    total_users = db.execute("SELECT COUNT(*) as c FROM sys_user WHERE status=1").fetchone()['c']
    
    return jsonify({'code': 0, 'data': {
        'production': {
            'total_orders': total_orders,
            'completed_orders': completed_orders,
            'completion_rate': round(completed_orders / total_orders * 100, 2) if total_orders > 0 else 0,
            'total_output': total_output,
            'total_defect': total_defect,
            'defect_rate': round(total_defect / (total_output + total_defect) * 100, 2) if (total_output + total_defect) > 0 else 0
        },
        'inventory': {
            'total_products': total_products,
            'total_stock': total_stock
        },
        'equipment': {
            'total': total_eqp,
            'running': running_eqp,
            'utilization': round(running_eqp / total_eqp * 100, 2) if total_eqp > 0 else 0
        },
        'personnel': {
            'total_users': total_users
        }
    }})
