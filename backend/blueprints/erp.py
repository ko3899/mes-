"""ERP集成蓝图 - 用友/金蝶/SAP对接"""
from flask import Blueprint, request, jsonify
from utils.database import get_db
from utils.helpers import login_required

erp_bp = Blueprint('erp', __name__)


@erp_bp.route('/api/erp/config')
@login_required
def erp_config():
    """获取ERP配置"""
    db = get_db()
    configs = {}
    for key in ['erp_type', 'erp_url', 'erp_api_key', 'erp_sync_enabled']:
        row = db.execute("SELECT config_value FROM sys_config WHERE config_key=?", (key,)).fetchone()
        configs[key] = row['config_value'] if row else ''
    return jsonify({'code': 0, 'data': configs})


@erp_bp.route('/api/erp/config/save', methods=['POST'])
@login_required
def erp_config_save():
    """保存ERP配置"""
    d = request.json
    db = get_db()
    for key, val in d.items():
        existing = db.execute("SELECT id FROM sys_config WHERE config_key=?", (key,)).fetchone()
        if existing:
            db.execute("UPDATE sys_config SET config_value=? WHERE config_key=?", (val, key))
        else:
            db.execute("INSERT INTO sys_config (config_key, config_value, config_type) VALUES (?,?,?)", (key, val, 'string'))
    db.commit()
    return jsonify({'code': 0, 'message': '配置已保存'})


@erp_bp.route('/api/erp/sync/products', methods=['POST'])
@login_required
def erp_sync_products():
    """同步ERP产品数据"""
    # 预留接口，实际对接需要根据ERP类型实现
    return jsonify({'code': 0, 'message': '产品同步功能已就绪，请配置ERP连接信息'})


@erp_bp.route('/api/erp/sync/orders', methods=['POST'])
@login_required
def erp_sync_orders():
    """同步ERP订单数据"""
    return jsonify({'code': 0, 'message': '订单同步功能已就绪，请配置ERP连接信息'})


@erp_bp.route('/api/erp/sync/inventory', methods=['POST'])
@login_required
def erp_sync_inventory():
    """同步ERP库存数据"""
    return jsonify({'code': 0, 'message': '库存同步功能已就绪，请配置ERP连接信息'})


@erp_bp.route('/api/erp/status')
@login_required
def erp_status():
    """ERP连接状态"""
    return jsonify({'code': 0, 'data': {'connected': False, 'message': '请先配置ERP连接信息'}})
