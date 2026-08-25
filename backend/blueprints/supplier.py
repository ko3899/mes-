"""供应商管理蓝图"""
from flask import Blueprint, request, jsonify
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete, permission_required

supplier_bp = Blueprint('supplier', __name__)


@supplier_bp.route('/api/base/supplier/list')
@login_required
def supplier_list():
    return jsonify(crud_list('base_supplier', request.args))


@supplier_bp.route('/api/base/supplier/add', methods=['POST'])
@permission_required('base:write')
def supplier_add():
    return jsonify(crud_add('base_supplier', request.json))


@supplier_bp.route('/api/base/supplier/update', methods=['POST'])
@permission_required('base:write')
def supplier_update():
    return jsonify(crud_update('base_supplier', request.json))


@supplier_bp.route('/api/base/supplier/delete', methods=['POST'])
@permission_required('base:write')
def supplier_delete():
    return jsonify(crud_delete('base_supplier', request.json.get('id')))


@supplier_bp.route('/api/base/supplier/all')
@login_required
def supplier_all():
    db = get_db()
    rows = db.execute("SELECT id, supplier_name, code FROM base_supplier WHERE status=1").fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})
