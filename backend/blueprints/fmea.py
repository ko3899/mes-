"""FMEA失效模式分析蓝图"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete, gen_no, permission_required

fmea_bp = Blueprint('fmea', __name__)


@fmea_bp.route('/api/fmea/list')
@login_required
def fmea_list():
    """FMEA列表"""
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as c FROM qm_fmea").fetchone()['c']
    rows = db.execute('''SELECT f.*, p.product_name, pr.process_name
        FROM qm_fmea f
        LEFT JOIN base_product p ON f.product_id=p.id
        LEFT JOIN base_process pr ON f.process_id=pr.id
        ORDER BY f.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@fmea_bp.route('/api/fmea/add', methods=['POST'])
@permission_required('quality:write')
def fmea_add():
    """新增FMEA"""
    d = request.json
    d['fmea_no'] = gen_no('FMEA')
    # 计算RPN
    severity = int(d.get('severity', 1))
    occurrence = int(d.get('occurrence', 1))
    detection = int(d.get('detection', 1))
    d['rpn'] = severity * occurrence * detection
    return jsonify(crud_add('qm_fmea', d))


@fmea_bp.route('/api/fmea/update', methods=['POST'])
@permission_required('quality:write')
def fmea_update():
    """更新FMEA"""
    d = request.json
    if 'severity' in d and 'occurrence' in d and 'detection' in d:
        d['rpn'] = int(d['severity']) * int(d['occurrence']) * int(d['detection'])
    return jsonify(crud_update('qm_fmea', d))


@fmea_bp.route('/api/fmea/delete', methods=['POST'])
@permission_required('quality:write')
def fmea_delete():
    """删除FMEA"""
    return jsonify(crud_delete('qm_fmea', request.json.get('id')))


@fmea_bp.route('/api/fmea/statistics')
@login_required
def fmea_statistics():
    """FMEA统计"""
    db = get_db()
    
    # 高风险项（RPN > 100）
    high_risk = db.execute("SELECT COUNT(*) as c FROM qm_fmea WHERE rpn > 100").fetchone()['c']
    
    # 按工序统计
    by_process = db.execute('''SELECT pr.process_name, COUNT(*) as count, AVG(f.rpn) as avg_rpn
        FROM qm_fmea f
        LEFT JOIN base_process pr ON f.process_id=pr.id
        GROUP BY f.process_id ORDER BY avg_rpn DESC''').fetchall()
    
    return jsonify({'code': 0, 'data': {
        'high_risk': high_risk,
        'by_process': [dict(r) for r in by_process]
    }})
