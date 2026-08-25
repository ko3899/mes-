"""质量管理增强蓝图 - 不良品处理、首件检验、8D报告、供方评审"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete, gen_no, permission_required

qm_ext_bp = Blueprint('qm_ext', __name__)


# ==================== 不良品处理 ====================
@qm_ext_bp.route('/api/qm/defect/list')
@login_required
def defect_process_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM qm_defect_process").fetchone()['cnt']
    rows = db.execute('''SELECT d.*, w.order_no as workorder_no, df.defect_name
        FROM qm_defect_process d
        LEFT JOIN prod_workorder w ON d.workorder_id=w.id
        LEFT JOIN base_defect df ON d.defect_id=df.id
        ORDER BY d.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@qm_ext_bp.route('/api/qm/defect/add', methods=['POST'])
@permission_required('quality:write')
def defect_process_add():
    data = request.json
    data['process_no'] = gen_no('DP')
    data['operator'] = session.get('user_id')
    return jsonify(crud_add('qm_defect_process', data))


@qm_ext_bp.route('/api/qm/defect/update', methods=['POST'])
@permission_required('quality:write')
def defect_process_update():
    return jsonify(crud_update('qm_defect_process', request.json))


# ==================== 首件检验 ====================
@qm_ext_bp.route('/api/qm/first/list')
@login_required
def first_inspect_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM qm_first_inspect").fetchone()['cnt']
    rows = db.execute('''SELECT f.*, w.order_no as workorder_no, p.process_name
        FROM qm_first_inspect f
        LEFT JOIN prod_workorder w ON f.workorder_id=w.id
        LEFT JOIN base_process p ON f.process_id=p.id
        ORDER BY f.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@qm_ext_bp.route('/api/qm/first/add', methods=['POST'])
@permission_required('quality:write')
def first_inspect_add():
    data = request.json
    data['inspect_no'] = gen_no('FI')
    data['operator'] = session.get('user_id')
    return jsonify(crud_add('qm_first_inspect', data))


@qm_ext_bp.route('/api/qm/first/update', methods=['POST'])
@permission_required('quality:write')
def first_inspect_update():
    return jsonify(crud_update('qm_first_inspect', request.json))


# ==================== 8D报告 ====================
@qm_ext_bp.route('/api/qm/8d/list')
@login_required
def report_8d_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM qm_8d_report").fetchone()['cnt']
    rows = db.execute('''SELECT * FROM qm_8d_report ORDER BY id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@qm_ext_bp.route('/api/qm/8d/add', methods=['POST'])
@permission_required('quality:write')
def report_8d_add():
    data = request.json
    data['report_no'] = gen_no('8D')
    return jsonify(crud_add('qm_8d_report', data))


@qm_ext_bp.route('/api/qm/8d/update', methods=['POST'])
@permission_required('quality:write')
def report_8d_update():
    return jsonify(crud_update('qm_8d_report', request.json))


@qm_ext_bp.route('/api/qm/8d/delete', methods=['POST'])
@permission_required('quality:write')
def report_8d_delete():
    return jsonify(crud_delete('qm_8d_report', request.json.get('id')))


# ==================== 供方评审 ====================
@qm_ext_bp.route('/api/qm/supplier-eval/list')
@login_required
def supplier_eval_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM qm_supplier_eval").fetchone()['cnt']
    rows = db.execute('''SELECT e.*, s.supplier_name
        FROM qm_supplier_eval e
        LEFT JOIN base_supplier s ON e.supplier_id=s.id
        ORDER BY e.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@qm_ext_bp.route('/api/qm/supplier-eval/add', methods=['POST'])
@permission_required('quality:write')
def supplier_eval_add():
    data = request.json
    data['evaluator'] = session.get('user_id')
    data['total_score'] = round((float(data.get('quality_score', 0)) + 
                                  float(data.get('delivery_score', 0)) + 
                                  float(data.get('service_score', 0))) / 3, 2)
    if data['total_score'] >= 90:
        data['grade'] = 'A'
    elif data['total_score'] >= 80:
        data['grade'] = 'B'
    elif data['total_score'] >= 70:
        data['grade'] = 'C'
    else:
        data['grade'] = 'D'
    return jsonify(crud_add('qm_supplier_eval', data))


@qm_ext_bp.route('/api/qm/supplier-eval/ranking')
@login_required
def supplier_eval_ranking():
    db = get_db()
    rows = db.execute('''SELECT s.supplier_name, 
        AVG(e.total_score) as avg_score,
        COUNT(*) as eval_count,
        MAX(e.grade) as latest_grade
        FROM qm_supplier_eval e
        LEFT JOIN base_supplier s ON e.supplier_id=s.id
        GROUP BY e.supplier_id
        ORDER BY avg_score DESC''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


# ==================== 质量统计 ====================
@qm_ext_bp.route('/api/qm/statistics')
@login_required
def quality_statistics():
    db = get_db()
    import datetime
    today = datetime.date.today()
    start = (today - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
    
    # 来料合格率
    incoming_total = db.execute("SELECT COUNT(*) as c FROM qm_incoming_inspection WHERE created_at >= ?", (start,)).fetchone()['c']
    incoming_pass = db.execute("SELECT COUNT(*) as c FROM qm_incoming_inspection WHERE result='合格' AND created_at >= ?", (start,)).fetchone()['c']
    
    # 过程合格率
    process_total = db.execute("SELECT COUNT(*) as c FROM qm_process_inspection WHERE created_at >= ?", (start,)).fetchone()['c']
    process_pass = db.execute("SELECT COUNT(*) as c FROM qm_process_inspection WHERE result='合格' AND created_at >= ?", (start,)).fetchone()['c']
    
    # 出货合格率
    outgoing_total = db.execute("SELECT COUNT(*) as c FROM qm_outgoing_inspection WHERE created_at >= ?", (start,)).fetchone()['c']
    outgoing_pass = db.execute("SELECT COUNT(*) as c FROM qm_outgoing_inspection WHERE result='合格' AND created_at >= ?", (start,)).fetchone()['c']
    
    # 不良品统计
    defect_stats = db.execute('''SELECT d.defect_name, COUNT(*) as count
        FROM qm_defect_process dp
        LEFT JOIN base_defect d ON dp.defect_id=d.id
        GROUP BY dp.defect_id ORDER BY count DESC LIMIT 10''').fetchall()
    
    return jsonify({'code': 0, 'data': {
        'incoming_rate': round(incoming_pass / incoming_total * 100, 2) if incoming_total > 0 else 100,
        'process_rate': round(process_pass / process_total * 100, 2) if process_total > 0 else 100,
        'outgoing_rate': round(outgoing_pass / outgoing_total * 100, 2) if outgoing_total > 0 else 100,
        'defect_stats': [dict(r) for r in defect_stats]
    }})
