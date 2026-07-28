"""系统管理蓝图"""
from flask import Blueprint, request, jsonify
from utils.database import get_db
from utils.helpers import (
    admin_required,
    crud_add,
    crud_delete,
    crud_list,
    crud_update,
    hash_password,
    login_required,
)

system_bp = Blueprint('system', __name__)


@system_bp.route('/api/sys/user/list')
@login_required
def sys_user_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    keyword = request.args.get('keyword', '')
    
    where = " WHERE 1=1"
    args = []
    if keyword:
        where += " AND (username LIKE ? OR real_name LIKE ? OR phone LIKE ?)"
        args.extend([f"%{keyword}%"] * 3)
    
    total = db.execute(f"SELECT COUNT(*) as cnt FROM sys_user{where}", args).fetchone()['cnt']
    # 不返回密码字段
    rows = db.execute(f"SELECT id, username, real_name, phone, email, dept_id, role_id, avatar, status, created_at FROM sys_user{where} ORDER BY id DESC LIMIT ? OFFSET ?",
                      args + [size, offset]).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total, 'page': page, 'size': size}})


@system_bp.route('/api/sys/user/add', methods=['POST'])
@admin_required
def sys_user_add():
    data = request.json
    data['password'] = hash_password(data.get('password', '123456'))
    return jsonify(crud_add('sys_user', data))


@system_bp.route('/api/sys/user/update', methods=['POST'])
@admin_required
def sys_user_update():
    data = request.json
    if 'password' in data and data['password']:
        data['password'] = hash_password(data['password'])
    else:
        data.pop('password', None)
    return jsonify(crud_update('sys_user', data))


@system_bp.route('/api/sys/user/delete', methods=['POST'])
@admin_required
def sys_user_delete():
    return jsonify(crud_delete('sys_user', request.json.get('id')))


@system_bp.route('/api/sys/role/list')
@login_required
def sys_role_list():
    return jsonify(crud_list('sys_role', request.args))


@system_bp.route('/api/sys/role/add', methods=['POST'])
@admin_required
def sys_role_add():
    return jsonify(crud_add('sys_role', request.json))


@system_bp.route('/api/sys/role/update', methods=['POST'])
@admin_required
def sys_role_update():
    return jsonify(crud_update('sys_role', request.json))


@system_bp.route('/api/sys/role/delete', methods=['POST'])
@admin_required
def sys_role_delete():
    return jsonify(crud_delete('sys_role', request.json.get('id')))


@system_bp.route('/api/sys/dept/list')
@login_required
def sys_dept_list():
    return jsonify(crud_list('sys_dept', request.args))


@system_bp.route('/api/sys/dept/add', methods=['POST'])
@admin_required
def sys_dept_add():
    return jsonify(crud_add('sys_dept', request.json))


@system_bp.route('/api/sys/dept/update', methods=['POST'])
@admin_required
def sys_dept_update():
    return jsonify(crud_update('sys_dept', request.json))


@system_bp.route('/api/sys/dept/delete', methods=['POST'])
@admin_required
def sys_dept_delete():
    return jsonify(crud_delete('sys_dept', request.json.get('id')))


@system_bp.route('/api/sys/menu/list')
@login_required
def sys_menu_list():
    db = get_db()
    rows = db.execute("SELECT * FROM sys_menu ORDER BY sort_order").fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@system_bp.route('/api/sys/menu/add', methods=['POST'])
@admin_required
def sys_menu_add():
    return jsonify(crud_add('sys_menu', request.json))


@system_bp.route('/api/sys/menu/update', methods=['POST'])
@admin_required
def sys_menu_update():
    return jsonify(crud_update('sys_menu', request.json))


@system_bp.route('/api/sys/menu/delete', methods=['POST'])
@admin_required
def sys_menu_delete():
    return jsonify(crud_delete('sys_menu', request.json.get('id')))


@system_bp.route('/api/sys/dict/list')
@login_required
def sys_dict_list():
    return jsonify(crud_list('sys_dict', request.args))


@system_bp.route('/api/sys/dict/add', methods=['POST'])
@admin_required
def sys_dict_add():
    return jsonify(crud_add('sys_dict', request.json))


@system_bp.route('/api/sys/dict/update', methods=['POST'])
@admin_required
def sys_dict_update():
    return jsonify(crud_update('sys_dict', request.json))


@system_bp.route('/api/sys/dict/delete', methods=['POST'])
@admin_required
def sys_dict_delete():
    return jsonify(crud_delete('sys_dict', request.json.get('id')))


@system_bp.route('/api/sys/log/list')
@login_required
def sys_log_list():
    return jsonify(crud_list('sys_log', request.args))
