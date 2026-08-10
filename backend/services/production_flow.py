"""Transactional rules for the order-driven MES production chain."""
from contextlib import contextmanager
from datetime import datetime
from uuid import uuid4


SALES = {'draft': 0, 'confirmed': 1, 'producing': 2, 'completed': 3, 'cancelled': 4}
PLAN = {'draft': 0, 'released': 1, 'producing': 2, 'completed': 3, 'cancelled': 4}
BATCH = {'draft': 0, 'scheduled': 1, 'producing': 2, 'completed': 3, 'cancelled': 4}
WORKORDER = {'draft': 0, 'released': 1, 'producing': 2, 'completed': 3, 'paused': 4, 'closed': 5, 'cancelled': 6}
TASK = {'pending': 0, 'running': 1, 'paused': 2, 'completed': 3}
REPORT = {'submitted': 0, 'approved': 1, 'posted': 2, 'rejected': 3}


class BusinessError(Exception):
    def __init__(self, message, status=400, details=None):
        super().__init__(message)
        self.status = status
        self.details = details


@contextmanager
def _atomic(db):
    nested = db.in_transaction
    if nested:
        db.execute('SAVEPOINT production_flow')
    else:
        db.execute('BEGIN IMMEDIATE')
    try:
        yield
        if nested:
            db.execute('RELEASE SAVEPOINT production_flow')
        else:
            db.commit()
    except Exception:
        if nested:
            db.execute('ROLLBACK TO SAVEPOINT production_flow')
            db.execute('RELEASE SAVEPOINT production_flow')
        else:
            db.rollback()
        raise


def _dict(row):
    return dict(row) if row is not None else None


def _number(prefix):
    return prefix + datetime.now().strftime('%Y%m%d%H%M%S') + uuid4().hex[:8].upper()


def _positive(value, message):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise BusinessError(message)
    if number <= 0:
        raise BusinessError(message)
    return number


def _log_status(db, entity_type, entity_id, old, new, user_id, action='', remark=''):
    db.execute(
        '''INSERT INTO sys_business_status_log
           (entity_type,entity_id,from_status,to_status,action,operator_id,remark)
           VALUES(?,?,?,?,?,?,?)''',
        (entity_type, entity_id, old, new, action, user_id, remark),
    )


def save_sales_order(db, payload, user_id):
    items = payload.get('items') or []
    if not items:
        raise BusinessError('销售订单至少需要一条产品明细')
    customer_id = payload.get('customer_id')
    customer = (payload.get('customer') or '').strip()
    if customer_id:
        row = db.execute(
            'SELECT customer_name,contact,phone FROM base_customer WHERE id=? AND status=1',
            (customer_id,),
        ).fetchone()
        if not row:
            raise BusinessError('客户不存在或未启用')
        customer = row['customer_name']
    if not customer:
        raise BusinessError('客户不能为空')
    with _atomic(db):
        order_no = payload.get('order_no') or _number('SO')
        cursor = db.execute(
            '''INSERT INTO prod_sales_order
               (order_no,customer_id,customer,contact,phone,total_amount,delivery_date,status,remark,created_by)
               VALUES(?,?,?,?,?,0,?,0,?,?)''',
            (order_no, customer_id, customer, payload.get('contact'), payload.get('phone'),
             payload.get('delivery_date'), payload.get('remark'), user_id),
        )
        order_id = cursor.lastrowid
        total = 0.0
        for item in items:
            quantity = _positive(item.get('quantity'), '产品明细数量必须大于0')
            product = db.execute('SELECT id FROM base_product WHERE id=?', (item.get('product_id'),)).fetchone()
            if not product:
                raise BusinessError('订单明细产品不存在')
            price = float(item.get('unit_price') or 0)
            if price < 0:
                raise BusinessError('产品明细单价不能小于0')
            amount = quantity * price
            total += amount
            db.execute(
                '''INSERT INTO prod_sales_order_item
                   (order_id,product_id,quantity,unit_price,amount,remark)
                   VALUES(?,?,?,?,?,?)''',
                (order_id, item['product_id'], quantity, price, amount, item.get('remark')),
            )
        db.execute('UPDATE prod_sales_order SET total_amount=? WHERE id=?', (total, order_id))
    return {'id': order_id, 'order_no': order_no, 'total_amount': total, 'items': len(items)}


