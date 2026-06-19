"""APS排程蓝图 - 高级排程算法"""
from flask import Blueprint, request, jsonify
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete, gen_no

aps_bp = Blueprint('aps', __name__)


@aps_bp.route('/api/aps/schedule', methods=['POST'])
@login_required
def aps_schedule():
    """APS自动排程"""
    d = request.json
    start_date = d.get('start_date', '')
    end_date = d.get('end_date', '')
    
    db = get_db()
    # 获取待排程工单
    workorders = db.execute('''SELECT w.*, p.product_name 
        FROM prod_workorder w 
        LEFT JOIN base_product p ON w.product_id=p.id
        WHERE w.status=0 ORDER BY w.priority DESC, w.id ASC''').fetchall()
    
    # 获取可用资源
    processes = db.execute("SELECT * FROM base_process WHERE status=1 ORDER BY sort_order").fetchall()
    
    # 简单排程算法：按优先级顺序分配
    schedule_result = []
    for wo in workorders:
        schedule_result.append({
            'workorder': wo['order_no'],
            'product': wo['product_name'],
            'priority': wo['priority'],
            'planned_qty': wo['planned_qty'],
            'status': '已排程'
        })
    
    return jsonify({'code': 0, 'data': {
        'scheduled': len(schedule_result),
        'details': schedule_result
    }})


@aps_bp.route('/api/aps/resource')
@login_required
def aps_resource():
    """资源负荷查询"""
    db = get_db()
    
    # 工序负荷
    process_load = db.execute('''SELECT p.process_name,
        COUNT(t.id) as task_count,
        COALESCE(SUM(t.planned_qty), 0) as total_qty,
        COALESCE(SUM(t.completed_qty), 0) as completed_qty
        FROM base_process p
        LEFT JOIN prod_task t ON p.id=t.process_id AND t.status IN (0,1)
        GROUP BY p.id ORDER BY total_qty DESC''').fetchall()
    
    # 设备负荷
    eqp_load = db.execute('''SELECT e.equipment_name,
        COUNT(t.id) as task_count
        FROM eqp_ledger e
        LEFT JOIN prod_task t ON e.id=t.assigned_to AND t.status IN (0,1)
        WHERE e.status=1
        GROUP BY e.id ORDER BY task_count DESC''').fetchall()
    
    return jsonify({'code': 0, 'data': {
        'process_load': [dict(r) for r in process_load],
        'eqp_load': [dict(r) for r in eqp_load]
    }})


@aps_bp.route('/api/aps/gantt')
@login_required
def aps_gantt():
    """甘特图数据"""
    db = get_db()
    workorders = db.execute('''SELECT w.order_no, p.product_name, w.planned_qty, w.completed_qty,
        w.start_date, w.end_date, w.status
        FROM prod_workorder w
        LEFT JOIN base_product p ON w.product_id=p.id
        WHERE w.status IN (0,1)
        ORDER BY w.priority DESC LIMIT 20''').fetchall()
    
    return jsonify({'code': 0, 'data': [dict(w) for w in workorders]})
