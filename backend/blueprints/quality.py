"""质量管理蓝图"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete, gen_no, permission_required

quality_bp = Blueprint('quality', __name__)


@quality_bp.route('/api/qm/incoming/list')
@login_required
def qm_incoming_list():
    return jsonify(crud_list('qm_incoming_inspection', request.args))


@quality_bp.route('/api/qm/incoming/add', methods=['POST'])
@permission_required('quality:write')
def qm_incoming_add():
    data = request.json
    data['inspect_no'] = gen_no('IQC')
    data['inspector'] = session.get('user_id')
    return jsonify(crud_add('qm_incoming_inspection', data))


@quality_bp.route('/api/qm/incoming/update', methods=['POST'])
@permission_required('quality:write')
def qm_incoming_update():
    return jsonify(crud_update('qm_incoming_inspection', request.json))


@quality_bp.route('/api/qm/incoming/delete', methods=['POST'])
@permission_required('quality:write')
def qm_incoming_delete():
    return jsonify(crud_delete('qm_incoming_inspection', request.json.get('id')))


@quality_bp.route('/api/qm/process/list')
@login_required
def qm_process_list():
    return jsonify(crud_list('qm_process_inspection', request.args))


@quality_bp.route('/api/qm/process/add', methods=['POST'])
@permission_required('quality:write')
def qm_process_add():
    data = request.json
    data['inspect_no'] = gen_no('PQC')
    data['inspector'] = session.get('user_id')
    return jsonify(crud_add('qm_process_inspection', data))


@quality_bp.route('/api/qm/process/update', methods=['POST'])
@permission_required('quality:write')
def qm_process_update():
    return jsonify(crud_update('qm_process_inspection', request.json))


@quality_bp.route('/api/qm/process/delete', methods=['POST'])
@permission_required('quality:write')
def qm_process_delete():
    return jsonify(crud_delete('qm_process_inspection', request.json.get('id')))


@quality_bp.route('/api/qm/outgoing/list')
@login_required
def qm_outgoing_list():
    return jsonify(crud_list('qm_outgoing_inspection', request.args))


@quality_bp.route('/api/qm/outgoing/add', methods=['POST'])
@permission_required('quality:write')
def qm_outgoing_add():
    data = request.json
    data['inspect_no'] = gen_no('OQC')
    data['inspector'] = session.get('user_id')
    return jsonify(crud_add('qm_outgoing_inspection', data))


@quality_bp.route('/api/qm/outgoing/update', methods=['POST'])
@permission_required('quality:write')
def qm_outgoing_update():
    return jsonify(crud_update('qm_outgoing_inspection', request.json))


@quality_bp.route('/api/qm/outgoing/delete', methods=['POST'])
@permission_required('quality:write')
def qm_outgoing_delete():
    return jsonify(crud_delete('qm_outgoing_inspection', request.json.get('id')))
