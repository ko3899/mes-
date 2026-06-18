"""设备增强蓝图 - 模具/工装夹具"""
from flask import Blueprint, request, jsonify
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete

eqp_plus_bp = Blueprint('eqp_plus', __name__)


# ==================== 模具管理 ====================
@eqp_plus_bp.route('/api/eqp/mold/list')
@login_required
def mold_list():
    db = get_db()
    rows = db.execute('''SELECT m.*, p.product_name
        FROM eqp_mold m
        LEFT JOIN base_product p ON m.product_id=p.id
        ORDER BY m.id DESC''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@eqp_plus_bp.route('/api/eqp/mold/add', methods=['POST'])
@login_required
def mold_add():
    return jsonify(crud_add('eqp_mold', request.json))


@eqp_plus_bp.route('/api/eqp/mold/update', methods=['POST'])
@login_required
def mold_update():
    return jsonify(crud_update('eqp_mold', request.json))


@eqp_plus_bp.route('/api/eqp/mold/delete', methods=['POST'])
@login_required
def mold_delete():
    return jsonify(crud_delete('eqp_mold', request.json.get('id')))


# ==================== 工装夹具 ====================
@eqp_plus_bp.route('/api/eqp/fixture/list')
@login_required
def fixture_list():
    db = get_db()
    rows = db.execute('''SELECT f.*, p.process_name
        FROM eqp_fixture f
        LEFT JOIN base_process p ON f.process_id=p.id
        ORDER BY f.id DESC''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@eqp_plus_bp.route('/api/eqp/fixture/add', methods=['POST'])
@login_required
def fixture_add():
    return jsonify(crud_add('eqp_fixture', request.json))


@eqp_plus_bp.route('/api/eqp/fixture/update', methods=['POST'])
@login_required
def fixture_update():
    return jsonify(crud_update('eqp_fixture', request.json))


@eqp_plus_bp.route('/api/eqp/fixture/delete', methods=['POST'])
@login_required
def fixture_delete():
    return jsonify(crud_delete('eqp_fixture', request.json.get('id')))