def save_plan(db, payload, user_id):
    items = payload.get('items') or []
    if not items:
        raise BusinessError('生产计划至少需要一条明细')
    start_date, end_date = payload.get('start_date'), payload.get('end_date')
    if start_date and end_date and end_date < start_date:
        raise BusinessError('计划结束日期不得早于开始日期')
    sales_order_id = payload.get('sales_order_id')
    if sales_order_id and not db.execute('SELECT 1 FROM prod_sales_order WHERE id=?', (sales_order_id,)).fetchone():
        raise BusinessError('销售订单不存在')
    with _atomic(db):
        plan_no = payload.get('plan_no') or _number('PL')
        plan_id = db.execute(
            '''INSERT INTO prod_plan
               (plan_no,sales_order_id,plan_type,start_date,end_date,status,remark,created_by)
               VALUES(?,?,?,?,?,0,?,?)''',
            (plan_no, sales_order_id, payload.get('plan_type'), start_date, end_date,
             payload.get('remark'), user_id),
        ).lastrowid
        for item in items:
            quantity = _positive(item.get('planned_qty'), '计划明细数量必须大于0')
            if not db.execute('SELECT 1 FROM base_product WHERE id=?', (item.get('product_id'),)).fetchone():
                raise BusinessError('计划明细产品不存在')
            if not db.execute('SELECT 1 FROM base_workshop WHERE id=? AND status=1', (item.get('workshop_id'),)).fetchone():
                raise BusinessError('计划明细车间不存在或未启用')
            db.execute(
                '''INSERT INTO prod_plan_item
                   (plan_id,sales_order_item_id,product_id,planned_qty,workshop_id,remark)
                   VALUES(?,?,?,?,?,?)''',
                (plan_id, item.get('sales_order_item_id'), item['product_id'], quantity,
                 item['workshop_id'], item.get('remark')),
            )
    return {'id': plan_id, 'plan_no': plan_no, 'items': len(items)}


def save_batch(db, payload, user_id):
    quantity = _positive(payload.get('planned_qty'), '生产批次数量必须大于0')
    plan_item = db.execute(
        '''SELECT i.*,p.sales_order_id FROM prod_plan_item i
           JOIN prod_plan p ON p.id=i.plan_id WHERE i.id=?''',
        (payload.get('plan_item_id'),),
    ).fetchone()
    if not plan_item:
        raise BusinessError('生产计划明细不存在')
    with _atomic(db):
        used = db.execute(
            'SELECT COALESCE(SUM(planned_qty),0) FROM prod_batch WHERE plan_item_id=? AND status<>4',
            (plan_item['id'],),
        ).fetchone()[0]
        if used + quantity > float(plan_item['planned_qty']):
            raise BusinessError('生产批次数量超过计划明细剩余数量')
        batch_no = payload.get('batch_no') or _number('PB')
        batch_id = db.execute(
            '''INSERT INTO prod_batch
               (batch_no,plan_id,plan_item_id,sales_order_id,product_id,workshop_id,
                planned_qty,start_date,end_date,status,remark,created_by)
               VALUES(?,?,?,?,?,?,?,?,?,0,?,?)''',
            (batch_no, plan_item['plan_id'], plan_item['id'], plan_item['sales_order_id'],
             plan_item['product_id'], plan_item['workshop_id'], quantity,
             payload.get('start_date'), payload.get('end_date'), payload.get('remark'), user_id),
        ).lastrowid
    return {'id': batch_id, 'batch_no': batch_no, 'planned_qty': quantity}


