"""人力资源蓝图 - 培训/技能矩阵"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete, gen_no, permission_required

hr_bp = Blueprint('hr', __name__)


# ==================== 培训管理 ====================
@hr_bp.route('/api/hr/training/list')
@login_required
def training_list():
    return jsonify(crud_list('hr_training', request.args))


@hr_bp.route('/api/hr/training/add', methods=['POST'])
@permission_required('hr:write')
def training_add():
    return jsonify(crud_add('hr_training', request.json))


@hr_bp.route('/api/hr/training/update', methods=['POST'])
@permission_required('hr:write')
def training_update():
    return jsonify(crud_update('hr_training', request.json))


@hr_bp.route('/api/hr/training/delete', methods=['POST'])
@permission_required('hr:write')
def training_delete():
    return jsonify(crud_delete('hr_training', request.json.get('id')))


@hr_bp.route('/api/hr/training/<int:training_id>/records')
@login_required
def training_records(training_id):
    db = get_db()
    rows = db.execute('''SELECT r.*, u.real_name
        FROM hr_training_record r
        LEFT JOIN sys_user u ON r.user_id=u.id
        WHERE r.training_id=?''', (training_id,)).fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@hr_bp.route('/api/hr/training/record/add', methods=['POST'])
@permission_required('hr:write')
def training_record_add():
    return jsonify(crud_add('hr_training_record', request.json))


# ==================== 技能矩阵 ====================
@hr_bp.route('/api/hr/skill-matrix/list')
@login_required
def skill_matrix_list():
    db = get_db()
    rows = db.execute('''SELECT s.*, u.real_name, p.process_name
        FROM hr_skill_matrix s
        LEFT JOIN sys_user u ON s.user_id=u.id
        LEFT JOIN base_process p ON s.process_id=p.id
        ORDER BY s.user_id, s.process_id''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@hr_bp.route('/api/hr/skill-matrix/add', methods=['POST'])
@permission_required('hr:write')
def skill_matrix_add():
    d = request.json
    d['evaluator'] = session.get('user_id')
    return jsonify(crud_add('hr_skill_matrix', d))


@hr_bp.route('/api/hr/skill-matrix/update', methods=['POST'])
@permission_required('hr:write')
def skill_matrix_update():
    return jsonify(crud_update('hr_skill_matrix', request.json))


@hr_bp.route('/api/hr/skill-matrix/delete', methods=['POST'])
@permission_required('hr:write')
def skill_matrix_delete():
    return jsonify(crud_delete('hr_skill_matrix', request.json.get('id')))


@hr_bp.route('/api/hr/skill-matrix/matrix')
@login_required
def skill_matrix_view():
    """技能矩阵视图"""
    db = get_db()
    users = db.execute("SELECT id, real_name FROM sys_user WHERE status=1 ORDER BY id").fetchall()
    processes = db.execute("SELECT id, process_name FROM base_process WHERE status=1 ORDER BY id").fetchall()
    skills = db.execute("SELECT * FROM hr_skill_matrix").fetchall()
    
    matrix = {}
    for s in skills:
        key = f"{s['user_id']}_{s['process_id']}"
        matrix[key] = s['skill_level']
    
    return jsonify({'code': 0, 'data': {
        'users': [dict(u) for u in users],
        'processes': [dict(p) for p in processes],
        'matrix': matrix
    }})
