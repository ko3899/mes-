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
    review_purchase_order,
    save_purchase_order,
    submit_purchase_order,
)
from services.receiving_service import (  # noqa: E402
    post_receipt,
    register_arrival,
)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / 'receiving-flow.db'
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
        "INSERT INTO base_supplier(supplier_name,code) VALUES('收料测试供应商','RCV-SUP')"
    ).lastrowid
    product_ids = [
        db.execute(
            'INSERT INTO base_product(product_name,code) VALUES(?,?)',
            ('收料测试物料%d' % index, 'RCV-P%d' % index),
        ).lastrowid
        for index in (1, 2)
    ]
    warehouse_id = db.execute(
        "INSERT INTO inv_warehouse(warehouse_name,code) VALUES('原料仓','WH-RCV')"
    ).lastrowid
    area_id = db.execute(
        "INSERT INTO inv_area(warehouse_id,area_name,code) VALUES(?,?,?)",
        (warehouse_id, '原料区', 'AR-RCV'),
    ).lastrowid
    location_id = db.execute(
        "INSERT INTO inv_location(area_id,location_name,code) VALUES(?,?,?)",
        (area_id, 'A1-01', 'LOC-RCV'),
    ).lastrowid
    db.commit()
    return {
        'supplier_id': supplier_id,
        'product_ids': product_ids,
        'warehouse_id': warehouse_id,
        'area_id': area_id,
        'location_id': location_id,
    }


def _order_payload(references, quantities=(10,)):
    return {
        'supplier_id': references['supplier_id'],
        'expected_date': '2026-08-30',
        'currency': 'CNY',
        'remark': '收料闭环测试',
        'items': [
            {
                'product_id': references['product_ids'][index],
                'ordered_qty': quantity,
                'unit_price': 12.5 + index,
                'tax_rate': 13,
            }
            for index, quantity in enumerate(quantities)
        ],
    }


def _create_approved_order(db, references, quantities=(10,), user_id=7):
    order = save_purchase_order(db, _order_payload(references, quantities), user_id)
    submit_purchase_order(db, order['id'], user_id)
    review_purchase_order(db, order['id'], True, user_id)
    return order


def _order_items(db, order_id):
    return db.execute(
        'SELECT id,product_id,ordered_qty,arrived_qty,posted_qty,accepted_qty '
        'FROM scm_purchase_order_item WHERE order_id=? ORDER BY id',
        (order_id,),
    ).fetchall()


def _register_arrival(db, order, references, quantities=(10,), user_id=7,
                      delivery_note='DN-RCV-001'):
    items = [
        {
            'purchase_order_item_id': row['id'],
            'product_id': row['product_id'],
            'quantity': quantity,
        }
        for row, quantity in zip(_order_items(db, order['id']), quantities)
    ]
    return register_arrival(db, {
        'purchase_order_id': order['id'],
        'supplier_id': references['supplier_id'],
        'expected_date': '2026-08-30',
        'delivery_note_no': delivery_note,
        'remark': '收料闭环测试到货',
        'items': items,
    }, user_id)


def _arrival_item_id(db, notice_id):
    return db.execute(
        'SELECT id FROM inv_arrival_notice_item WHERE notice_id=? ORDER BY id',
        (notice_id,),
    ).fetchone()['id']


def _posting_payload(references, arrival_item_id, quantity, client_operation_id=None):
    payload = {
        'arrival_item_id': arrival_item_id,
        'warehouse_id': references['warehouse_id'],
        'area_id': references['area_id'],
        'location_id': references['location_id'],
        'batch_no': 'B20260830',
        'quantity': quantity,
    }
    if client_operation_id:
        payload['client_operation_id'] = client_operation_id
    return payload


def _stock_quantity(db, references, product_id, batch_no='B20260830'):
    row = db.execute(
        '''SELECT quantity FROM inv_stock_balance
           WHERE product_id=? AND warehouse_id=? AND area_id=?
             AND location_id=? AND batch_no=?''',
        (product_id, references['warehouse_id'], references['area_id'],
         references['location_id'], batch_no),
    ).fetchone()
    return float(row['quantity']) if row else 0.0


def _status_log(db, order_id):
    return [dict(row) for row in db.execute(
        '''SELECT from_status,to_status,action,operator_id,reason
           FROM scm_procurement_status_log
           WHERE entity_type='purchase_order' AND entity_id=? ORDER BY id''',
        (order_id,),
    )]