def save_workorder(db, payload, user_id):
    quantity = _positive(payload.get('planned_qty'), '工单计划数量必须大于0')
    product_id, workshop_id = payload.get('product_id'), payload.get('workshop_id')
    batch_id = payload.get('production_batch_id')
    plan_id, plan_item_id, sales_order_id = payload.get('plan_id'), payload.get('plan_item_id'), payload.get('sales_order_id')
    if batch_id:
        batch = db.execute('SELECT * FROM prod_batch WHERE id=? AND status<>4', (batch_id,)).fetchone()
        if not batch:
            raise BusinessError('生产批次不存在或已取消')
        product_id, workshop_id = batch['product_id'], batch['workshop_id']
        plan_id, plan_item_id, sales_order_id = batch['plan_id'], batch['plan_item_id'], batch['sales_order_id']
        if quantity > float(batch['planned_qty']):
            raise BusinessError('工单数量超过生产批次数量')
    route = db.execute(
        '''SELECT * FROM base_process_route
           WHERE id=? AND product_id=? AND status=1
             AND (workshop_id=? OR workshop_id IS NULL)''',
        (payload.get('route_id'), product_id, workshop_id),
    ).fetchone()
    if not route:
        raise BusinessError('工艺路线与产品或车间不匹配')
    with _atomic(db):
        order_no = payload.get('order_no') or _number('WO')
        workorder_id = db.execute(
            '''INSERT INTO prod_workorder
               (order_no,plan_id,plan_item_id,sales_order_id,production_batch_id,
                product_id,route_id,planned_qty,workshop_id,priority,status,start_date,end_date,remark,created_by)
               VALUES(?,?,?,?,?,?,?,?,?,?,0,?,?,?,?)''',
            (order_no, plan_id, plan_item_id, sales_order_id, batch_id, product_id,
             route['id'], quantity, workshop_id, payload.get('priority') or 1,
             payload.get('start_date'), payload.get('end_date'), payload.get('remark'), user_id),
        ).lastrowid
    return {'id': workorder_id, 'order_no': order_no}


def release_workorder(db, workorder_id, user_id, remark=''):
    workorder = db.execute('SELECT * FROM prod_workorder WHERE id=?', (workorder_id,)).fetchone()
    if not workorder:
        raise BusinessError('工单不存在', 404)
    existing = db.execute(
        'SELECT id FROM prod_workorder_route_snapshot WHERE workorder_id=?', (workorder_id,)
    ).fetchone()
    if existing:
        return _snapshot_result(db, workorder_id)
    if workorder['status'] != WORKORDER['draft']:
        raise BusinessError('只有草稿工单可以下达')
    if not workorder['route_id'] or not workorder['workshop_id']:
        raise BusinessError('工单必须补全车间和工艺路线后才能下达')
    route = db.execute(
        '''SELECT * FROM base_process_route WHERE id=? AND product_id=? AND status=1
           AND (workshop_id=? OR workshop_id IS NULL)''',
        (workorder['route_id'], workorder['product_id'], workorder['workshop_id']),
    ).fetchone()
    if not route:
        raise BusinessError('工单工艺路线与产品或车间不匹配')
    steps = db.execute(
        '''SELECT d.*,p.process_name,p.code AS process_code,
                  COALESCE(d.workshop_id,p.workshop_id) AS actual_workshop_id,
                  COALESCE(d.standard_time,p.standard_time) AS actual_standard_time
           FROM base_process_route_detail d JOIN base_process p ON p.id=d.process_id
           WHERE d.route_id=? AND p.status=1 ORDER BY d.step_no''',
        (route['id'],),
    ).fetchall()
    if not steps:
        raise BusinessError('工艺路线没有可执行步骤')
    for step in steps:
        if not step['actual_workshop_id']:
            raise BusinessError('路线步骤存在未分配车间的工序')
    bom = db.execute(
        '''SELECT b.*,p.product_name AS material_name,p.code AS material_code
           FROM base_bom b JOIN base_product p ON p.id=b.material_id
           WHERE b.product_id=? ORDER BY b.id''', (workorder['product_id'],)
    ).fetchall()
    if not bom:
        raise BusinessError('工单产品没有BOM，不能下达')
    with _atomic(db):
        snapshot_id = db.execute(
            '''INSERT INTO prod_workorder_route_snapshot
               (workorder_id,source_route_id,route_name,route_version,product_id,workshop_id,description)
               VALUES(?,?,?,?,?,?,?)''',
            (workorder_id, route['id'], route['route_name'], route['version'] or 1,
             workorder['product_id'], workorder['workshop_id'], route['description']),
        ).lastrowid
        for step in steps:
            db.execute(
                '''INSERT INTO prod_workorder_route_step
                   (snapshot_id,source_detail_id,process_id,process_code,process_name,workshop_id,
                    step_no,standard_time,is_inspection_point,description)
                   VALUES(?,?,?,?,?,?,?,?,?,?)''',
                (snapshot_id, step['id'], step['process_id'], step['process_code'],
                 step['process_name'], step['actual_workshop_id'], step['step_no'],
                 step['actual_standard_time'], step['is_inspection_point'] or 0, step['description']),
            )
        bom_version = datetime.now().strftime('%Y%m%d%H%M%S')
        for item in bom:
            db.execute(
                '''INSERT INTO prod_workorder_bom_snapshot
                   (workorder_id,source_bom_id,material_id,material_code,material_name,
                    quantity_per_unit,required_qty,unit,bom_version)
                   VALUES(?,?,?,?,?,?,?,?,?)''',
                (workorder_id, item['id'], item['material_id'], item['material_code'],
                 item['material_name'], item['quantity'], item['quantity'] * workorder['planned_qty'],
                 item['unit'], bom_version),
            )
        db.execute(
            '''UPDATE prod_workorder SET status=?,route_version=?,bom_version=?,updated_at=CURRENT_TIMESTAMP
               WHERE id=?''', (WORKORDER['released'], route['version'] or 1, bom_version, workorder_id)
        )
        _log_status(db, 'workorder', workorder_id, WORKORDER['draft'], WORKORDER['released'],
                    user_id, 'release', remark)
    return {'id': workorder_id, 'route_steps': len(steps), 'bom_items': len(bom)}


