import os
import sqlite3
import sys

import pytest


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app import create_app  # noqa: E402
from utils import database  # noqa: E402


@pytest.fixture()
def inventory_client(tmp_path, monkeypatch):
    path = tmp_path / 'inventory-posting.db'
    monkeypatch.setattr(database, 'DB_PATH', str(path))
    database.init_db()
    database._init_extra_tables()
    db = sqlite3.connect(path)
    product_id = db.execute(
        "INSERT INTO base_product(product_name,code,unit) VALUES('库存测试产品','INV-TEST','个')"
    ).lastrowid
    db.commit()
    db.close()

    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY='inventory-posting-test')
    client = app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = 1
        session['username'] = 'admin'
    client.product_id = product_id
    return client


def _db_row(sql, params=()):
    db = sqlite3.connect(database.DB_PATH)
    db.row_factory = sqlite3.Row
    row = db.execute(sql, params).fetchone()
    db.close()
    return dict(row) if row else None


def _add_document(client, kind, quantity, unit_price):
    party = {'supplier': '测试供应商'} if kind == 'inbound' else {'customer': '测试客户'}
    response = client.post(f'/api/inv/{kind}/add', json={
        'product_id': client.product_id,
        'quantity': quantity,
        'unit_price': unit_price,
        **party,
    })
    assert response.status_code == 200
    assert response.get_json()['code'] == 0
    return response.get_json()['data']['id']


def test_inbound_draft_and_post_are_atomic_and_idempotent(inventory_client):
    document_id = _add_document(inventory_client, 'inbound', 10, 2.5)
    item = _db_row(
        'SELECT product_id,quantity,unit_price,amount FROM inv_inbound_item WHERE inbound_id=?',
        (document_id,),
    )
    assert item == {
        'product_id': inventory_client.product_id,
        'quantity': 10.0,
        'unit_price': 2.5,
        'amount': 25.0,
    }
    assert _db_row('SELECT * FROM inv_balance WHERE product_id=?', (inventory_client.product_id,)) is None

    posted = inventory_client.post(f'/api/inv/inbound/{document_id}/post', json={})
    assert posted.status_code == 200
    balance = _db_row(
        'SELECT quantity,amount FROM inv_balance WHERE product_id=?',
        (inventory_client.product_id,),
    )
    assert balance == {'quantity': 10.0, 'amount': 25.0}

    repeated = inventory_client.post(f'/api/inv/inbound/{document_id}/post', json={})
    assert repeated.status_code == 409
    assert _db_row(
        'SELECT quantity,amount FROM inv_balance WHERE product_id=?',
        (inventory_client.product_id,),
    ) == balance
    transaction = _db_row('SELECT COUNT(*) AS count FROM inv_transaction WHERE ref_no LIKE "RK%"')
    assert transaction['count'] == 1


def test_outbound_post_deducts_stock_and_rejects_shortage(inventory_client):
    inbound_id = _add_document(inventory_client, 'inbound', 10, 2.5)
    assert inventory_client.post(f'/api/inv/inbound/{inbound_id}/post', json={}).status_code == 200

    outbound_id = _add_document(inventory_client, 'outbound', 4, 4)
    assert inventory_client.post(f'/api/inv/outbound/{outbound_id}/post', json={}).status_code == 200
    assert _db_row(
        'SELECT quantity,amount FROM inv_balance WHERE product_id=?',
        (inventory_client.product_id,),
    ) == {'quantity': 6.0, 'amount': 15.0}

    shortage_id = _add_document(inventory_client, 'outbound', 7, 4)
    shortage = inventory_client.post(f'/api/inv/outbound/{shortage_id}/post', json={})
    assert shortage.status_code == 409
    assert shortage.get_json()['data'][0]['shortage_qty'] == 1
    assert _db_row(
        'SELECT quantity,amount FROM inv_balance WHERE product_id=?',
        (inventory_client.product_id,),
    ) == {'quantity': 6.0, 'amount': 15.0}
    assert _db_row('SELECT status FROM inv_outbound WHERE id=?', (shortage_id,))['status'] == 0


def test_posted_document_cannot_be_deleted_or_modified(inventory_client):
    document_id = _add_document(inventory_client, 'inbound', 3, 1)
    assert inventory_client.post(f'/api/inv/inbound/{document_id}/post', json={}).status_code == 200

    deleted = inventory_client.post('/api/inv/inbound/delete', json={'id': document_id})
    assert deleted.status_code == 409
    updated = inventory_client.post('/api/inv/inbound/update', json={
        'id': document_id,
        'product_id': inventory_client.product_id,
        'quantity': 8,
        'unit_price': 1,
    })
    assert updated.status_code == 409
    assert _db_row(
        'SELECT quantity FROM inv_balance WHERE product_id=?',
        (inventory_client.product_id,),
    ) == {'quantity': 3.0}
