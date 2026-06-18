"""审批流程蓝图"""
import json
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required

flow_bp = Blueprint('flow', __name__)


@flow_bp.route('/api/flow/definition/list')
@login_required
def flow_def_list():
    db = get_db()
    rows = db.execute("SELECT * FROM flow_definition ORDER BY id DESC").fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': len(rows)}})


@flow_bp.route('/api/flow/definition/add', methods=['POST'])
@login_required
def flow_def_add():
    d = request.json
    db = get_db()
    db.execute("INSERT INTO flow_definition (flow_name,flow_key,description,steps,status) VALUES (?,?,?,?,?)",
               (d['flow_name'], d['flow_key'], d.get('description',''), d.get('steps','[]'), d.get('status',1)))
    db.commit()
    return jsonify({'code': 0})


@flow_bp.route('/api/flow/definition/update', methods=['POST'])
@login_required
def flow_def_update():
    d = request.json
    db = get_db()
    db.execute("UPDATE flow_definition SET flow_name=?,description=?,steps=?,status=? WHERE id=?",
               (d['flow_name'], d.get('description',''), d.get('steps','[]'), d.get('status',1), d['id']))
    db.commit()
    return jsonify({'code': 0})


@flow_bp.route('/api/flow/definition/delete', methods=['POST'])
@login_required
def flow_def_delete():
    db = get_db()
    db.execute("DELETE FROM flow_definition WHERE id=?", (request.json['id'],))
    db.commit()
    return jsonify({'code': 0})


@flow_bp.route('/api/flow/instance/submit', methods=['POST'])
@login_required
def flow_instance_submit():
    d = request.json
    db = get_db()
    flow = db.execute("SELECT * FROM flow_definition WHERE id=?", (d['flow_id'],)).fetchone()
    if not flow:
        return jsonify({'code': 400, 'message': '流程不存在'})
    steps = json.loads(flow['steps']) if flow['steps'] else []
    cur = session.get('user_id')
    db.execute("INSERT INTO flow_instance (flow_id,biz_type,biz_id,title,current_step,status,creator) VALUES (?,?,?,?,?,0,?)",
               (d['flow_id'], d.get('biz_type',''), d.get('biz_id',0), d.get('title',''), 1, cur))
    inst_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    if steps:
        assignee = steps[0].get('assignee', cur)
        db.execute("INSERT INTO flow_task (instance_id,step_no,assignee,status) VALUES (?,?,?,0)", (inst_id, 1, assignee))
    db.commit()
    return jsonify({'code': 0, 'data': {'id': inst_id}})


@flow_bp.route('/api/flow/instance/list')
@login_required
def flow_instance_list():
    db = get_db()
    cur = session.get('user_id')
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 15))
    tab = request.args.get('tab', 'mine')
    if tab == 'mine':
        total = db.execute("SELECT COUNT(*) as c FROM flow_instance WHERE creator=?", (cur,)).fetchone()['c']
        rows = db.execute('''SELECT fi.*, fd.flow_name FROM flow_instance fi
            LEFT JOIN flow_definition fd ON fi.flow_id=fd.id
            WHERE fi.creator=? ORDER BY fi.id DESC LIMIT ? OFFSET ?''', (cur, size, (page-1)*size)).fetchall()
    else:
        total = db.execute("SELECT COUNT(*) as c FROM flow_task WHERE assignee=? AND status=0", (cur,)).fetchone()['c']
        rows = db.execute('''SELECT fi.*, fd.flow_name FROM flow_task ft
            JOIN flow_instance fi ON ft.instance_id=fi.id
            LEFT JOIN flow_definition fd ON fi.flow_id=fd.id
            WHERE ft.assignee=? AND ft.status=0 ORDER BY fi.id DESC LIMIT ? OFFSET ?''', (cur, size, (page-1)*size)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@flow_bp.route('/api/flow/task/approve', methods=['POST'])
@login_required
def flow_task_approve():
    d = request.json
    db = get_db()
    cur = session.get('user_id')
    task = db.execute("SELECT * FROM flow_task WHERE id=? AND assignee=? AND status=0", (d['id'], cur)).fetchone()
    if not task:
        return jsonify({'code': 400, 'message': '任务不存在或已处理'})
    db.execute("UPDATE flow_task SET status=1,action='approve',comment=?,completed_at=CURRENT_TIMESTAMP WHERE id=?",
               (d.get('comment',''), d['id']))
    inst = db.execute("SELECT * FROM flow_instance WHERE id=?", (task['instance_id'],)).fetchone()
    flow = db.execute("SELECT * FROM flow_definition WHERE id=?", (inst['flow_id'],)).fetchone()
    steps = json.loads(flow['steps']) if flow['steps'] else []
    next_step = task['step_no'] + 1
    if next_step > len(steps):
        db.execute("UPDATE flow_instance SET status=1, current_step=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                   (next_step, inst['id']))
        if inst['biz_type'] == 'workorder' and inst['biz_id']:
            db.execute("UPDATE prod_workorder SET status=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (inst['biz_id'],))
    else:
        db.execute("UPDATE flow_instance SET current_step=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                   (next_step, inst['id']))
        next_assignee = steps[next_step-1].get('assignee', cur)
        db.execute("INSERT INTO flow_task (instance_id,step_no,assignee,status) VALUES (?,?,?,0)",
                   (inst['id'], next_step, next_assignee))
    db.commit()
    return jsonify({'code': 0})


@flow_bp.route('/api/flow/task/reject', methods=['POST'])
@login_required
def flow_task_reject():
    d = request.json
    db = get_db()
    cur = session.get('user_id')
    task = db.execute("SELECT * FROM flow_task WHERE id=? AND assignee=? AND status=0", (d['id'], cur)).fetchone()
    if not task:
        return jsonify({'code': 400, 'message': '任务不存在或已处理'})
    db.execute("UPDATE flow_task SET status=2,action='reject',comment=?,completed_at=CURRENT_TIMESTAMP WHERE id=?",
               (d.get('comment',''), d['id']))
    db.execute("UPDATE flow_instance SET status=2, updated_at=CURRENT_TIMESTAMP WHERE id=?", (task['instance_id'],))
    db.commit()
    return jsonify({'code': 0})


@flow_bp.route('/api/flow/pending/count')
@login_required
def flow_pending_count():
    db = get_db()
    cur = session.get('user_id')
    cnt = db.execute("SELECT COUNT(*) as c FROM flow_task WHERE assignee=? AND status=0", (cur,)).fetchone()['c']
    return jsonify({'code': 0, 'data': {'count': cnt}})