def _snapshot_result(db, workorder_id):
    route_steps = db.execute(
        '''SELECT COUNT(*) FROM prod_workorder_route_step s
           JOIN prod_workorder_route_snapshot h ON h.id=s.snapshot_id WHERE h.workorder_id=?''',
        (workorder_id,),
    ).fetchone()[0]
    bom_items = db.execute(
        'SELECT COUNT(*) FROM prod_workorder_bom_snapshot WHERE workorder_id=?', (workorder_id,)
    ).fetchone()[0]
    return {'id': workorder_id, 'route_steps': route_steps, 'bom_items': bom_items}


def generate_tasks(db, workorder_id, user_id):
    workorder = db.execute('SELECT * FROM prod_workorder WHERE id=?', (workorder_id,)).fetchone()
    if not workorder:
        raise BusinessError('工单不存在', 404)
    steps = db.execute(
        '''SELECT s.* FROM prod_workorder_route_step s
           JOIN prod_workorder_route_snapshot h ON h.id=s.snapshot_id
           WHERE h.workorder_id=? ORDER BY s.step_no''', (workorder_id,)
    ).fetchall()
    if not steps:
        raise BusinessError('工单尚未冻结工艺路线')
    with _atomic(db):
        for step in steps:
            exists = db.execute('SELECT 1 FROM prod_task WHERE route_step_id=?', (step['id'],)).fetchone()
            if not exists:
                db.execute(
                    '''INSERT INTO prod_task
                       (task_no,workorder_id,process_id,route_step_id,planned_qty,status,remark)
                       VALUES(?,?,?,?,?,0,?)''',
                    (_number('TK'), workorder_id, step['process_id'], step['id'],
                     workorder['planned_qty'], workorder['remark']),
                )
    return [_dict(row) for row in db.execute(
        'SELECT * FROM prod_task WHERE workorder_id=? ORDER BY route_step_id', (workorder_id,)
    ).fetchall()]


def generate_material_requirements(db, workorder_id, user_id):
    snapshots = db.execute(
        'SELECT * FROM prod_workorder_bom_snapshot WHERE workorder_id=? ORDER BY id',
        (workorder_id,),
    ).fetchall()
    if not snapshots:
        raise BusinessError('工单尚未冻结BOM')
    workorder = db.execute('SELECT production_batch_id,remark FROM prod_workorder WHERE id=?', (workorder_id,)).fetchone()
    with _atomic(db):
        for item in snapshots:
            exists = db.execute('SELECT 1 FROM prod_material_req WHERE bom_snapshot_id=?', (item['id'],)).fetchone()
            if not exists:
                db.execute(
                    '''INSERT INTO prod_material_req
                       (req_no,production_batch_id,workorder_id,bom_snapshot_id,product_id,quantity,
                        required_qty,req_type,status,operator,remark)
                       VALUES(?,?,?,?,?,?,?,?,0,?,?)''',
                    (_number('MR'), workorder['production_batch_id'], workorder_id, item['id'],
                     item['material_id'], item['required_qty'], item['required_qty'], '领料',
                     user_id, workorder['remark']),
                )
    return [_dict(row) for row in db.execute(
        'SELECT * FROM prod_material_req WHERE workorder_id=? ORDER BY id', (workorder_id,)
    ).fetchall()]


