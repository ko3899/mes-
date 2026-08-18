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
def report_client(tmp_path, monkeypatch):
    path = tmp_path / 'report-transfer.db'
    monkeypatch.setattr(database, 'DB_PATH', str(path))
    database.init_db()
    database._init_extra_tables()
    db = sqlite3.connect(path)
    workshop = db.execute("INSERT INTO base_workshop(workshop_name,code) VALUES('报工车间','REP-WS')").lastrowid
    product = db.execute("INSERT INTO base_product(product_name,code) VALUES('报工产品','REP-P')").lastrowid
    processes = [db.execute(
        'INSERT INTO base_process(process_name,code,workshop_id) VALUES(?,?,?)',
        (f'报工工序{i}', f'REP-PR-{i}', workshop),
    ).lastrowid for i in range(1, 4)]
    workorder = db.execute(
        "INSERT INTO prod_workorder(order_no,product_id,planned_qty,workshop_id,status,remark) VALUES('REP-WO',?,10,?,2,'生产业务链测试')",
        (product, workshop),
    ).lastrowid
    snapshot = db.execute(
        'INSERT INTO prod_workorder_route_snapshot(workorder_id,route_name,product_id,workshop_id) VALUES(?,?,?,?)',
        (workorder, '冻结测试路线', product, workshop),
    ).lastrowid
    steps, tasks = [], []
    for step_no, process in enumerate(processes, 1):
        step = db.execute(
            '''INSERT INTO prod_workorder_route_step
               (snapshot_id,process_id,process_name,workshop_id,step_no)
               VALUES(?,?,?,?,?)''', (snapshot, process, f'报工工序{step_no}', workshop, step_no)
        ).lastrowid
        task = db.execute(
            '''INSERT INTO prod_task(task_no,workorder_id,process_id,route_step_id,planned_qty,status)
               VALUES(?,?,?,?,10,0)''', (f'REP-TASK-{step_no}', workorder, process, step)
        ).lastrowid
        steps.append(step)
        tasks.append(task)
    db.commit()
    db.close()
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY='report-transfer-test')
    client = app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = 1
        session['username'] = 'admin'
    client.ids = {'workorder': workorder, 'processes': processes, 'steps': steps, 'tasks': tasks}
    return client


def submit(client, task_index, qualified, defect=0):
    ids = client.ids
    return client.post('/api/prod/report/add', json={
        'task_id': ids['tasks'][task_index], 'workorder_id': ids['workorder'],
        'process_id': ids['processes'][task_index], 'qualified_qty': qualified,
        'defect_qty': defect, 'controlled': True, 'remark': '生产业务链测试',
    })


def test_submitted_report_does_not_change_task_until_posted(report_client):
    response = submit(report_client, 0, 8, 2)
    assert response.status_code == 200
    report_id = response.get_json()['data']['id']
    db = sqlite3.connect(database.DB_PATH)
    assert db.execute('SELECT completed_qty,defect_qty FROM prod_task WHERE id=?', (report_client.ids['tasks'][0],)).fetchone() == (0, 0)
    db.close()
    assert report_client.post(f'/api/prod/report/{report_id}/approve').status_code == 200
    assert report_client.post(f'/api/prod/report/{report_id}/post').status_code == 200
    db = sqlite3.connect(database.DB_PATH)
    assert db.execute('SELECT completed_qty,defect_qty FROM prod_task WHERE id=?', (report_client.ids['tasks'][0],)).fetchone() == (8, 2)
    db.close()


def test_second_step_cannot_report_more_than_transferred(report_client):
    report_id = submit(report_client, 0, 8).get_json()['data']['id']
    report_client.post(f'/api/prod/report/{report_id}/approve')
    report_client.post(f'/api/prod/report/{report_id}/post')
    ids = report_client.ids
    transfer = report_client.post('/api/prod/transfer/add', json={
        'workorder_id': ids['workorder'], 'from_process_id': ids['processes'][0],
        'to_process_id': ids['processes'][1], 'quantity': 8, 'remark': '生产业务链测试',
    })
    assert transfer.status_code == 200
    rejected = submit(report_client, 1, 9)
    assert rejected.status_code == 409
    assert '可执行数量为 8' in rejected.get_json()['message']


def test_transfer_rejects_non_adjacent_route_steps(report_client):
    ids = report_client.ids
    response = report_client.post('/api/prod/transfer/add', json={
        'workorder_id': ids['workorder'], 'from_process_id': ids['processes'][0],
        'to_process_id': ids['processes'][2], 'quantity': 1,
    })
    assert response.status_code == 400


def test_report_must_be_approved_before_posting_and_posted_report_cannot_delete(report_client):
    report_id = submit(report_client, 0, 2).get_json()['data']['id']
    direct_post = report_client.post(f'/api/prod/report/{report_id}/post')
    assert direct_post.status_code == 400
    assert report_client.post(f'/api/prod/report/{report_id}/approve').status_code == 200
    assert report_client.post(f'/api/prod/report/{report_id}/post').status_code == 200
    deleted = report_client.post('/api/prod/report/delete', json={'id': report_id})
    assert deleted.status_code == 400