# ==================== 到货登记 ====================

def test_arrival_registration_creates_notice_and_links_order(db, references):
    order = _create_approved_order(db, references)
    notice = _register_arrival(db, order, references)

    assert notice['notice_no'].startswith('AR')
    assert notice['purchase_order_id'] == order['id']
    assert len(notice['items']) == 1
    item = notice['items'][0]
    assert item['quantity'] == 10
    assert item['normal_qty'] == 10
    assert item['pending_qty'] == 10
    assert item['excess_qty'] == 0

    order_item = _order_items(db, order['id'])[0]
    assert order_item['arrived_qty'] == 10
    assert order_item['posted_qty'] == 0


def test_arrival_registration_rejects_draft_or_unknown_order(db, references):
    order = _create_approved_order(db, references)
    db.execute('UPDATE scm_purchase_order SET status=? WHERE id=?',
               (PURCHASE['draft'], order['id']))
    db.commit()
    with pytest.raises(BusinessError, match='已审核或到货'):
        _register_arrival(db, order, references)


def test_arrival_excess_quantity_is_recorded(db, references):
    order = _create_approved_order(db, references, quantities=(10,))
    notice = _register_arrival(db, order, references, quantities=(12,))
    item = notice['items'][0]
    assert item['normal_qty'] == 10
    assert item['excess_qty'] == 2
    assert item['pending_qty'] == 10
    assert _order_items(db, order['id'])[0]['arrived_qty'] == 12


# ==================== 收料过账 + 库存累计 ====================

def test_receipt_posting_updates_stock_and_marks_partial_arrival(db, references):
    order = _create_approved_order(db, references, quantities=(10,))
    notice = _register_arrival(db, order, references)
    arrival_item_id = _arrival_item_id(db, notice['id'])

    posting = post_receipt(
        db, _posting_payload(references, arrival_item_id, 6, 'op-partial'), 7,
    )
    assert posting['posting_no'].startswith('RP')
    assert posting['quantity'] == 6
    assert posting['operator_id'] == 7
    assert _stock_quantity(db, references, references['product_ids'][0]) == 6

    status = db.execute(
        'SELECT status FROM scm_purchase_order WHERE id=?', (order['id'],),
    ).fetchone()['status']
    assert status == PURCHASE['partial_arrival']
    assert _status_log(db, order['id'])[-1]['action'] == 'receipt'


def test_receipt_posting_accumulates_same_location_batch(db, references):
    order = _create_approved_order(db, references, quantities=(10,))
    notice = _register_arrival(db, order, references)
    arrival_item_id = _arrival_item_id(db, notice['id'])

    post_receipt(db, _posting_payload(references, arrival_item_id, 4, 'op-a'), 7)
    post_receipt(db, _posting_payload(references, arrival_item_id, 6, 'op-b'), 7)

    assert _stock_quantity(db, references, references['product_ids'][0]) == 10
    posting_count = db.execute(
        'SELECT COUNT(*) AS c FROM inv_receipt_posting WHERE arrival_item_id=?',
        (arrival_item_id,),
    ).fetchone()['c']
    assert posting_count == 2
    balance_rows = db.execute(
        'SELECT COUNT(*) AS c FROM inv_stock_balance WHERE product_id=?',
        (references['product_ids'][0],),
    ).fetchone()['c']
    assert balance_rows == 1


def test_order_becomes_fully_arrived_when_all_posted(db, references):
    order = _create_approved_order(db, references, quantities=(10,))
    notice = _register_arrival(db, order, references)
    arrival_item_id = _arrival_item_id(db, notice['id'])

    post_receipt(db, _posting_payload(references, arrival_item_id, 10, 'op-full'), 7)

    status = db.execute(
        'SELECT status FROM scm_purchase_order WHERE id=?', (order['id'],),
    ).fetchone()['status']
    assert status == PURCHASE['fully_arrived']
    order_item = _order_items(db, order['id'])[0]
    assert order_item['posted_qty'] == 10
    assert order_item['accepted_qty'] == 10
    pending = db.execute(
        'SELECT pending_qty,accepted_qty FROM inv_arrival_notice_item WHERE id=?',
        (arrival_item_id,),
    ).fetchone()
    assert pending['pending_qty'] == 0
    assert pending['accepted_qty'] == 10


