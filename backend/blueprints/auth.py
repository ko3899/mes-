"""认证蓝图"""
import hashlib
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '')
    password = data.get('password', '')
    pwd_hash = hashlib.md5(password.encode()).hexdigest()
    db = get_db()
    user = db.execute("SELECT * FROM sys_user WHERE username=? AND password=?", (username, pwd_hash)).fetchone()
    if not user:
        return jsonify({'code': 400, 'message': '用户名或密码错误'})
    session['user_id'] = user['id']
    session['username'] = user['username']
    return jsonify({
        'code': 0,
        'data': {
            'id': user['id'],
            'username': user['username'],
            'real_name': user['real_name'],
            'phone': user['phone'],
            'avatar': user['avatar']
        }
    })


@auth_bp.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'code': 0, 'message': '已退出'})


@auth_bp.route('/api/user/info')
@login_required
def user_info():
    db = get_db()
    user = db.execute("SELECT id, username, real_name, phone, email, dept_id, role_id, avatar FROM sys_user WHERE id=?",
                      (session['user_id'],)).fetchone()
    return jsonify({'code': 0, 'data': dict(user)})
