"""排班管理蓝图"""
from flask import Blueprint, request, jsonify
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete

schedule_bp = Blueprint('schedule', __name__)


@schedule_bp.route('/api/sched/team/list')
@login_required
def sched_team_list():
    return jsonify(crud_list('sched_team', request.args))


@schedule_bp.route('/api/sched/team/add', methods=['POST'])
@login_required
def sched_team_add():
    return jsonify(crud_add('sched_team', request.json))


@schedule_bp.route('/api/sched/team/update', methods=['POST'])
@login_required
def sched_team_update():
    return jsonify(crud_update('sched_team', request.json))


@schedule_bp.route('/api/sched/team/delete', methods=['POST'])
@login_required
def sched_team_delete():
    return jsonify(crud_delete('sched_team', request.json.get('id')))


@schedule_bp.route('/api/sched/plan/list')
@login_required
def sched_plan_list():
    db = get_db()
    rows = db.execute('''SELECT sp.*, st.team_name
        FROM sched_plan sp
        LEFT JOIN sched_team st ON sp.team_id=st.id
        ORDER BY sp.id DESC''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@schedule_bp.route('/api/sched/plan/add', methods=['POST'])
@login_required
def sched_plan_add():
    return jsonify(crud_add('sched_plan', request.json))


@schedule_bp.route('/api/sched/plan/update', methods=['POST'])
@login_required
def sched_plan_update():
    return jsonify(crud_update('sched_plan', request.json))


@schedule_bp.route('/api/sched/plan/delete', methods=['POST'])
@login_required
def sched_plan_delete():
    return jsonify(crud_delete('sched_plan', request.json.get('id')))
