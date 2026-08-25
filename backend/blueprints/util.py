"""公共事业蓝图 - 能耗/环境"""
from flask import Blueprint, request, jsonify
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_delete, permission_required

util_bp = Blueprint('util', __name__)


# ==================== 能耗管理 ====================
@util_bp.route('/api/util/energy/list')
@login_required
def energy_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM util_energy").fetchone()['cnt']
    rows = db.execute('''SELECT e.*, ws.workshop_name
        FROM util_energy e
        LEFT JOIN base_workshop ws ON e.workshop_id=ws.id
        ORDER BY e.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@util_bp.route('/api/util/energy/add', methods=['POST'])
@permission_required('util:write')
def energy_add():
    return jsonify(crud_add('util_energy', request.json))


@util_bp.route('/api/util/energy/delete', methods=['POST'])
@permission_required('util:write')
def energy_delete():
    return jsonify(crud_delete('util_energy', request.json.get('id')))


@util_bp.route('/api/util/energy/statistics')
@login_required
def energy_statistics():
    db = get_db()
    rows = db.execute('''SELECT energy_type, SUM(quantity) as total_qty, SUM(cost) as total_cost
        FROM util_energy GROUP BY energy_type ORDER BY total_cost DESC''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


# ==================== 环境监控 ====================
@util_bp.route('/api/util/environment/list')
@login_required
def environment_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM util_environment").fetchone()['cnt']
    rows = db.execute('''SELECT e.*, ws.workshop_name
        FROM util_environment e
        LEFT JOIN base_workshop ws ON e.workshop_id=ws.id
        ORDER BY e.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@util_bp.route('/api/util/environment/add', methods=['POST'])
@permission_required('util:write')
def environment_add():
    return jsonify(crud_add('util_environment', request.json))


@util_bp.route('/api/util/environment/latest')
@login_required
def environment_latest():
    db = get_db()
    rows = db.execute('''SELECT e.*, ws.workshop_name
        FROM util_environment e
        LEFT JOIN base_workshop ws ON e.workshop_id=ws.id
        WHERE e.id IN (SELECT MAX(id) FROM util_environment GROUP BY workshop_id)
        ORDER BY e.id DESC''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})
