"""多租户蓝图"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete

tenant_bp = Blueprint('tenant', __name__)


@tenant_bp.route('/api/tenant/list')
@login_required
def tenant_list():
    return jsonify(crud_list('sys_tenant', request.args))


@tenant_bp.route('/api/tenant/add', methods=['POST'])
@login_required
def tenant_add():
    return jsonify(crud_add('sys_tenant', request.json))


@tenant_bp.route('/api/tenant/update', methods=['POST'])
@login_required
def tenant_update():
    return jsonify(crud_update('sys_tenant', request.json))


@tenant_bp.route('/api/tenant/delete', methods=['POST'])
@login_required
def tenant_delete():
    return jsonify(crud_delete('sys_tenant', request.json.get('id')))


@tenant_bp.route('/api/tenant/current')
@login_required
def tenant_current():
    """获取当前租户信息"""
    db = get_db()
    user = db.execute("SELECT tenant_id FROM sys_user WHERE id=?", (session.get('user_id'),)).fetchone()
    if user and user['tenant_id']:
        tenant = db.execute("SELECT * FROM sys_tenant WHERE id=?", (user['tenant_id'],)).fetchone()
        if tenant:
            return jsonify({'code': 0, 'data': dict(tenant)})
    return jsonify({'code': 0, 'data': {'tenant_name': '默认租户', 'tenant_code': 'default'}})
