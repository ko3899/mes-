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
    db = sqlite3.connect(database.DB_PATH)
    db.execute('UPDATE prod_sales_order SET status=1 WHERE id=?', (sales_id,))
    db.commit()
    db.close()
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


def test_sales_list_honors_persisted_manual_order(client):
    first = create_sales(client, 10)
    second = create_sales(client, 20)
    moved = client.post('/api/table-order/move', json={
        'table_key': 'prod/sales', 'record_id': first, 'target_position': 1,
    })
    assert moved.status_code == 200
    rows = client.get('/api/prod/sales/list').get_json()['data']['list']
    assert rows[0]['id'] == first
    assert rows[1]['id'] == second


def test_plan_requires_confirmed_sales_and_cannot_exceed_sales_line(client):
    sales_id = create_sales(client, 10)
    ids = client.reference_ids
    payload = {
        'sales_order_id': sales_id, 'plan_type': '订单生产',
        'items': [{'sales_order_item_id': 1, 'product_id': ids['product'],
                   'planned_qty': 11, 'workshop_id': ids['workshop']}],
    }
    rejected_draft = client.post('/api/prod/plan/save', json=payload)
    assert rejected_draft.status_code == 400
    db = sqlite3.connect(database.DB_PATH)
    db.execute('UPDATE prod_sales_order SET status=1 WHERE id=?', (sales_id,))
    db.commit()
    db.close()
    rejected_over = client.post('/api/prod/plan/save', json=payload)
    assert rejected_over.status_code == 400
    assert '超出' in rejected_over.get_json()['message']


def test_workorders_cannot_exceed_batch_total(client):
    sales_id = create_sales(client, 10)
    ids = client.reference_ids
    db = sqlite3.connect(database.DB_PATH)
    db.execute('UPDATE prod_sales_order SET status=1 WHERE id=?', (sales_id,))
    route = db.execute(
        "INSERT INTO base_process_route(route_name,product_id,workshop_id,status) VALUES('R',?,?,1)",
        (ids['product'], ids['workshop']),
    ).lastrowid
    process = db.execute(
        "INSERT INTO base_process(process_name,code,workshop_id,status) VALUES('P','P',?,1)",
        (ids['workshop'],),
    ).lastrowid
    db.execute('INSERT INTO base_process_route_detail(route_id,process_id,step_no) VALUES(?,?,1)', (route, process))
    material = db.execute("INSERT INTO base_product(product_name,code) VALUES('M','M')").lastrowid
    db.execute('INSERT INTO base_bom(product_id,material_id,quantity) VALUES(?,?,1)', (ids['product'], material))
    db.commit()
    db.close()
    plan = client.post('/api/prod/plan/save', json={
        'sales_order_id': sales_id, 'items': [{'sales_order_item_id': 1,
        'product_id': ids['product'], 'planned_qty': 10, 'workshop_id': ids['workshop']}],
    }).get_json()['data']['id']
    item = client.get(f'/api/prod/plan/{plan}').get_json()['data']['items'][0]['id']
    batch = client.post('/api/prod/batch/save', json={'plan_item_id': item, 'planned_qty': 10}).get_json()['data']['id']
    for qty in (6, 5):
        response = client.post('/api/prod/workorder/save', json={
            'production_batch_id': batch, 'route_id': route, 'planned_qty': qty,
        })
        if qty == 5:
            assert response.status_code == 400


def test_confirmed_sales_cannot_be_changed_through_legacy_crud(client):
    sales_id = create_sales(client, 10)
    db = sqlite3.connect(database.DB_PATH)
    db.execute('UPDATE prod_sales_order SET status=1 WHERE id=?', (sales_id,))
    db.commit()
    db.close()
    response = client.post('/api/prod/sales/update', json={'id': sales_id, 'customer': 'changed'})
    assert response.status_code == 400
