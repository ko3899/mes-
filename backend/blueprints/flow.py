"""审批流程蓝图。"""
import json
import sqlite3

from flask import Blueprint, jsonify, request, session

from utils.database import get_db
from utils.helpers import login_required, permission_required
from utils.db_errors import INTEGRITY_ERRORS


flow_bp = Blueprint('flow', __name__)


def _error(message, status=400):
    return jsonify({'code': status, 'message': message}), status


def _positive_int(value, field_name):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f'{field_name}格式错误')
    if parsed <= 0:
        raise ValueError(f'{field_name}必须大于0')
    return parsed


def _parse_steps(raw_steps, db):
    try:
        steps = json.loads(raw_steps) if isinstance(raw_steps, str) else raw_steps
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError('流程步骤必须是JSON数组') from exc
    if not isinstance(steps, list) or not steps:
        raise ValueError('流程至少需要一个审批步骤')

    normalized = []
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise ValueError(f'第{index}个流程步骤格式错误')
        assignee = _positive_int(step.get('assignee'), f'第{index}步审批人')
        user = db.execute(
            'SELECT 1 FROM sys_user WHERE id=? AND status=1', (assignee,)
        ).fetchone()
        if not user:
            raise ValueError(f'第{index}步审批人不存在或已停用')
        name = str(step.get('name') or f'第{index}步审批').strip()
        normalized.append({'step': index, 'name': name, 'assignee': assignee})
    return normalized


def _load_instance_steps(instance, flow):
    raw_steps = instance['steps_snapshot'] if 'steps_snapshot' in instance.keys() else None
    if not raw_steps:
        raw_steps = flow['steps']
    try:
        steps = json.loads(raw_steps) if raw_steps else []
    except (TypeError, json.JSONDecodeError):
        return []
    return steps if isinstance(steps, list) else []


@flow_bp.route('/api/flow/definition/list')
@login_required
def flow_def_list():
    db = get_db()
    rows = db.execute('SELECT * FROM flow_definition ORDER BY id DESC').fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': len(rows)}})


@flow_bp.route('/api/flow/definition/add', methods=['POST'])
@permission_required('flow:write')
def flow_def_add():
    data = request.get_json(silent=True) or {}
    flow_name = str(data.get('flow_name') or '').strip()
    flow_key = str(data.get('flow_key') or '').strip()
    if not flow_name or not flow_key:
        return _error('流程名称和流程标识不能为空')

    db = get_db()
    try:
        steps = _parse_steps(data.get('steps', []), db)
        status = int(data.get('status', 1))
        if status not in (0, 1):
            raise ValueError('流程状态只能是启用或停用')
        cursor = db.execute(
            '''INSERT INTO flow_definition
               (flow_name,flow_key,description,steps,status) VALUES (?,?,?,?,?)''',
            (flow_name, flow_key, str(data.get('description') or '').strip(),
             json.dumps(steps, ensure_ascii=False), status),
        )
        db.commit()
    except ValueError as exc:
        return _error(str(exc))
    except INTEGRITY_ERRORS:
        db.rollback()
        return _error('流程标识已存在', 409)
    return jsonify({'code': 0, 'data': {'id': cursor.lastrowid}})


@flow_bp.route('/api/flow/definition/update', methods=['POST'])
@permission_required('flow:write')
def flow_def_update():
    data = request.get_json(silent=True) or {}
    try:
        flow_id = _positive_int(data.get('id'), '流程ID')
    except ValueError as exc:
        return _error(str(exc))
    flow_name = str(data.get('flow_name') or '').strip()
    if not flow_name:
        return _error('流程名称不能为空')

    db = get_db()
    current = db.execute('SELECT * FROM flow_definition WHERE id=?', (flow_id,)).fetchone()
    if not current:
        return _error('流程不存在', 404)
    try:
        steps = _parse_steps(data.get('steps', current['steps']), db)
        status = int(data.get('status', current['status']))
        if status not in (0, 1):
            raise ValueError('流程状态只能是启用或停用')
    except ValueError as exc:
        return _error(str(exc))

    db.execute(
        '''UPDATE flow_definition SET flow_name=?,description=?,steps=?,status=?
           WHERE id=?''',
        (flow_name, str(data.get('description') or '').strip(),
         json.dumps(steps, ensure_ascii=False), status, flow_id),
    )
    db.commit()
    return jsonify({'code': 0})


@flow_bp.route('/api/flow/definition/delete', methods=['POST'])
@permission_required('flow:write')
def flow_def_delete():
    data = request.get_json(silent=True) or {}
    try:
        flow_id = _positive_int(data.get('id'), '流程ID')
    except ValueError as exc:
        return _error(str(exc))
    db = get_db()
    if not db.execute('SELECT 1 FROM flow_definition WHERE id=?', (flow_id,)).fetchone():
        return _error('流程不存在', 404)
    if db.execute('SELECT 1 FROM flow_instance WHERE flow_id=? LIMIT 1', (flow_id,)).fetchone():
        return _error('流程已有审批记录，不能删除；可改为停用', 409)
    db.execute('DELETE FROM flow_definition WHERE id=?', (flow_id,))
    db.commit()
    return jsonify({'code': 0})


