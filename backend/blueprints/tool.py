"""工具管理蓝图。"""
from flask import Blueprint, jsonify, request, session

from utils.database import get_db
from utils.helpers import crud_add, crud_delete, crud_list, crud_update, gen_no_in_transaction, login_required


tool_bp = Blueprint('tool', __name__)


def _error(message, status=400, data=None):
    payload = {'code': status, 'message': message}
    if data is not None:
        payload['data'] = data
    return jsonify(payload), status


@tool_bp.route('/api/tool/type/list')
@login_required
def tool_type_list():
    return jsonify(crud_list('tool_type', request.args))


@tool_bp.route('/api/tool/type/add', methods=['POST'])
@login_required
def tool_type_add():
    return jsonify(crud_add('tool_type', request.get_json(silent=True)))


@tool_bp.route('/api/tool/ledger/list')
@login_required
def tool_ledger_list():
    db = get_db()
    rows = db.execute('''SELECT tl.*, tt.type_name,
        MAX(0, tl.quantity - COALESCE((
            SELECT SUM(tb.borrow_qty - tb.return_qty)
            FROM tool_borrow tb
            WHERE tb.tool_id=tl.id AND tb.status=0
        ), 0)) AS available_qty
        FROM tool_ledger tl
        LEFT JOIN tool_type tt ON tl.type_id=tt.id
        ORDER BY tl.id DESC''').fetchall()
    return jsonify({'code': 0, 'data': [dict(row) for row in rows]})


@tool_bp.route('/api/tool/ledger/add', methods=['POST'])
@login_required
def tool_ledger_add():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error('请求数据必须是JSON对象')
    try:
        quantity = float(data.get('quantity') or 0)
    except (TypeError, ValueError):
        return _error('工具数量必须是数字')
    if quantity < 0:
        return _error('工具数量不能小于0')
    data['quantity'] = quantity
    return jsonify(crud_add('tool_ledger', data))


@tool_bp.route('/api/tool/ledger/update', methods=['POST'])
@login_required
def tool_ledger_update():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data.get('id'):
        return _error('缺少工具ID')
    try:
        quantity = float(data.get('quantity') or 0)
    except (TypeError, ValueError):
        return _error('工具数量必须是数字')
    outstanding = get_db().execute(
        '''SELECT COALESCE(SUM(borrow_qty - return_qty), 0) AS quantity
           FROM tool_borrow WHERE tool_id=? AND status=0''',
        (data['id'],),
    ).fetchone()['quantity']
    if quantity + 1e-9 < float(outstanding):
        return _error(
            '台账数量不能小于当前未归还数量',
            409,
            {'outstanding_qty': float(outstanding)},
        )
    data['quantity'] = quantity
    return jsonify(crud_update('tool_ledger', data))


@tool_bp.route('/api/tool/ledger/delete', methods=['POST'])
@login_required
def tool_ledger_delete():
    data = request.get_json(silent=True) or {}
    tool_id = data.get('id')
    if not tool_id:
        return _error('缺少工具ID')
    active = get_db().execute(
        'SELECT 1 FROM tool_borrow WHERE tool_id=? AND status=0 LIMIT 1',
        (tool_id,),
    ).fetchone()
    if active:
        return _error('工具仍有未归还记录，不能删除', 409)
    return jsonify(crud_delete('tool_ledger', tool_id))


@tool_bp.route('/api/tool/borrow/list')
@login_required
def tool_borrow_list():
    db = get_db()
    rows = db.execute('''SELECT tb.*, tl.tool_name, tl.code as tool_code,
        u.real_name as borrower_name,
        MAX(0, tb.borrow_qty - tb.return_qty) AS outstanding_qty
        FROM tool_borrow tb
        LEFT JOIN tool_ledger tl ON tb.tool_id=tl.id
        LEFT JOIN sys_user u ON tb.borrower=u.id
        ORDER BY tb.id DESC''').fetchall()
    return jsonify({'code': 0, 'data': [dict(row) for row in rows]})


