"""5S管理蓝图"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete, gen_no

five_s_bp = Blueprint('five_s', __name__)


@five_s_bp.route('/api/5s/audit/list')
@login_required
def audit_5s_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM sys_5s_audit").fetchone()['cnt']
    rows = db.execute('''SELECT a.*, ws.workshop_name, u.real_name as auditor_name
        FROM sys_5s_audit a
        LEFT JOIN base_workshop ws ON a.workshop_id=ws.id
        LEFT JOIN sys_user u ON a.auditor=u.id
        ORDER BY a.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@five_s_bp.route('/api/5s/audit/add', methods=['POST'])
@login_required
def audit_5s_add():
    d = request.json
    d['audit_no'] = gen_no('5S')
    d['auditor'] = session.get('user_id')
    # 计算总分
    scores = [int(d.get('sort_score', 0)), int(d.get('set_in_order_score', 0)),
              int(d.get('shine_score', 0)), int(d.get('standardize_score', 0)),
              int(d.get('sustain_score', 0))]
    d['total_score'] = round(sum(scores) / 5, 2)
    return jsonify(crud_add('sys_5s_audit', d))


@five_s_bp.route('/api/5s/audit/update', methods=['POST'])
@login_required
def audit_5s_update():
    d = request.json
    scores = [int(d.get('sort_score', 0)), int(d.get('set_in_order_score', 0)),
              int(d.get('shine_score', 0)), int(d.get('standardize_score', 0)),
              int(d.get('sustain_score', 0))]
    d['total_score'] = round(sum(scores) / 5, 2)
    return jsonify(crud_update('sys_5s_audit', d))


@five_s_bp.route('/api/5s/audit/delete', methods=['POST'])
@login_required
def audit_5s_delete():
    return jsonify(crud_delete('sys_5s_audit', request.json.get('id')))


@five_s_bp.route('/api/5s/statistics')
@login_required
def audit_5s_stats():
    db = get_db()
    rows = db.execute('''SELECT ws.workshop_name, AVG(a.total_score) as avg_score, COUNT(*) as audit_count
        FROM sys_5s_audit a
        LEFT JOIN base_workshop ws ON a.workshop_id=ws.id
        GROUP BY a.workshop_id ORDER BY avg_score DESC''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})
