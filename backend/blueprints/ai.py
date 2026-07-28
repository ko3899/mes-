"""AI质检蓝图 - 视觉检测/智能分析"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import admin_required, login_required, crud_list, crud_add

ai_bp = Blueprint('ai', __name__)


@ai_bp.route('/api/ai/inspect', methods=['POST'])
@login_required
def ai_inspect():
    """AI视觉检测（当前尚无可用适配器）。"""
    return jsonify({
        'code': 503,
        'message': 'AI 检测适配器尚未配置',
    }), 503


@ai_bp.route('/api/ai/config')
@admin_required
def ai_config():
    """AI配置"""
    keys = ('ai_enabled', 'ai_provider', 'ai_api_key', 'ai_model')
    rows = get_db().execute(
        """SELECT config_key, config_value FROM sys_config
           WHERE config_key IN (?,?,?,?)""",
        keys,
    ).fetchall()
    values = {row['config_key']: row['config_value'] for row in rows}
    enabled = str(values.get('ai_enabled') or '').strip().lower() in {
        '1', 'true', 'yes', 'on',
    }
    return jsonify({'code': 0, 'data': {
        'ai_enabled': enabled,
        'ai_provider': values.get('ai_provider') or '',
        'ai_api_key_configured': bool(
            str(values.get('ai_api_key') or '').strip()
        ),
        'ai_model': values.get('ai_model') or '',
    }})


@ai_bp.route('/api/ai/config/save', methods=['POST'])
@admin_required
def ai_config_save():
    """保存AI配置"""
    d = request.json
    db = get_db()
    allowed_keys = {
        'ai_enabled',
        'ai_provider',
        'ai_api_key',
        'ai_model',
    }
    for key, val in d.items():
        if key not in allowed_keys:
            continue
        if key == 'ai_api_key' and not str(val or '').strip():
            continue
        existing = db.execute("SELECT id FROM sys_config WHERE config_key=?", (key,)).fetchone()
        if existing:
            db.execute("UPDATE sys_config SET config_value=? WHERE config_key=?", (val, key))
        else:
            db.execute("INSERT INTO sys_config (config_key, config_value, config_type) VALUES (?,?,?)", (key, val, 'string'))
    db.commit()
    return jsonify({'code': 0, 'message': 'AI配置已保存'})
