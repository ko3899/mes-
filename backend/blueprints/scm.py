"""供应链管理蓝图"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete, gen_no

scm_bp = Blueprint('scm', __name__)


@scm_bp.route('/api/scm/purchase/list')
@login_required
def purchase_list():
    """采购单列表"""
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as c FROM inv_inbound WHERE inbound_type='采购'").fetchone()['c']
    rows = db.execute('''SELECT i.*, s.supplier_name FROM inv_inbound i
        LEFT JOIN base_supplier s ON i.supplier=s.supplier_name
        WHERE i.inbound_type='采购' ORDER BY i.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@scm_bp.route('/api/scm/supplier/eval/list')
@login_required
def supplier_eval_list():
    """供应商评估列表"""
    db = get_db()
    rows = db.execute('''SELECT s.supplier_name, 
        COALESCE(AVG(e.total_score), 0) as avg_score,
        COUNT(e.id) as eval_count
        FROM base_supplier s
        LEFT JOIN qm_supplier_eval e ON s.id=e.supplier_id
        GROUP BY s.id ORDER BY avg_score DESC''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@scm_bp.route('/api/scm/supplier/ranking')
@login_required
def supplier_ranking():
    """供应商排名"""
    db = get_db()
    rows = db.execute('''SELECT s.supplier_name, s.code,
        COALESCE(AVG(e.total_score), 0) as avg_score,
        COUNT(e.id) as eval_count
        FROM base_supplier s
        LEFT JOIN qm_supplier_eval e ON s.id=e.supplier_id
        WHERE s.status=1
        GROUP BY s.id ORDER BY avg_score DESC''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})
