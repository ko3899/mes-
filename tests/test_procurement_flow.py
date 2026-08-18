import os
import sqlite3
import sys

import pytest


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from utils import database  # noqa: E402
from services.procurement_flow import (  # noqa: E402
    BusinessError,
    PURCHASE,
    cancel_purchase_order,
    close_purchase_order,
    review_purchase_order,
    save_purchase_order,
    submit_purchase_order,
)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / 'procurement-flow.db'
    monkeypatch.setattr(database, 'DB_PATH', str(path))
    database.init_db()
    database._init_extra_tables()
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    yield connection
    connection.close()


@pytest.fixture()
def references(db):
    supplier_id = db.execute(
        "INSERT INTO base_supplier(supplier_name,code) VALUES('状态机测试供应商','PO-FLOW-SUP')"
    ).lastrowid
    product_ids = [
        db.execute(
            'INSERT INTO base_product(product_name,code) VALUES(?,?)',
            ('状态机测试物料%d' % index, 'PO-FLOW-P%d' % index),
        ).lastrowid
        for index in (1, 2)
    ]
    db.commit()
    return supplier_id, product_ids


def _payload(references, quantities=(10,)):
    supplier_id, product_ids = references
    return {
        'supplier_id': supplier_id,
        'expected_date': '2026-08-30',
        'currency': 'CNY',
        'remark': '采购状态机测试',
        'items': [
            {
                'product_id': product_ids[index],
                'ordered_qty': quantity,
                'unit_price': 12.5 + index,
                'tax_rate': 13,
            }
            for index, quantity in enumerate(quantities)
        ],
    }


def _create_order(db, references, user_id=7, quantities=(10,)):
    return save_purchase_order(db, _payload(references, quantities), user_id)


def _status_log(db, order_id):
    return [dict(row) for row in db.execute(
        '''SELECT from_status,to_status,action,operator_id,reason
           FROM scm_procurement_status_log
           WHERE entity_type='purchase_order' AND entity_id=? ORDER BY id''',
        (order_id,),
    )]


def test_business_error_exposes_http_status_and_details():
    error = BusinessError('冲突', 409, {'field': 'status'})
    assert str(error) == '冲突'
    assert error.status == 409
    assert error.details == {'field': 'status'}


@pytest.mark.parametrize('items', [[], None])
def test_purchase_order_requires_at_least_one_line(db, references, items):
    payload = _payload(references)
    payload['items'] = items
    with pytest.raises(BusinessError, match='至少需要一条'):
        save_purchase_order(db, payload, 7)
    assert db.execute('SELECT COUNT(*) FROM scm_purchase_order').fetchone()[0] == 0


def test_purchase_order_requires_an_enabled_supplier(db, references):
    payload = _payload(references)
    payload['supplier_id'] = 999999
    with pytest.raises(BusinessError, match='供应商'):
        save_purchase_order(db, payload, 7)


@pytest.mark.parametrize('quantity', [0, -1, float('nan'), float('inf'), 'not-a-number'])
def test_purchase_quantity_must_be_positive_and_finite(db, references, quantity):
    payload = _payload(references)
    payload['items'][0]['ordered_qty'] = quantity
    with pytest.raises(BusinessError, match='采购数量必须为大于0的有限数值'):
        save_purchase_order(db, payload, 7)
    assert db.execute('SELECT COUNT(*) FROM scm_purchase_order').fetchone()[0] == 0


def test_new_order_uses_server_number_and_begin_immediate(db, references):
    payload = _payload(references)
    payload['order_no'] = 'CLIENT-CONTROLLED'
    statements = []
    db.set_trace_callback(statements.append)
    result = save_purchase_order(db, payload, 7)
    db.set_trace_callback(None)

    assert result['order_no'].startswith('PO')
    assert result['order_no'] != 'CLIENT-CONTROLLED'
    assert result['status'] == PURCHASE['draft']
    assert any(statement.upper().startswith('BEGIN IMMEDIATE') for statement in statements)
    row = db.execute(
        'SELECT supplier_id,status,created_by FROM scm_purchase_order WHERE id=?',
        (result['id'],),
    ).fetchone()
    assert tuple(row) == (references[0], PURCHASE['draft'], 7)
    assert _status_log(db, result['id']) == [{
        'from_status': None,
        'to_status': str(PURCHASE['draft']),
        'action': 'create',
        'operator_id': 7,
        'reason': None,
    }]


def test_draft_save_replaces_lines_atomically(db, references):
    order = _create_order(db, references)
    replacement = _payload(references, (4, 6))
    replacement['id'] = order['id']
    result = save_purchase_order(db, replacement, 8)

    assert result['id'] == order['id']
    assert result['items'] == 2
    lines = db.execute(
        'SELECT product_id,ordered_qty FROM scm_purchase_order_item WHERE order_id=? ORDER BY id',
        (order['id'],),
    ).fetchall()
    assert [(row['product_id'], row['ordered_qty']) for row in lines] == [
        (references[1][0], 4),
        (references[1][1], 6),
    ]