def request_material(db, request_id, quantity, user_id):
    quantity = _positive(quantity, '申请数量必须大于0')
    with _atomic(db):
        row = db.execute('SELECT * FROM prod_material_req WHERE id=?', (request_id,)).fetchone()
        if not row:
            raise BusinessError('领料需求不存在', 404)
        remaining = float(row['required_qty']) - float(row['requested_qty'] or 0)
        if quantity > remaining:
            raise BusinessError('申请数量超过剩余需求数量')
        db.execute(
            '''UPDATE prod_material_req SET requested_qty=requested_qty+?,status=1,operator=?
               WHERE id=?''', (quantity, user_id, request_id)
        )
    return _dict(db.execute('SELECT * FROM prod_material_req WHERE id=?', (request_id,)).fetchone())


def issue_material(db, request_id, quantity, warehouse_id, location_id, batch_no, user_id):
    quantity = _positive(quantity, '发料数量必须大于0')
    with _atomic(db):
        request_row = db.execute('SELECT * FROM prod_material_req WHERE id=?', (request_id,)).fetchone()
        if not request_row:
            raise BusinessError('领料需求不存在', 404)
        remaining = float(request_row['requested_qty'] or request_row['required_qty']) - float(request_row['issued_qty'] or 0)
        if quantity > remaining:
            raise BusinessError('发料数量超过待发数量')
        balance = db.execute('SELECT * FROM inv_balance WHERE product_id=?', (request_row['product_id'],)).fetchone()
        available = float(balance['quantity']) if balance else 0
        if quantity > available:
            raise BusinessError('库存不足', 409, {
                'required_qty': quantity, 'available_qty': available,
                'shortage_qty': quantity - available,
            })
        new_balance = available - quantity
        db.execute('UPDATE inv_balance SET quantity=?,updated_at=CURRENT_TIMESTAMP WHERE product_id=?',
                   (new_balance, request_row['product_id']))
        db.execute(
            '''UPDATE prod_material_req SET issued_qty=issued_qty+?,warehouse_id=?,location_id=?,
               material_batch_no=?,issued_by=?,issued_at=CURRENT_TIMESTAMP,status=2 WHERE id=?''',
            (quantity, warehouse_id, location_id, batch_no, user_id, request_id),
        )
        db.execute(
            '''INSERT INTO inv_transaction
               (product_id,trans_type,quantity,balance,ref_no,remark)
               VALUES(?,?,?,?,?,?)''',
            (request_row['product_id'], '生产发料', -quantity, new_balance,
             request_row['req_no'], request_row['remark']),
        )
    return _dict(db.execute('SELECT * FROM prod_material_req WHERE id=?', (request_id,)).fetchone())


def receive_material(db, request_id, quantity, user_id):
    quantity = _positive(quantity, '收料数量必须大于0')
    with _atomic(db):
        row = db.execute('SELECT * FROM prod_material_req WHERE id=?', (request_id,)).fetchone()
        if not row:
            raise BusinessError('领料需求不存在', 404)
        remaining = float(row['issued_qty'] or 0) - float(row['received_qty'] or 0)
        if quantity > remaining:
            raise BusinessError('收料数量超过待收数量')
        db.execute(
            '''UPDATE prod_material_req SET received_qty=received_qty+?,received_by=?,
               received_at=CURRENT_TIMESTAMP,status=3 WHERE id=?''',
            (quantity, user_id, request_id),
        )
    return _dict(db.execute('SELECT * FROM prod_material_req WHERE id=?', (request_id,)).fetchone())


