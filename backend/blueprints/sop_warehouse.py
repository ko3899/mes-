"""电子SOP和线边仓管理蓝图"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete, gen_no, permission_required

sop_bp = Blueprint('sop', __name__)


# ==================== 电子SOP ====================
@sop_bp.route('/api/sop/list')
@login_required
def sop_list():
    """SOP文档列表"""
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as c FROM sys_document WHERE doc_type='SOP'").fetchone()['c']
    rows = db.execute('''SELECT d.*, u.real_name as uploader_name
        FROM sys_document d
        LEFT JOIN sys_user u ON d.uploader=u.id
        WHERE d.doc_type='SOP'
        ORDER BY d.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@sop_bp.route('/api/sop/process/<int:process_id>')
@login_required
def sop_by_process(process_id):
    """按工序获取SOP"""
    db = get_db()
    rows = db.execute('''SELECT * FROM sys_document 
        WHERE doc_type='SOP' AND category=? 
        ORDER BY version DESC''', (str(process_id),)).fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


# ==================== 线边仓管理 ====================
@sop_bp.route('/api/line-warehouse/list')
@login_required
def line_warehouse_list():
    """线边仓库存"""
    db = get_db()
    rows = db.execute('''SELECT lw.*, p.product_name, p.code, ws.workshop_name
        FROM inv_line_warehouse lw
        LEFT JOIN base_product p ON lw.product_id=p.id
        LEFT JOIN base_workshop ws ON lw.workshop_id=ws.id
        ORDER BY lw.id DESC''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@sop_bp.route('/api/line-warehouse/add', methods=['POST'])
@permission_required('inv:write')
def line_warehouse_add():
    """添加线边仓库存"""
    return jsonify(crud_add('inv_line_warehouse', request.json))


@sop_bp.route('/api/line-warehouse/replenish', methods=['POST'])
@permission_required('inv:write')
def line_warehouse_replenish():
    """补货请求"""
    d = request.get_json(silent=True) or {}
    if not d.get('product_id') or not d.get('workshop_id'):
        return jsonify({'code': 400, 'message': '产品和车间不能为空'}), 400
    db = get_db()
    d['req_no'] = gen_no('RP')
    d['operator'] = session.get('user_id')
    db.execute("INSERT INTO inv_line_warehouse (product_id, workshop_id, quantity, min_quantity) VALUES (?,?,?,?)",
               (d['product_id'], d['workshop_id'], d.get('quantity', 0), d.get('min_quantity', 10)))
    db.commit()
    return jsonify({'code': 0, 'message': '补货请求已提交'})
