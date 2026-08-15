"""系统管理蓝图"""
from flask import Blueprint, request, jsonify, session
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
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'code': 400, 'message': '请求数据必须是JSON对象'}), 400
    username = str(data.get('username') or '').strip()
    password = str(data.get('password') or '')
    if not username or len(password) < 6:
        return jsonify({'code': 400, 'message': '用户名不能为空，密码至少6位'}), 400
    data['username'] = username
    data['password'] = hash_password(password)
    db = get_db()
    # New users get the ordinary role unless an explicit valid role was supplied.
    role_id = data.get('role_id')
    if role_id in (None, ''):
        role = db.execute("SELECT id FROM sys_role WHERE role_key='user' AND status=1").fetchone()
        if role:
            data['role_id'] = role['id']
    elif not db.execute("SELECT 1 FROM sys_role WHERE id=? AND status=1", (role_id,)).fetchone():
        return jsonify({'code': 400, 'message': '角色不存在或已停用'}), 400
    for field, table in (('tenant_id', 'sys_tenant'), ('dept_id', 'sys_dept')):
        if data.get(field) not in (None, '') and not db.execute(
                f"SELECT 1 FROM {table} WHERE id=? AND status=1", (data[field],)).fetchone():
            return jsonify({'code': 400, 'message': f'{field}引用不存在或已停用'}), 400
    return jsonify(crud_add('sys_user', data))


@system_bp.route('/api/sys/user/update', methods=['POST'])
@admin_required
def sys_user_update():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data.get('id'):
        return jsonify({'code': 400, 'message': '缺少用户ID'}), 400
    data.pop('username', None)
    db = get_db()
    for field, table in (('role_id', 'sys_role'), ('tenant_id', 'sys_tenant'), ('dept_id', 'sys_dept')):
        if field in data and data[field] not in (None, ''):
            if not db.execute(f"SELECT 1 FROM {table} WHERE id=? AND status=1", (data[field],)).fetchone():
                return jsonify({'code': 400, 'message': f'{field}引用不存在或已停用'}), 400
    if 'password' in data and data['password']:
        if len(str(data['password'])) < 6:
            return jsonify({'code': 400, 'message': '密码至少6位'}), 400
        data['password'] = hash_password(data['password'])
    else:
        data.pop('password', None)
    return jsonify(crud_update('sys_user', data))


@system_bp.route('/api/sys/user/delete', methods=['POST'])
@admin_required
def sys_user_delete():
    data = request.get_json(silent=True) or {}
    user_id = data.get('id')
    if not user_id:
        return jsonify({'code': 400, 'message': '缺少用户ID'}), 400
    if int(user_id) == int(session.get('user_id')):
        return jsonify({'code': 409, 'message': '不能删除当前登录账号'}), 409
    return jsonify(crud_delete('sys_user', user_id))


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
