"""售后管理蓝图"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete, gen_no

svc_bp = Blueprint('svc', __name__)


# ==================== 客诉管理 ====================
@svc_bp.route('/api/svc/complaint/list')
@login_required
def complaint_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM svc_complaint").fetchone()['cnt']
    rows = db.execute('''SELECT c.*, cu.customer_name, p.product_name
        FROM svc_complaint c
        LEFT JOIN base_customer cu ON c.customer_id=cu.id
        LEFT JOIN base_product p ON c.product_id=p.id
        ORDER BY c.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@svc_bp.route('/api/svc/complaint/add', methods=['POST'])
@login_required
def complaint_add():
    d = request.json
    d['complaint_no'] = gen_no('CS')
    d['handler'] = session.get('user_id')
    return jsonify(crud_add('svc_complaint', d))


@svc_bp.route('/api/svc/complaint/update', methods=['POST'])
@login_required
def complaint_update():
    return jsonify(crud_update('svc_complaint', request.json))


# ==================== 退换货 ====================
@svc_bp.route('/api/svc/return/list')
@login_required
def return_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM svc_return").fetchone()['cnt']
    rows = db.execute('''SELECT r.*, cu.customer_name, p.product_name
        FROM svc_return r
        LEFT JOIN base_customer cu ON r.customer_id=cu.id
        LEFT JOIN base_product p ON r.product_id=p.id
        ORDER BY r.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@svc_bp.route('/api/svc/return/add', methods=['POST'])
@login_required
def return_add():
    d = request.json
    d['return_no'] = gen_no('SR')
    return jsonify(crud_add('svc_return', d))


@svc_bp.route('/api/svc/return/update', methods=['POST'])
@login_required
def return_update():
    return jsonify(crud_update('svc_return', request.json))


@svc_bp.route('/api/svc/statistics')
@login_required
def svc_statistics():
    db = get_db()
    total_complaints = db.execute("SELECT COUNT(*) as c FROM svc_complaint").fetchone()['c']
    pending = db.execute("SELECT COUNT(*) as c FROM svc_complaint WHERE status=0").fetchone()['c']
    total_returns = db.execute("SELECT COUNT(*) as c FROM svc_return").fetchone()['c']
    
    by_type = db.execute('''SELECT complaint_type, COUNT(*) as count FROM svc_complaint 
        GROUP BY complaint_type ORDER BY count DESC''').fetchall()
    
    return jsonify({'code': 0, 'data': {
        'total_complaints': total_complaints,
        'pending': pending,
        'total_returns': total_returns,
        'by_type': [dict(r) for r in by_type]
    }})
