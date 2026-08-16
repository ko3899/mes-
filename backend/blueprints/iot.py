"""IoT数据采集蓝图 - 实时数据/PLC对接"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required

iot_bp = Blueprint('iot', __name__)


@iot_bp.route('/api/iot/device/list')
@login_required
def iot_device_list():
    """IoT设备列表"""
    db = get_db()
    rows = db.execute("SELECT * FROM eqp_ledger WHERE status=1").fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@iot_bp.route('/api/iot/data/push', methods=['POST'])
@login_required
def iot_data_push():
    """接收IoT设备数据"""
    d = request.get_json(silent=True) or {}
    db = get_db()
    device_id = d.get('device_id')
    metric = d.get('metric', '')
    if not device_id or not metric:
        return jsonify({'code': 400, 'message': '设备和指标不能为空'}), 400
    try:
        value = float(d.get('value'))
    except (TypeError, ValueError):
        return jsonify({'code': 400, 'message': '指标值必须是数字'}), 400
    
    # 存储到SPC数据表
    db.execute("INSERT INTO spc_data (equipment_id, process_id, item_name, value, unit) VALUES (?,?,?,?,?)",
               (device_id, d.get('process_id'), metric, value, d.get('unit', '')))
    db.commit()
    return jsonify({'code': 0, 'message': '数据已接收'})


@iot_bp.route('/api/iot/data/latest')
@login_required
def iot_data_latest():
    """获取最新IoT数据"""
    db = get_db()
    rows = db.execute('''SELECT s.*, p.process_name 
        FROM spc_data s 
        LEFT JOIN base_process p ON s.process_id=p.id
        ORDER BY s.id DESC LIMIT 100''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@iot_bp.route('/api/iot/webhook', methods=['POST'])
def iot_webhook():
    """Webhook接收外部数据"""
    d = request.json
    # 记录webhook数据
    db = get_db()
    db.execute("INSERT INTO sys_log (operation, method, url, params) VALUES (?,?,?,?)",
               ('IoT Webhook', 'POST', '/api/iot/webhook', str(d)[:500]))
    db.commit()
    return jsonify({'code': 0, 'message': 'received'})
