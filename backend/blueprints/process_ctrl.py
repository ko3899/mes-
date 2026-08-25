"""制程管控蓝图 - 过站/跳站/出站/重工/关箱/拆箱/锁料/解料/返线/不良品/料号"""
from flask import Blueprint, request, jsonify, session
from utils.database import get_db
from utils.helpers import login_required, crud_list, crud_add, crud_update, crud_delete, gen_no, permission_required

process_bp = Blueprint('process', __name__)


# ==================== 站点配置 ====================
@process_bp.route('/api/process/station-config/list')
@login_required
def station_config_list():
    return jsonify(crud_list('base_station_config', request.args))


@process_bp.route('/api/process/station-config/add', methods=['POST'])
@permission_required('process:write')
def station_config_add():
    return jsonify(crud_add('base_station_config', request.json))


@process_bp.route('/api/process/station-config/update', methods=['POST'])
@permission_required('process:write')
def station_config_update():
    return jsonify(crud_update('base_station_config', request.json))


@process_bp.route('/api/process/station-config/delete', methods=['POST'])
@permission_required('process:write')
def station_config_delete():
    return jsonify(crud_delete('base_station_config', request.json.get('id')))


# ==================== 过站 ====================
@process_bp.route('/api/process/pass-station', methods=['POST'])
@permission_required('process:write')
def pass_station():
    """过站 - 产品通过当前站点（含防呆校验）"""
    d = request.json
    sn = d.get('sn', '')
    station = d.get('station', '')
    process_name = d.get('process_name', '')
    material_no = d.get('material_no', '')
    
    if not sn or not station:
        return jsonify({'code': 400, 'message': 'SN和站点必填'})
    
    db = get_db()
    errors = []
    warnings = []
    
    # 检查站点配置
    station_config = db.execute("SELECT * FROM base_station_config WHERE station=? AND status=1", (station,)).fetchone()
    if station_config:
        # 防呆1: 重复过站检查
        allow_repeat = station_config['allow_repeat']
        max_pass_count = station_config['max_pass_count']
        
        if not allow_repeat:
            existing = db.execute("SELECT COUNT(*) as c FROM prod_station_record WHERE sn=? AND station=? AND action='过站'",
                                  (sn, station)).fetchone()['c']
            if existing > 0:
                errors.append(f'防呆拦截: SN {sn} 已通过站点 {station}，禁止重复过站')
        
        if max_pass_count > 0:
            pass_count = db.execute("SELECT COUNT(*) as c FROM prod_station_record WHERE sn=? AND station=? AND action='过站'",
                                    (sn, station)).fetchone()['c']
            if pass_count >= max_pass_count:
                errors.append(f'防呆拦截: 站点 {station} 最大过站次数 {max_pass_count} 已达上限')
        
        # 防呆2: 必须扫码SN
        if station_config['required_sn'] and not sn:
            errors.append('防呆拦截: 该站点要求必须扫描SN')
        
        # 防呆3: 必须扫码物料
        if station_config['required_material'] and not material_no:
            errors.append('防呆拦截: 该站点要求必须扫描物料条码')
        
        # 防呆4: 工序校验
        if station_config['required_process']:
            required = station_config['required_process']
            if process_name != required:
                errors.append(f'防呆拦截: 该站点要求工序为 {required}，当前为 {process_name}')
        
        # 防呆5: 站点顺序校验
        if station_config['check_sequence'] and station_config['prev_station']:
            prev_station = station_config['prev_station']
            prev_record = db.execute("SELECT * FROM prod_station_record WHERE sn=? AND station=? AND action='过站' ORDER BY id DESC LIMIT 1",
                                     (sn, prev_station)).fetchone()
            if not prev_record:
                errors.append(f'防呆拦截: 必须先通过站点 {prev_station} 才能进入 {station}')
    
    # 防呆6: 物料绑定校验
    if material_no:
        material = db.execute("SELECT * FROM base_material WHERE material_no=? AND status=1", (material_no,)).fetchone()
        if not material:
            errors.append(f'防呆拦截: 物料 {material_no} 不存在或已禁用')
        else:
            # 检查物料是否被锁
            lock = db.execute("SELECT * FROM prod_material_lock WHERE material_id=? AND status=1", (material['id'],)).fetchone()
            if lock:
                errors.append(f'防呆拦截: 物料 {material_no} 已被锁定，原因: {lock["reason"]}')
    
    # 如果有错误，返回拦截信息
    if errors:
        return jsonify({'code': 400, 'message': ' | '.join(errors), 'errors': errors})
    
    # 查找或创建流转记录
    flow = db.execute("SELECT * FROM prod_station_flow WHERE sn=? ORDER BY id DESC LIMIT 1", (sn,)).fetchone()
    if not flow:
        flow_no = gen_no('SF')
        db.execute("INSERT INTO prod_station_flow (flow_no, sn, current_station, current_process, status) VALUES (?,?,?,?,0)",
                   (flow_no, sn, station, process_name))
        db.commit()
        flow = db.execute("SELECT * FROM prod_station_flow WHERE sn=? ORDER BY id DESC LIMIT 1", (sn,)).fetchone()
    
    # 记录过站
    db.execute("INSERT INTO prod_station_record (flow_id, sn, station, process_name, action, operator, result) VALUES (?,?,?,?,?,?,?)",
               (flow['id'], sn, station, process_name, '过站', session.get('user_id'), 'PASS'))
    
    # 更新流转状态
    db.execute("UPDATE prod_station_flow SET current_station=?, current_process=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
               (station, process_name, flow['id']))
    db.commit()
    
    msg = f'过站成功: {sn} -> {station}'
    if warnings:
        msg += ' (警告: ' + ', '.join(warnings) + ')'
    return jsonify({'code': 0, 'message': msg})


