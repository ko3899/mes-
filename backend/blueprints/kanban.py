"""生产看板蓝图。"""
import datetime
import os

from flask import Blueprint, jsonify, send_from_directory

from utils.database import BASE_DIR, get_db
from utils.helpers import login_required

kanban_bp = Blueprint('kanban', __name__)
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')


@kanban_bp.route('/api/kanban/realtime')
@login_required
def kanban_realtime():
    """返回生产看板当前完整快照。"""
    db = get_db()
    now = datetime.datetime.now()
    today = now.date().isoformat()

    active_orders = db.execute('''SELECT w.id, w.order_no, p.product_name,
        p.code AS product_code, w.planned_qty, w.completed_qty, w.status,
        ws.workshop_name, w.priority
        FROM prod_workorder w
        LEFT JOIN base_product p ON w.product_id=p.id
        LEFT JOIN base_workshop ws ON w.workshop_id=ws.id
        WHERE w.status IN (0,1)
        ORDER BY w.priority DESC, w.id ASC LIMIT 10''').fetchall()
    today_report = db.execute('''SELECT COALESCE(SUM(qualified_qty),0) AS qualified,
        COALESCE(SUM(defect_qty),0) AS defect
        FROM prod_report WHERE DATE(report_time)=?''', (today,)).fetchone()

    equipment = []
    for status, label in [(1, '运行'), (2, '维修'), (0, '停用')]:
        count = db.execute(
            "SELECT COUNT(*) AS count FROM eqp_ledger WHERE status=?",
            (status,),
        ).fetchone()['count']
        equipment.append({'name': label, 'value': count})

    workshop_output = db.execute('''SELECT ws.workshop_name,
        COALESCE(SUM(r.qualified_qty),0) AS qty
        FROM base_workshop ws
        LEFT JOIN base_process p ON ws.id=p.workshop_id
        LEFT JOIN prod_report r ON p.id=r.process_id AND DATE(r.report_time)=?
        GROUP BY ws.id ORDER BY qty DESC''', (today,)).fetchall()
    pending_quality = db.execute(
        "SELECT COUNT(*) AS count FROM qm_incoming_inspection WHERE status=0"
    ).fetchone()['count']
    failed_quality = db.execute(
        """SELECT COUNT(*) AS count FROM qm_incoming_inspection
           WHERE result='不合格' AND DATE(created_at)=?""",
        (today,),
    ).fetchone()['count']
    active_order_rows = [dict(row) for row in active_orders]

    return jsonify({'code': 0, 'data': {
        'server_time': now.isoformat(timespec='seconds'),
        'active_orders': active_order_rows,
        'active_order_count': len(active_order_rows),
        'today_qualified': today_report['qualified'],
        'today_defect': today_report['defect'],
        'eqp_stats': equipment,
        'equipment': equipment,
        'workshop_output': [dict(row) for row in workshop_output],
        'quality_alerts': {
            'pending': pending_quality,
            'failed_today': failed_quality,
        },
    }})


@kanban_bp.route('/kanban')
def kanban_page():
    return send_from_directory(FRONTEND_DIR, 'kanban.html')
