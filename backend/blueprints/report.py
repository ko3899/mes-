"""报表蓝图"""
import datetime
from flask import Blueprint, request, jsonify, send_file
from utils.database import get_db
from utils.helpers import login_required
from utils.pdf_generator import generate_production_report_html, save_report_html

report_bp = Blueprint('report', __name__)


@report_bp.route('/api/report/production')
@login_required
def report_production():
    db = get_db()
    total_orders = db.execute("SELECT COUNT(*) as cnt FROM prod_workorder").fetchone()['cnt']
    completed = db.execute("SELECT COUNT(*) as cnt FROM prod_workorder WHERE status=3").fetchone()['cnt']
    in_progress = db.execute("SELECT COUNT(*) as cnt FROM prod_workorder WHERE status IN (1,2)").fetchone()['cnt']
    pending = db.execute("SELECT COUNT(*) as cnt FROM prod_workorder WHERE status=0").fetchone()['cnt']
    total_qty = db.execute("SELECT COALESCE(SUM(completed_qty),0) as total FROM prod_workorder").fetchone()['total']
    defect_qty = db.execute("SELECT COALESCE(SUM(defect_qty),0) as total FROM prod_workorder").fetchone()['total']
    today_reports = db.execute("SELECT COUNT(*) as cnt FROM prod_report WHERE DATE(report_time)=DATE('now')").fetchone()['cnt']
    workshop_stats = db.execute('''SELECT ws.workshop_name, COALESCE(SUM(w.completed_qty),0) as qty
        FROM base_workshop ws
        LEFT JOIN prod_workorder w ON ws.id=w.workshop_id
        GROUP BY ws.id ORDER BY qty DESC''').fetchall()

    return jsonify({
        'code': 0,
        'data': {
            'total_orders': total_orders,
            'completed': completed,
            'in_progress': in_progress,
            'pending': pending,
            'total_qty': total_qty,
            'defect_qty': defect_qty,
            'defect_rate': round(defect_qty / total_qty * 100, 2) if total_qty > 0 else 0,
            'today_reports': today_reports,
            'workshop_stats': [dict(r) for r in workshop_stats]
        }
    })


@report_bp.route('/api/spc/data')
@login_required
def spc_data():
    db = get_db()
    process_id = request.args.get('process_id')
    product_id = request.args.get('product_id')
    days = int(request.args.get('days', 30))
    today = datetime.date.today()
    start = (today - datetime.timedelta(days=days)).strftime('%Y-%m-%d')

    where = "WHERE r.report_time >= ?"
    params = [start]
    if process_id:
        where += " AND r.process_id=?"
        params.append(int(process_id))
    if product_id:
        where += " AND t.workorder_id IN (SELECT id FROM prod_workorder WHERE product_id=?)"
        params.append(int(product_id))

    rows = db.execute(f'''SELECT r.report_time, r.qualified_qty, r.defect_qty,
        p.process_name, r.process_id
        FROM prod_report r
        LEFT JOIN base_process p ON r.process_id=p.id
        LEFT JOIN prod_task t ON r.task_id=t.id
        {where}
        ORDER BY r.report_time''', params).fetchall()

    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@report_bp.route('/api/spc/chart')
@login_required
def spc_chart():
    db = get_db()
    process_id = request.args.get('process_id')
    days = int(request.args.get('days', 30))
    today = datetime.date.today()
    start = (today - datetime.timedelta(days=days)).strftime('%Y-%m-%d')

    where = "WHERE r.report_time >= ?"
    params = [start]
    if process_id:
        where += " AND r.process_id=?"
        params.append(int(process_id))

    rows = db.execute(f'''SELECT DATE(r.report_time) as dt,
        AVG(r.qualified_qty) as avg_q, MAX(r.qualified_qty) as max_q, MIN(r.qualified_qty) as min_q,
        SUM(r.qualified_qty) as sum_q, SUM(r.defect_qty) as sum_d, COUNT(*) as cnt
        FROM prod_report r {where}
        GROUP BY DATE(r.report_time) ORDER BY dt''', params).fetchall()

    data = []
    for r in rows:
        total = r['sum_q'] + r['sum_d']
        rate = round(r['sum_q'] / total * 100, 2) if total > 0 else 100
        data.append({
            'date': r['dt'], 'avg': round(r['avg_q'], 2),
            'max': r['max_q'], 'min': r['min_q'],
            'rate': rate, 'total': total
        })

    if len(data) >= 2:
        rates = [d['rate'] for d in data]
        x_bar = sum(rates) / len(rates)
        variance = sum((x - x_bar) ** 2 for x in rates) / len(rates)
        std = variance ** 0.5
        ucl = min(round(x_bar + 3 * std, 2), 100)
        lcl = max(round(x_bar - 3 * std, 2), 0)
        cl = round(x_bar, 2)
    else:
        ucl, lcl, cl = 100, 0, 100

    return jsonify({'code': 0, 'data': {'points': data, 'ucl': ucl, 'lcl': lcl, 'cl': cl}})