# ==================== 跳站 ====================
@process_bp.route('/api/process/skip-station', methods=['POST'])
@permission_required('process:write')
def skip_station():
    """跳站 - 跳过当前站点"""
    d = request.json
    sn = d.get('sn', '')
    station = d.get('station', '')
    reason = d.get('reason', '')
    
    if not sn or not station:
        return jsonify({'code': 400, 'message': 'SN和站点必填'})
    
    db = get_db()
    flow = db.execute("SELECT * FROM prod_station_flow WHERE sn=? ORDER BY id DESC LIMIT 1", (sn,)).fetchone()
    if not flow:
        return jsonify({'code': 404, 'message': '未找到流转记录'})
    
    db.execute("INSERT INTO prod_station_record (flow_id, sn, station, action, operator, result, remark) VALUES (?,?,?,?,?,?,?)",
               (flow['id'], sn, station, '跳站', session.get('user_id'), 'SKIP', reason))
    db.commit()
    
    return jsonify({'code': 0, 'message': f'跳站成功: {sn} <- {station}'})


# ==================== 出站 ====================
@process_bp.route('/api/process/exit-station', methods=['POST'])
@permission_required('process:write')
def exit_station():
    """出站 - 离开当前站点"""
    d = request.json
    sn = d.get('sn', '')
    station = d.get('station', '')
    
    if not sn or not station:
        return jsonify({'code': 400, 'message': 'SN和站点必填'})
    
    db = get_db()
    flow = db.execute("SELECT * FROM prod_station_flow WHERE sn=? ORDER BY id DESC LIMIT 1", (sn,)).fetchone()
    if not flow:
        return jsonify({'code': 404, 'message': '未找到流转记录'})
    
    db.execute("INSERT INTO prod_station_record (flow_id, sn, station, action, operator, result) VALUES (?,?,?,?,?,?)",
               (flow['id'], sn, station, '出站', session.get('user_id'), 'EXIT'))
    db.commit()
    
    return jsonify({'code': 0, 'message': f'出站成功: {sn} <- {station}'})


