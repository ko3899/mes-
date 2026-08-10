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
def client(tmp_path, monkeypatch):
    path = tmp_path / 'sales-plan.db'
    monkeypatch.setattr(database, 'DB_PATH', str(path))
    database.init_db()
    database._init_extra_tables()
    db = sqlite3.connect(path)
    customer = db.execute(
        "INSERT INTO base_customer(customer_name,code) VALUES('验收客户','CUS-FLOW')"
    ).lastrowid
    product = db.execute(
        "INSERT INTO base_product(product_name,code,unit) VALUES('验收产品','PROD-FLOW','件')"
    ).lastrowid
    workshop = db.execute(
        "INSERT INTO base_workshop(workshop_name,code) VALUES('验收车间','WS-FLOW')"
    ).lastrowid
    db.commit()
    db.close()
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY='sales-plan-test')
    test_client = app.test_client()
    with test_client.session_transaction() as session:
        session['user_id'] = 1
        session['username'] = 'admin'
    test_client.reference_ids = {'customer': customer, 'product': product, 'workshop': workshop}
    return test_client


def create_sales(client, quantity=100):
    ids = client.reference_ids
    response = client.post('/api/prod/sales/save', json={
        'customer_id': ids['customer'], 'delivery_date': '2026-08-30',
        'remark': '生产业务链测试',
        'items': [{'product_id': ids['product'], 'quantity': quantity, 'unit_price': 12.5}],
    })
    assert response.status_code == 200
    return response.get_json()['data']['id']


def test_sales_save_and_detail_keep_header_and_lines_together(client):
    sales_id = create_sales(client, 10)
    detail = client.get(f'/api/prod/sales/{sales_id}').get_json()['data']
    assert detail['header']['customer_name'] == '验收客户'
    assert detail['header']['total_amount'] == 125
    assert detail['items'][0]['quantity'] == 10
    listing = client.get('/api/prod/sales/list').get_json()['data']['list'][0]
    assert listing['line_count'] == 1


def test_confirmed_sales_lines_can_be_carried_to_plan(client):
    sales_id = create_sales(client, 100)
    db = sqlite3.connect(database.DB_PATH)
    db.execute('UPDATE prod_sales_order SET status=1 WHERE id=?', (sales_id,))
    db.commit()
    db.close()
    response = client.get(f'/api/prod/plan/source/{sales_id}')
    assert response.status_code == 200
    line = response.get_json()['data']['items'][0]
    assert line['remaining_qty'] == 100
    assert line['product_name'] == '验收产品'


def test_two_batches_may_split_but_not_exceed_plan_line(client):
    sales_id = create_sales(client, 100)
    ids = client.reference_ids
    response = client.post('/api/prod/plan/save', json={
        'sales_order_id': sales_id, 'plan_type': '订单生产',
        'start_date': '2026-08-11', 'end_date': '2026-08-20',
        'remark': '生产业务链测试',
        'items': [{'sales_order_item_id': 1, 'product_id': ids['product'],
                   'planned_qty': 100, 'workshop_id': ids['workshop']}],
    })
    assert response.status_code == 200
    plan_id = response.get_json()['data']['id']
    plan_item = client.get(f'/api/prod/plan/{plan_id}').get_json()['data']['items'][0]['id']
    for quantity in (40, 60):
        assert client.post('/api/prod/batch/save', json={
            'plan_item_id': plan_item, 'planned_qty': quantity,
            'remark': '生产业务链测试',
        }).status_code == 200
    rejected = client.post('/api/prod/batch/save', json={
        'plan_item_id': plan_item, 'planned_qty': 1,
        'remark': '生产业务链测试',
    })
    assert rejected.status_code == 400
    assert '剩余数量' in rejected.get_json()['message']
    batches = client.get('/api/prod/batch/list').get_json()['data']['list']
    assert [row['planned_qty'] for row in batches] == [60, 40]
