"""条码管理蓝图 - 生成/打印/扫描/查询"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import crud_list, login_required, gen_no

barcode_bp = Blueprint('barcode', __name__)


@barcode_bp.route('/api/barcode/generate', methods=['POST'])
@login_required
def barcode_generate():
    """生成条码"""
    d = request.json
    biz_type = d.get('biz_type', '')
    biz_id = d.get('biz_id', 0)
    
    import datetime
    import random
    prefix_map = {'WO': 'WO', 'TK': 'TK', 'PR': 'PR', 'EQ': 'EQ', 'MT': 'MT', 'BOX': 'BOX'}
    prefix = prefix_map.get(biz_type, 'BC')
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    seq = str(random.randint(1000, 9999))
    barcode = f"{prefix}{timestamp}{seq}"
    
    db = get_db()
    db.execute("INSERT INTO sys_barcode (barcode, biz_type, biz_id) VALUES (?,?,?)",
               (barcode, biz_type, biz_id))
    db.commit()
    return jsonify({'code': 0, 'data': {'barcode': barcode}})


@barcode_bp.route('/api/barcode/scan')
@login_required
def barcode_scan():
    """扫描条码查询"""
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
    elif record['biz_type'] == 'PR':
        product = db.execute("SELECT * FROM base_product WHERE id=?", (record['biz_id'],)).fetchone()
        if product:
            result['data'] = dict(product)
    
    return jsonify({'code': 0, 'data': result})


@barcode_bp.route('/api/barcode/list')
@login_required
def barcode_list():
    """条码列表"""
    return jsonify(crud_list('sys_barcode', request.args))


@barcode_bp.route('/api/barcode/batch-generate', methods=['POST'])
@login_required
def barcode_batch_generate():
    """批量生成条码"""
    d = request.json
    biz_type = d.get('biz_type', '')
    count = int(d.get('count', 10))
    
    import datetime
    import random
    prefix_map = {'WO': 'WO', 'TK': 'TK', 'PR': 'PR', 'EQ': 'EQ', 'MT': 'MT'}
    prefix = prefix_map.get(biz_type, 'BC')
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    
    db = get_db()
    barcodes = []
    for i in range(count):
        seq = str(random.randint(1000, 9999))
        barcode = f"{prefix}{timestamp}{seq}{str(i).zfill(3)}"
        db.execute("INSERT INTO sys_barcode (barcode, biz_type, biz_id) VALUES (?,?,?)",
                   (barcode, biz_type, 0))
        barcodes.append(barcode)
    db.commit()
    return jsonify({'code': 0, 'data': {'barcodes': barcodes, 'count': len(barcodes)}})