# ==================== 重工 ====================
@process_bp.route('/api/process/rework', methods=['POST'])
@permission_required('process:write')
def rework():
    """重工 - 产品返回指定站点重新加工"""
    d = request.json
    sn = d.get('sn', '')
    target_station = d.get('target_station', '')
    reason = d.get('reason', '')
    
    if not sn or not target_station:
        return jsonify({'code': 400, 'message': 'SN和目标站点必填'})
    
    db = get_db()
    flow = db.execute("SELECT * FROM prod_station_flow WHERE sn=? ORDER BY id DESC LIMIT 1", (sn,)).fetchone()
    if not flow:
        return jsonify({'code': 404, 'message': '未找到流转记录'})
    
    db.execute("INSERT INTO prod_station_record (flow_id, sn, station, action, operator, result, remark) VALUES (?,?,?,?,?,?,?)",
               (flow['id'], sn, target_station, '重工', session.get('user_id'), 'REWORK', reason))
    db.execute("UPDATE prod_station_flow SET current_station=?, status=0, updated_at=CURRENT_TIMESTAMP WHERE id=?",
               (target_station, flow['id']))
    db.commit()
    
    return jsonify({'code': 0, 'message': f'重工成功: {sn} -> {target_station}'})


# ==================== 关箱 ====================
@process_bp.route('/api/process/close-box', methods=['POST'])
@permission_required('process:write')
def close_box():
    """关箱 - 封装产品"""
    d = request.json
    box_no = d.get('box_no', '') or gen_no('BOX')
    sn_list = d.get('sn_list', [])
    product_id = d.get('product_id')
    
    db = get_db()
    db.execute("INSERT INTO prod_box (box_no, box_type, sn_list, product_id, quantity, status) VALUES (?,?,?,?,?,1)",
               (box_no, '关箱', ','.join(sn_list), product_id, len(sn_list)))
    db.commit()
    
    return jsonify({'code': 0, 'message': f'关箱成功: {box_no} ({len(sn_list)}个产品)'})


# ==================== 拆箱 ====================
@process_bp.route('/api/process/open-box', methods=['POST'])
@permission_required('process:write')
def open_box():
    """拆箱 - 打开已封装的产品"""
    d = request.json
    box_no = d.get('box_no', '')
    
    if not box_no:
        return jsonify({'code': 400, 'message': '箱号必填'})
    
    db = get_db()
    box = db.execute("SELECT * FROM prod_box WHERE box_no=? AND status=1", (box_no,)).fetchone()
    if not box:
        return jsonify({'code': 404, 'message': '未找到已关箱的箱号'})
    
    db.execute("UPDATE prod_box SET status=2 WHERE id=?", (box['id'],))
    db.commit()
    
    return jsonify({'code': 0, 'message': f'拆箱成功: {box_no}'})


# ==================== 锁料 ====================
@process_bp.route('/api/process/lock-material', methods=['POST'])
@permission_required('process:write')
def lock_material():
    """锁料 - 锁定物料"""
    d = request.json
    lock_no = gen_no('LK')
    d['lock_no'] = lock_no
    d['lock_type'] = '锁料'
    d['operator'] = session.get('user_id')
    
    db = get_db()
    db.execute("INSERT INTO prod_material_lock (lock_no, material_id, lock_type, reason, operator, status) VALUES (?,?,?,?,?,1)",
               (lock_no, d['material_id'], '锁料', d.get('reason', ''), d['operator']))
    db.commit()
    
    return jsonify({'code': 0, 'message': f'锁料成功: {lock_no}'})


# ==================== 解料 ====================
@process_bp.route('/api/process/unlock-material', methods=['POST'])
@permission_required('process:write')
def unlock_material():
    """解料 - 解锁物料"""
    d = request.get_json(silent=True) or {}
    lock_id = d.get('id')
    if not lock_id:
        return jsonify({'code': 400, 'message': '缺少锁料记录ID'}), 400
    
    db = get_db()
    cursor = db.execute("UPDATE prod_material_lock SET status=0, released_at=CURRENT_TIMESTAMP WHERE id=? AND status=1", (lock_id,))
    if cursor.rowcount == 0:
        return jsonify({'code': 409, 'message': '锁料记录不存在或已解锁'}), 409
    db.commit()
    
    return jsonify({'code': 0, 'message': '解料成功'})


