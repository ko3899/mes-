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
    path = tmp_path / 'process-route.db'
    monkeypatch.setattr(database, 'DB_PATH', str(path))
    database.init_db()
    database._init_extra_tables()
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY='process-route-test')
    test_client = app.test_client()
    with test_client.session_transaction() as session:
        session['user_id'] = 1
        session['username'] = 'admin'
    return test_client


def seed_route_references(client):
    path = database.DB_PATH
    db = sqlite3.connect(path)
    workshop_a = db.execute(
        "INSERT INTO base_workshop(workshop_name,code) VALUES('车间A','WS-A')"
    ).lastrowid
    workshop_b = db.execute(
        "INSERT INTO base_workshop(workshop_name,code) VALUES('车间B','WS-B')"
    ).lastrowid
    product = db.execute(
        "INSERT INTO base_product(product_name,code) VALUES('产品A','PROD-A')"
    ).lastrowid
    process_a = db.execute(
        "INSERT INTO base_process(process_name,code,workshop_id) VALUES('工序A','P-A',?)",
        (workshop_a,),
    ).lastrowid
    process_b = db.execute(
        "INSERT INTO base_process(process_name,code,workshop_id) VALUES('工序B','P-B',?)",
        (workshop_b,),
    ).lastrowid
    db.commit()
    db.close()
    return workshop_a, workshop_b, product, process_a, process_b


def test_new_process_requires_workshop(client):
    response = client.post('/api/base/process/add', json={'process_name': '测试', 'code': 'P1'})
    assert response.status_code == 400
    assert response.get_json()['message'] == '所属车间必填'


def test_process_list_filters_by_workshop_and_status(client):
    workshop_a, workshop_b, _, process_a, _ = seed_route_references(client)
    response = client.get(f'/api/base/process/list?workshop_id={workshop_a}&status=1')
    assert response.status_code == 200
    assert [row['id'] for row in response.get_json()['data']] == [process_a]
    assert all(row['workshop_id'] != workshop_b for row in response.get_json()['data'])


def test_route_rejects_process_from_another_workshop(client):
    workshop_a, _, product, _, process_b = seed_route_references(client)
    response = client.post('/api/base/route/save', json={
        'route_name': '错误跨车间路线', 'product_id': product,
        'workshop_id': workshop_a, 'version': 1, 'status': 1,
        'steps': [{'process_id': process_b, 'workshop_id': workshop_a}],
    })
    assert response.status_code == 400
    assert '不属于路线车间' in response.get_json()['message']


def test_route_save_returns_ordered_steps_and_filters_headers(client):
    workshop_a, workshop_b, product, process_a, _ = seed_route_references(client)
    response = client.post('/api/base/route/save', json={
        'route_name': '产品A装配路线', 'product_id': product,
        'workshop_id': workshop_a, 'version': 3, 'status': 1,
        'description': '生产业务链测试',
        'steps': [
            {'process_id': process_a, 'workshop_id': workshop_a,
             'standard_time': 12, 'is_inspection_point': 1},
        ],
    })
    assert response.status_code == 200
    route_id = response.get_json()['data']['id']
    payload = client.get(
        f'/api/base/route/list?product_id={product}&workshop_id={workshop_a}'
    ).get_json()['data']
    assert [row['id'] for row in payload] == [route_id]
    assert payload[0]['version'] == 3
    assert payload[0]['steps'][0]['step_no'] == 1
    assert payload[0]['steps'][0]['process_name'] == '工序A'
    assert client.get(
        f'/api/base/route/list?product_id={product}&workshop_id={workshop_b}'
    ).get_json()['data'] == []
