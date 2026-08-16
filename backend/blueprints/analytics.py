"""数据分析蓝图 - OEE、产能、交期预警、库存周转"""
import datetime
from flask import Blueprint, request, jsonify
from utils.database import get_db
from utils.helpers import login_required

analytics_bp = Blueprint('analytics', __name__)


# ==================== OEE分析 ====================
@analytics_bp.route('/api/analytics/oee')
@login_required
def oee_analysis():
    db = get_db()
    days = int(request.args.get('days', 30))
    today = datetime.date.today()
    start = (today - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
    
    # 设备总数
    total_eqp = db.execute("SELECT COUNT(*) as c FROM eqp_ledger").fetchone()['c']
    running_eqp = db.execute("SELECT COUNT(*) as c FROM eqp_ledger WHERE status=1").fetchone()['c']
    
    # 可用率 = 运行设备 / 总设备
    availability = round(running_eqp / total_eqp * 100, 2) if total_eqp > 0 else 0
    
    # 表现率 = 实际产出 / 理论产出（简化计算）
    total_planned = db.execute("SELECT COALESCE(SUM(planned_qty),0) as t FROM prod_workorder WHERE created_at >= ?", (start,)).fetchone()['t']
    total_completed = db.execute("SELECT COALESCE(SUM(completed_qty),0) as t FROM prod_workorder WHERE created_at >= ?", (start,)).fetchone()['t']
    performance = round(total_completed / total_planned * 100, 2) if total_planned > 0 else 100
    
    # 良品率
    total_qualified = db.execute("SELECT COALESCE(SUM(qualified_qty),0) as q FROM prod_report WHERE report_time >= ?", (start,)).fetchone()['q']
    total_defect = db.execute("SELECT COALESCE(SUM(defect_qty),0) as d FROM prod_report WHERE report_time >= ?", (start,)).fetchone()['d']
    total_output = total_qualified + total_defect
    quality = round(total_qualified / total_output * 100, 2) if total_output > 0 else 100
    
    # OEE = 可用率 × 表现率 × 良品率
    oee = round(availability * performance * quality / 10000, 2)
    
    return jsonify({'code': 0, 'data': {
        'availability': availability,
        'performance': performance,
        'quality': quality,
        'oee': oee,
        'total_eqp': total_eqp,
        'running_eqp': running_eqp
    }})


# ==================== 产能分析 ====================
@analytics_bp.route('/api/analytics/capacity')
@login_required
def capacity_analysis():
    db = get_db()
    
    # 各车间产能
    workshops = db.execute('''SELECT ws.id, ws.workshop_name,
        (SELECT COUNT(*) FROM base_process p WHERE p.workshop_id=ws.id) as process_count,
        COALESCE(SUM(CASE WHEN w.status IN (0,1,2,4) THEN w.planned_qty ELSE 0 END), 0) as pending_qty,
        COALESCE(SUM(CASE WHEN w.status=3 THEN w.completed_qty ELSE 0 END), 0) as completed_qty
        FROM base_workshop ws
        LEFT JOIN prod_workorder w ON w.workshop_id=ws.id
        GROUP BY ws.id ORDER BY pending_qty DESC''').fetchall()
    
    # 员工效率
    employee_stats = db.execute('''SELECT u.real_name,
        COUNT(DISTINCT r.task_id) as task_count,
        COALESCE(SUM(r.qualified_qty), 0) as total_qualified,
        COALESCE(SUM(r.defect_qty), 0) as total_defect
        FROM prod_report r
        LEFT JOIN sys_user u ON r.user_id=u.id
        GROUP BY r.user_id ORDER BY total_qualified DESC LIMIT 20''').fetchall()
    
    return jsonify({'code': 0, 'data': {
        'workshops': [dict(w) for w in workshops],
        'employees': [dict(e) for e in employee_stats]
    }})


# ==================== 交期预警 ====================
@analytics_bp.route('/api/analytics/delivery-alert')
@login_required
def delivery_alert():
    db = get_db()
    today = datetime.date.today().strftime('%Y-%m-%d')
    
    # 逾期工单
    overdue = db.execute('''SELECT w.order_no, p.product_name, w.planned_qty, w.completed_qty,
        w.end_date, ws.workshop_name
        FROM prod_workorder w
        LEFT JOIN base_product p ON w.product_id=p.id
        LEFT JOIN base_workshop ws ON w.workshop_id=ws.id
        WHERE w.end_date IS NOT NULL AND w.end_date < ? AND w.status IN (0,1,2,4)
        ORDER BY w.end_date ASC''', (today,)).fetchall()
    
    # 即将到期（3天内）
    soon = (datetime.date.today() + datetime.timedelta(days=3)).strftime('%Y-%m-%d')
    upcoming = db.execute('''SELECT w.order_no, p.product_name, w.planned_qty, w.completed_qty,
        w.end_date, ws.workshop_name
        FROM prod_workorder w
        LEFT JOIN base_product p ON w.product_id=p.id
        LEFT JOIN base_workshop ws ON w.workshop_id=ws.id
        WHERE w.end_date IS NOT NULL AND w.end_date BETWEEN ? AND ? AND w.status IN (0,1,2,4)
        ORDER BY w.end_date ASC''', (today, soon)).fetchall()
    
    return jsonify({'code': 0, 'data': {
        'overdue': [dict(r) for r in overdue],
        'upcoming': [dict(r) for r in upcoming]
    }})


# ==================== 库存周转率 ====================
@analytics_bp.route('/api/analytics/inventory-turnover')
@login_required
def inventory_turnover():
    db = get_db()
    days = int(request.args.get('days', 30))
    today = datetime.date.today()
    start = (today - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
    
    # 库存统计
    total_stock = db.execute("SELECT COALESCE(SUM(quantity),0) as q, COALESCE(SUM(amount),0) as a FROM inv_balance").fetchone()
    
    # 出库总量
    outbound_qty = db.execute('''SELECT COALESCE(SUM(oi.quantity),0) as q
        FROM inv_outbound_item oi
        JOIN inv_outbound o ON oi.outbound_id=o.id
        WHERE o.created_at >= ?''', (start,)).fetchone()['q']
    
    # 库存周转率 = 出库量 / 平均库存
    turnover_rate = round(outbound_qty / total_stock['q'], 2) if total_stock['q'] > 0 else 0
    
    # ABC分析
    abc_data = db.execute('''SELECT p.product_name, b.quantity, b.amount,
        CASE 
            WHEN b.amount >= 10000 THEN 'A'
            WHEN b.amount >= 1000 THEN 'B'
            ELSE 'C'
        END as abc_class
        FROM inv_balance b
        LEFT JOIN base_product p ON b.product_id=p.id
        ORDER BY b.amount DESC''').fetchall()
    
    # 低库存预警
    low_stock = db.execute('''SELECT p.product_name, p.code, b.quantity
        FROM inv_balance b JOIN base_product p ON b.product_id=p.id
        WHERE b.quantity < 10 ORDER BY b.quantity ASC''').fetchall()
    
    return jsonify({'code': 0, 'data': {
        'total_stock_qty': total_stock['q'],
        'total_stock_amount': total_stock['a'],
        'outbound_qty': outbound_qty,
        'turnover_rate': turnover_rate,
        'abc_analysis': [dict(r) for r in abc_data],
        'low_stock': [dict(r) for r in low_stock]
    }})


# ==================== 移动端报表数据 ====================
@analytics_bp.route('/api/analytics/mobile-dashboard')
@login_required
def mobile_dashboard():
    db = get_db()
    today = datetime.date.today().strftime('%Y-%m-%d')
    
    today_report = db.execute('''SELECT COALESCE(SUM(qualified_qty),0) as qualified,
        COALESCE(SUM(defect_qty),0) as defect
        FROM prod_report WHERE DATE(report_time)=?''', (today,)).fetchone()
    
    active_orders = db.execute("SELECT COUNT(*) as c FROM prod_workorder WHERE status IN (0,1,2,4)").fetchone()['c']
    pending_tasks = db.execute("SELECT COUNT(*) as c FROM prod_task WHERE status=0").fetchone()['c']
    
    total_eqp = db.execute("SELECT COUNT(*) as c FROM eqp_ledger").fetchone()['c']
    running_eqp = db.execute("SELECT COUNT(*) as c FROM eqp_ledger WHERE status=1").fetchone()['c']
    eqp_rate = round(running_eqp / total_eqp * 100, 1) if total_eqp > 0 else 0
    
    return jsonify({'code': 0, 'data': {
        'today_qualified': today_report['qualified'],
        'today_defect': today_report['defect'],
        'active_orders': active_orders,
        'pending_tasks': pending_tasks,
        'eqp_rate': eqp_rate
    }})


# ==================== 良率统计 ====================
@analytics_bp.route('/api/analytics/yield')
@login_required
def yield_analysis():
    """良率统计"""
    db = get_db()
    days = int(request.args.get('days', 30))
    process_id = request.args.get('process_id', '')
    today = datetime.date.today()
    start = (today - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
    
    where = "WHERE r.report_time >= ?"
    params = [start]
    if process_id:
        where += " AND r.process_id=?"
        params.append(int(process_id))
    
    # 每日良率
    daily_yield = db.execute(f'''SELECT DATE(r.report_time) as dt,
        COALESCE(SUM(r.qualified_qty),0) as qualified,
        COALESCE(SUM(r.defect_qty),0) as defect
        FROM prod_report r {where}
        GROUP BY DATE(r.report_time) ORDER BY dt''', params).fetchall()
    
    daily_data = []
    for row in daily_yield:
        total = row['qualified'] + row['defect']
        rate = round(row['qualified'] / total * 100, 2) if total > 0 else 100
        daily_data.append({
            'date': row['dt'],
            'qualified': row['qualified'],
            'defect': row['defect'],
            'total': total,
            'yield_rate': rate
        })
    
    # 各工序良率
    process_yield = db.execute(f'''SELECT p.process_name,
        COALESCE(SUM(r.qualified_qty),0) as qualified,
        COALESCE(SUM(r.defect_qty),0) as defect
        FROM prod_report r
        LEFT JOIN base_process p ON r.process_id=p.id
        {where}
        GROUP BY r.process_id ORDER BY qualified DESC''', params).fetchall()
    
    process_data = []
    for row in process_yield:
        total = row['qualified'] + row['defect']
        rate = round(row['qualified'] / total * 100, 2) if total > 0 else 100
        process_data.append({
            'process': row['process_name'] or '-',
            'qualified': row['qualified'],
            'defect': row['defect'],
            'yield_rate': rate
        })
    
    # 总体良率
    total_qualified = sum(d['qualified'] for d in daily_data)
    total_defect = sum(d['defect'] for d in daily_data)
    total_all = total_qualified + total_defect
    overall_yield = round(total_qualified / total_all * 100, 2) if total_all > 0 else 100
    
    # 良率趋势
    if len(daily_data) >= 2:
        rates = [d['yield_rate'] for d in daily_data]
        avg_rate = sum(rates) / len(rates)
        trend = 'up' if rates[-1] > rates[0] else ('down' if rates[-1] < rates[0] else 'stable')
    else:
        avg_rate = overall_yield
        trend = 'stable'
    
    return jsonify({'code': 0, 'data': {
        'overall_yield': overall_yield,
        'avg_yield': round(avg_rate, 2),
        'total_qualified': total_qualified,
        'total_defect': total_defect,
        'trend': trend,
        'daily': daily_data,
        'by_process': process_data
    }})


# ==================== 数据看板 ====================
@analytics_bp.route('/api/analytics/data-dashboard')
@login_required
def data_dashboard():
    """综合数据看板"""
    db = get_db()
    today = datetime.date.today()
    today_str = today.strftime('%Y-%m-%d')
    
    # 生产数据
    today_output = db.execute('''SELECT COALESCE(SUM(qualified_qty),0) as q, COALESCE(SUM(defect_qty),0) as d
        FROM prod_report WHERE DATE(report_time)=?''', (today_str,)).fetchone()
    today_total = today_output['q'] + today_output['d']
    today_yield = round(today_output['q'] / today_total * 100, 2) if today_total > 0 else 100
    
    # 工单状态
    wo_stats = []
    for st, label in [(0,'草稿'),(1,'已下达'),(2,'生产中'),(3,'已完工'),(4,'已暂停'),(5,'已关闭'),(6,'已取消')]:
        cnt = db.execute("SELECT COUNT(*) as c FROM prod_workorder WHERE status=?", (st,)).fetchone()['c']
        wo_stats.append({'name': label, 'value': cnt})
    
    # 设备状态
    eqp_stats = []
    for st, label in [(1,'运行'),(2,'维修'),(0,'停用')]:
        cnt = db.execute("SELECT COUNT(*) as c FROM eqp_ledger WHERE status=?", (st,)).fetchone()['c']
        eqp_stats.append({'name': label, 'value': cnt})
    
    # 库存预警
    low_stock = db.execute('''SELECT p.product_name, p.code, b.quantity
        FROM inv_balance b JOIN base_product p ON b.product_id=p.id
        WHERE b.quantity < 10 ORDER BY b.quantity ASC LIMIT 10''').fetchall()
    
    # 异常统计
    exceptions = db.execute("SELECT COUNT(*) as c FROM prod_exception WHERE status=0").fetchone()['c']
    defects = db.execute("SELECT COUNT(*) as c FROM prod_defect_receive WHERE status=0").fetchone()['c']
    
    # 近7天良率趋势
    yield_trend = []
    for i in range(6, -1, -1):
        d = today - datetime.timedelta(days=i)
        ds = d.strftime('%Y-%m-%d')
        row = db.execute('''SELECT COALESCE(SUM(qualified_qty),0) as q, COALESCE(SUM(defect_qty),0) as d
            FROM prod_report WHERE DATE(report_time)=?''', (ds,)).fetchone()
        total = row['q'] + row['d']
        rate = round(row['q'] / total * 100, 2) if total > 0 else 100
        yield_trend.append({'date': ds, 'rate': rate, 'total': total})
    
    return jsonify({'code': 0, 'data': {
        'today': {
            'output': today_total,
            'qualified': today_output['q'],
            'defect': today_output['d'],
            'yield_rate': today_yield
        },
        'wo_stats': wo_stats,
        'eqp_stats': eqp_stats,
        'low_stock': [dict(r) for r in low_stock],
        'alerts': {
            'exceptions': exceptions,
            'defects': defects
        },
        'yield_trend': yield_trend
    }})