# ==================== 返线 ====================
@process_bp.route('/api/process/return-to-line', methods=['POST'])
@permission_required('process:write')
def return_to_line():
    """返线 - 产品返回产线"""
    d = request.json
    sn = d.get('sn', '')
    station = d.get('station', '')
    
    if not sn or not station:
        return jsonify({'code': 400, 'message': 'SN和站点必填'})
    
    db = get_db()
    flow = db.execute("SELECT * FROM prod_station_flow WHERE sn=? ORDER BY id DESC LIMIT 1", (sn,)).fetchone()
    if not flow:
        return jsonify({'code': 404, 'message': '未找到流转记录'})
    
    db.execute("INSERT INTO prod_station_record (flow_id, sn, station, action, operator, result) VALUES (?,?,?,?,?,?)",
               (flow['id'], sn, station, '返线', session.get('user_id'), 'RETURN'))
    db.execute("UPDATE prod_station_flow SET current_station=?, status=0, updated_at=CURRENT_TIMESTAMP WHERE id=?",
               (station, flow['id']))
    db.commit()
    
    return jsonify({'code': 0, 'message': f'返线成功: {sn} -> {station}'})


# ==================== 不良品接收 ====================
@process_bp.route('/api/process/defect-receive', methods=['POST'])
@permission_required('process:write')
def defect_receive():
    """不良品接收"""
    d = request.json
    receive_no = gen_no('DR')
    d['receive_no'] = receive_no
    d['operator'] = session.get('user_id')
    
    db = get_db()
    db.execute("INSERT INTO prod_defect_receive (receive_no, sn, product_id, defect_id, station, quantity, process_type, operator, status) VALUES (?,?,?,?,?,?,?,?,0)",
               (receive_no, d.get('sn'), d.get('product_id'), d.get('defect_id'), d.get('station'), d.get('quantity', 1), d.get('process_type', '待处理'), d['operator']))
    db.commit()
    
    return jsonify({'code': 0, 'message': f'不良品接收成功: {receive_no}'})


# ==================== 料号维护 ====================
@process_bp.route('/api/process/material/list')
@login_required
def material_list():
    return jsonify(crud_list('base_material', request.args))


@process_bp.route('/api/process/material/add', methods=['POST'])
@permission_required('process:write')
def material_add():
    return jsonify(crud_add('base_material', request.json))


@process_bp.route('/api/process/material/update', methods=['POST'])
@permission_required('process:write')
def material_update():
    return jsonify(crud_update('base_material', request.json))


@process_bp.route('/api/process/material/delete', methods=['POST'])
@permission_required('process:write')
def material_delete():
    return jsonify(crud_delete('base_material', request.json.get('id')))


# ==================== 过站记录查询 ====================
@process_bp.route('/api/process/flow/list')
@login_required
def flow_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    keyword = request.args.get('keyword', '')
    offset = (page - 1) * size
    
    where = "WHERE 1=1"
    params = []
    if keyword:
        where += " AND (f.sn LIKE ? OR f.flow_no LIKE ?)"
        like = f'%{keyword}%'
        params.extend([like, like])
    
    total = db.execute(f"SELECT COUNT(*) as c FROM prod_station_flow f {where}", params).fetchone()['c']
    rows = db.execute(f'''SELECT f.*, p.product_name
        FROM prod_station_flow f
        LEFT JOIN base_product p ON f.product_id=p.id
        {where}
        ORDER BY f.id DESC LIMIT ? OFFSET ?''', params + [size, offset]).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@process_bp.route('/api/process/record/list')
@login_required
def record_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    keyword = request.args.get('keyword', '')
    offset = (page - 1) * size
    
    where = "WHERE 1=1"
    params = []
    if keyword:
        where += " AND (r.sn LIKE ? OR r.station LIKE ?)"
        like = f'%{keyword}%'
        params.extend([like, like])
    
    total = db.execute(f"SELECT COUNT(*) as c FROM prod_station_record r {where}", params).fetchone()['c']
    rows = db.execute(f'''SELECT r.*, u.real_name
        FROM prod_station_record r
        LEFT JOIN sys_user u ON r.operator=u.id
        {where}
        ORDER BY r.id DESC LIMIT ? OFFSET ?''', params + [size, offset]).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


