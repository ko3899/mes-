"""ERP集成蓝图 - 用友/金蝶/SAP对接"""
from flask import Blueprint, request, jsonify
from utils.database import get_db
from utils.helpers import admin_required, login_required, permission_required

erp_bp = Blueprint('erp', __name__)


@erp_bp.route('/api/erp/config')
@admin_required
def erp_config():
    """获取ERP配置"""
    db = get_db()
    configs = {}
    for key in ['erp_type', 'erp_url', 'erp_api_key', 'erp_sync_enabled']:
        row = db.execute("SELECT config_value FROM sys_config WHERE config_key=?", (key,)).fetchone()
        configs[key] = row['config_value'] if row else ''
    api_key = configs.pop('erp_api_key')
    configs['erp_api_key_configured'] = bool(str(api_key).strip())
    return jsonify({'code': 0, 'data': configs})


@erp_bp.route('/api/erp/config/save', methods=['POST'])
@admin_required
def erp_config_save():
    """保存ERP配置"""
    d = request.json
    db = get_db()
    allowed_keys = {
        'erp_type',
        'erp_url',
        'erp_api_key',
        'erp_sync_enabled',
    }
    for key, val in d.items():
        if key not in allowed_keys:
            continue
        if key == 'erp_api_key' and not str(val or '').strip():
            continue
        existing = db.execute("SELECT id FROM sys_config WHERE config_key=?", (key,)).fetchone()
        if existing:
            db.execute("UPDATE sys_config SET config_value=? WHERE config_key=?", (val, key))
        else:
            db.execute("INSERT INTO sys_config (config_key, config_value, config_type) VALUES (?,?,?)", (key, val, 'string'))
    db.commit()
    return jsonify({'code': 0, 'message': '配置已保存'})


@erp_bp.route('/api/erp/sync/products', methods=['POST'])
@permission_required('erp:write')
def erp_sync_products():
    """同步ERP产品数据"""
    return _integration_not_implemented()


@erp_bp.route('/api/erp/sync/orders', methods=['POST'])
@permission_required('erp:write')
def erp_sync_orders():
    """同步ERP订单数据"""
    return _integration_not_implemented()


@erp_bp.route('/api/erp/sync/inventory', methods=['POST'])
@permission_required('erp:write')
def erp_sync_inventory():
    """同步ERP库存数据"""
    return _integration_not_implemented()


@erp_bp.route('/api/erp/status')
@login_required
def erp_status():
    """ERP连接状态"""
    return jsonify({'code': 0, 'data': {'connected': False, 'message': '请先配置ERP连接信息'}})


def _integration_not_implemented():
    return jsonify({
        'code': 501,
        'message': '该集成适配器尚未实现',
    }), 501
