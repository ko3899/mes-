"""ERP深度集成蓝图 - 用友/金蝶/SAP"""
import json
from flask import Blueprint, request, jsonify
from utils.database import get_db
from utils.helpers import login_required

erp_deep_bp = Blueprint('erp_deep', __name__)


@erp_deep_bp.route('/api/erp/yonyou/sync', methods=['POST'])
@login_required
def yonyou_sync():
    """用友U8/U9对接"""
    d = request.json
    sync_type = d.get('type', 'product')
    
    # 用友API对接模板
    api_config = {
        'base_url': 'http://u8-server:8080/api',
        'app_key': d.get('app_key', ''),
        'app_secret': d.get('app_secret', '')
    }
    
    return jsonify({'code': 0, 'message': f'用友{sync_type}同步接口已就绪', 'config': api_config})


@erp_deep_bp.route('/api/erp/kingdee/sync', methods=['POST'])
@login_required
def kingdee_sync():
    """金蝶云星空对接"""
    d = request.json
    sync_type = d.get('type', 'product')
    
    api_config = {
        'base_url': 'https://api.kingdee.com',
        'app_key': d.get('app_key', ''),
        'app_secret': d.get('app_secret', '')
    }
    
    return jsonify({'code': 0, 'message': f'金蝶{sync_type}同步接口已就绪', 'config': api_config})


@erp_deep_bp.route('/api/erp/sap/sync', methods=['POST'])
@login_required
def sap_sync():
    """SAP对接"""
    d = request.json
    sync_type = d.get('type', 'material')
    
    return jsonify({'code': 0, 'message': f'SAP {sync_type} 同步接口已就绪'})


@erp_deep_bp.route('/api/erp/sync/status')
@login_required
def erp_sync_status():
    """同步状态查询"""
    db = get_db()
    # 查询最近的同步记录
    logs = db.execute('''SELECT * FROM sys_log 
        WHERE operation LIKE '%同步%' OR operation LIKE '%sync%'
        ORDER BY id DESC LIMIT 10''').fetchall()
    return jsonify({'code': 0, 'data': [dict(l) for l in logs]})


@erp_deep_bp.route('/api/erp/config/yonyou', methods=['GET', 'POST'])
@login_required
def yonyou_config():
    """用友配置"""
    db = get_db()
    if request.method == 'GET':
        configs = {}
        for key in ['yonyou_url', 'yonyou_app_key', 'yonyou_app_secret']:
            row = db.execute("SELECT config_value FROM sys_config WHERE config_key=?", (key,)).fetchone()
            configs[key] = row['config_value'] if row else ''
        return jsonify({'code': 0, 'data': configs})
    else:
        d = request.json
        for key, val in d.items():
            existing = db.execute("SELECT id FROM sys_config WHERE config_key=?", (key,)).fetchone()
            if existing:
                db.execute("UPDATE sys_config SET config_value=? WHERE config_key=?", (val, key))
            else:
                db.execute("INSERT INTO sys_config (config_key, config_value, config_type) VALUES (?,?,?)", (key, val, 'string'))
        db.commit()
        return jsonify({'code': 0, 'message': '用友配置已保存'})


@erp_deep_bp.route('/api/erp/config/kingdee', methods=['GET', 'POST'])
@login_required
def kingdee_config():
    """金蝶配置"""
    db = get_db()
    if request.method == 'GET':
        configs = {}
        for key in ['kingdee_url', 'kingdee_app_key', 'kingdee_app_secret']:
            row = db.execute("SELECT config_value FROM sys_config WHERE config_key=?", (key,)).fetchone()
            configs[key] = row['config_value'] if row else ''
        return jsonify({'code': 0, 'data': configs})
    else:
        d = request.json
        for key, val in d.items():
            existing = db.execute("SELECT id FROM sys_config WHERE config_key=?", (key,)).fetchone()
            if existing:
                db.execute("UPDATE sys_config SET config_value=? WHERE config_key=?", (val, key))
            else:
                db.execute("INSERT INTO sys_config (config_key, config_value, config_type) VALUES (?,?,?)", (key, val, 'string'))
        db.commit()
        return jsonify({'code': 0, 'message': '金蝶配置已保存'})
