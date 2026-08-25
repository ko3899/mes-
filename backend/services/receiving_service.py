"""采购收料闭环领域服务。

实现 到货登记 → 收料过账 → 库存累计 → 采购单状态联动 的完整事务链。

数据表契约（由 backend/utils/database.py 初始化）：
- inv_arrival_notice / inv_arrival_notice_item ：到货通知单与明细
- inv_receipt_posting ：收料过账记录（posting_no 唯一，operator_id+client_operation_id 幂等）
- inv_stock_balance ：库存余额（product_id+warehouse_id+area_id+location_id+batch_no 唯一，同库位批次累加）
- scm_purchase_order / scm_purchase_order_item ：采购单与明细（posted_qty/arrived_qty 联动）
- scm_procurement_status_log ：采购状态日志（复用 procurement_flow 的日志格式）

所有写操作都在单一事务内完成：收料过账 + 库存累计 + 采购单状态更新，
任一步失败整体回滚；重复过账通过 client_operation_id / posting_no 幂等保护。
"""
from contextlib import contextmanager
from datetime import datetime
import math
from uuid import uuid4

from services.procurement_flow import BusinessError, PURCHASE


# 收料过账允许的采购单状态：已审核 / 部分到货 / 全部到货
_RECEIVABLE_STATUSES = (
    PURCHASE['approved'],
    PURCHASE['partial_arrival'],
    PURCHASE['fully_arrived'],
)


@contextmanager
def _atomic(db):
    """事务上下文：支持嵌套（SAVEPOINT），与 procurement_flow 语义一致。"""
    nested = db.in_transaction
    if nested:
        db.execute('SAVEPOINT receiving_service')
    else:
        db.execute('BEGIN IMMEDIATE')
    try:
        yield
        if nested:
            db.execute('RELEASE SAVEPOINT receiving_service')
        else:
            db.commit()
    except Exception:
        if nested:
            db.execute('ROLLBACK TO SAVEPOINT receiving_service')
            db.execute('RELEASE SAVEPOINT receiving_service')
        else:
            db.rollback()
        raise


def _number(prefix):
    return prefix + datetime.now().strftime('%Y%m%d%H%M%S') + uuid4().hex[:8].upper()


def _finite_quantity(value, message):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise BusinessError(message)
    if not math.isfinite(number) or number <= 0:
        raise BusinessError(message)
    return number


def _log_status(db, order_id, old_status, new_status, action, user_id, reason=None):
    db.execute(
        '''INSERT INTO scm_procurement_status_log
           (entity_type,entity_id,from_status,to_status,action,operator_id,reason)
           VALUES('purchase_order',?,?,?,?,?,?)''',
        (order_id, old_status, new_status, action, user_id, reason),
    )


def _order(db, order_id):
    row = db.execute(
        'SELECT id,order_no,status FROM scm_purchase_order WHERE id=?',
        (order_id,),
    ).fetchone()
    if row is None:
        raise BusinessError('采购订单不存在', 404)
    return row


def _require_warehouse(db, warehouse_id, area_id, location_id):
    """校验仓库/库区/库位存在且层级归属正确。"""
    warehouse = db.execute(
        'SELECT id FROM inv_warehouse WHERE id=? AND status=1', (warehouse_id,),
    ).fetchone()
    if warehouse is None:
        raise BusinessError('仓库不存在或未启用')
    area = db.execute(
        'SELECT id,warehouse_id FROM inv_area WHERE id=? AND status=1', (area_id,),
    ).fetchone()
    if area is None:
        raise BusinessError('库区不存在或未启用')
    if area['warehouse_id'] != warehouse_id:
        raise BusinessError('库区不属于所选仓库')
    location = db.execute(
        'SELECT id,area_id FROM inv_location WHERE id=? AND status=1', (location_id,),
    ).fetchone()
    if location is None:
        raise BusinessError('库位不存在或未启用')
    if location['area_id'] != area_id:
        raise BusinessError('库位不属于所选库区')