def test_submitted_order_cannot_be_edited_and_original_lines_remain(db, references):
    order = _create_order(db, references)
    submit_purchase_order(db, order['id'], 7)
    payload = _payload(references, (4, 6))
    payload['id'] = order['id']
    with pytest.raises(BusinessError, match='草稿或驳回'):
        save_purchase_order(db, payload, 8)
    assert db.execute(
        'SELECT ordered_qty FROM scm_purchase_order_item WHERE order_id=?',
        (order['id'],),
    ).fetchone()[0] == 10


def test_submit_only_allows_draft_or_rejected_and_writes_audit_log(db, references):
    order = _create_order(db, references)
    result = submit_purchase_order(db, order['id'], 8)
    assert result['status'] == PURCHASE['submitted']
    row = db.execute(
        'SELECT status,submitted_by,submitted_at FROM scm_purchase_order WHERE id=?',
        (order['id'],),
    ).fetchone()
    assert row['status'] == PURCHASE['submitted']
    assert row['submitted_by'] == 8
    assert row['submitted_at'] is not None
    assert _status_log(db, order['id'])[-1]['action'] == 'submit'

    with pytest.raises(BusinessError, match='草稿或驳回'):
        submit_purchase_order(db, order['id'], 8)
    assert len(_status_log(db, order['id'])) == 2


def test_only_submitted_order_can_be_reviewed(db, references):
    order = _create_order(db, references)
    with pytest.raises(BusinessError, match='待审核'):
        review_purchase_order(db, order['id'], True, 9)
    assert _status_log(db, order['id'])[-1]['action'] == 'create'


def test_rejection_requires_reason_and_can_be_edited_then_resubmitted(db, references):
    order = _create_order(db, references)
    submit_purchase_order(db, order['id'], 7)
    with pytest.raises(BusinessError, match='驳回原因'):
        review_purchase_order(db, order['id'], False, 9, '  ')

    rejected = review_purchase_order(db, order['id'], False, 9, '价格需复核')
    assert rejected['status'] == PURCHASE['rejected']
    payload = _payload(references, (8, 2))
    payload['id'] = order['id']
    assert save_purchase_order(db, payload, 7)['status'] == PURCHASE['rejected']
    assert submit_purchase_order(db, order['id'], 7)['status'] == PURCHASE['submitted']
    assert review_purchase_order(db, order['id'], True, 9)['status'] == PURCHASE['approved']

    row = db.execute(
        'SELECT approved_by,approved_at,rejected_reason FROM scm_purchase_order WHERE id=?',
        (order['id'],),
    ).fetchone()
    assert row['approved_by'] == 9
    assert row['approved_at'] is not None
    assert row['rejected_reason'] is None


def test_missing_order_returns_not_found(db):
    with pytest.raises(BusinessError) as caught:
        submit_purchase_order(db, 999999, 1)
    assert caught.value.status == 404


def test_cancellation_requires_reason_and_is_audited(db, references):
    order = _create_order(db, references)
    with pytest.raises(BusinessError, match='取消原因'):
        cancel_purchase_order(db, order['id'], 9, '')
    result = cancel_purchase_order(db, order['id'], 9, '需求取消')
    assert result['status'] == PURCHASE['cancelled']
    assert _status_log(db, order['id'])[-1] == {
        'from_status': str(PURCHASE['draft']),
        'to_status': str(PURCHASE['cancelled']),
        'action': 'cancel',
        'operator_id': 9,
        'reason': '需求取消',
    }


def test_order_with_arrival_record_cannot_be_cancelled(db, references):
    order = _create_order(db, references)
    db.execute(
        '''INSERT INTO inv_arrival_notice
           (notice_no,purchase_order_id,supplier_id,status,created_by)
           VALUES('ARR-CANCEL-GUARD',?,?,0,7)''',
        (order['id'], references[0]),
    )
    db.commit()
    with pytest.raises(BusinessError, match='已发生到货'):
        cancel_purchase_order(db, order['id'], 9, '测试取消')
    assert db.execute(
        'SELECT status FROM scm_purchase_order WHERE id=?', (order['id'],)
    ).fetchone()[0] == PURCHASE['draft']


@pytest.mark.parametrize('status', [
    PURCHASE['approved'], PURCHASE['partial_arrival'], PURCHASE['fully_arrived'],
])
def test_approved_or_arriving_order_can_be_closed_with_reason(db, references, status):
    order = _create_order(db, references)
    db.execute('UPDATE scm_purchase_order SET status=? WHERE id=?', (status, order['id']))
    db.commit()
    with pytest.raises(BusinessError, match='关闭原因'):
        close_purchase_order(db, order['id'], 10, ' ')
    result = close_purchase_order(db, order['id'], 10, '不再采购剩余数量')
    assert result['status'] == PURCHASE['closed']
    assert db.execute(
        'SELECT closed_reason FROM scm_purchase_order WHERE id=?', (order['id'],)
    ).fetchone()[0] == '不再采购剩余数量'


def test_draft_order_cannot_be_closed(db, references):
    order = _create_order(db, references)
    with pytest.raises(BusinessError, match='已审核或到货'):
        close_purchase_order(db, order['id'], 10, '无效关闭')
