"""Transactional purchase-order rules for the controlled receiving workflow."""
from contextlib import contextmanager
from datetime import datetime
import math
from uuid import uuid4


PURCHASE = {
    'draft': 0,
    'submitted': 1,
    'approved': 2,
    'partial_arrival': 3,
    'fully_arrived': 4,
    'closed': 5,
    'rejected': 6,
    'cancelled': 7,
}


class BusinessError(Exception):
    def __init__(self, message, status=400, details=None):
        super().__init__(message)
        self.status = status
        self.details = details


@contextmanager
def _atomic(db):
    nested = db.in_transaction
    if nested:
        db.execute('SAVEPOINT procurement_flow')
    else:
        db.execute('BEGIN IMMEDIATE')
    try:
        yield
        if nested:
            db.execute('RELEASE SAVEPOINT procurement_flow')
        else:
            db.commit()
    except Exception:
        if nested:
            db.execute('ROLLBACK TO SAVEPOINT procurement_flow')
            db.execute('RELEASE SAVEPOINT procurement_flow')
        else:
            db.rollback()
        raise


def _number():
    return 'PO' + datetime.now().strftime('%Y%m%d%H%M%S') + uuid4().hex[:8].upper()


def _finite_number(value, message, positive=False, nonnegative=False):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise BusinessError(message)
    if not math.isfinite(number):
        raise BusinessError(message)
    if positive and number <= 0:
        raise BusinessError(message)
    if nonnegative and number < 0:
        raise BusinessError(message)
    return number


def _required_reason(reason, message):
    normalized = (reason or '').strip()
    if not normalized:
        raise BusinessError(message)
    return normalized


def _order(db, order_id):
    row = db.execute(
        'SELECT id,order_no,status FROM scm_purchase_order WHERE id=?',
        (order_id,),
    ).fetchone()
    if row is None:
        raise BusinessError('采购订单不存在', 404)
    return row


def _log_status(db, order_id, old_status, new_status, action, user_id, reason=None):
    db.execute(
        '''INSERT INTO scm_procurement_status_log
           (entity_type,entity_id,from_status,to_status,action,operator_id,reason)
           VALUES('purchase_order',?,?,?,?,?,?)''',
        (order_id, old_status, new_status, action, user_id, reason),
    )


def _result(db, order_id):
    row = db.execute(
        'SELECT id,order_no,status FROM scm_purchase_order WHERE id=?',
        (order_id,),
    ).fetchone()
    return {'id': row['id'], 'order_no': row['order_no'], 'status': row['status']}


def save_purchase_order(db, payload, user_id):
    items = payload.get('items') or []
    if not items:
        raise BusinessError('采购订单至少需要一条物料明细')

    with _atomic(db):
        supplier_id = payload.get('supplier_id')
        supplier = db.execute(
            'SELECT id FROM base_supplier WHERE id=? AND status=1',
            (supplier_id,),
        ).fetchone()
        if supplier is None:
            raise BusinessError('供应商不存在或未启用')

        normalized_items = []
        for item in items:
            quantity = _finite_number(
                item.get('ordered_qty'),
                '采购数量必须为大于0的有限数值',
                positive=True,
            )
            product_id = item.get('product_id')
            product = db.execute(
                'SELECT id FROM base_product WHERE id=? AND status=1',
                (product_id,),
            ).fetchone()
            if product is None:
                raise BusinessError('采购明细物料不存在或未启用')
            price = _finite_number(
                item.get('unit_price') or 0,
                '采购单价必须为非负有限数值',
                nonnegative=True,
            )
            tax_rate = _finite_number(
                item.get('tax_rate') or 0,
                '税率必须为非负有限数值',
                nonnegative=True,
            )
            normalized_items.append((product_id, quantity, price, tax_rate))

        order_id = payload.get('id')
        if order_id:
            current = _order(db, order_id)
            if current['status'] not in (PURCHASE['draft'], PURCHASE['rejected']):
                raise BusinessError('只有草稿或驳回的采购订单可以编辑', 409)
            cursor = db.execute(
                '''UPDATE scm_purchase_order
                   SET supplier_id=?,expected_date=?,currency=?,remark=?,updated_at=CURRENT_TIMESTAMP
                   WHERE id=? AND status IN (?,?)''',
                (
                    supplier_id,
                    payload.get('expected_date'),
                    payload.get('currency'),
                    payload.get('remark'),
                    order_id,
                    PURCHASE['draft'],
                    PURCHASE['rejected'],
                ),
            )
            if cursor.rowcount != 1:
                raise BusinessError('采购订单状态已变化，请刷新后重试', 409)
            db.execute('DELETE FROM scm_purchase_order_item WHERE order_id=?', (order_id,))
            status = current['status']
            order_no = current['order_no']
        else:
            order_no = _number()
            cursor = db.execute(
                '''INSERT INTO scm_purchase_order
                   (order_no,supplier_id,status,expected_date,currency,remark,created_by)
                   VALUES(?,?,0,?,?,?,?)''',
                (
                    order_no,
                    supplier_id,
                    payload.get('expected_date'),
                    payload.get('currency'),
                    payload.get('remark'),
                    user_id,
                ),
            )
            order_id = cursor.lastrowid
            status = PURCHASE['draft']

        for product_id, quantity, price, tax_rate in normalized_items:
            db.execute(
                '''INSERT INTO scm_purchase_order_item
                   (order_id,product_id,ordered_qty,unit_price,tax_rate)
                   VALUES(?,?,?,?,?)''',
                (order_id, product_id, quantity, price, tax_rate),
            )

        if status == PURCHASE['draft'] and not payload.get('id'):
            _log_status(
                db, order_id, None, PURCHASE['draft'], 'create', user_id
            )

    result = _result(db, order_id)
    result['items'] = len(normalized_items)
    return result


