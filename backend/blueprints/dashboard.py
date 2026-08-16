"""仪表盘蓝图"""
import datetime
from flask import Blueprint, request, jsonify
from utils.database import get_db
from utils.helpers import login_required

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/api/dashboard')
@login_required
def dashboard():
    db = get_db()
    stats = {
        'products': db.execute("SELECT COUNT(*) as cnt FROM base_product WHERE status=1").fetchone()['cnt'],
        'workorders': db.execute("SELECT COUNT(*) as cnt FROM prod_workorder WHERE status IN (0,1,2,4)").fetchone()['cnt'],
        'inventory': db.execute("SELECT COUNT(*) as cnt FROM inv_balance").fetchone()['cnt'],
        'equipment': db.execute("SELECT COUNT(*) as cnt FROM eqp_ledger WHERE status=1").fetchone()['cnt'],
        'users': db.execute("SELECT COUNT(*) as cnt FROM sys_user WHERE status=1").fetchone()['cnt'],
        'tasks': db.execute("SELECT COUNT(*) as cnt FROM prod_task WHERE status IN (0,1)").fetchone()['cnt'],
    }
    return jsonify({'code': 0, 'data': stats})


@dashboard_bp.route('/api/dashboard/charts')
@login_required
def dashboard_charts():
    db = get_db()
    today = datetime.date.today()

    daily_output = []
    for i in range(6, -1, -1):
        d = today - datetime.timedelta(days=i)
        ds = d.strftime('%Y-%m-%d')
        row = db.execute("SELECT COALESCE(SUM(qualified_qty),0) as qty, COALESCE(SUM(defect_qty),0) as defect FROM prod_report WHERE DATE(report_time)=?", (ds,)).fetchone()
        daily_output.append({'date': ds, 'qualified': row['qty'], 'defect': row['defect']})

    wo_stats = []
    for st, label in [(0,'草稿'),(1,'已下达'),(2,'生产中'),(3,'已完工'),(4,'已暂停'),(5,'已关闭'),(6,'已取消')]:
        cnt = db.execute("SELECT COUNT(*) as c FROM prod_workorder WHERE status=?", (st,)).fetchone()['c']
        if cnt > 0:
            wo_stats.append({'name': label, 'value': cnt})

    total_eqp = db.execute("SELECT COUNT(*) as c FROM eqp_ledger").fetchone()['c']
    running_eqp = db.execute("SELECT COUNT(*) as c FROM eqp_ledger WHERE status=1").fetchone()['c']
    repair_eqp = db.execute("SELECT COUNT(*) as c FROM eqp_ledger WHERE status=2").fetchone()['c']
    eqp_rate = round(running_eqp / total_eqp * 100, 1) if total_eqp > 0 else 0

    workshop_output = db.execute('''
        SELECT ws.workshop_name, COALESCE(SUM(r.qualified_qty),0) as qty
        FROM base_workshop ws
        LEFT JOIN base_process p ON ws.id=p.workshop_id
        LEFT JOIN prod_report r ON p.id=r.process_id
        GROUP BY ws.id ORDER BY qty DESC
    ''').fetchall()

    total_qualified = db.execute("SELECT COALESCE(SUM(qualified_qty),0) as q FROM prod_report").fetchone()['q']
    total_defect = db.execute("SELECT COALESCE(SUM(defect_qty),0) as d FROM prod_report").fetchone()['d']
    total_qty = total_qualified + total_defect
    pass_rate = round(total_qualified / total_qty * 100, 1) if total_qty > 0 else 100

    low_stock = db.execute('''
        SELECT p.product_name, p.code, b.quantity
        FROM inv_balance b JOIN base_product p ON b.product_id=p.id
        WHERE b.quantity < 10 ORDER BY b.quantity ASC
    ''').fetchall()

    overdue_maint = db.execute('''
        SELECT m.plan_name, e.equipment_name, m.next_date
        FROM eqp_maintenance_plan m
        JOIN eqp_ledger e ON m.equipment_id=e.id
        WHERE m.next_date < ? AND m.status=1
        ORDER BY m.next_date ASC LIMIT 10
    ''', (today.strftime('%Y-%m-%d'),)).fetchall()

    return jsonify({'code': 0, 'data': {
        'daily_output': daily_output,
        'wo_stats': wo_stats,
        'eqp_rate': eqp_rate,
        'eqp_total': total_eqp,
        'eqp_running': running_eqp,
        'eqp_repair': repair_eqp,
        'workshop_output': [dict(r) for r in workshop_output],
        'pass_rate': pass_rate,
        'total_qualified': total_qualified,
        'total_defect': total_defect,
        'low_stock': [dict(r) for r in low_stock],
        'overdue_maint': [dict(r) for r in overdue_maint],
    }})
