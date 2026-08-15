"""多租户蓝图"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import admin_required, login_required, crud_list, crud_add, crud_update, crud_delete

tenant_bp = Blueprint('tenant', __name__)


@tenant_bp.route('/api/tenant/list')
@login_required
def tenant_list():
    return jsonify(crud_list('sys_tenant', request.args))


@tenant_bp.route('/api/tenant/add', methods=['POST'])
@admin_required
def tenant_add():
    return jsonify(crud_add('sys_tenant', request.json))


@tenant_bp.route('/api/tenant/update', methods=['POST'])
@admin_required
def tenant_update():
    return jsonify(crud_update('sys_tenant', request.json))


@tenant_bp.route('/api/tenant/delete', methods=['POST'])
@admin_required
def tenant_delete():
    tenant_id = (request.get_json(silent=True) or {}).get('id')
    db = get_db()
    if tenant_id in (None, ''):
        return jsonify({'code': 400, 'message': '缂哄皯绉熸埛ID'}), 400
    if db.execute('SELECT 1 FROM sys_user WHERE tenant_id=? LIMIT 1', (tenant_id,)).fetchone():
        return jsonify({'code': 409, 'message': '绉熸埛仍有用户绑定，不能删除'}), 409
    return jsonify(crud_delete('sys_tenant', tenant_id))


@tenant_bp.route('/api/tenant/current')
@login_required
def tenant_current():
    """获取当前租户信息"""
    db = get_db()
    user = db.execute("SELECT tenant_id FROM sys_user WHERE id=?", (session.get('user_id'),)).fetchone()
    if user and user['tenant_id']:
        tenant = db.execute(
            "SELECT * FROM sys_tenant WHERE id=? AND status=1", (user['tenant_id'],)
        ).fetchone()
        if tenant:
            return jsonify({'code': 0, 'data': dict(tenant)})
    return jsonify({'code': 0, 'data': {'tenant_name': '默认租户', 'tenant_code': 'default'}})