@flow_bp.route('/api/flow/instance/submit', methods=['POST'])
@permission_required('flow:write')
def flow_instance_submit():
    data = request.get_json(silent=True) or {}
    try:
        flow_id = _positive_int(data.get('flow_id'), '流程ID')
    except ValueError as exc:
        return _error(str(exc))
    title = str(data.get('title') or '').strip()
    if not title:
        return _error('审批标题不能为空')

    biz_type = str(data.get('biz_type') or '').strip()
    if biz_type not in ('', 'workorder'):
        return _error('当前仅支持关联工单；入出库请使用正式过账')

    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        flow = db.execute(
            'SELECT * FROM flow_definition WHERE id=? AND status=1', (flow_id,)
        ).fetchone()
        if not flow:
            db.rollback()
            return _error('流程不存在或已停用', 404)
        steps = _parse_steps(flow['steps'], db)
    except ValueError as exc:
        db.rollback()
        return _error(f'流程配置无效：{exc}', 409)

    biz_id = 0
    if biz_type == 'workorder':
        try:
            biz_id = _positive_int(data.get('biz_id'), '关联工单ID')
        except ValueError as exc:
            db.rollback()
            return _error(str(exc))
        workorder = db.execute(
            'SELECT status FROM prod_workorder WHERE id=?', (biz_id,)
        ).fetchone()
        if not workorder:
            db.rollback()
            return _error('关联工单不存在', 404)
        if workorder['status'] != 0:
            db.rollback()
            return _error('只有待审批工单可以提交审批', 409)
        if db.execute(
            '''SELECT 1 FROM flow_instance
               WHERE biz_type='workorder' AND biz_id=? AND status=0 LIMIT 1''',
            (biz_id,),
        ).fetchone():
            db.rollback()
            return _error('该工单已有审批中的流程', 409)

    try:
        cursor = db.execute(
            '''INSERT INTO flow_instance
               (flow_id,biz_type,biz_id,title,current_step,status,creator,steps_snapshot)
               VALUES (?,?,?,?,1,0,?,?)''',
            (flow_id, biz_type, biz_id, title, session.get('user_id'),
             json.dumps(steps, ensure_ascii=False)),
        )
        instance_id = cursor.lastrowid
        db.execute(
            '''INSERT INTO flow_task (instance_id,step_no,assignee,status)
               VALUES (?,?,?,0)''',
            (instance_id, 1, steps[0]['assignee']),
        )
        db.commit()
    except INTEGRITY_ERRORS:
        db.rollback()
        return _error('该业务已有审批中的流程', 409)
    return jsonify({'code': 0, 'data': {'id': instance_id}})


@flow_bp.route('/api/flow/instance/list')
@login_required
def flow_instance_list():
    db = get_db()
    current_user = session.get('user_id')
    try:
        page = max(1, int(request.args.get('page', 1)))
        size = min(100, max(1, int(request.args.get('size', 15))))
    except (TypeError, ValueError):
        return _error('分页参数格式错误')
    tab = request.args.get('tab', 'mine')
    offset = (page - 1) * size
    if tab == 'mine':
        total = db.execute(
            'SELECT COUNT(*) AS count FROM flow_instance WHERE creator=?', (current_user,)
        ).fetchone()['count']
        rows = db.execute(
            '''SELECT fi.*,fd.flow_name FROM flow_instance fi
               LEFT JOIN flow_definition fd ON fi.flow_id=fd.id
               WHERE fi.creator=? ORDER BY fi.id DESC LIMIT ? OFFSET ?''',
            (current_user, size, offset),
        ).fetchall()
    elif tab == 'pending':
        total = db.execute(
            '''SELECT COUNT(*) AS count FROM flow_task ft
               JOIN flow_instance fi ON ft.instance_id=fi.id
               WHERE ft.assignee=? AND ft.status=0 AND fi.status=0''',
            (current_user,),
        ).fetchone()['count']
        rows = db.execute(
            '''SELECT fi.*,fd.flow_name,ft.id AS task_id,ft.step_no AS task_step_no
               FROM flow_task ft
               JOIN flow_instance fi ON ft.instance_id=fi.id
               LEFT JOIN flow_definition fd ON fi.flow_id=fd.id
               WHERE ft.assignee=? AND ft.status=0 AND fi.status=0
               ORDER BY ft.id DESC LIMIT ? OFFSET ?''',
            (current_user, size, offset),
        ).fetchall()
    else:
        return _error('审批列表类型无效')
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