def test_rejected_report_can_be_deleted_without_counting_in_task(report_client):
    report_id = submit(report_client, 0, 2).get_json()['data']['id']
    assert report_client.post(f'/api/prod/report/{report_id}/reject', json={'remark': 'test'}).status_code == 200
    deleted = report_client.post('/api/prod/report/delete', json={'id': report_id})
    assert deleted.status_code == 200
    import sqlite3
    db = sqlite3.connect(database.DB_PATH)
    assert db.execute('SELECT completed_qty,defect_qty FROM prod_task WHERE id=?',
                      (report_client.ids['tasks'][0],)).fetchone() == (0, 0)
    db.close()


def test_report_requires_controlled_workflow_marker(report_client):
    ids = report_client.ids
    response = report_client.post('/api/prod/report/add', json={
        'task_id': ids['tasks'][0], 'workorder_id': ids['workorder'],
        'process_id': ids['processes'][0], 'qualified_qty': 1,
        'defect_qty': 0,
    })
    assert response.status_code == 400
    assert 'controlled' in response.get_json()['message']


def test_non_admin_cannot_write_master_data(report_client):
    db = sqlite3.connect(database.DB_PATH)
    try:
        role_id = db.execute(
            "INSERT INTO sys_role(role_name,role_key,description,menu_ids) VALUES(?,?,?,?)",
            ('操作员', 'operator', '仅查看', '[]'),
        ).lastrowid
        user_id = db.execute(
            "INSERT INTO sys_user(username,password,real_name,role_id,status) VALUES(?,?,?,?,1)",
            ('operator', 'unused', '操作员', role_id),
        ).lastrowid
        db.commit()
    finally:
        db.close()

    with report_client.session_transaction() as session:
        session['user_id'] = user_id
        session['username'] = 'operator'
    response = report_client.post('/api/base/process/add', json={
        'process_name': '禁止写入', 'code': 'DENY-PROCESS', 'workshop_id': 1,
    })
    assert response.status_code == 403


def test_legacy_production_add_route_cannot_bypass_domain_flow(report_client):
    response = report_client.post('/api/prod/sales/add', json={'customer': '旁路订单'})
    assert response.status_code == 410
    db = sqlite3.connect(database.DB_PATH)
    try:
        assert db.execute("SELECT COUNT(*) FROM prod_sales_order WHERE customer=?", ('旁路订单',)).fetchone()[0] == 0
    finally:
        db.close()


def test_report_creator_cannot_delete_another_users_report(report_client):
    report_id = submit(report_client, 0, 1).get_json()['data']['id']
    assert report_client.post(f'/api/prod/report/{report_id}/reject', json={'remark': '拒绝'}).status_code == 200
    db = sqlite3.connect(database.DB_PATH)
    try:
        role_id = db.execute(
            "INSERT INTO sys_role(role_name,role_key,description,menu_ids) VALUES(?,?,?,?)",
            ('报工员', 'reporter', '只能创建报工', '["prod:report:create"]'),
        ).lastrowid
        user_id = db.execute(
            "INSERT INTO sys_user(username,password,real_name,role_id,status) VALUES(?,?,?,?,1)",
            ('reporter', 'unused', '报工员', role_id),
        ).lastrowid
        db.commit()
    finally:
        db.close()
    with report_client.session_transaction() as session:
        session['user_id'] = user_id
        session['username'] = 'reporter'
    response = report_client.post('/api/prod/report/delete', json={'id': report_id})
    assert response.status_code == 403


def test_legacy_draft_update_rejects_relationship_and_quantity_fields(report_client):
    sales_id = report_client.post('/api/prod/sales/save', json={
        'customer': '草稿订单', 'items': [{'product_id': 1, 'quantity': 2}],
    }).get_json()['data']['id']
    response = report_client.post('/api/prod/sales/update', json={
        'id': sales_id, 'total_amount': 999999, 'customer_id': 999,
    })
    assert response.status_code == 400


def test_report_operator_cannot_read_sales_without_sales_permission(report_client):
    db = sqlite3.connect(database.DB_PATH)
    try:
        role_id = db.execute(
            "INSERT INTO sys_role(role_name,role_key,description,menu_ids) VALUES(?,?,?,?)",
            ('报工查看员', 'report-viewer', '仅报工', '["prod:report:create"]'),
        ).lastrowid
        user_id = db.execute(
            "INSERT INTO sys_user(username,password,real_name,role_id,status) VALUES(?,?,?,?,1)",
            ('report-viewer', 'unused', '报工查看员', role_id),
        ).lastrowid
        db.commit()
    finally:
        db.close()
    with report_client.session_transaction() as session:
        session['user_id'] = user_id
        session['username'] = 'report-viewer'
    assert report_client.get('/api/prod/sales/list').status_code == 403


def test_material_legacy_crud_write_is_disabled_until_domain_service_exists(report_client):
    response = report_client.post('/api/prod/material/add', json={
        'workorder_id': 1, 'product_id': 1, 'required_qty': 1,
    })
    assert response.status_code == 410