def notice_detail(db, notice_id):
    """到货通知详情（含明细与供应商/采购单信息）。"""
    row = db.execute(
        '''SELECT a.*, s.supplier_name, po.order_no
           FROM inv_arrival_notice a
           LEFT JOIN base_supplier s ON s.id=a.supplier_id
           LEFT JOIN scm_purchase_order po ON po.id=a.purchase_order_id
           WHERE a.id=?''',
        (notice_id,),
    ).fetchone()
    items = db.execute(
        '''SELECT i.*, p.product_name, p.code AS product_code
           FROM inv_arrival_notice_item i
           LEFT JOIN base_product p ON p.id=i.product_id
           WHERE i.notice_id=? ORDER BY i.id''',
        (notice_id,),
    ).fetchall()
    result = dict(row)
    result['items'] = [dict(item) for item in items]
    return result


def register_arrival(db, payload, user_id):
    """到货登记：生成 inv_arrival_notice（含明细），并累计采购明细 arrived_qty。

    校验采购单必须处于 已审核/部分到货/全部到货 状态；
    同一采购明细的累计到货数量允许超收，超出部分记入 excess_qty。
    """
    if not isinstance(payload, dict):
        raise BusinessError('请求数据必须是JSON对象')
    order_id = payload.get('purchase_order_id')
    items = payload.get('items')
    if not order_id:
        raise BusinessError('必须指定采购订单')
    if not isinstance(items, list) or not items:
        raise BusinessError('到货登记至少需要一条明细')

    with _atomic(db):
        current = _order(db, order_id)
        if current['status'] not in _RECEIVABLE_STATUSES:
            raise BusinessError('只有已审核或到货中的采购订单可以登记到货', 409)

        normalized_items = []
        seen_purchase_item_ids = set()
        for index, raw in enumerate(items, 1):
            if not isinstance(raw, dict):
                raise BusinessError(f'第{index}条到货明细格式错误')
            purchase_item_id = raw.get('purchase_order_item_id')
            order_item = db.execute(
                '''SELECT id,product_id,ordered_qty,arrived_qty
                   FROM scm_purchase_order_item WHERE id=? AND order_id=?''',
                (purchase_item_id, order_id),
            ).fetchone()
            if order_item is None:
                raise BusinessError(f'第{index}条明细关联的采购明细不存在')
            if purchase_item_id in seen_purchase_item_ids:
                raise BusinessError(f'第{index}条明细重复关联同一采购明细')
            seen_purchase_item_ids.add(purchase_item_id)
            quantity = _finite_quantity(raw.get('quantity'), f'第{index}条到货数量必须为大于0的有限数值')
            product_id = raw.get('product_id')
            if int(product_id) != int(order_item['product_id']):
                raise BusinessError(f'第{index}条明细物料与采购明细不一致')
            normalized_items.append((order_item, quantity))

        notice_no = _number('AR')
        cursor = db.execute(
            '''INSERT INTO inv_arrival_notice
               (notice_no, purchase_order_id, supplier_id, status,
                expected_date, delivery_note_no, remark, created_by)
               VALUES (?,?,?,0,?,?,?,?)''',
            (
                notice_no,
                order_id,
                payload.get('supplier_id') or db.execute(
                    'SELECT supplier_id FROM scm_purchase_order WHERE id=?', (order_id,)
                ).fetchone()['supplier_id'],
                payload.get('expected_date'),
                str(payload.get('delivery_note_no') or '').strip() or None,
                str(payload.get('remark') or '').strip() or None,
                user_id,
            ),
        )
        notice_id = cursor.lastrowid

        for order_item, quantity in normalized_items:
            remaining = float(order_item['ordered_qty']) - float(order_item['arrived_qty'] or 0)
            normal_qty = min(quantity, max(0.0, remaining))
            excess_qty = round(quantity - normal_qty, 6)
            db.execute(
                '''INSERT INTO inv_arrival_notice_item
                   (notice_id, product_id, quantity, purchase_order_item_id,
                    arrived_qty, normal_qty, excess_qty, accepted_qty,
                    returned_qty, pending_qty, inspection_mode, created_at)
                   VALUES (?,?,?,?,?,?,?,0,0,?,?,CURRENT_TIMESTAMP)''',
                (
                    notice_id,
                    order_item['product_id'],
                    quantity,
                    order_item['id'],
                    quantity,
                    round(normal_qty, 6),
                    excess_qty,
                    round(normal_qty, 6),
                    str(payload.get('inspection_mode') or '').strip() or None,
                ),
            )
            db.execute(
                '''UPDATE scm_purchase_order_item
                   SET arrived_qty=?
                   WHERE id=?''',
                (round(float(order_item['arrived_qty'] or 0) + quantity, 6), order_item['id']),
            )

    return notice_detail(db, notice_id)


