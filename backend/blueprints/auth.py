"""认证蓝图"""
import random
import string
import os
import time
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import hash_password, login_required, verify_password

auth_bp = Blueprint('auth', __name__)
_captcha_store = {}
_login_attempts = {}

# 验证码存储（内存）
_captcha_store = {}


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
    data = request.get_json(silent=True) or {}
    username = data.get('username', '')
    password = data.get('password', '')
    captcha_key = data.get('captcha_key', '')
    captcha_code = data.get('captcha_code', '')
    
    # 验证码校验（如果提供了）
    now = time.time()
    attempt_key = f'{request.remote_addr}:{username}'
    attempts = [t for t in _login_attempts.get(attempt_key, []) if now - t < 300]
    _login_attempts[attempt_key] = attempts
    if len(attempts) >= 5 and not captcha_key:
        return jsonify({'code': 429, 'message': '登录失败次数过多，请先获取验证码'}), 429
    if captcha_key and captcha_key in _captcha_store:
        captcha = _captcha_store[captcha_key]
        if captcha['code'] != captcha_code:
            captcha['attempts'] += 1
            if captcha['attempts'] >= 3:
                del _captcha_store[captcha_key]
            return jsonify({'code': 400, 'message': '验证码错误'})
        del _captcha_store[captcha_key]
    elif captcha_key:
        return jsonify({'code': 400, 'message': '验证码已过期'}), 400
    
    db = get_db()
    user = db.execute("SELECT * FROM sys_user WHERE username=?", (username,)).fetchone()
    if not user or not verify_password(password, user['password']):
        attempts.append(now)
        _login_attempts[attempt_key] = attempts
        # 记录登录失败
        db.execute("INSERT INTO sys_login_log (username, login_ip, status) VALUES (?,?,0)",
                   (username, request.remote_addr))
        db.commit()
        return jsonify({'code': 400, 'message': '用户名或密码错误'})
    
    if not user['status']:
        return jsonify({'code': 403, 'message': '账号已停用'}), 403

    session['user_id'] = user['id']
    session['username'] = user['username']
    _login_attempts.pop(attempt_key, None)
    
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
    user_id = session.get('user_id')
    if user_id:
        try:
            from blueprints.sys_ext import remove_online_user
            remove_online_user(user_id)
        except Exception:
            pass
    session.clear()
    return jsonify({'code': 0, 'message': '已退出'})


@auth_bp.route('/api/user/info')
@login_required
def user_info():
    db = get_db()
    user = db.execute("SELECT id, username, real_name, phone, email, dept_id, role_id, avatar FROM sys_user WHERE id=?",
                      (session['user_id'],)).fetchone()
    if not user:
        session.clear()
        return jsonify({'code': 401, 'message': '鐢ㄦ埛涓嶅瓨鍦?'}), 401
    return jsonify({'code': 0, 'data': dict(user)})
