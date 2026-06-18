"""API安全蓝图 - Token认证、限流"""
import time
import hashlib
import secrets
from functools import wraps
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required

security_bp = Blueprint('security', __name__)

# 简单的内存限流器
_rate_limit_store = {}

def rate_limit(max_requests=60, window=60):
    """限流装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            ip = request.remote_addr
            now = time.time()
            key = f"{ip}:{f.__name__}"
            
            if key not in _rate_limit_store:
                _rate_limit_store[key] = []
            
            # 清理过期记录
            _rate_limit_store[key] = [t for t in _rate_limit_store[key] if now - t < window]
            
            if len(_rate_limit_store[key]) >= max_requests:
                return jsonify({'code': 429, 'message': '请求过于频繁，请稍后再试'}), 429
            
            _rate_limit_store[key].append(now)
            return f(*args, **kwargs)
        return decorated
    return decorator


@security_bp.route('/api/security/token/generate', methods=['POST'])
@login_required
def generate_token():
    """生成API Token"""
    token = secrets.token_hex(32)
    db = get_db()
    user_id = session.get('user_id')
    db.execute("INSERT INTO sys_barcode (barcode, biz_type, biz_id) VALUES (?, 'TOKEN', ?)",
               (token, user_id))
    db.commit()
    return jsonify({'code': 0, 'data': {'token': token}})


@security_bp.route('/api/security/token/verify', methods=['POST'])
def verify_token():
    """验证API Token"""
    token = request.json.get('token', '')
    if not token:
        return jsonify({'code': 400, 'message': 'Token为空'})
    
    db = get_db()
    record = db.execute("SELECT * FROM sys_barcode WHERE barcode=? AND biz_type='TOKEN'", (token,)).fetchone()
    if not record:
        return jsonify({'code': 401, 'message': 'Token无效'})
    
    return jsonify({'code': 0, 'data': {'user_id': record['biz_id']}})


@security_bp.route('/api/security/log')
@login_required
def security_log():
    """安全日志"""
    db = get_db()
    logs = db.execute('''SELECT * FROM sys_log 
        WHERE method IN ('POST', 'PUT', 'DELETE') 
        ORDER BY id DESC LIMIT 100''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in logs]})
