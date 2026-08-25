"""生产现场蓝图 - 工位/安灯/返工报废"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import (
    login_required, permission_required, crud_list, crud_add, crud_update,
    crud_delete, gen_no_in_transaction,
)
from services.production_flow import BusinessError, transition_status
from services.quality_disposition import (
    approve_disposition, reject_disposition, validate_rework_task_start,
)

site_bp = Blueprint('site', __name__)


# ==================== 工位管理 ====================
@site_bp.route('/api/site/workstation/list')
@login_required
def workstation_list():
    db = get_db()
    rows = db.execute('''SELECT w.*, ws.workshop_name, p.process_name
        FROM base_workstation w
        LEFT JOIN base_workshop ws ON w.workshop_id=ws.id
        LEFT JOIN base_process p ON w.process_id=p.id
        ORDER BY w.id DESC''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@site_bp.route('/api/site/workstation/add', methods=['POST'])
@permission_required('site:write')
def workstation_add():
    data = request.get_json(silent=True) or {}
    if not str(data.get('station_name') or '').strip() or not str(data.get('code') or '').strip():
        return jsonify({'code': 400, 'message': '工位名称和编码不能为空'}), 400
    data['station_name'] = str(data['station_name']).strip()
    data['code'] = str(data['code']).strip()
    return jsonify(crud_add('base_workstation', data))


@site_bp.route('/api/site/workstation/update', methods=['POST'])
@permission_required('site:write')
def workstation_update():
    return jsonify(crud_update('base_workstation', request.json))


@site_bp.route('/api/site/workstation/delete', methods=['POST'])
@permission_required('site:write')
def workstation_delete():
    data = request.get_json(silent=True) or {}
    try:
        workstation_id = int(data.get('id'))
    except (TypeError, ValueError):
        return jsonify({'code': 400, 'message': '工位ID格式错误'}), 400
    db = get_db()
    if not db.execute('SELECT 1 FROM base_workstation WHERE id=?', (workstation_id,)).fetchone():
        return jsonify({'code': 404, 'message': '工位不存在'}), 404
    if db.execute('SELECT 1 FROM prod_andon WHERE workstation_id=? LIMIT 1', (workstation_id,)).fetchone():
        return jsonify({'code': 409, 'message': '工位已有安灯记录，不能删除；可停用并保留历史'}), 409
    db.execute('DELETE FROM base_workstation WHERE id=?', (workstation_id,))
    db.commit()
    return jsonify({'code': 0, 'message': '删除成功'})


# ==================== 安灯系统 ====================
@site_bp.route('/api/site/andon/list')
@login_required
def andon_list():
    db = get_db()
    try:
        page = max(1, int(request.args.get('page', 1)))
        size = min(100, max(1, int(request.args.get('size', 20))))
    except (TypeError, ValueError):
        return jsonify({'code': 400, 'message': '分页参数格式错误'}), 400
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM prod_andon").fetchone()['cnt']
    rows = db.execute('''SELECT a.*, ws.station_name,
        u1.real_name as caller_name, u2.real_name as responder_name
        FROM prod_andon a
        LEFT JOIN base_workstation ws ON a.workstation_id=ws.id
        LEFT JOIN sys_user u1 ON a.caller=u1.id
        LEFT JOIN sys_user u2 ON a.responder=u2.id
        ORDER BY a.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@site_bp.route('/api/site/andon/call', methods=['POST'])
@permission_required('site:write')
def andon_call():
    d = request.get_json(silent=True) or {}
    try:
        workstation_id = int(d.get('workstation_id'))
        priority = int(d.get('priority', 1))
    except (TypeError, ValueError):
        return jsonify({'code': 400, 'message': '工位或优先级格式错误'}), 400
    if workstation_id <= 0 or priority not in (1, 2, 3):
        return jsonify({'code': 400, 'message': '工位无效或优先级超出范围'}), 400
    andon_type = str(d.get('andon_type') or '').strip()
    if andon_type not in ('quality', 'equipment', 'material', 'safety'):
        return jsonify({'code': 400, 'message': '安灯类型无效'}), 400
    description = str(d.get('description') or '').strip()
    if not description:
        return jsonify({'code': 400, 'message': '安灯描述不能为空'}), 400
    db = get_db()
    db.execute('BEGIN IMMEDIATE')
    if not db.execute('SELECT 1 FROM base_workstation WHERE id=? AND status=1', (workstation_id,)).fetchone():
        db.rollback()
        return jsonify({'code': 404, 'message': '工位不存在或已停用'}), 404
    if db.execute('''SELECT 1 FROM prod_andon
                     WHERE workstation_id=? AND andon_type=? AND status IN (0,1) LIMIT 1''',
                  (workstation_id, andon_type)).fetchone():
        db.rollback()
        return jsonify({'code': 409, 'message': '该工位已有同类型未解决安灯'}), 409
    cursor = db.execute('''INSERT INTO prod_andon
        (andon_no,workstation_id,andon_type,description,priority,caller,status)
        VALUES (?,?,?,?,?,?,0)''',
        (gen_no_in_transaction(db, 'AD'), workstation_id, andon_type, description,
         priority, session.get('user_id')))
    db.commit()
    return jsonify({'code': 0, 'data': {'id': cursor.lastrowid}})


@site_bp.route('/api/site/andon/respond', methods=['POST'])
@permission_required('site:write')
def andon_respond():
    import datetime
    d = request.get_json(silent=True) or {}
    if not d.get('id'):
        return jsonify({'code': 400, 'message': '缺少安灯记录ID'}), 400
    db = get_db()
    cursor = db.execute("UPDATE prod_andon SET status=1, responder=?, response_time=CURRENT_TIMESTAMP WHERE id=? AND status=0",
                        (session.get('user_id'), d['id']))
    if cursor.rowcount == 0:
        return jsonify({'code': 409, 'message': '安灯记录不存在或已响应'}), 409
    db.commit()
    return jsonify({'code': 0, 'message': '已响应'})


@site_bp.route('/api/site/andon/resolve', methods=['POST'])
@permission_required('site:write')
def andon_resolve():
    d = request.get_json(silent=True) or {}
    if not d.get('id'):
        return jsonify({'code': 400, 'message': '缺少安灯记录ID'}), 400
    db = get_db()
    cursor = db.execute("UPDATE prod_andon SET status=2, resolve_time=CURRENT_TIMESTAMP, remark=? WHERE id=? AND status=1",
                        (d.get('remark', ''), d['id']))
    if cursor.rowcount == 0:
        return jsonify({'code': 409, 'message': '安灯记录不存在、未响应或已解决'}), 409
    db.commit()
    return jsonify({'code': 0, 'message': '已解决'})


# ==================== 返工报废 ====================
@site_bp.route('/api/site/rework/list')
@login_required
def rework_list():
    db = get_db()
    try:
        page = max(1, int(request.args.get('page', 1)))
        size = min(100, max(1, int(request.args.get('size', 20))))
    except (TypeError, ValueError):
        return jsonify({'code': 400, 'message': '分页参数格式错误'}), 400
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as cnt FROM prod_quality_disposition").fetchone()['cnt']
    rows = db.execute('''SELECT d.*,w.order_no AS workorder_no,
               s.process_name,ir.result AS inspection_result,
               ir.original_filename,t.task_no AS rework_task_no,
               t.status AS rework_task_status,req.station_code
        FROM prod_quality_disposition d
        LEFT JOIN prod_workorder w ON w.id=d.workorder_id
        LEFT JOIN prod_workorder_route_step s ON s.id=d.route_step_id
        LEFT JOIN iot_inspection_report ir ON ir.id=d.inspection_report_id
        LEFT JOIN prod_task t ON t.id=d.rework_task_id
        LEFT JOIN iot_machine_request req ON req.id=d.machine_request_id
        ORDER BY d.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@site_bp.route('/api/site/rework/<int:record_id>/approve', methods=['POST'])
@permission_required('qm:process:list')
def rework_approve(record_id):
    data = request.get_json(silent=True) or {}
    try:
        result = approve_disposition(
            get_db(), record_id, data.get('action'), session.get('user_id'),
            str(data.get('reason') or '').strip(),
        )
        return jsonify({'code': 0, 'data': result})
    except ValueError as exc:
        return jsonify({'code': 409, 'message': str(exc)}), 409


@site_bp.route('/api/site/rework/<int:record_id>/reject', methods=['POST'])
@permission_required('qm:process:list')
def rework_reject(record_id):
    data = request.get_json(silent=True) or {}
    try:
        result = reject_disposition(
            get_db(), record_id, session.get('user_id'), data.get('reason'),
        )
        return jsonify({'code': 0, 'data': result})
    except ValueError as exc:
        return jsonify({'code': 409, 'message': str(exc)}), 409


@site_bp.route('/api/site/rework/<int:record_id>/start-task', methods=['POST'])
@permission_required('prod:task:list')
def rework_start_task(record_id):
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        disposition = db.execute(
            'SELECT * FROM prod_quality_disposition WHERE id=?', (record_id,)
        ).fetchone()
        if not disposition or not disposition['rework_task_id']:
            raise ValueError('处置单没有可启动的返工任务')
        validate_rework_task_start(db, disposition['rework_task_id'])
        transition_status(
            db, 'task', disposition['rework_task_id'], 1,
            session.get('user_id'), '启动质量处置返工任务',
        )
        updated = db.execute(
            '''UPDATE prod_quality_disposition SET status='task_started'
               WHERE id=? AND status='approved' ''', (record_id,),
        ).rowcount
        if updated != 1:
            raise ValueError('处置单状态已变化，不能启动返工任务')
        db.commit()
        return jsonify({'code': 0, 'message': '返工任务已启动'})
    except (ValueError, BusinessError) as exc:
        db.rollback()
        status = getattr(exc, 'status', 409)
        return jsonify({'code': status, 'message': str(exc)}), status


@site_bp.route('/api/site/rework/add', methods=['POST'])
@permission_required('site:write')
def rework_add():
    d = request.get_json(silent=True) or {}
    try:
        workorder_id = int(d.get('workorder_id'))
        quantity = float(d.get('quantity'))
    except (TypeError, ValueError):
        return jsonify({'code': 400, 'message': '工单或数量格式错误'}), 400
    if workorder_id <= 0 or quantity <= 0:
        return jsonify({'code': 400, 'message': '工单必填且数量必须大于0'}), 400
    disposition = str(d.get('disposition') or d.get('rework_type') or '').strip()
    if disposition not in ('返工', '报废'):
        return jsonify({'code': 400, 'message': '处理类型只能是返工或报废'}), 400
    reason = str(d.get('reason') or '').strip()
    if not reason:
        return jsonify({'code': 400, 'message': '原因不能为空'}), 400
    db = get_db()
    db.execute('BEGIN IMMEDIATE')
    workorder = db.execute('SELECT planned_qty FROM prod_workorder WHERE id=?', (workorder_id,)).fetchone()
    if not workorder:
        db.rollback()
        return jsonify({'code': 404, 'message': '工单不存在'}), 404
    existing = db.execute(
        'SELECT COALESCE(SUM(quantity),0) AS quantity FROM prod_rework WHERE workorder_id=?',
        (workorder_id,),
    ).fetchone()['quantity']
    if existing + quantity > workorder['planned_qty']:
        db.rollback()
        return jsonify({'code': 409, 'message': '返工/报废累计数量不能超过工单计划数量'}), 409
    cursor = db.execute('''INSERT INTO prod_rework
        (rework_no,workorder_id,quantity,reason,disposition,operator,status,remark)
        VALUES (?,?,?,?,?,?,0,?)''',
        (gen_no_in_transaction(db, 'RW'), workorder_id, quantity, reason, disposition,
         session.get('user_id'), str(d.get('remark') or '').strip()))
    db.commit()
    return jsonify({'code': 0, 'data': {'id': cursor.lastrowid}})


@site_bp.route('/api/site/rework/update', methods=['POST'])
@permission_required('site:write')
def rework_update():
    return jsonify({'code': 409, 'message': '返工/报废单提交后不能直接修改，请按流程处理'}), 409


@site_bp.route('/api/site/rework/<int:record_id>/complete', methods=['POST'])
@permission_required('site:write')
def rework_complete(record_id):
    db = get_db()
    cursor = db.execute('UPDATE prod_rework SET status=1 WHERE id=? AND status=0', (record_id,))
    if cursor.rowcount != 1:
        db.rollback()
        return jsonify({'code': 409, 'message': '记录不存在或已处理'}), 409
    db.commit()
    return jsonify({'code': 0, 'message': '处理完成'})
