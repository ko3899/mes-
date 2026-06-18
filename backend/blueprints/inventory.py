"""库存管理蓝图"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete, gen_no

inventory_bp = Blueprint('inventory', __name__)


@inventory_bp.route('/api/inv/inbound/list')
@login_required
def inv_inbound_list():
    return jsonify(crud_list('inv_inbound', request.args))


@inventory_bp.route('/api/inv/inbound/add', methods=['POST'])
@login_required
def inv_inbound_add():
    data = request.json
    data['inbound_no'] = gen_no('RK')
    data['created_by'] = session.get('user_id')
    return jsonify(crud_add('inv_inbound', data))


@inventory_bp.route('/api/inv/inbound/update', methods=['POST'])
@login_required
def inv_inbound_update():
    return jsonify(crud_update('inv_inbound', request.json))


@inventory_bp.route('/api/inv/inbound/delete', methods=['POST'])
@login_required
def inv_inbound_delete():
    return jsonify(crud_delete('inv_inbound', request.json.get('id')))


@inventory_bp.route('/api/inv/outbound/list')
@login_required
def inv_outbound_list():
    return jsonify(crud_list('inv_outbound', request.args))


@inventory_bp.route('/api/inv/outbound/add', methods=['POST'])
@login_required
def inv_outbound_add():
    data = request.json
    data['outbound_no'] = gen_no('CK')
    data['created_by'] = session.get('user_id')
    return jsonify(crud_add('inv_outbound', data))


@inventory_bp.route('/api/inv/outbound/update', methods=['POST'])
@login_required
def inv_outbound_update():
    return jsonify(crud_update('inv_outbound', request.json))


@inventory_bp.route('/api/inv/outbound/delete', methods=['POST'])
@login_required
def inv_outbound_delete():
    return jsonify(crud_delete('inv_outbound', request.json.get('id')))


@inventory_bp.route('/api/inv/balance/list')
@login_required
def inv_balance_list():
    db = get_db()
    rows = db.execute('''SELECT b.*, p.product_name, p.code, p.unit
        FROM inv_balance b
        LEFT JOIN base_product p ON b.product_id=p.id
        ORDER BY b.id DESC''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})
