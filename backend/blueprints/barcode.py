"""条码管理蓝图"""
import datetime
from flask import Blueprint, request, jsonify
from utils.database import get_db
from utils.helpers import login_required

barcode_bp = Blueprint('barcode', __name__)


def generate_barcode(biz_type):
    """生成条码"""
    prefix_map = {'WO': 'WO', 'TK': 'TK', 'PR': 'PR', 'EQ': 'EQ', 'TL': 'TL'}
    prefix = prefix_map.get(biz_type, 'BC')
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    import random
    seq = str(random.randint(1000, 9999))
    return f"{prefix}{timestamp}{seq}"


@barcode_bp.route('/api/barcode/generate', methods=['POST'])
@login_required
def barcode_generate():
    d = request.json
    biz_type = d.get('biz_type', '')
    biz_id = d.get('biz_id', 0)
    barcode = generate_barcode(biz_type)
    
    db = get_db()
    db.execute("INSERT INTO sys_barcode (barcode, biz_type, biz_id) VALUES (?,?,?)",
               (barcode, biz_type, biz_id))
    db.commit()
    return jsonify({'code': 0, 'data': {'barcode': barcode}})


@barcode_bp.route('/api/barcode/scan')
@login_required
def barcode_scan():
    barcode = request.args.get('barcode', '')
    if not barcode:
        return jsonify({'code': 400, 'message': '条码为空'})
    
    db = get_db()
    record = db.execute("SELECT * FROM sys_barcode WHERE barcode=?", (barcode,)).fetchone()
    if not record:
        return jsonify({'code': 404, 'message': '条码不存在'})
    
    result = {'biz_type': record['biz_type'], 'biz_id': record['biz_id']}
    
    if record['biz_type'] == 'WO':
        wo = db.execute("SELECT * FROM prod_workorder WHERE id=?", (record['biz_id'],)).fetchone()
        if wo:
            result['data'] = dict(wo)
    elif record['biz_type'] == 'TK':
        task = db.execute("SELECT * FROM prod_task WHERE id=?", (record['biz_id'],)).fetchone()
        if task:
            result['data'] = dict(task)
    
    return jsonify({'code': 0, 'data': result})