def post_receipt(db, payload, user_id):
    """收料过账：写入 inv_receipt_posting → upsert 库存余额 → 推进采购单状态。

    幂等：若提供 client_operation_id 且 (operator_id, client_operation_id) 已存在，
    直接返回既有过账记录；posting_no 唯一约束兜底并发重复。
    """
    if not isinstance(payload, dict):
        raise BusinessError('请求数据必须是JSON对象')
    arrival_item_id = payload.get('arrival_item_id')
    if not arrival_item_id:
        raise BusinessError('必须指定到货明细')
    quantity = _finite_quantity(payload.get('quantity'), '收料数量必须为大于0的有限数值')
    batch_no = str(payload.get('batch_no') or '').strip()
    if not batch_no:
        raise BusinessError('批次号不能为空')
    client_operation_id = str(payload.get('client_operation_id') or '').strip() or None

    with _atomic(db):
        # 幂等保护：同一操作员 + 客户端操作ID 的重复提交直接返回
        if client_operation_id:
            existing = db.execute(
                '''SELECT id FROM inv_receipt_posting
                   WHERE operator_id=? AND client_operation_id=?''',
                (user_id, client_operation_id),
            ).fetchone()
            if existing is not None:
                return _posting_result(db, existing['id'])

        arrival_item = db.execute(
            '''SELECT i.*, n.purchase_order_id, n.supplier_id
               FROM inv_arrival_notice_item i
               JOIN inv_arrival_notice n ON n.id=i.notice_id
               WHERE i.id=?''',
            (arrival_item_id,),
        ).fetchone()
        if arrival_item is None:
            raise BusinessError('到货明细不存在', 404)

        pending_qty = float(arrival_item['pending_qty'] or 0)
        if pending_qty + 1e-9 < quantity:
            raise BusinessError('收料数量超过该到货明细待收数量', 409)

        order = _order(db, arrival_item['purchase_order_id'])
        if order['status'] not in _RECEIVABLE_STATUSES:
            raise BusinessError('采购单当前状态不允许收料过账', 409)

        inspection_id = payload.get('inspection_id')
        if inspection_id:
            inspection = db.execute(
                'SELECT id FROM qm_incoming_inspection WHERE id=?', (inspection_id,),
            ).fetchone()
            if inspection is None:
                raise BusinessError('关联的来料检验记录不存在')

        warehouse_id = payload.get('warehouse_id')
        area_id = payload.get('area_id')
        location_id = payload.get('location_id')
        if not warehouse_id or not area_id or not location_id:
            raise BusinessError('收料必须指定仓库、库区与库位')
        _require_warehouse(db, warehouse_id, area_id, location_id)

        posting_no = _number('RP')
        cursor = db.execute(
            '''INSERT INTO inv_receipt_posting
               (posting_no, arrival_item_id, inspection_id, product_id,
                warehouse_id, area_id, location_id, batch_no, quantity,
                operator_id, client_operation_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (
                posting_no,
                arrival_item_id,
                inspection_id,
                arrival_item['product_id'],
                warehouse_id,
                area_id,
                location_id,
                batch_no,
                quantity,
                user_id,
                client_operation_id,
            ),
        )
        posting_id = cursor.lastrowid

        # 库存累计：同库位批次 upsert 累加
        balance = db.execute(
            '''SELECT id, quantity FROM inv_stock_balance
               WHERE product_id=? AND warehouse_id=? AND area_id=?
                 AND location_id=? AND batch_no=?''',
            (arrival_item['product_id'], warehouse_id, area_id, location_id, batch_no),
        ).fetchone()
        if balance:
            db.execute(
                '''UPDATE inv_stock_balance
                   SET quantity=?, updated_at=CURRENT_TIMESTAMP
                   WHERE id=?''',
                (round(float(balance['quantity']) + quantity, 6), balance['id']),
            )
        else:
            db.execute(
                '''INSERT INTO inv_stock_balance
                   (product_id, warehouse_id, area_id, location_id, batch_no, quantity)
                   VALUES (?,?,?,?,?,?)''',
                (arrival_item['product_id'], warehouse_id, area_id, location_id,
                 batch_no, quantity),
            )

        # 到货明细待收/实收更新
        db.execute(
            '''UPDATE inv_arrival_notice_item
               SET pending_qty=?, accepted_qty=?
               WHERE id=?''',
            (
                round(pending_qty - quantity, 6),
                round(float(arrival_item['accepted_qty'] or 0) + quantity, 6),
                arrival_item_id,
            ),
        )

        # 采购明细过账数量累计（以 scm_purchase_order_item 当前值为基准）
        order_item_row = db.execute(
            'SELECT posted_qty, accepted_qty FROM scm_purchase_order_item WHERE id=?',
            (arrival_item['purchase_order_item_id'],),
        ).fetchone()
        db.execute(
            '''UPDATE scm_purchase_order_item
               SET posted_qty=?, accepted_qty=?
               WHERE id=?''',
            (
                round(float(order_item_row['posted_qty'] or 0) + quantity, 6),
                round(float(order_item_row['accepted_qty'] or 0) + quantity, 6),
                arrival_item['purchase_order_item_id'],
            ),
        )

        _advance_order_status(
            db,
            arrival_item['purchase_order_id'],
            order['status'],
            user_id,
            reason=f'收料过账 {posting_no}',
        )

    return _posting_result(db, posting_id)


def _advance_order_status(db, order_id, current_status, user_id, reason=None):
    """按已过账数量推进采购单状态：全部明细过账完成 → 全部到货，否则 → 部分到货。"""
    rows = db.execute(
        '''SELECT ordered_qty, posted_qty FROM scm_purchase_order_item
           WHERE order_id=?''',
        (order_id,),
    ).fetchall()
    if not rows:
        return
    all_complete = all(
        float(row['posted_qty'] or 0) + 1e-9 >= float(row['ordered_qty'])
        for row in rows
    )
    target = PURCHASE['fully_arrived'] if all_complete else PURCHASE['partial_arrival']
    if current_status == target:
        return
    if current_status == PURCHASE['fully_arrived']:
        return
    cursor = db.execute(
        '''UPDATE scm_purchase_order SET status=?, updated_at=CURRENT_TIMESTAMP
           WHERE id=? AND status=?''',
        (target, order_id, current_status),
    )
    if cursor.rowcount == 1:
        _log_status(db, order_id, current_status, target, 'receipt', user_id, reason)


def _posting_result(db, posting_id):
    row = db.execute(
        '''SELECT r.*, p.product_name, p.code AS product_code,
                  w.warehouse_name, a.area_name, l.location_name, po.order_no
           FROM inv_receipt_posting r
           LEFT JOIN base_product p ON p.id=r.product_id
           LEFT JOIN inv_warehouse w ON w.id=r.warehouse_id
           LEFT JOIN inv_area a ON a.id=r.area_id
           LEFT JOIN inv_location l ON l.id=r.location_id
           LEFT JOIN inv_arrival_notice_item ai ON ai.id=r.arrival_item_id
           LEFT JOIN inv_arrival_notice n ON n.id=ai.notice_id
           LEFT JOIN scm_purchase_order po ON po.id=n.purchase_order_id
           WHERE r.id=?''',
        (posting_id,),
    ).fetchone()
    if row is None:
        raise BusinessError('收料过账记录不存在', 404)
    return dict(row)


def arrival_list(db, page=1, size=20, keyword='', status=None):
    """到货通知分页列表（含明细数量汇总）。"""
    page = max(1, int(page))
    size = min(500, max(1, int(size)))
    where = ' WHERE 1=1'
    params = []
    if keyword:
        like = f'%{keyword}%'
        where += ''' AND (a.notice_no LIKE ? OR a.delivery_note_no LIKE ?
            OR s.supplier_name LIKE ? OR po.order_no LIKE ?)'''
        params.extend([like, like, like, like])
    if status not in (None, ''):
        where += ' AND a.status=?'
        params.append(status)
    total = db.execute(
        '''SELECT COUNT(*) AS cnt FROM inv_arrival_notice a
           LEFT JOIN base_supplier s ON s.id=a.supplier_id
           LEFT JOIN scm_purchase_order po ON po.id=a.purchase_order_id''' + where,
        params,
    ).fetchone()['cnt']
    rows = db.execute(
        '''SELECT a.*, s.supplier_name, po.order_no,
                  (SELECT COUNT(*) FROM inv_arrival_notice_item i
                   WHERE i.notice_id=a.id) AS item_count
           FROM inv_arrival_notice a
           LEFT JOIN base_supplier s ON s.id=a.supplier_id
           LEFT JOIN scm_purchase_order po ON po.id=a.purchase_order_id''' + where
        + ' ORDER BY a.id DESC LIMIT ? OFFSET ?',
        params + [size, (page - 1) * size],
    ).fetchall()
    return {
        'list': [dict(row) for row in rows],
        'total': total,
        'page': page,
        'size': size,
    }


def receipt_list(db, page=1, size=20, keyword='', purchase_order_id=None):
    """收料过账分页列表。"""
    page = max(1, int(page))
    size = min(500, max(1, int(size)))
    where = ' WHERE 1=1'
    params = []
    if keyword:
        like = f'%{keyword}%'
        where += ''' AND (r.posting_no LIKE ? OR r.batch_no LIKE ?
            OR p.product_name LIKE ? OR po.order_no LIKE ?)'''
        params.extend([like, like, like, like])
    if purchase_order_id not in (None, ''):
        where += ' AND n.purchase_order_id=?'
        params.append(purchase_order_id)
    total = db.execute(
        '''SELECT COUNT(*) AS cnt FROM inv_receipt_posting r
           LEFT JOIN inv_arrival_notice_item ai ON ai.id=r.arrival_item_id
           LEFT JOIN inv_arrival_notice n ON n.id=ai.notice_id
           LEFT JOIN scm_purchase_order po ON po.id=n.purchase_order_id
           LEFT JOIN base_product p ON p.id=r.product_id''' + where,
        params,
    ).fetchone()['cnt']
    rows = db.execute(
        '''SELECT r.*, p.product_name, p.code AS product_code,
                  w.warehouse_name, a.area_name, l.location_name, po.order_no
           FROM inv_receipt_posting r
           LEFT JOIN inv_arrival_notice_item ai ON ai.id=r.arrival_item_id
           LEFT JOIN inv_arrival_notice n ON n.id=ai.notice_id
           LEFT JOIN scm_purchase_order po ON po.id=n.purchase_order_id
           LEFT JOIN base_product p ON p.id=r.product_id
           LEFT JOIN inv_warehouse w ON w.id=r.warehouse_id
           LEFT JOIN inv_area a ON a.id=r.area_id
           LEFT JOIN inv_location l ON l.id=r.location_id''' + where
        + ' ORDER BY r.id DESC LIMIT ? OFFSET ?',
        params + [size, (page - 1) * size],
    ).fetchall()
    return {
        'list': [dict(row) for row in rows],
        'total': total,
        'page': page,
        'size': size,
    }


def order_receipt_summary(db, order_id):
    """采购单收料进度汇总：供前端查看到货/过账/待收状态。"""
    order = _order(db, order_id)
    order_item_rows = db.execute(
        '''SELECT i.*, p.product_name, p.code AS product_code
           FROM scm_purchase_order_item i
           LEFT JOIN base_product p ON p.id=i.product_id
           WHERE i.order_id=? ORDER BY i.id''',
        (order_id,),
    ).fetchall()
    items = []
    for row in order_item_rows:
        item = dict(row)
        remaining = float(row['ordered_qty']) - float(row['posted_qty'] or 0)
        item['pending_qty'] = round(max(0.0, remaining), 6)
        items.append(item)
    arrivals = db.execute(
        '''SELECT COUNT(*) AS cnt FROM inv_arrival_notice
           WHERE purchase_order_id=?''',
        (order_id,),
    ).fetchone()['cnt']
    postings = db.execute(
        '''SELECT COUNT(*) AS cnt FROM inv_receipt_posting r
           JOIN inv_arrival_notice_item ai ON ai.id=r.arrival_item_id
           JOIN inv_arrival_notice n ON n.id=ai.notice_id
           WHERE n.purchase_order_id=?''',
        (order_id,),
    ).fetchone()['cnt']
    return {
        'order': dict(order),
        'items': items,
        'arrival_count': arrivals,
        'receipt_posting_count': postings,
    }