def submit_purchase_order(db, order_id, user_id):
    with _atomic(db):
        current = _order(db, order_id)
        allowed = (PURCHASE['draft'], PURCHASE['rejected'])
        if current['status'] not in allowed:
            raise BusinessError('只有草稿或驳回的采购订单可以提交审核', 409)
        cursor = db.execute(
            '''UPDATE scm_purchase_order
               SET status=?,submitted_by=?,submitted_at=CURRENT_TIMESTAMP,
                   rejected_reason=NULL,updated_at=CURRENT_TIMESTAMP
               WHERE id=? AND status IN (?,?)''',
            (PURCHASE['submitted'], user_id, order_id) + allowed,
        )
        if cursor.rowcount != 1:
            raise BusinessError('采购订单状态已变化，请刷新后重试', 409)
        _log_status(
            db, order_id, current['status'], PURCHASE['submitted'], 'submit', user_id
        )
    return _result(db, order_id)


def review_purchase_order(db, order_id, approved, user_id, reason=''):
    rejected_reason = None
    if not approved:
        rejected_reason = _required_reason(reason, '驳回原因不能为空')
    target = PURCHASE['approved'] if approved else PURCHASE['rejected']
    action = 'approve' if approved else 'reject'

    with _atomic(db):
        current = _order(db, order_id)
        if current['status'] != PURCHASE['submitted']:
            raise BusinessError('只有待审核的采购订单可以审核', 409)
        if approved:
            cursor = db.execute(
                '''UPDATE scm_purchase_order
                   SET status=?,approved_by=?,approved_at=CURRENT_TIMESTAMP,
                       rejected_reason=NULL,updated_at=CURRENT_TIMESTAMP
                   WHERE id=? AND status=?''',
                (target, user_id, order_id, PURCHASE['submitted']),
            )
        else:
            cursor = db.execute(
                '''UPDATE scm_purchase_order
                   SET status=?,approved_by=NULL,approved_at=NULL,rejected_reason=?,
                       updated_at=CURRENT_TIMESTAMP
                   WHERE id=? AND status=?''',
                (target, rejected_reason, order_id, PURCHASE['submitted']),
            )
        if cursor.rowcount != 1:
            raise BusinessError('采购订单状态已变化，请刷新后重试', 409)
        _log_status(
            db,
            order_id,
            current['status'],
            target,
            action,
            user_id,
            rejected_reason,
        )
    return _result(db, order_id)


def cancel_purchase_order(db, order_id, user_id, reason):
    normalized_reason = _required_reason(reason, '取消原因不能为空')
    allowed = (
        PURCHASE['draft'],
        PURCHASE['submitted'],
        PURCHASE['approved'],
        PURCHASE['rejected'],
    )
    with _atomic(db):
        current = _order(db, order_id)
        if current['status'] not in allowed:
            raise BusinessError('当前状态的采购订单不能取消', 409)
        arrival = db.execute(
            'SELECT 1 FROM inv_arrival_notice WHERE purchase_order_id=? LIMIT 1',
            (order_id,),
        ).fetchone()
        if arrival is not None:
            raise BusinessError('采购订单已发生到货，不能取消，只能关闭', 409)
        placeholders = ','.join('?' for _ in allowed)
        cursor = db.execute(
            '''UPDATE scm_purchase_order SET status=?,updated_at=CURRENT_TIMESTAMP
               WHERE id=? AND status IN (%s)''' % placeholders,
            (PURCHASE['cancelled'], order_id) + allowed,
        )
        if cursor.rowcount != 1:
            raise BusinessError('采购订单状态已变化，请刷新后重试', 409)
        _log_status(
            db,
            order_id,
            current['status'],
            PURCHASE['cancelled'],
            'cancel',
            user_id,
            normalized_reason,
        )
    return _result(db, order_id)


def close_purchase_order(db, order_id, user_id, reason):
    normalized_reason = _required_reason(reason, '关闭原因不能为空')
    allowed = (
        PURCHASE['approved'],
        PURCHASE['partial_arrival'],
        PURCHASE['fully_arrived'],
    )
    with _atomic(db):
        current = _order(db, order_id)
        if current['status'] not in allowed:
            raise BusinessError('只有已审核或到货中的采购订单可以关闭', 409)
        placeholders = ','.join('?' for _ in allowed)
        cursor = db.execute(
            '''UPDATE scm_purchase_order
               SET status=?,closed_reason=?,updated_at=CURRENT_TIMESTAMP
               WHERE id=? AND status IN (%s)''' % placeholders,
            (PURCHASE['closed'], normalized_reason, order_id) + allowed,
        )
        if cursor.rowcount != 1:
            raise BusinessError('采购订单状态已变化，请刷新后重试', 409)
        _log_status(
            db,
            order_id,
            current['status'],
            PURCHASE['closed'],
            'close',
            user_id,
            normalized_reason,
        )
    return _result(db, order_id)