@report_bp.route('/api/spc/cpk')
@login_required
def spc_cpk():
    db = get_db()
    process_id = request.args.get('process_id')
    days = int(request.args.get('days', 30))
    usl = float(request.args.get('usl', 100))
    lsl = float(request.args.get('lsl', 0))
    today = datetime.date.today()
    start = (today - datetime.timedelta(days=days)).strftime('%Y-%m-%d')

    where = "WHERE r.report_time >= ?"
    params = [start]
    if process_id:
        where += " AND r.process_id=?"
        params.append(int(process_id))

    rows = db.execute(f'''SELECT r.qualified_qty FROM prod_report r {where}''', params).fetchall()
    values = [r['qualified_qty'] for r in rows if r['qualified_qty'] is not None]

    if len(values) < 2:
        return jsonify({'code': 0, 'data': {'cp': 0, 'cpk': 0, 'count': len(values)}})

    x_bar = sum(values) / len(values)
    variance = sum((x - x_bar) ** 2 for x in values) / len(values)
    std = variance ** 0.5

    if std == 0:
        cp = cpk = float('inf')
    else:
        cp = (usl - lsl) / (6 * std)
        cpu = (usl - x_bar) / (3 * std)
        cpl = (x_bar - lsl) / (3 * std)
        cpk = min(cpu, cpl)

    if cpk >= 1.67:
        judgment = '过程能力优秀'
    elif cpk >= 1.33:
        judgment = '过程能力良好'
    elif cpk >= 1.0:
        judgment = '过程能力尚可'
    else:
        judgment = '过程能力不足，需改善'

    return jsonify({'code': 0, 'data': {
        'cp': round(cp, 4), 'cpk': round(cpk, 4),
        'x_bar': round(x_bar, 4), 'std': round(std, 4),
        'usl': usl, 'lsl': lsl,
        'count': len(values), 'judgment': judgment
    }})


@report_bp.route('/api/kanban/production')
@login_required
def kanban_production():
    db = get_db()
    orders = db.execute('''SELECT w.order_no, p.product_name, w.planned_qty, w.completed_qty,
        w.status, ws.workshop_name
        FROM prod_workorder w
        LEFT JOIN base_product p ON w.product_id=p.id
        LEFT JOIN base_workshop ws ON w.workshop_id=ws.id
        WHERE w.status IN (0,1,2,4)
        ORDER BY w.priority DESC, w.id ASC LIMIT 20''').fetchall()

    process_stats = db.execute('''SELECT pr.process_name,
        COALESCE(SUM(t.completed_qty),0) as completed,
        COALESCE(SUM(t.defect_qty),0) as defect
        FROM base_process pr
        LEFT JOIN prod_task t ON pr.id=t.process_id
        GROUP BY pr.id ORDER BY completed DESC''').fetchall()

    return jsonify({
        'code': 0,
        'data': {
            'orders': [dict(r) for r in orders],
            'process_stats': [dict(r) for r in process_stats]
        }
    })


@report_bp.route('/api/report/production/pdf')
@login_required
def export_production_pdf():
    """导出生产报表"""
    db = get_db()
    total_orders = db.execute("SELECT COUNT(*) as cnt FROM prod_workorder").fetchone()['cnt']
    completed = db.execute("SELECT COUNT(*) as cnt FROM prod_workorder WHERE status=3").fetchone()['cnt']
    in_progress = db.execute("SELECT COUNT(*) as cnt FROM prod_workorder WHERE status IN (1,2)").fetchone()['cnt']
    total_qty = db.execute("SELECT COALESCE(SUM(completed_qty),0) as total FROM prod_workorder").fetchone()['total']
    defect_qty = db.execute("SELECT COALESCE(SUM(defect_qty),0) as total FROM prod_workorder").fetchone()['total']
    workshop_stats = db.execute('''SELECT ws.workshop_name, COALESCE(SUM(w.completed_qty),0) as qty
        FROM base_workshop ws LEFT JOIN prod_workorder w ON ws.id=w.workshop_id
        GROUP BY ws.id ORDER BY qty DESC''').fetchall()

    data = {
        'total_orders': total_orders,
        'completed': completed,
        'in_progress': in_progress,
        'defect_rate': round(defect_qty / total_qty * 100, 2) if total_qty > 0 else 0,
        'workshop_stats': [dict(r) for r in workshop_stats]
    }

    html = generate_production_report_html(data)
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    filepath = save_report_html(html, f'production_report_{timestamp}.html')
    return send_file(filepath, as_attachment=True, download_name=f'生产报表_{timestamp}.html')
