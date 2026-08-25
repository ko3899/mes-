# -*- coding: utf-8 -*-
"""认证蓝图"""
import html
import random
import secrets
import string
import time

from flask import Blueprint, Response, jsonify, request, session

from utils.database import get_db
from utils.helpers import hash_password, login_required, verify_password

auth_bp = Blueprint('auth', __name__)

_captcha_store = {}
_login_attempts = {}

CAPTCHA_TTL = 300
CAPTCHA_WIDTH = 130
CAPTCHA_HEIGHT = 44


def _cleanup_captcha(now=None):
    now = now or time.time()
    expired = [key for key, item in _captcha_store.items()
               if item.get('expires', 0) < now]
    for key in expired:
        _captcha_store.pop(key, None)


def generate_captcha():
    """生成验证码；验证码明文只保存在服务端内存，不返回给客户端。"""
    _cleanup_captcha()
    code = ''.join(random.choices(string.digits, k=4))
    key = secrets.token_urlsafe(16)
    _captcha_store[key] = {
        'code': code,
        'attempts': 0,
        'expires': time.time() + CAPTCHA_TTL,
    }
    return key


def _render_captcha_svg(code):
    """生成简单的 SVG 图形验证码，避免直接向客户端返回明文。"""
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CAPTCHA_WIDTH}" height="{CAPTCHA_HEIGHT}" viewBox="0 0 {CAPTCHA_WIDTH} {CAPTCHA_HEIGHT}">',
        f'<rect width="100%" height="100%" fill="#f8fafc" rx="6"/>',
    ]
    for _ in range(5):
        lines.append(
            f'<line x1="{random.randint(0, CAPTCHA_WIDTH)}" y1="{random.randint(0, CAPTCHA_HEIGHT)}" '
            f'x2="{random.randint(0, CAPTCHA_WIDTH)}" y2="{random.randint(0, CAPTCHA_HEIGHT)}" '
            f'stroke="#cbd5e1" stroke-width="1"/>'
        )
    for _ in range(8):
        lines.append(
            f'<circle cx="{random.randint(0, CAPTCHA_WIDTH)}" cy="{random.randint(0, CAPTCHA_HEIGHT)}" '
            f'r="{random.randint(1, 2)}" fill="#94a3b8"/>'
        )
    colors = ['#1e3a8a', '#b91c1c', '#047857', '#7c3aed', '#b45309']
    start_x = 18
    step = 26
    for i, ch in enumerate(code):
        x = start_x + i * step
        y = random.randint(26, 34)
        rotation = random.randint(-22, 22)
        fill = random.choice(colors)
        lines.append(
            f'<text x="{x}" y="{y}" font-size="26" font-family="monospace" '
            f'font-weight="bold" fill="{fill}" '
            f'transform="rotate({rotation} {x} {y})">{html.escape(ch)}</text>'
        )
    lines.append('</svg>')
    return '\n'.join(lines)


@auth_bp.route('/api/captcha')
def get_captcha():
    """获取验证码 key；验证码图片通过 /api/captcha/image/<key> 获取。"""
    key = generate_captcha()
    return jsonify({'code': 0, 'data': {'key': key}})


@auth_bp.route('/api/captcha/image/<key>')
def captcha_image(key):
    item = _captcha_store.get(key)
    if not item or item.get('expires', 0) < time.time():
        return '', 404
    svg = _render_captcha_svg(item['code'])
    return Response(
        svg,
        mimetype='image/svg+xml',
        headers={'Cache-Control': 'no-store, no-cache, must-revalidate'},
    )


@auth_bp.route('/api/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '')
    password = data.get('password', '')
    captcha_key = data.get('captcha_key', '')
    captcha_code = data.get('captcha_code', '')

    now = time.time()
    _cleanup_captcha(now)

    attempt_key = f'{request.remote_addr}:{username}'
    attempts = [t for t in _login_attempts.get(attempt_key, []) if now - t < 300]
    _login_attempts[attempt_key] = attempts

    # 失败次数达到阈值时锁定 5 分钟（验证码为可选解锁方式，不强制）
    # 采集端等终端不携带验证码也可登录；带 captcha_key 的客户端（如管理后台）可提前解锁
    if len(attempts) >= 5 and not captcha_key:
        return jsonify({'code': 429, 'message': '登录失败次数过多，请5分钟后再试'}), 429

    if captcha_key:
        captcha = _captcha_store.get(captcha_key)
        if not captcha or captcha.get('expires', 0) < now:
            return jsonify({'code': 400, 'message': '验证码已过期'}), 400
        if captcha['code'] != captcha_code:
            captcha['attempts'] += 1
            if captcha['attempts'] >= 3:
                _captcha_store.pop(captcha_key, None)
            return jsonify({'code': 400, 'message': '验证码错误'}), 400
        _captcha_store.pop(captcha_key, None)

    db = get_db()
    user = db.execute("SELECT * FROM sys_user WHERE username=?", (username,)).fetchone()
    if not user or not verify_password(password, user['password']):
        attempts.append(now)
        _login_attempts[attempt_key] = attempts
        db.execute("INSERT INTO sys_login_log (username, login_ip, status) VALUES (?,?,0)",
                   (username, request.remote_addr))
        db.commit()
        return jsonify({'code': 400, 'message': '用户名或密码错误'}), 400

    if not user['status']:
        return jsonify({'code': 403, 'message': '账号已停用'}), 403

    # 旧版 MD5 哈希登录成功后自动升级为 PBKDF2-SHA256
    if '$' not in user['password']:
        new_hash = hash_password(password)
        db.execute("UPDATE sys_user SET password=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                   (new_hash, user['id']))
        db.commit()

    session['user_id'] = user['id']
    session['username'] = user['username']
    _login_attempts.pop(attempt_key, None)

    db.execute("INSERT INTO sys_login_log (username, login_ip, status) VALUES (?,?,1)",
               (username, request.remote_addr))
    db.commit()

    try:
        from blueprints.sys_ext import record_online_user
        record_online_user(user['id'], user['username'], request.remote_addr)
    except Exception:
        pass

    return jsonify({
        'code': 0,
        'data': {
            'id': user['id'],
            'username': user['username'],
            'real_name': user['real_name'],
            'phone': user['phone'],
            'avatar': user['avatar'],
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
        return jsonify({'code': 401, 'message': '登录状态已失效'}), 401
    return jsonify({'code': 0, 'data': dict(user)})