@tool_bp.route('/api/tool/borrow/add', methods=['POST'])
@login_required
def tool_borrow_add():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error('请求数据必须是JSON对象')
    try:
        tool_id = int(data.get('tool_id'))
        borrow_qty = float(data.get('borrow_qty'))
    except (TypeError, ValueError):
        return _error('工具和借用数量格式错误')
    if borrow_qty <= 0:
        return _error('借用数量必须大于0')

    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        tool = db.execute(
            '''SELECT tl.*,
                MAX(0, tl.quantity - COALESCE((
                    SELECT SUM(tb.borrow_qty - tb.return_qty)
                    FROM tool_borrow tb
                    WHERE tb.tool_id=tl.id AND tb.status=0
                ), 0)) AS available_qty
                FROM tool_ledger tl WHERE tl.id=?''',
            (tool_id,),
        ).fetchone()
        if not tool:
            db.rollback()
            return _error('工具不存在', 404)
        if tool['status'] != 1:
            db.rollback()
            return _error('工具当前已停用，不能借出', 409)
        if borrow_qty > float(tool['available_qty']) + 1e-9:
            available = float(tool['available_qty'])
            db.rollback()
            return _error(
                '可借数量不足',
                409,
                {'requested_qty': borrow_qty, 'available_qty': available},
            )
        borrow_no = gen_no_in_transaction(db, 'GJ')
        cursor = db.execute(
            '''INSERT INTO tool_borrow
               (borrow_no, tool_id, borrower, borrow_qty, return_qty, status, remark)
               VALUES (?,?,?,?,0,0,?)''',
            (borrow_no, tool_id, session.get('user_id'), borrow_qty,
             str(data.get('remark') or '').strip() or None),
        )
        db.commit()
        return jsonify({
            'code': 0,
            'message': '借用成功',
            'data': {'id': cursor.lastrowid, 'borrow_no': borrow_no},
        })
    except Exception:
        db.rollback()
        raise


@tool_bp.route('/api/tool/borrow/return', methods=['POST'])
@login_required
def tool_borrow_return():
    data = request.get_json(silent=True) or {}
    if not data.get('id'):
        return _error('缺少借用记录ID')
    try:
        return_qty = float(data.get('return_qty', 0))
    except (TypeError, ValueError):
        return _error('归还数量必须是数字')
    if return_qty <= 0:
        return _error('归还数量必须大于0')

    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        record = db.execute(
            'SELECT * FROM tool_borrow WHERE id=?',
            (data['id'],),
        ).fetchone()
        if not record:
            db.rollback()
            return _error('借用记录不存在', 404)
        if record['status'] != 0:
            db.rollback()
            return _error('该借用记录已经全部归还', 409)
        outstanding = float(record['borrow_qty']) - float(record['return_qty'])
        if return_qty > outstanding + 1e-9:
            db.rollback()
            return _error(
                '归还数量不能超过未还数量',
                409,
                {'outstanding_qty': outstanding},
            )
        new_return_qty = float(record['return_qty']) + return_qty
        completed = abs(new_return_qty - float(record['borrow_qty'])) < 1e-9
        db.execute(
            '''UPDATE tool_borrow
               SET return_qty=?, return_time=CASE WHEN ?=1 THEN CURRENT_TIMESTAMP ELSE return_time END,
                   status=? WHERE id=? AND status=0''',
            (new_return_qty, 1 if completed else 0, 1 if completed else 0, data['id']),
        )
        db.commit()
        return jsonify({
            'code': 0,
            'message': '归还成功' if completed else '部分归还成功',
            'data': {'return_qty': new_return_qty, 'outstanding_qty': max(0, outstanding - return_qty)},
        })
    except Exception:
        db.rollback()
        raise


@tool_bp.route('/api/tool/borrow/delete', methods=['POST'])
@login_required
def tool_borrow_delete():
    data = request.get_json(silent=True) or {}
    record_id = data.get('id')
    if not record_id:
        return _error('缺少借用记录ID')
    record = get_db().execute(
        'SELECT status FROM tool_borrow WHERE id=?',
        (record_id,),
    ).fetchone()
    if not record:
        return _error('借用记录不存在', 404)
    if record['status'] == 0:
        return _error('工具尚未全部归还，不能删除借用记录', 409)
    return jsonify(crud_delete('tool_borrow', record_id))