@process_bp.route('/api/process/record/sn/<sn>')
@login_required
def record_by_sn(sn):
    """按SN查询过站记录"""
    db = get_db()
    rows = db.execute('''SELECT r.*, u.real_name
        FROM prod_station_record r
        LEFT JOIN sys_user u ON r.operator=u.id
        WHERE r.sn=?
        ORDER BY r.id ASC''', (sn,)).fetchall()
    return jsonify({'code': 0, 'data': [dict(r) for r in rows]})


# ==================== 箱号管理 ====================
@process_bp.route('/api/process/box/list')
@login_required
def box_list():
    return jsonify(crud_list('prod_box', request.args))


# ==================== 锁料管理 ====================
@process_bp.route('/api/process/lock/list')
@login_required
def lock_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as c FROM prod_material_lock").fetchone()['c']
    rows = db.execute('''SELECT l.*, m.material_name, m.material_no, u.real_name
        FROM prod_material_lock l
        LEFT JOIN base_material m ON l.material_id=m.id
        LEFT JOIN sys_user u ON l.operator=u.id
        ORDER BY l.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


# ==================== 不良品接收 ====================
@process_bp.route('/api/process/defect/list')
@login_required
def defect_receive_list():
    db = get_db()
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size
    total = db.execute("SELECT COUNT(*) as c FROM prod_defect_receive").fetchone()['c']
    rows = db.execute('''SELECT d.*, p.product_name, df.defect_name, u.real_name
        FROM prod_defect_receive d
        LEFT JOIN base_product p ON d.product_id=p.id
        LEFT JOIN base_defect df ON d.defect_id=df.id
        LEFT JOIN sys_user u ON d.operator=u.id
        ORDER BY d.id DESC LIMIT ? OFFSET ?''', (size, offset)).fetchall()
    return jsonify({'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total}})


# ==================== 异常处理 ====================
@process_bp.route('/api/process/exception/list')
@login_required
def exception_list():
    return jsonify(crud_list('prod_exception', request.args))


@process_bp.route('/api/process/exception/add', methods=['POST'])
@permission_required('process:write')
def exception_add():
    d = request.json
    d['exception_no'] = gen_no('EX')
    return jsonify(crud_add('prod_exception', d))


@process_bp.route('/api/process/exception/resolve', methods=['POST'])
@permission_required('process:write')
def exception_resolve():
    d = request.json
    db = get_db()
    db.execute("UPDATE prod_exception SET status=1, handler=?, resolved_at=CURRENT_TIMESTAMP WHERE id=?",
               (session.get('user_id'), d['id']))
    db.commit()
    return jsonify({'code': 0, 'message': '异常已处理'})


# ==================== 制程统计 ====================
@process_bp.route('/api/process/statistics')
@login_required
def process_statistics():
    db = get_db()
    
    # 过站统计
    total_flows = db.execute("SELECT COUNT(*) as c FROM prod_station_flow").fetchone()['c']
    active_flows = db.execute("SELECT COUNT(*) as c FROM prod_station_flow WHERE status=0").fetchone()['c']
    
    # 各站点过站次数
    station_stats = db.execute('''SELECT station, COUNT(*) as count 
        FROM prod_station_record WHERE action='过站' 
        GROUP BY station ORDER BY count DESC LIMIT 10''').fetchall()
    
    # 今日过站数
    import datetime
    today = datetime.date.today().strftime('%Y-%m-%d')
    today_pass = db.execute("SELECT COUNT(*) as c FROM prod_station_record WHERE action='过站' AND DATE(created_at)=?", (today,)).fetchone()['c']
    
    # 不良品统计
    defect_count = db.execute("SELECT COUNT(*) as c FROM prod_defect_receive WHERE status=0").fetchone()['c']
    
    # 异常统计
    exception_count = db.execute("SELECT COUNT(*) as c FROM prod_exception WHERE status=0").fetchone()['c']
    
    # 锁料统计
    lock_count = db.execute("SELECT COUNT(*) as c FROM prod_material_lock WHERE status=1").fetchone()['c']
    
    return jsonify({'code': 0, 'data': {
        'total_flows': total_flows,
        'active_flows': active_flows,
        'today_pass': today_pass,
        'station_stats': [dict(r) for r in station_stats],
        'defect_count': defect_count,
        'exception_count': exception_count,
        'lock_count': lock_count
    }})