def _get_pending_task(db, task_id, current_user):
    return db.execute(
        '''SELECT ft.* FROM flow_task ft
           JOIN flow_instance fi ON fi.id=ft.instance_id
           WHERE ft.id=? AND ft.assignee=? AND ft.status=0 AND fi.status=0''',
        (task_id, current_user),
    ).fetchone()


@flow_bp.route('/api/flow/task/approve', methods=['POST'])
@permission_required('flow:approve')
def flow_task_approve():
    data = request.get_json(silent=True) or {}
    try:
        task_id = _positive_int(data.get('id'), '任务ID')
    except ValueError as exc:
        return _error(str(exc))
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        task = _get_pending_task(db, task_id, session.get('user_id'))
        if not task:
            db.rollback()
            return _error('任务不存在或已处理', 409)
        instance = db.execute(
            'SELECT * FROM flow_instance WHERE id=? AND status=0',
            (task['instance_id'],),
        ).fetchone()
        flow = db.execute(
            'SELECT * FROM flow_definition WHERE id=?', (instance['flow_id'],)
        ).fetchone()
        steps = _load_instance_steps(instance, flow)
        if task['step_no'] < 1 or task['step_no'] > len(steps):
            db.rollback()
            return _error('审批实例的步骤配置已损坏', 409)

        updated = db.execute(
            '''UPDATE flow_task SET status=1,action='approve',comment=?,
               completed_at=CURRENT_TIMESTAMP WHERE id=? AND status=0''',
            (str(data.get('comment') or '').strip(), task_id),
        )
        if updated.rowcount != 1:
            db.rollback()
            return _error('任务已被处理', 409)

        next_step = task['step_no'] + 1
        if next_step > len(steps):
            db.execute(
                '''UPDATE flow_instance SET status=1,current_step=?,
                   updated_at=CURRENT_TIMESTAMP WHERE id=? AND status=0''',
                (task['step_no'], instance['id']),
            )
            if instance['biz_type'] == 'workorder' and instance['biz_id']:
                workorder_update = db.execute(
                    '''UPDATE prod_workorder SET status=1,updated_at=CURRENT_TIMESTAMP
                       WHERE id=? AND status=0''',
                    (instance['biz_id'],),
                )
                if workorder_update.rowcount != 1:
                    raise ValueError('关联工单状态已变化，审批结果未生效')
        else:
            next_assignee = _positive_int(
                steps[next_step - 1].get('assignee'), f'第{next_step}步审批人'
            )
            if not db.execute(
                'SELECT 1 FROM sys_user WHERE id=? AND status=1', (next_assignee,)
            ).fetchone():
                raise ValueError(f'第{next_step}步审批人不存在或已停用')
            db.execute(
                '''UPDATE flow_instance SET current_step=?,updated_at=CURRENT_TIMESTAMP
                   WHERE id=? AND status=0''',
                (next_step, instance['id']),
            )
            db.execute(
                '''INSERT INTO flow_task (instance_id,step_no,assignee,status)
                   VALUES (?,?,?,0)''',
                (instance['id'], next_step, next_assignee),
            )
        db.commit()
    except (ValueError,) + INTEGRITY_ERRORS as exc:
        db.rollback()
        return _error(str(exc), 409)
    return jsonify({'code': 0})


@flow_bp.route('/api/flow/task/reject', methods=['POST'])
@permission_required('flow:approve')
def flow_task_reject():
    data = request.get_json(silent=True) or {}
    try:
        task_id = _positive_int(data.get('id'), '任务ID')
    except ValueError as exc:
        return _error(str(exc))
    comment = str(data.get('comment') or '').strip()
    if not comment:
        return _error('驳回原因不能为空')
    db = get_db()
    db.execute('BEGIN IMMEDIATE')
    task = _get_pending_task(db, task_id, session.get('user_id'))
    if not task:
        db.rollback()
        return _error('任务不存在或已处理', 409)
    updated = db.execute(
        '''UPDATE flow_task SET status=2,action='reject',comment=?,
           completed_at=CURRENT_TIMESTAMP WHERE id=? AND status=0''',
        (comment, task_id),
    )
    if updated.rowcount != 1:
        db.rollback()
        return _error('任务已被处理', 409)
    db.execute(
        '''UPDATE flow_instance SET status=2,updated_at=CURRENT_TIMESTAMP
           WHERE id=? AND status=0''',
        (task['instance_id'],),
    )
    db.commit()
    return jsonify({'code': 0})


@flow_bp.route('/api/flow/pending/count')
@login_required
def flow_pending_count():
    db = get_db()
    count = db.execute(
        '''SELECT COUNT(*) AS count FROM flow_task ft
           JOIN flow_instance fi ON fi.id=ft.instance_id
           WHERE ft.assignee=? AND ft.status=0 AND fi.status=0''',
        (session.get('user_id'),),
    ).fetchone()['count']
    return jsonify({'code': 0, 'data': {'count': count}})
