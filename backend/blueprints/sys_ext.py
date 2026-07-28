"""系统管理增强蓝图 - 密码/权限/在线用户/登录日志/配置/公告/审计/监控/IP白名单/打印模板"""
import os
import datetime
import psutil
from flask import Blueprint, request, jsonify, session
from utils.database import get_db, BASE_DIR
from utils.helpers import (
    admin_required,
    crud_add,
    crud_delete,
    crud_list,
    crud_update,
    hash_password,
    login_required,
    verify_password,
)

sys_ext_bp = Blueprint('sys_ext', __name__)

# 在线用户存储（内存）
_online_users = {}


# ==================== 密码管理 ====================
@sys_ext_bp.route('/api/sys/user/change-password', methods=['POST'])
@login_required
def change_password():
    d = request.json
    user_id = session.get('user_id')
    old_pwd = d.get('old_password', '')
    new_pwd = d.get('new_password', '')
    
    if not old_pwd or not new_pwd:
        return jsonify({'code': 400, 'message': '请输入旧密码和新密码'})
    
    if len(new_pwd) < 6:
        return jsonify({'code': 400, 'message': '新密码至少6位'})
    
    db = get_db()
    user = db.execute("SELECT * FROM sys_user WHERE id=?", (user_id,)).fetchone()
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'})
    
    if not verify_password(old_pwd, user['password']):
        return jsonify({'code': 400, 'message': '旧密码错误'})
    
    new_hash = hash_password(new_pwd)
    db.execute("UPDATE sys_user SET password=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (new_hash, user_id))
    db.commit()
    return jsonify({'code': 0, 'message': '密码修改成功'})


@sys_ext_bp.route('/api/sys/user/reset-password', methods=['POST'])
@admin_required
def reset_password():
    d = request.json
    target_id = d.get('user_id')
    new_pwd = d.get('new_password', '123456')
    
    db = get_db()
    new_hash = hash_password(new_pwd)
    db.execute("UPDATE sys_user SET password=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (new_hash, target_id))
    db.commit()
    return jsonify({'code': 0, 'message': f'密码已重置为: {new_pwd}'})


# ==================== 权限管理 ====================
@sys_ext_bp.route('/api/sys/role/permissions/<int:role_id>')
@login_required
def get_role_permissions(role_id):
    db = get_db()
    role = db.execute("SELECT * FROM sys_role WHERE id=?", (role_id,)).fetchone()
    if not role:
        return jsonify({'code': 404, 'message': '角色不存在'})
    menu_ids = role['menu_ids'] or ''
    return jsonify({'code': 0, 'data': {'menu_ids': menu_ids}})


@sys_ext_bp.route('/api/sys/role/permissions', methods=['POST'])
@admin_required
def set_role_permissions():
    d = request.json
    role_id = d.get('role_id')
    menu_ids = d.get('menu_ids', '')
    
    db = get_db()
    db.execute("UPDATE sys_role SET menu_ids=? WHERE id=?", (menu_ids, role_id))
    db.commit()
    return jsonify({'code': 0, 'message': '权限设置成功'})


# ==================== 在线用户 ====================
@sys_ext_bp.route('/api/sys/online/list')
@admin_required
def online_list():
    now = datetime.datetime.now()
    # 清理超过30分钟的用户
    expired = [uid for uid, info in _online_users.items() 
               if (now - info['last_active']).seconds > 1800]
    for uid in expired:
        del _online_users[uid]
    
    return jsonify({'code': 0, 'data': list(_online_users.values())})


@sys_ext_bp.route('/api/sys/online/kick', methods=['POST'])
@admin_required
def kick_user():
    d = request.json
    target_id = str(d.get('user_id'))
    if target_id in _online_users:
        del _online_users[target_id]
        return jsonify({
            'code': 0,
            'message': '已从在线列表移除；现有会话不会被强制失效',
        })
    return jsonify({'code': 404, 'message': '用户不在线'})


def record_online_user(user_id, username, ip):
    """记录在线用户"""
    _online_users[str(user_id)] = {
        'user_id': user_id,
        'username': username,
        'login_ip': ip,
        'last_active': datetime.datetime.now(),
        'login_time': _online_users.get(str(user_id), {}).get('login_time', datetime.datetime.now())
    }


# ==================== 登录日志 ====================
@sys_ext_bp.route('/api/sys/login-log/list')
@admin_required
def login_log_list():
    return jsonify(crud_list('sys_login_log', request.args))


@sys_ext_bp.route('/api/sys/login-log/statistics')
@admin_required
def login_log_stats():
    db = get_db()
    today = datetime.date.today().strftime('%Y-%m-%d')
    
    today_count = db.execute("SELECT COUNT(*) as c FROM sys_login_log WHERE DATE(login_time)=?", (today,)).fetchone()['c']
    total_count = db.execute("SELECT COUNT(*) as c FROM sys_login_log").fetchone()['c']
    failed_count = db.execute("SELECT COUNT(*) as c FROM sys_login_log WHERE status=0").fetchone()['c']
    
    # 近7天登录趋势
    trend = []
    for i in range(6, -1, -1):
        d = (datetime.date.today() - datetime.timedelta(days=i)).strftime('%Y-%m-%d')
        cnt = db.execute("SELECT COUNT(*) as c FROM sys_login_log WHERE DATE(login_time)=?", (d,)).fetchone()['c']
        trend.append({'date': d, 'count': cnt})
    
    return jsonify({'code': 0, 'data': {
        'today': today_count,
        'total': total_count,
        'failed': failed_count,
        'trend': trend
    }})


# ==================== 系统配置 ====================
_SENSITIVE_CONFIG_KEY_PARTS = (
    'api_key',
    'secret',
    'password',
    'token',
)


def _is_sensitive_config_key(key):
    normalized = str(key or '').lower()
    return any(part in normalized for part in _SENSITIVE_CONFIG_KEY_PARTS)


def _redact_config(config):
    result = dict(config)
    if _is_sensitive_config_key(result.get('config_key')):
        value = result.pop('config_value', None)
        result['value_configured'] = bool(str(value or '').strip())
    return result


@sys_ext_bp.route('/api/sys/config/list')
@admin_required
def config_list():
    result = crud_list('sys_config', request.args)
    result['data']['list'] = [
        _redact_config(config)
        for config in result['data']['list']
    ]
    return jsonify(result)


@sys_ext_bp.route('/api/sys/config/get')
@admin_required
def config_get():
    key = request.args.get('key', '')
    db = get_db()
    config = db.execute("SELECT * FROM sys_config WHERE config_key=?", (key,)).fetchone()
    if config:
        return jsonify({'code': 0, 'data': _redact_config(config)})
    return jsonify({'code': 404, 'message': '配置不存在'})


@sys_ext_bp.route('/api/sys/config/save', methods=['POST'])
@admin_required
def config_save():
    d = request.json
    db = get_db()
    key = d.get('config_key')
    existing = db.execute(
        "SELECT id, config_value FROM sys_config WHERE config_key=?",
        (key,),
    ).fetchone()
    value = d.get('config_value', '')
    if (
        existing
        and _is_sensitive_config_key(key)
        and not str(value or '').strip()
    ):
        value = existing['config_value']
    if existing:
        db.execute("UPDATE sys_config SET config_value=?, description=?, updated_at=CURRENT_TIMESTAMP WHERE config_key=?",
                   (value, d.get('description', ''), key))
    else:
        db.execute("INSERT INTO sys_config (config_key, config_value, config_type, description) VALUES (?,?,?,?)",
                   (key, value, d.get('config_type', 'string'), d.get('description', '')))
    db.commit()
    return jsonify({'code': 0, 'message': '保存成功'})


# ==================== 系统公告 ====================
@sys_ext_bp.route('/api/sys/announcement/list')
@login_required
def announcement_list():
    return jsonify(crud_list('sys_announcement', request.args))


@sys_ext_bp.route('/api/sys/announcement/add', methods=['POST'])
@admin_required
def announcement_add():
    data = request.json
    data['publisher'] = session.get('user_id')
    return jsonify(crud_add('sys_announcement', data))


@sys_ext_bp.route('/api/sys/announcement/update', methods=['POST'])
@admin_required
def announcement_update():
    return jsonify(crud_update('sys_announcement', request.json))


@sys_ext_bp.route('/api/sys/announcement/delete', methods=['POST'])
@admin_required
def announcement_delete():
    return jsonify(crud_delete('sys_announcement', request.json.get('id')))


@sys_ext_bp.route('/api/sys/announcement/latest')
@login_required
def announcement_latest():
    db = get_db()
    rows = db.execute('''SELECT * FROM sys_announcement 
        WHERE status=1 AND (expire_time IS NULL OR expire_time >= CURRENT_TIMESTAMP)
        ORDER BY priority DESC, publish_time DESC LIMIT 5''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


# ==================== 操作审计 ====================
@sys_ext_bp.route('/api/sys/audit/list')
@login_required
def audit_list():
    return jsonify(crud_list('sys_log', request.args))


@sys_ext_bp.route('/api/sys/audit/statistics')
@login_required
def audit_stats():
    db = get_db()
    today = datetime.date.today().strftime('%Y-%m-%d')
    
    today_ops = db.execute("SELECT COUNT(*) as c FROM sys_log WHERE DATE(created_at)=?", (today,)).fetchone()['c']
    total_ops = db.execute("SELECT COUNT(*) as c FROM sys_log").fetchone()['c']
    
    # 按操作类型统计
    by_type = db.execute('''SELECT method, COUNT(*) as count FROM sys_log 
        GROUP BY method ORDER BY count DESC''').fetchall()
    
    # 按用户统计
    by_user = db.execute('''SELECT username, COUNT(*) as count FROM sys_log 
        GROUP BY username ORDER BY count DESC LIMIT 10''').fetchall()
    
    return jsonify({'code': 0, 'data': {
        'today': today_ops,
        'total': total_ops,
        'by_type': [dict(r) for r in by_type],
        'by_user': [dict(r) for r in by_user]
    }})


# ==================== 数据清理 ====================
@sys_ext_bp.route('/api/sys/cleanup/logs', methods=['POST'])
@admin_required
def cleanup_logs():
    d = request.json
    days = int(d.get('days', 90))
    db = get_db()
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
    result = db.execute("DELETE FROM sys_log WHERE created_at < ?", (cutoff,))
    db.commit()
    return jsonify({'code': 0, 'message': f'已清理 {result.rowcount} 条日志'})


@sys_ext_bp.route('/api/sys/cleanup/login-logs', methods=['POST'])
@admin_required
def cleanup_login_logs():
    d = request.json
    days = int(d.get('days', 90))
    db = get_db()
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
    result = db.execute("DELETE FROM sys_login_log WHERE login_time < ?", (cutoff,))
    db.commit()
    return jsonify({'code': 0, 'message': f'已清理 {result.rowcount} 条登录日志'})


@sys_ext_bp.route('/api/sys/cleanup/vacuum', methods=['POST'])
@admin_required
def vacuum_database():
    db = get_db()
    db.execute("VACUUM")
    db.commit()
    return jsonify({'code': 0, 'message': '数据库压缩完成'})


# ==================== 系统监控 ====================
@sys_ext_bp.route('/api/sys/monitor')
@login_required
def system_monitor():
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return jsonify({'code': 0, 'data': {
        'cpu': {
            'percent': cpu_percent,
            'count': psutil.cpu_count()
        },
        'memory': {
            'total': memory.total,
            'used': memory.used,
            'available': memory.available,
            'percent': memory.percent
        },
        'disk': {
            'total': disk.total,
            'used': disk.used,
            'free': disk.free,
            'percent': disk.percent
        },
        'database_size': os.path.getsize(os.path.join(BASE_DIR, 'database', 'mes.db')) if os.path.exists(os.path.join(BASE_DIR, 'database', 'mes.db')) else 0
    }})


# ==================== IP白名单 ====================
@sys_ext_bp.route('/api/sys/ip-whitelist/list')
@admin_required
def ip_whitelist_list():
    return jsonify(crud_list('sys_ip_whitelist', request.args))


@sys_ext_bp.route('/api/sys/ip-whitelist/add', methods=['POST'])
@admin_required
def ip_whitelist_add():
    return jsonify(crud_add('sys_ip_whitelist', request.json))


@sys_ext_bp.route('/api/sys/ip-whitelist/delete', methods=['POST'])
@admin_required
def ip_whitelist_delete():
    return jsonify(crud_delete('sys_ip_whitelist', request.json.get('id')))


# ==================== 打印模板 ====================
@sys_ext_bp.route('/api/sys/print-template/list')
@admin_required
def print_template_list():
    return jsonify(crud_list('sys_print_template', request.args))


@sys_ext_bp.route('/api/sys/print-template/add', methods=['POST'])
@admin_required
def print_template_add():
    return jsonify(crud_add('sys_print_template', request.json))


@sys_ext_bp.route('/api/sys/print-template/update', methods=['POST'])
@admin_required
def print_template_update():
    return jsonify(crud_update('sys_print_template', request.json))


@sys_ext_bp.route('/api/sys/print-template/delete', methods=['POST'])
@admin_required
def print_template_delete():
    return jsonify(crud_delete('sys_print_template', request.json.get('id')))


# ==================== 通知渠道 ====================
@sys_ext_bp.route('/api/sys/notify-channel/list')
@admin_required
def notify_channel_list():
    result = crud_list('sys_notify_channel', request.args)
    for channel in result['data']['list']:
        config = channel.pop('config', None)
        channel['config_configured'] = bool(str(config or '').strip())
    return jsonify(result)


@sys_ext_bp.route('/api/sys/notify-channel/add', methods=['POST'])
@admin_required
def notify_channel_add():
    return jsonify(crud_add('sys_notify_channel', request.json))


@sys_ext_bp.route('/api/sys/notify-channel/update', methods=['POST'])
@admin_required
def notify_channel_update():
    return jsonify(crud_update('sys_notify_channel', request.json))


@sys_ext_bp.route('/api/sys/notify-channel/delete', methods=['POST'])
@admin_required
def notify_channel_delete():
    return jsonify(crud_delete('sys_notify_channel', request.json.get('id')))


@sys_ext_bp.route('/api/sys/notify-channel/test', methods=['POST'])
@admin_required
def notify_channel_test():
    """测试通知渠道"""
    return jsonify({
        'code': 501,
        'message': '通知渠道测试适配器尚未实现',
    }), 501
