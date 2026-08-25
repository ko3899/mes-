"""售后管理蓝图"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete, gen_no, permission_required

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
@permission_required('svc:write')
def complaint_add():
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        return jsonify({'code': 400, 'message': '请求数据必须是JSON对象'}), 400
    if not d.get('customer_id') or not d.get('product_id'):
        return jsonify({'code': 400, 'message': '客户和产品不能为空'}), 400
    if not str(d.get('description') or '').strip():
        return jsonify({'code': 400, 'message': '客诉描述不能为空'}), 400
    if d.get('severity', 'medium') not in ('low', 'medium', 'high', 'critical'):
        return jsonify({'code': 400, 'message': '严重度参数错误'}), 400
    db = get_db()
    if not db.execute('SELECT 1 FROM base_customer WHERE id=?', (d['customer_id'],)).fetchone():
        return jsonify({'code': 404, 'message': '客户不存在'}), 404
    if not db.execute('SELECT 1 FROM base_product WHERE id=?', (d['product_id'],)).fetchone():
        return jsonify({'code': 404, 'message': '产品不存在'}), 404
    d['complaint_no'] = gen_no('CS')
    d['handler'] = session.get('user_id')
    return jsonify(crud_add('svc_complaint', d))


@svc_bp.route('/api/svc/complaint/update', methods=['POST'])
@permission_required('svc:write')
def complaint_update():
    return jsonify(crud_update('svc_complaint', request.json))


@svc_bp.route('/api/svc/complaint/delete', methods=['POST'])
@permission_required('svc:write')
def complaint_delete():
    return jsonify(crud_delete('svc_complaint', request.json.get('id')))


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
@permission_required('svc:write')
def return_add():
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        return jsonify({'code': 400, 'message': '请求数据必须是JSON对象'}), 400
    try:
        quantity = float(d.get('quantity'))
    except (TypeError, ValueError):
        return jsonify({'code': 400, 'message': '退换货数量必须是数字'}), 400
    if quantity <= 0:
        return jsonify({'code': 400, 'message': '退换货数量必须大于0'}), 400
    if not d.get('customer_id') or not d.get('product_id'):
        return jsonify({'code': 400, 'message': '客户和产品不能为空'}), 400
    reason = str(d.pop('reason', d.get('return_reason') or '') or '').strip()
    if not reason:
        return jsonify({'code': 400, 'message': '退换货原因不能为空'}), 400
    db = get_db()
    if not db.execute('SELECT 1 FROM base_customer WHERE id=?', (d['customer_id'],)).fetchone():
        return jsonify({'code': 404, 'message': '客户不存在'}), 404
    if not db.execute('SELECT 1 FROM base_product WHERE id=?', (d['product_id'],)).fetchone():
        return jsonify({'code': 404, 'message': '产品不存在'}), 404
    complaint_id = d.get('complaint_id')
    if complaint_id and not db.execute(
        'SELECT 1 FROM svc_complaint WHERE id=?', (complaint_id,)
    ).fetchone():
        return jsonify({'code': 404, 'message': '关联客诉不存在'}), 404
    d['quantity'] = quantity
    d['return_reason'] = reason
    d['handler'] = session.get('user_id')
    d['return_no'] = gen_no('SR')
    return jsonify(crud_add('svc_return', d))


@svc_bp.route('/api/svc/return/update', methods=['POST'])
@permission_required('svc:write')
def return_update():
    d = request.get_json(silent=True)
    if not isinstance(d, dict) or not d.get('id'):
        return jsonify({'code': 400, 'message': '缺少退换货记录ID'}), 400
    if 'quantity' in d:
        try:
            d['quantity'] = float(d['quantity'])
        except (TypeError, ValueError):
            return jsonify({'code': 400, 'message': '退换货数量必须是数字'}), 400
        if d['quantity'] <= 0:
            return jsonify({'code': 400, 'message': '退换货数量必须大于0'}), 400
    if 'reason' in d:
        d['return_reason'] = d.pop('reason')
    return jsonify(crud_update('svc_return', d))


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
