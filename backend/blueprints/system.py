"""系统管理蓝图"""
import hashlib
from flask import Blueprint, request, jsonify
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete

system_bp = Blueprint('system', __name__)


@system_bp.route('/api/sys/user/list')
@login_required
def sys_user_list():
    return jsonify(crud_list('sys_user', request.args))


@system_bp.route('/api/sys/user/add', methods=['POST'])
@login_required
def sys_user_add():
    data = request.json
    data['password'] = hashlib.md5((data.get('password', '123456')).encode()).hexdigest()
    return jsonify(crud_add('sys_user', data))


@system_bp.route('/api/sys/user/update', methods=['POST'])
@login_required
def sys_user_update():
    data = request.json
    if 'password' in data and data['password']:
        data['password'] = hashlib.md5(data['password'].encode()).hexdigest()
    else:
        data.pop('password', None)
    return jsonify(crud_update('sys_user', data))


@system_bp.route('/api/sys/user/delete', methods=['POST'])
@login_required
def sys_user_delete():
    return jsonify(crud_delete('sys_user', request.json.get('id')))


@system_bp.route('/api/sys/role/list')
@login_required
def sys_role_list():
    return jsonify(crud_list('sys_role', request.args))


@system_bp.route('/api/sys/role/add', methods=['POST'])
@login_required
def sys_role_add():
    return jsonify(crud_add('sys_role', request.json))


@system_bp.route('/api/sys/role/update', methods=['POST'])
@login_required
def sys_role_update():
    return jsonify(crud_update('sys_role', request.json))


@system_bp.route('/api/sys/role/delete', methods=['POST'])
@login_required
def sys_role_delete():
    return jsonify(crud_delete('sys_role', request.json.get('id')))


@system_bp.route('/api/sys/dept/list')
@login_required
def sys_dept_list():
    return jsonify(crud_list('sys_dept', request.args))


@system_bp.route('/api/sys/dept/add', methods=['POST'])
@login_required
def sys_dept_add():
    return jsonify(crud_add('sys_dept', request.json))


@system_bp.route('/api/sys/dept/update', methods=['POST'])
@login_required
def sys_dept_update():
    return jsonify(crud_update('sys_dept', request.json))


@system_bp.route('/api/sys/dept/delete', methods=['POST'])
@login_required
def sys_dept_delete():
    return jsonify(crud_delete('sys_dept', request.json.get('id')))


@system_bp.route('/api/sys/menu/list')
@login_required
def sys_menu_list():
    db = get_db()
    rows = db.execute("SELECT * FROM sys_menu ORDER BY sort_order").fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@system_bp.route('/api/sys/menu/add', methods=['POST'])
@login_required
def sys_menu_add():
    return jsonify(crud_add('sys_menu', request.json))


@system_bp.route('/api/sys/menu/update', methods=['POST'])
@login_required
def sys_menu_update():
    return jsonify(crud_update('sys_menu', request.json))


@system_bp.route('/api/sys/menu/delete', methods=['POST'])
@login_required
def sys_menu_delete():
    return jsonify(crud_delete('sys_menu', request.json.get('id')))


@system_bp.route('/api/sys/dict/list')
@login_required
def sys_dict_list():
    return jsonify(crud_list('sys_dict', request.args))


@system_bp.route('/api/sys/dict/add', methods=['POST'])
@login_required
def sys_dict_add():
    return jsonify(crud_add('sys_dict', request.json))


@system_bp.route('/api/sys/dict/update', methods=['POST'])
@login_required
def sys_dict_update():
    return jsonify(crud_update('sys_dict', request.json))


@system_bp.route('/api/sys/dict/delete', methods=['POST'])
@login_required
def sys_dict_delete():
    return jsonify(crud_delete('sys_dict', request.json.get('id')))


@system_bp.route('/api/sys/log/list')
@login_required
def sys_log_list():
    return jsonify(crud_list('sys_log', request.args))
