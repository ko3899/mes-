"""认证蓝图"""
import hashlib
import random
import string
import os
import secrets
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required

auth_bp = Blueprint('auth', __name__)

# 验证码存储（内存）
_captcha_store = {}


def _hash_password(password, salt=None):
    """安全的密码哈希（PBKDF2 + SHA256 + 盐值）"""
    if salt is None:
        salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}${pwd_hash.hex()}"


def _verify_password(password, stored_hash):
    """验证密码"""
    if '$' not in stored_hash:
        # 兼容旧MD5格式
        return hashlib.md5(password.encode()).hexdigest() == stored_hash
    salt, _ = stored_hash.split('$', 1)
    return _hash_password(password, salt) == stored_hash


def generate_captcha():
    """生成验证码"""
    code = ''.join(random.choices(string.digits, k=4))
    key = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    _captcha_store[key] = {'code': code, 'attempts': 0}
    return key, code


@auth_bp.route('/api/captcha')
def get_captcha():
    """获取验证码"""
    key, code = generate_captcha()
    # 返回简单的文本验证码（生产环境可用图片验证码）
    return jsonify({'code': 0, 'data': {'key': key, 'hint': f'请输入验证码: {code}'}})


@auth_bp.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '')
    password = data.get('password', '')
    captcha_key = data.get('captcha_key', '')
    captcha_code = data.get('captcha_code', '')
    
    # 验证码校验（如果提供了）
    if captcha_key and captcha_key in _captcha_store:
        captcha = _captcha_store[captcha_key]
        if captcha['code'] != captcha_code:
            captcha['attempts'] += 1
            if captcha['attempts'] >= 3:
                del _captcha_store[captcha_key]
            return jsonify({'code': 400, 'message': '验证码错误'})
        del _captcha_store[captcha_key]
    
    pwd_hash = _hash_password(password)
    db = get_db()
    user = db.execute("SELECT * FROM sys_user WHERE username=?", (username,)).fetchone()
    if not user or not _verify_password(password, user['password']):
        # 记录登录失败
        db.execute("INSERT INTO sys_login_log (username, login_ip, status) VALUES (?,?,0)",
                   (username, request.remote_addr))
        db.commit()
        return jsonify({'code': 400, 'message': '用户名或密码错误'})
    
    session['user_id'] = user['id']
    session['username'] = user['username']
    
    # 记录登录成功
    db.execute("INSERT INTO sys_login_log (username, login_ip, status) VALUES (?,?,1)",
               (username, request.remote_addr))
    db.commit()
    
    # 记录在线用户
    try:
        from blueprints.sys_ext import record_online_user
        record_online_user(user['id'], user['username'], request.remote_addr)
    except:
        pass
    
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
