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
def flow_client(tmp_path, monkeypatch):
    path = tmp_path / 'workorder-flow.db'
    monkeypatch.setattr(database, 'DB_PATH', str(path))
    database.init_db()
    database._init_extra_tables()
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    workshop = db.execute("INSERT INTO base_workshop(workshop_name,code) VALUES('工单车间','WO-WS')").lastrowid
    product = db.execute("INSERT INTO base_product(product_name,code) VALUES('工单产品','WO-P')").lastrowid
    other_product = db.execute("INSERT INTO base_product(product_name,code) VALUES('其他产品','OTHER-P')").lastrowid
    material = db.execute("INSERT INTO base_product(product_name,code) VALUES('工单物料','WO-M')").lastrowid
    processes = [db.execute(
        'INSERT INTO base_process(process_name,code,workshop_id) VALUES(?,?,?)',
        (f'工单工序{i}', f'WO-PR-{i}', workshop),
    ).lastrowid for i in range(1, 4)]
    route = db.execute(
        'INSERT INTO base_process_route(product_id,route_name,workshop_id,version) VALUES(?,?,?,2)',
        (product, '工单测试路线', workshop),
    ).lastrowid
    other_route = db.execute(
        'INSERT INTO base_process_route(product_id,route_name,workshop_id,version) VALUES(?,?,?,1)',
        (other_product, '其他产品路线', workshop),
    ).lastrowid
    for step_no, process in enumerate(processes, 1):
        db.execute(
            'INSERT INTO base_process_route_detail(route_id,process_id,step_no,workshop_id) VALUES(?,?,?,?)',
            (route, process, step_no, workshop),
        )
    db.execute('INSERT INTO base_bom(product_id,material_id,quantity,unit) VALUES(?,?,2,?)', (product, material, '个'))
    plan = db.execute("INSERT INTO prod_plan(plan_no,status,remark) VALUES('WO-PLAN',1,'生产业务链测试')").lastrowid
    plan_item = db.execute(
        'INSERT INTO prod_plan_item(plan_id,product_id,planned_qty,workshop_id,remark) VALUES(?,?,?,?,?)',
        (plan, product, 50, workshop, '生产业务链测试'),
    ).lastrowid
    batch = db.execute(
        '''INSERT INTO prod_batch(batch_no,plan_id,plan_item_id,product_id,workshop_id,planned_qty,remark)
           VALUES('WO-BATCH',?,?,?,?,50,'生产业务链测试')''',
        (plan, plan_item, product, workshop),
    ).lastrowid
    db.commit()
    db.close()
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY='workorder-flow-test')
    client = app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = 1
        session['username'] = 'admin'
    client.ids = {'workshop': workshop, 'product': product, 'other_product': other_product,
                  'route': route, 'other_route': other_route, 'processes': processes,
                  'plan_item': plan_item, 'batch': batch}
    return client


def save_workorder(client, route_id=None):
    ids = client.ids
    return client.post('/api/prod/workorder/save', json={
        'production_batch_id': ids['batch'], 'product_id': ids['product'],
        'workshop_id': ids['workshop'], 'route_id': route_id or ids['route'],
        'planned_qty': 50, 'priority': 3, 'start_date': '2026-08-11',
        'end_date': '2026-08-20', 'remark': '生产业务链测试',
    })


def test_workorder_options_filter_routes_for_plan_product_and_workshop(flow_client):
    ids = flow_client.ids
    response = flow_client.get(f"/api/prod/workorder/options?plan_item_id={ids['plan_item']}")
    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['product_id'] == ids['product']
    assert data['workshop_id'] == ids['workshop']
    assert [route['id'] for route in data['routes']] == [ids['route']]


def test_workorder_rejects_route_for_other_product(flow_client):
    response = save_workorder(flow_client, flow_client.ids['other_route'])
    assert response.status_code == 400
    assert '不匹配' in response.get_json()['message']


def test_task_generation_uses_only_frozen_route_steps_and_is_idempotent(flow_client):
    saved = save_workorder(flow_client)
    assert saved.status_code == 200
    workorder = saved.get_json()['data']['id']
    released = flow_client.post(f'/api/prod/workorder/{workorder}/release', json={'remark': '生产业务链测试'})
    assert released.status_code == 200
    first = flow_client.post(f'/api/prod/workorder/{workorder}/generate-tasks').get_json()['data']
    second = flow_client.post(f'/api/prod/workorder/{workorder}/generate-tasks').get_json()['data']
    assert [row['process_id'] for row in first] == flow_client.ids['processes']
    assert [row['id'] for row in second] == [row['id'] for row in first]
    listing = flow_client.get('/api/prod/workorder/list').get_json()['data']['list'][0]
    assert listing['route_version'] == 2
    assert listing['batch_no'] == 'WO-BATCH'
