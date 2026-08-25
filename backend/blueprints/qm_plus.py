"""质量增强蓝图 - CAPA/控制计划/变更管理"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete, gen_no, permission_required

qm_plus_bp = Blueprint('qm_plus', __name__)


# ==================== CAPA ====================
@qm_plus_bp.route('/api/qm/capa/list')
@login_required
def capa_list():
    return jsonify(crud_list('qm_capa', request.args))


@qm_plus_bp.route('/api/qm/capa/add', methods=['POST'])
@permission_required('quality:write')
def capa_add():
    d = request.json
    d['capa_no'] = gen_no('CP')
    return jsonify(crud_add('qm_capa', d))


@qm_plus_bp.route('/api/qm/capa/update', methods=['POST'])
@permission_required('quality:write')
def capa_update():
    return jsonify(crud_update('qm_capa', request.json))


@qm_plus_bp.route('/api/qm/capa/delete', methods=['POST'])
@permission_required('quality:write')
def capa_delete():
    return jsonify(crud_delete('qm_capa', request.json.get('id')))


# ==================== 控制计划 ====================
@qm_plus_bp.route('/api/qm/control-plan/list')
@login_required
def control_plan_list():
    db = get_db()
    rows = db.execute('''SELECT c.*, p.product_name, pr.process_name
        FROM qm_control_plan c
        LEFT JOIN base_product p ON c.product_id=p.id
        LEFT JOIN base_process pr ON c.process_id=pr.id
        ORDER BY c.id DESC''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@qm_plus_bp.route('/api/qm/control-plan/add', methods=['POST'])
@permission_required('quality:write')
def control_plan_add():
    return jsonify(crud_add('qm_control_plan', request.json))


@qm_plus_bp.route('/api/qm/control-plan/update', methods=['POST'])
@permission_required('quality:write')
def control_plan_update():
    return jsonify(crud_update('qm_control_plan', request.json))


@qm_plus_bp.route('/api/qm/control-plan/delete', methods=['POST'])
@permission_required('quality:write')
def control_plan_delete():
    return jsonify(crud_delete('qm_control_plan', request.json.get('id')))


# ==================== 工程变更 ====================
@qm_plus_bp.route('/api/qm/eco/list')
@login_required
def eco_list():
    return jsonify(crud_list('qm_eco', request.args))


@qm_plus_bp.route('/api/qm/eco/add', methods=['POST'])
@permission_required('quality:write')
def eco_add():
    d = request.json
    d['eco_no'] = gen_no('ECO')
    d['applicant'] = session.get('user_id')
    return jsonify(crud_add('qm_eco', d))


@qm_plus_bp.route('/api/qm/eco/update', methods=['POST'])
@permission_required('quality:write')
def eco_update():
    return jsonify(crud_update('qm_eco', request.json))


@qm_plus_bp.route('/api/qm/eco/delete', methods=['POST'])
@permission_required('quality:write')
def eco_delete():
    return jsonify(crud_delete('qm_eco', request.json.get('id')))
