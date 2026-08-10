import os
import sqlite3
import sys

import pytest


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from utils import database  # noqa: E402
from app import create_app  # noqa: E402


@pytest.fixture()
def material_client(tmp_path, monkeypatch):
    path = tmp_path / 'material-flow.db'
    monkeypatch.setattr(database, 'DB_PATH', str(path))
    database.init_db()
    database._init_extra_tables()
    db = sqlite3.connect(path)
    product = db.execute("INSERT INTO base_product(product_name,code) VALUES('领料成品','MAT-FG')").lastrowid
    material = db.execute("INSERT INTO base_product(product_name,code) VALUES('领料物料','MAT-RM')").lastrowid
    workorder = db.execute(
        "INSERT INTO prod_workorder(order_no,product_id,planned_qty,status,remark) VALUES('MAT-WO',?,10,1,'生产业务链测试')",
        (product,),
    ).lastrowid
    snapshot = db.execute(
        '''INSERT INTO prod_workorder_bom_snapshot
           (workorder_id,material_id,material_name,quantity_per_unit,required_qty,unit)
           VALUES(?,?,?,1,10,'个')''', (workorder, material, '领料物料')
    ).lastrowid
    request_id = db.execute(
        '''INSERT INTO prod_material_req
           (req_no,workorder_id,bom_snapshot_id,product_id,quantity,required_qty,status,remark)
           VALUES('MAT-REQ',?,?,?,?,10,0,'生产业务链测试')''',
        (workorder, snapshot, material, 10),
    ).lastrowid
    db.execute('INSERT INTO inv_balance(product_id,quantity) VALUES(?,6)', (material,))
    db.commit()
    db.close()
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY='material-flow-test')
    client = app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = 1
        session['username'] = 'admin'
    client.ids = {'material': material, 'workorder': workorder, 'request': request_id}
    return client


def stock_of(material_id):
    db = sqlite3.connect(database.DB_PATH)
    value = db.execute('SELECT quantity FROM inv_balance WHERE product_id=?', (material_id,)).fetchone()[0]
    db.close()
    return value


def test_material_issue_is_atomic_and_rejects_short_stock(material_client):
    request_id = material_client.ids['request']
    requested = material_client.post(f'/api/prod/material/{request_id}/request', json={'quantity': 10})
    assert requested.status_code == 200
    response = material_client.post(f'/api/prod/material/{request_id}/issue', json={
        'quantity': 10, 'warehouse_id': 1, 'batch_no': 'RM-BATCH-TEST',
    })
    assert response.status_code == 409
    assert response.get_json()['data']['shortage_qty'] == 4
    assert stock_of(material_client.ids['material']) == 6


def test_issue_receive_and_return_update_stock_once(material_client):
    request_id = material_client.ids['request']
    material_client.post(f'/api/prod/material/{request_id}/request', json={'quantity': 6})
    issued = material_client.post(f'/api/prod/material/{request_id}/issue', json={
        'quantity': 6, 'warehouse_id': 1, 'batch_no': 'RM-BATCH-TEST',
    })
    assert issued.status_code == 200
    assert stock_of(material_client.ids['material']) == 0
    assert material_client.post(f'/api/prod/material/{request_id}/receive', json={'quantity': 6}).status_code == 200
    returned = material_client.post(f'/api/prod/material/{request_id}/return', json={'quantity': 2})
    assert returned.status_code == 200
    assert stock_of(material_client.ids['material']) == 2
    db = sqlite3.connect(database.DB_PATH)
    row = db.execute('SELECT trans_type,quantity FROM inv_transaction ORDER BY id DESC LIMIT 1').fetchone()
    totals = db.execute('SELECT issued_qty,received_qty,returned_qty FROM prod_material_req WHERE id=?', (request_id,)).fetchone()
    db.close()
    assert row == ('生产退料', 2)
    assert totals == (6, 6, 2)
