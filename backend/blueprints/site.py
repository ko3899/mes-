"""生产现场蓝图 - 工位/安灯/返工报废"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete, gen_no

site_bp = Blueprint('site', __name__)


# ==================== 工位管理 ====================
@site_bp.route('/api/site/workstation/list')
@login_required
def workstation_list():
    db = get_db()
    rows = db.execute('''SELECT w.*, ws.workshop_name, p.process_name
        FROM base_workstation w
        LEFT JOIN base_workshop ws ON w.workshop_id=ws.id
        LEFT JOIN base_process p ON w.process_id=p.id
        ORDER BY w.id DESC''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@site_bp.route('/api/site/workstation/add', methods=['POST'])
@login_required
def workstation_add():
    return jsonify(crud_add('base_workstation', request.json))


@site_bp.route('/api/site/workstation/update', methods=['POST'])
@login_required
def workstation_update():
    return jsonify(crud_update('base_workstation', request.json))


@site_bp.route('/api/site/workstation/delete', methods=['POST'])
@login_required
def workstation_delete():
    return jsonify(crud_delete('base_workstation', request.json.get('id')))


# ==================== 安灯系统 ====================
@site_bp.route('/api/site/andon/list')
@login_required
def andon_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM prod_andon").fetchone()['cnt']
    rows = db.execute('''SELECT a.*, ws.station_name,
        u1.real_name as caller_name, u2.real_name as responder_name
        FROM prod_andon a
        LEFT JOIN base_workstation ws ON a.workstation_id=ws.id
        LEFT JOIN sys_user u1 ON a.caller=u1.id
        LEFT JOIN sys_user u2 ON a.responder=u2.id
        ORDER BY a.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@site_bp.route('/api/site/andon/call', methods=['POST'])
@login_required
def andon_call():
    d = request.json
    d['andon_no'] = gen_no('AD')
    d['caller'] = session.get('user_id')
    return jsonify(crud_add('prod_andon', d))


@site_bp.route('/api/site/andon/respond', methods=['POST'])
@login_required
def andon_respond():
    import datetime
    d = request.json
    db = get_db()
    db.execute("UPDATE prod_andon SET status=1, responder=?, response_time=CURRENT_TIMESTAMP WHERE id=?",
               (session.get('user_id'), d['id']))
    db.commit()
    return jsonify({'code': 0, 'message': '已响应'})


@site_bp.route('/api/site/andon/resolve', methods=['POST'])
@login_required
def andon_resolve():
    d = request.json
    db = get_db()
    db.execute("UPDATE prod_andon SET status=2, resolve_time=CURRENT_TIMESTAMP, remark=? WHERE id=?",
               (d.get('remark', ''), d['id']))
    db.commit()
    return jsonify({'code': 0, 'message': '已解决'})


# ==================== 返工报废 ====================
@site_bp.route('/api/site/rework/list')
@login_required
def rework_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM prod_rework").fetchone()['cnt']
    rows = db.execute('''SELECT r.*, w.order_no as workorder_no
        FROM prod_rework r
        LEFT JOIN prod_workorder w ON r.workorder_id=w.id
        ORDER BY r.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@site_bp.route('/api/site/rework/add', methods=['POST'])
@login_required
def rework_add():
    d = request.json
    d['rework_no'] = gen_no('RW')
    d['operator'] = session.get('user_id')
    return jsonify(crud_add('prod_rework', d))


@site_bp.route('/api/site/rework/update', methods=['POST'])
@login_required
def rework_update():
    return jsonify(crud_update('prod_rework', request.json))
