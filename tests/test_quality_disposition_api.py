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
from utils.helpers import hash_password  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    path = tmp_path / 'quality-api.db'
    monkeypatch.setattr(database, 'DB_PATH', str(path))
    database.init_db()
    database._init_extra_tables()
    db = sqlite3.connect(path)
    db.execute("INSERT INTO base_product(code,product_name) VALUES('P-QD','测试产品')")
    product_id = db.execute("SELECT id FROM base_product WHERE code='P-QD'").fetchone()[0]
    db.execute("INSERT INTO base_workshop(workshop_name,code) VALUES('测试车间','WS-QD')")
    workshop_id = db.execute("SELECT id FROM base_workshop WHERE code='WS-QD'").fetchone()[0]
    db.execute("INSERT INTO base_process(code,process_name,workshop_id) VALUES('PROC-QD','AIM检测',?)", (workshop_id,))
    process_id = db.execute("SELECT id FROM base_process WHERE code='PROC-QD'").fetchone()[0]
    db.execute(
        "INSERT INTO prod_workorder(order_no,product_id,planned_qty,status) VALUES('WO-QD',?,1,2)",
        (product_id,),
    )
    workorder_id = db.execute("SELECT id FROM prod_workorder WHERE order_no='WO-QD'").fetchone()[0]
    snapshot_id = db.execute(
        "INSERT INTO prod_workorder_route_snapshot(workorder_id,product_id,workshop_id,route_name,route_version) VALUES(?,?,?,?,?)",
        (workorder_id, product_id, workshop_id, '测试路线', 1),
    ).lastrowid
    step_id = db.execute(
        "INSERT INTO prod_workorder_route_step(snapshot_id,step_no,process_id,process_name,workshop_id) VALUES(?,?,?,?,?)",
        (snapshot_id, 1, process_id, 'AIM检测', workshop_id),
    ).lastrowid
    task_id = db.execute(
        "INSERT INTO prod_task(task_no,workorder_id,process_id,route_step_id,planned_qty,status) VALUES('TASK-QD',?,?,?,?,1)",
        (workorder_id, process_id, step_id, 1),
    ).lastrowid
    db.execute(
        "INSERT INTO prod_serial(serial_no,product_id,workorder_id,quality_status) VALUES('SN-QD',?,?,'quality_hold')",
        (product_id, workorder_id),
    )
    disposition_id = db.execute(
        '''INSERT INTO prod_quality_disposition
           (disposition_no,sn,workorder_id,source_task_id,route_step_id,status)
           VALUES('QD-API','SN-QD',?,?,?,'pending_review')''',
        (workorder_id, task_id, step_id),
    ).lastrowid
    user_role = db.execute("SELECT id FROM sys_role WHERE role_key='user'").fetchone()[0]
    operator_id = db.execute(
        "INSERT INTO sys_user(username,password,real_name,role_id,status) VALUES(?,?,?,?,1)",
        ('operator', hash_password('password123'), '操作员', user_role),
    ).lastrowid
    db.commit()
    db.close()
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY='quality-api-test')
    test_client = app.test_client()
    test_client.disposition_id = disposition_id
    test_client.operator_id = operator_id
    return test_client


def _login(client, user_id, username):
    with client.session_transaction() as session:
        session['user_id'] = user_id
        session['username'] = username


def test_disposition_commands_enforce_permissions_and_admin_can_approve(client):
    url = '/api/site/rework/%s/approve' % client.disposition_id
    assert client.post(url, json={'action': 'rework'}).status_code == 401
    _login(client, client.operator_id, 'operator')
    assert client.post(url, json={'action': 'rework'}).status_code == 403
    _login(client, 1, 'admin')
    response = client.post(url, json={'action': 'rework', 'reason': '批准返工'})
    assert response.status_code == 200
    assert response.get_json()['data']['status'] == 'approved'
    started = client.post(
        '/api/site/rework/%s/start-task' % client.disposition_id, json={}
    )
    assert started.status_code == 200
    listed = client.get('/api/site/rework/list').get_json()['data']['list'][0]
    assert listed['status'] == 'task_started'
    assert listed['rework_task_status'] == 1
    assert client.get('/api/site/rework/list').status_code == 200
