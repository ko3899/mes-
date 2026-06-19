"""AI质检蓝图 - 视觉检测/智能分析"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add

ai_bp = Blueprint('ai', __name__)


@ai_bp.route('/api/ai/inspect', methods=['POST'])
@login_required
def ai_inspect():
    """AI视觉检测"""
    d = request.json
    image_url = d.get('image_url', '')
    product_id = d.get('product_id')
    
    # 预留AI接口，实际对接需要配置AI服务
    return jsonify({
        'code': 0,
        'data': {
            'result': 'PASS',
            'confidence': 0.95,
            'defects': [],
            'message': 'AI检测功能已就绪，请配置AI服务'
        }
    })


@ai_bp.route('/api/ai/config')
@login_required
def ai_config():
    """AI配置"""
    return jsonify({'code': 0, 'data': {
        'ai_enabled': False,
        'ai_provider': '',
        'ai_api_key': '',
        'ai_model': ''
    }})


@ai_bp.route('/api/ai/config/save', methods=['POST'])
@login_required
def ai_config_save():
    """保存AI配置"""
    d = request.json
    db = get_db()
    for key, val in d.items():
        existing = db.execute("SELECT id FROM sys_config WHERE config_key=?", (key,)).fetchone()
        if existing:
            db.execute("UPDATE sys_config SET config_value=? WHERE config_key=?", (val, key))
        else:
            db.execute("INSERT INTO sys_config (config_key, config_value, config_type) VALUES (?,?,?)", (key, val, 'string'))
    db.commit()
    return jsonify({'code': 0, 'message': 'AI配置已保存'})
