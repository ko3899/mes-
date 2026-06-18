"""设备管理蓝图"""
import datetime
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete, gen_no

equipment_bp = Blueprint('equipment', __name__)


@equipment_bp.route('/api/eqp/type/list')
@login_required
def eqp_type_list():
    return jsonify(crud_list('eqp_type', request.args))


@equipment_bp.route('/api/eqp/type/add', methods=['POST'])
@login_required
def eqp_type_add():
    return jsonify(crud_add('eqp_type', request.json))


@equipment_bp.route('/api/eqp/ledger/list')
@login_required
def eqp_ledger_list():
    db = get_db()
    rows = db.execute('''SELECT el.*, et.type_name, ws.workshop_name
        FROM eqp_ledger el
        LEFT JOIN eqp_type et ON el.type_id=et.id
        LEFT JOIN base_workshop ws ON el.workshop_id=ws.id
        ORDER BY el.id DESC''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@equipment_bp.route('/api/eqp/ledger/add', methods=['POST'])
@login_required
def eqp_ledger_add():
    return jsonify(crud_add('eqp_ledger', request.json))


@equipment_bp.route('/api/eqp/ledger/update', methods=['POST'])
@login_required
def eqp_ledger_update():
    return jsonify(crud_update('eqp_ledger', request.json))


@equipment_bp.route('/api/eqp/ledger/delete', methods=['POST'])
@login_required
def eqp_ledger_delete():
    return jsonify(crud_delete('eqp_ledger', request.json.get('id')))


@equipment_bp.route('/api/eqp/repair/list')
@login_required
def eqp_repair_list():
    db = get_db()
    rows = db.execute('''SELECT er.*, el.equipment_name, el.code as eqp_code,
        u1.real_name as reporter_name, u2.real_name as repairer_name
        FROM eqp_repair_order er
        LEFT JOIN eqp_ledger el ON er.equipment_id=el.id
        LEFT JOIN sys_user u1 ON er.reporter=u1.id
        LEFT JOIN sys_user u2 ON er.repairer=u2.id
        ORDER BY er.id DESC''').fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@equipment_bp.route('/api/eqp/repair/add', methods=['POST'])
@login_required
def eqp_repair_add():
    data = request.json
    data['repair_no'] = gen_no('WX')
    data['reporter'] = session.get('user_id')
    return jsonify(crud_add('eqp_repair_order', data))


@equipment_bp.route('/api/eqp/repair/update', methods=['POST'])
@login_required
def eqp_repair_update():
    return jsonify(crud_update('eqp_repair_order', request.json))


@equipment_bp.route('/api/eqp/repair/delete', methods=['POST'])
@login_required
def eqp_repair_delete():
    return jsonify(crud_delete('eqp_repair_order', request.json.get('id')))


@equipment_bp.route('/api/eqp/maintenance/list')
@login_required
def eqp_maint_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 15))
    total = db.execute("SELECT COUNT(*) as c FROM eqp_maintenance_plan").fetchone()['c']
    rows = db.execute('''SELECT m.*, e.equipment_name, e.code as eqp_code
        FROM eqp_maintenance_plan m
        LEFT JOIN eqp_ledger e ON m.equipment_id=e.id
        ORDER BY m.id DESC LIMIT ? OFFSET ?''', (size, (page-1)*size)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@equipment_bp.route('/api/eqp/maintenance/add', methods=['POST'])
@login_required
def eqp_maint_add():
    d = request.json
    db = get_db()
    db.execute("INSERT INTO eqp_maintenance_plan (plan_name,equipment_id,check_items,frequency,next_date,status) VALUES (?,?,?,?,?,?)",
               (d['plan_name'], d['equipment_id'], d.get('check_items',''), d.get('frequency',''), d.get('next_date',''), d.get('status',1)))
    db.commit()
    return jsonify({'code': 0})


@equipment_bp.route('/api/eqp/maintenance/update', methods=['POST'])
@login_required
def eqp_maint_update():
    d = request.json
    db = get_db()
    db.execute("UPDATE eqp_maintenance_plan SET plan_name=?,equipment_id=?,check_items=?,frequency=?,next_date=?,status=? WHERE id=?",
               (d['plan_name'], d['equipment_id'], d.get('check_items',''), d.get('frequency',''), d.get('next_date',''), d.get('status',1), d['id']))
    db.commit()
    return jsonify({'code': 0})


@equipment_bp.route('/api/eqp/maintenance/delete', methods=['POST'])
@login_required
def eqp_maint_delete():
    db = get_db()
    db.execute("DELETE FROM eqp_maintenance_plan WHERE id=?", (request.json['id'],))
    db.commit()
    return jsonify({'code': 0})


@equipment_bp.route('/api/eqp/maintenance/overdue')
@login_required
def eqp_maint_overdue():
    db = get_db()
    today = datetime.date.today().strftime('%Y-%m-%d')
    rows = db.execute('''SELECT m.*, e.equipment_name FROM eqp_maintenance_plan m
        JOIN eqp_ledger e ON m.equipment_id=e.id
        WHERE m.next_date < ? AND m.status=1 ORDER BY m.next_date''', (today,)).fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


@equipment_bp.route('/api/eqp/check/add', methods=['POST'])
@login_required
def eqp_check_add():
    d = request.json
    db = get_db()
    no = 'JC' + datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    db.execute("INSERT INTO eqp_check_workorder (workorder_no,plan_id,equipment_id,check_result,status,assigned_to,check_time,remark) VALUES (?,?,?,?,?,?,CURRENT_TIMESTAMP,?)",
               (no, d['plan_id'], d['equipment_id'], d.get('check_result',''), d.get('status',1), session.get('user_id'), d.get('remark','')))
    plan = db.execute("SELECT * FROM eqp_maintenance_plan WHERE id=?", (d['plan_id'],)).fetchone()
    if plan:
        freq = plan['frequency']
        today = datetime.date.today()
        if freq == '日':
            next_d = today + datetime.timedelta(days=1)
        elif freq == '周':
            next_d = today + datetime.timedelta(weeks=1)
        elif freq == '月':
            next_d = today + datetime.timedelta(days=30)
        elif freq == '季':
            next_d = today + datetime.timedelta(days=90)
        elif freq == '年':
            next_d = today + datetime.timedelta(days=365)
        else:
            next_d = today + datetime.timedelta(days=30)
        db.execute("UPDATE eqp_maintenance_plan SET next_date=? WHERE id=?", (next_d.strftime('%Y-%m-%d'), d['plan_id']))
    db.commit()
    return jsonify({'code': 0})


@equipment_bp.route('/api/eqp/check/list')
@login_required
def eqp_check_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 15))
    total = db.execute("SELECT COUNT(*) as c FROM eqp_check_workorder").fetchone()['c']
    rows = db.execute('''SELECT c.*, e.equipment_name, m.plan_name
        FROM eqp_check_workorder c
        LEFT JOIN eqp_ledger e ON c.equipment_id=e.id
        LEFT JOIN eqp_maintenance_plan m ON c.plan_id=m.id
        ORDER BY c.id DESC LIMIT ? OFFSET ?''', (size, (page-1)*size)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})
