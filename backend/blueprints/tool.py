"""工具管理蓝图"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete, gen_no

tool_bp = Blueprint('tool', __name__)


@tool_bp.route('/api/tool/type/list')
@login_required
def tool_type_list():
    return jsonify(crud_list('tool_type', request.args))


@tool_bp.route('/api/tool/type/add', methods=['POST'])
@login_required
def tool_type_add():
    return jsonify(crud_add('tool_type', request.json))


@tool_bp.route('/api/tool/ledger/list')
@login_required
def tool_ledger_list():
    db = get_db()
    rows = db.execute('''SELECT tl.*, tt.type_name
        FROM tool_ledger tl
        LEFT JOIN tool_type tt ON tl.type_id=tt.id
        ORDER BY tl.id DESC''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@tool_bp.route('/api/tool/ledger/add', methods=['POST'])
@login_required
def tool_ledger_add():
    return jsonify(crud_add('tool_ledger', request.json))


@tool_bp.route('/api/tool/ledger/update', methods=['POST'])
@login_required
def tool_ledger_update():
    return jsonify(crud_update('tool_ledger', request.json))


@tool_bp.route('/api/tool/ledger/delete', methods=['POST'])
@login_required
def tool_ledger_delete():
    return jsonify(crud_delete('tool_ledger', request.json.get('id')))


@tool_bp.route('/api/tool/borrow/list')
@login_required
def tool_borrow_list():
    db = get_db()
    rows = db.execute('''SELECT tb.*, tl.tool_name, tl.code as tool_code,
        u.real_name as borrower_name
        FROM tool_borrow tb
        LEFT JOIN tool_ledger tl ON tb.tool_id=tl.id
        LEFT JOIN sys_user u ON tb.borrower=u.id
        ORDER BY tb.id DESC''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@tool_bp.route('/api/tool/borrow/add', methods=['POST'])
@login_required
def tool_borrow_add():
    data = request.json
    data['borrow_no'] = gen_no('GJ')
    data['borrower'] = session.get('user_id')
    return jsonify(crud_add('tool_borrow', data))


@tool_bp.route('/api/tool/borrow/return', methods=['POST'])
@login_required
def tool_borrow_return():
    data = request.json
    db = get_db()
    db.execute("UPDATE tool_borrow SET return_qty=?, return_time=CURRENT_TIMESTAMP, status=1 WHERE id=?",
               (data.get('return_qty', 0), data.get('id')))
    db.commit()
    return jsonify({'code': 0, 'message': '归还成功'})


@tool_bp.route('/api/tool/borrow/delete', methods=['POST'])
@login_required
def tool_borrow_delete():
    return jsonify(crud_delete('tool_borrow', request.json.get('id')))