def return_material(db, request_id, quantity, user_id):
    quantity = _positive(quantity, '退料数量必须大于0')
    with _atomic(db):
        row = db.execute('SELECT * FROM prod_material_req WHERE id=?', (request_id,)).fetchone()
        if not row:
            raise BusinessError('领料需求不存在', 404)
        returnable = float(row['received_qty'] or 0) - float(row['returned_qty'] or 0)
        if quantity > returnable:
            raise BusinessError('退料数量超过可退数量')
        balance = db.execute('SELECT * FROM inv_balance WHERE product_id=?', (row['product_id'],)).fetchone()
        current = float(balance['quantity']) if balance else 0
        new_balance = current + quantity
        if balance:
            db.execute('UPDATE inv_balance SET quantity=?,updated_at=CURRENT_TIMESTAMP WHERE product_id=?',
                       (new_balance, row['product_id']))
        else:
            db.execute('INSERT INTO inv_balance(product_id,quantity) VALUES(?,?)', (row['product_id'], new_balance))
        db.execute('UPDATE prod_material_req SET returned_qty=returned_qty+? WHERE id=?', (quantity, request_id))
        db.execute(
            '''INSERT INTO inv_transaction(product_id,trans_type,quantity,balance,ref_no,remark)
               VALUES(?,?,?,?,?,?)''',
            (row['product_id'], '生产退料', quantity, new_balance, row['req_no'], row['remark']),
        )
    return _dict(db.execute('SELECT * FROM prod_material_req WHERE id=?', (request_id,)).fetchone())


def post_report(db, report_id, user_id, remark=''):
    report = db.execute('SELECT * FROM prod_report WHERE id=?', (report_id,)).fetchone()
    if not report:
        raise BusinessError('报工记录不存在', 404)
    if report['approval_status'] not in (REPORT['submitted'], REPORT['approved']):
        raise BusinessError('当前报工状态不能记账')
    total = float(report['qualified_qty']) + float(report['defect_qty'] or 0)
    task = db.execute('SELECT * FROM prod_task WHERE id=?', (report['task_id'],)).fetchone()
    if not task or float(task['completed_qty'] or 0) + float(task['defect_qty'] or 0) + total > float(task['planned_qty']):
        raise BusinessError('报工数量超过任务剩余数量')
    with _atomic(db):
        db.execute(
            '''UPDATE prod_task SET completed_qty=completed_qty+?,defect_qty=defect_qty+?,
               status=CASE WHEN completed_qty+defect_qty+?>=planned_qty THEN 3 ELSE 1 END WHERE id=?''',
            (report['qualified_qty'], report['defect_qty'] or 0, total, task['id']),
        )
        db.execute(
            '''UPDATE prod_workorder SET completed_qty=completed_qty+?,defect_qty=defect_qty+?,
               status=CASE WHEN status=1 THEN 2 ELSE status END,updated_at=CURRENT_TIMESTAMP WHERE id=?''',
            (report['qualified_qty'], report['defect_qty'] or 0, report['workorder_id']),
        )
        db.execute('UPDATE prod_report SET approval_status=2,posted_at=CURRENT_TIMESTAMP WHERE id=?', (report_id,))
        _log_status(db, 'report', report_id, report['approval_status'], REPORT['posted'], user_id, 'post', remark)
    return _dict(db.execute('SELECT * FROM prod_report WHERE id=?', (report_id,)).fetchone())


def task_availability(db, task_id):
    task = db.execute(
        '''SELECT t.*,s.step_no,s.id AS snapshot_step_id,h.workorder_id AS snapshot_workorder_id
           FROM prod_task t
           JOIN prod_workorder_route_step s ON s.id=t.route_step_id
           JOIN prod_workorder_route_snapshot h ON h.id=s.snapshot_id
           WHERE t.id=?''', (task_id,)
    ).fetchone()
    if not task:
        raise BusinessError('任务不存在或未关联冻结路线', 404)
    if task['step_no'] == 1:
        upstream = float(task['planned_qty'])
    else:
        upstream = float(db.execute(
            '''SELECT COALESCE(SUM(quantity),0) FROM prod_transfer
               WHERE workorder_id=? AND to_route_step_id=? AND status=1''',
            (task['workorder_id'], task['snapshot_step_id']),
        ).fetchone()[0])
    posted = float(task['completed_qty'] or 0) + float(task['defect_qty'] or 0)
    return {
        'task_id': task_id, 'planned_qty': float(task['planned_qty']),
        'upstream_qty': upstream, 'posted_qty': posted,
        'available_qty': max(0, upstream - posted),
    }