# ==================== 幂等保护 ====================

def test_duplicate_posting_is_idempotent_via_client_operation_id(db, references):
    order = _create_approved_order(db, references, quantities=(10,))
    notice = _register_arrival(db, order, references)
    arrival_item_id = _arrival_item_id(db, notice['id'])

    first = post_receipt(
        db, _posting_payload(references, arrival_item_id, 6, 'op-dup'), 7,
    )
    second = post_receipt(
        db, _posting_payload(references, arrival_item_id, 6, 'op-dup'), 7,
    )
    assert second['id'] == first['id']
    assert _stock_quantity(db, references, references['product_ids'][0]) == 6
    posting_count = db.execute(
        'SELECT COUNT(*) AS c FROM inv_receipt_posting WHERE arrival_item_id=?',
        (arrival_item_id,),
    ).fetchone()['c']
    assert posting_count == 1


def test_posting_beyond_pending_quantity_is_rejected_atomically(db, references):
    order = _create_approved_order(db, references, quantities=(10,))
    notice = _register_arrival(db, order, references)
    arrival_item_id = _arrival_item_id(db, notice['id'])

    with pytest.raises(BusinessError, match='待收数量'):
        post_receipt(db, _posting_payload(references, arrival_item_id, 11), 7)
    assert _stock_quantity(db, references, references['product_ids'][0]) == 0
    assert db.execute(
        'SELECT COUNT(*) AS c FROM inv_receipt_posting'
    ).fetchone()['c'] == 0
    assert db.execute(
        'SELECT status FROM scm_purchase_order WHERE id=?', (order['id'],),
    ).fetchone()['status'] == PURCHASE['approved']


def test_posting_requires_valid_warehouse_location(db, references):
    order = _create_approved_order(db, references, quantities=(10,))
    notice = _register_arrival(db, order, references)
    arrival_item_id = _arrival_item_id(db, notice['id'])

    payload = _posting_payload(references, arrival_item_id, 5, 'op-wh')
    payload['location_id'] = 999999
    with pytest.raises(BusinessError, match='库位不存在'):
        post_receipt(db, payload, 7)
    assert _stock_quantity(db, references, references['product_ids'][0]) == 0


# ==================== HTTP 权限 ====================

@pytest.fixture()
def http_client(tmp_path, monkeypatch):
    path = tmp_path / 'receiving-http.db'
    monkeypatch.setattr(database, 'DB_PATH', str(path))
    database.init_db()
    database._init_extra_tables()
    db = sqlite3.connect(path)
    # 质检员角色：不含任何 scm:* 权限，用于验证 403
    db.execute("INSERT INTO sys_role(role_name,role_key,description,menu_ids,status) "
               "VALUES('质检员','qc','质量操作',?,1)",
               ('["quality:write","inv:read"]',))
    role_id = db.execute("SELECT id FROM sys_role WHERE role_key='qc'").fetchone()[0]
    cursor = db.execute(
        "INSERT INTO sys_user(username,password,real_name,role_id,tenant_id,status) "
        "VALUES('qcuser','x','质检员',?,1,1)",
        (role_id,),
    )
    user_id = cursor.lastrowid
    db.commit()
    db.close()

    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY='receiving-http-test')
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = 'qcuser'
    client.user_id = user_id
    return client


def test_receipt_post_without_permission_returns_403(http_client):
    response = http_client.post('/api/scm/receiving/post', json={
        'arrival_item_id': 1,
        'warehouse_id': 1,
        'area_id': 1,
        'location_id': 1,
        'batch_no': 'B',
        'quantity': 1,
    })
    assert response.status_code == 403
    assert response.get_json()['code'] == 403


def test_arrival_add_without_permission_returns_403(http_client):
    response = http_client.post('/api/scm/receiving/arrival/add', json={
        'purchase_order_id': 1,
        'items': [{'purchase_order_item_id': 1, 'product_id': 1, 'quantity': 1}],
    })
    assert response.status_code == 403
    assert response.get_json()['code'] == 403


def test_receipt_list_is_accessible_to_any_logged_in_user(http_client):
    response = http_client.get('/api/scm/receiving/list?page=1&size=10')
    assert response.status_code == 200
    assert response.get_json()['code'] == 0
