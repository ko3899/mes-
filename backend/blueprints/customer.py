"""客户管理蓝图"""
from flask import Blueprint, request, jsonify
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete

customer_bp = Blueprint('customer', __name__)


@customer_bp.route('/api/base/customer/list')
@login_required
def customer_list():
    return jsonify(crud_list('base_customer', request.args))


@customer_bp.route('/api/base/customer/add', methods=['POST'])
@login_required
def customer_add():
    return jsonify(crud_add('base_customer', request.json))


@customer_bp.route('/api/base/customer/update', methods=['POST'])
@login_required
def customer_update():
    return jsonify(crud_update('base_customer', request.json))


@customer_bp.route('/api/base/customer/delete', methods=['POST'])
@login_required
def customer_delete():
    return jsonify(crud_delete('base_customer', request.json.get('id')))


@customer_bp.route('/api/base/customer/all')
@login_required
def customer_all():
    db = get_db()
    rows = db.execute("SELECT id, customer_name, code FROM base_customer WHERE status=1").fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})