def create_transfer(db, payload, user_id):
    quantity = _positive(payload.get('quantity'), '转移数量必须大于0')
    workorder_id = payload.get('workorder_id')
    with _atomic(db):
        steps = db.execute(
            '''SELECT s.* FROM prod_workorder_route_step s
               JOIN prod_workorder_route_snapshot h ON h.id=s.snapshot_id
               WHERE h.workorder_id=? AND s.process_id IN (?,?) ORDER BY s.step_no''',
            (workorder_id, payload.get('from_process_id'), payload.get('to_process_id')),
        ).fetchall()
        by_process = {row['process_id']: row for row in steps}
        source = by_process.get(int(payload.get('from_process_id') or 0))
        target = by_process.get(int(payload.get('to_process_id') or 0))
        if not source or not target:
            raise BusinessError('来源或目标工序不属于工单冻结路线')
        if target['step_no'] != source['step_no'] + 1:
            raise BusinessError('工序转移只允许相邻路线步骤')
        qualified = float(db.execute(
            '''SELECT COALESCE(SUM(r.qualified_qty),0) FROM prod_report r
               JOIN prod_task t ON t.id=r.task_id
               WHERE r.workorder_id=? AND t.route_step_id=? AND r.approval_status=2''',
            (workorder_id, source['id']),
        ).fetchone()[0])
        transferred = float(db.execute(
            '''SELECT COALESCE(SUM(quantity),0) FROM prod_transfer
               WHERE workorder_id=? AND from_route_step_id=? AND status=1''',
            (workorder_id, source['id']),
        ).fetchone()[0])
        available = max(0, qualified - transferred)
        if quantity > available:
            raise BusinessError(f'可转移数量为 {available:g}', 409,
                                {'available_qty': available})
        transfer_no = _number('TR')
        transfer_id = db.execute(
            '''INSERT INTO prod_transfer
               (transfer_no,workorder_id,from_process_id,to_process_id,from_route_step_id,
                to_route_step_id,quantity,status,operator,remark)
               VALUES(?,?,?,?,?,?,?,1,?,?)''',
            (transfer_no, workorder_id, source['process_id'], target['process_id'],
             source['id'], target['id'], quantity, user_id, payload.get('remark')),
        ).lastrowid
    return {'id': transfer_id, 'transfer_no': transfer_no, 'quantity': quantity}


_TRANSITIONS = {
    'sales': ({0: {1, 4}, 1: {2, 4}, 2: {3}}, 'prod_sales_order'),
    'plan': ({0: {1, 4}, 1: {2, 4}, 2: {3}}, 'prod_plan'),
    'batch': ({0: {1, 4}, 1: {2, 4}, 2: {3}}, 'prod_batch'),
    'workorder': ({0: {1, 6}, 1: {2, 4, 6}, 2: {3, 4}, 4: {2, 6}, 3: {5}}, 'prod_workorder'),
    'task': ({0: {1}, 1: {2, 3}, 2: {1, 3}}, 'prod_task'),
    'report': ({0: {1, 3}, 1: {2}}, 'prod_report'),
}


def transition_status(db, entity_type, entity_id, target_status, user_id, remark=''):
    config = _TRANSITIONS.get(entity_type)
    if not config:
        raise BusinessError('不支持的业务类型')
    graph, table = config
    status_column = 'approval_status' if entity_type == 'report' else 'status'
    row = db.execute(f'SELECT {status_column} AS status FROM {table} WHERE id=?', (entity_id,)).fetchone()
    if not row:
        raise BusinessError('业务记录不存在', 404)
    old = row['status']
    target_status = int(target_status)
    if target_status not in graph.get(old, set()):
        raise BusinessError(f'不允许从状态 {old} 变更为 {target_status}')
    with _atomic(db):
        db.execute(f'UPDATE {table} SET {status_column}=? WHERE id=?', (target_status, entity_id))
        _log_status(db, entity_type, entity_id, old, target_status, user_id, 'transition', remark)
    return {'id': entity_id, 'from_status': old, 'status': target_status}
