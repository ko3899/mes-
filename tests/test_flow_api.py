import json
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
def flow_client(tmp_path, monkeypatch):
    path = tmp_path / 'flow.db'
    monkeypatch.setattr(database, 'DB_PATH', str(path))
    database.init_db()
    database._init_extra_tables()
    db = sqlite3.connect(path)
    approver_id = db.execute(
        """INSERT INTO sys_user(username,password,real_name,status)
           VALUES('approver','x','审批人',1)"""
    ).lastrowid
    # 审批人需要具备审批权限（/api/flow/task/approve|reject 依赖 flow:approve）：
    # 绑定 admin 角色让其命中 permission_required 的管理员放行分支。
    # init_db 已种子 role_key='admin'，INSERT OR IGNORE 仅为兜底。
    db.execute(
        """INSERT OR IGNORE INTO sys_role(role_name,role_key,description,menu_ids,status)
           VALUES('超级管理员','admin','拥有所有权限','',1)"""
    )
    db.execute(
        "UPDATE sys_user SET role_id=(SELECT id FROM sys_role WHERE role_key='admin') WHERE id=?",
        (approver_id,),
    )
    product_id = db.execute(
        "INSERT INTO base_product(product_name,code,unit) VALUES('审批产品','FLOW-P','个')"
    ).lastrowid
    workorder_id = db.execute(
        """INSERT INTO prod_workorder(order_no,product_id,planned_qty,status)
           VALUES('FLOW-WO',?,10,0)""",
        (product_id,),
    ).lastrowid
    db.commit()
    db.close()

    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY='flow-test')
    client = app.test_client()
    with client.session_transaction() as user_session:
        user_session['user_id'] = 1
        user_session['username'] = 'admin'
    client.approver_id = approver_id
    client.workorder_id = workorder_id
    return client


def _login_as(client, user_id, username):
    with client.session_transaction() as user_session:
        user_session['user_id'] = user_id
        user_session['username'] = username


def _add_flow(client, steps=None, key='workorder-flow'):
    if steps is None:
        steps = [{'name': '主管审批', 'assignee': client.approver_id}]
    response = client.post('/api/flow/definition/add', json={
        'flow_name': '工单审批',
        'flow_key': key,
        'steps': steps,
    })
    assert response.status_code == 200
    return response.get_json()['data']['id']


def _submit_workorder(client, flow_id):
    return client.post('/api/flow/instance/submit', json={
        'flow_id': flow_id,
        'title': '工单审批',
        'biz_type': 'workorder',
        'biz_id': client.workorder_id,
    })


def _db_row(sql, params=()):
    db = sqlite3.connect(database.DB_PATH)
    db.row_factory = sqlite3.Row
    row = db.execute(sql, params).fetchone()
    db.close()
    return dict(row) if row else None


def test_flow_validates_steps_assignee_and_active_definition(flow_client):
    empty = flow_client.post('/api/flow/definition/add', json={
        'flow_name': '空流程', 'flow_key': 'empty', 'steps': [],
    })
    assert empty.status_code == 400
    missing_user = flow_client.post('/api/flow/definition/add', json={
        'flow_name': '坏流程', 'flow_key': 'bad',
        'steps': [{'name': '审批', 'assignee': 99999}],
    })
    assert missing_user.status_code == 400

    flow_id = _add_flow(flow_client)
    duplicate_key = flow_client.post('/api/flow/definition/add', json={
        'flow_name': '重复', 'flow_key': 'workorder-flow',
        'steps': [{'assignee': flow_client.approver_id}],
    })
    assert duplicate_key.status_code == 409
    disabled = flow_client.post('/api/flow/definition/update', json={
        'id': flow_id, 'flow_name': '工单审批', 'status': 0,
    })
    assert disabled.status_code == 200
    assert _submit_workorder(flow_client, flow_id).status_code == 404


def test_pending_list_returns_task_id_and_approval_is_idempotent(flow_client):
    flow_id = _add_flow(flow_client)
    submitted = _submit_workorder(flow_client, flow_id)
    assert submitted.status_code == 200
    instance_id = submitted.get_json()['data']['id']
    assert _submit_workorder(flow_client, flow_id).status_code == 409

    _login_as(flow_client, flow_client.approver_id, 'approver')
    pending = flow_client.get('/api/flow/instance/list?tab=pending').get_json()['data']
    assert pending['total'] == 1
    task_id = pending['list'][0]['task_id']
    assert pending['list'][0]['id'] == instance_id
    assert task_id == _db_row(
        'SELECT id FROM flow_task WHERE instance_id=?', (instance_id,)
    )['id']

    approved = flow_client.post('/api/flow/task/approve', json={'id': task_id})
    assert approved.status_code == 200
    assert flow_client.post('/api/flow/task/approve', json={'id': task_id}).status_code == 409
    assert _db_row('SELECT status FROM flow_instance WHERE id=?', (instance_id,))['status'] == 1
    assert _db_row('SELECT status FROM prod_workorder WHERE id=?', (flow_client.workorder_id,))['status'] == 1


def test_running_instance_uses_step_snapshot_after_definition_changes(flow_client):
    flow_id = _add_flow(flow_client, steps=[
        {'name': '一级', 'assignee': flow_client.approver_id},
        {'name': '二级', 'assignee': 1},
    ])
    submitted = _submit_workorder(flow_client, flow_id)
    instance_id = submitted.get_json()['data']['id']

    changed = flow_client.post('/api/flow/definition/update', json={
        'id': flow_id,
        'flow_name': '工单审批新版',
        'steps': [{'name': '新版单步', 'assignee': flow_client.approver_id}],
    })
    assert changed.status_code == 200
    cannot_delete = flow_client.post('/api/flow/definition/delete', json={'id': flow_id})
    assert cannot_delete.status_code == 409

    _login_as(flow_client, flow_client.approver_id, 'approver')
    first_task = _db_row(
        'SELECT id FROM flow_task WHERE instance_id=? AND step_no=1', (instance_id,)
    )['id']
    assert flow_client.post('/api/flow/task/approve', json={'id': first_task}).status_code == 200
    second_task = _db_row(
        'SELECT assignee,status FROM flow_task WHERE instance_id=? AND step_no=2',
        (instance_id,),
    )
    assert second_task == {'assignee': 1, 'status': 0}
    assert _db_row('SELECT status,current_step FROM flow_instance WHERE id=?', (instance_id,)) == {
        'status': 0, 'current_step': 2,
    }


def test_flow_rejects_fake_or_unsupported_business_links(flow_client):
    flow_id = _add_flow(flow_client)
    missing = flow_client.post('/api/flow/instance/submit', json={
        'flow_id': flow_id, 'title': '不存在', 'biz_type': 'workorder', 'biz_id': 99999,
    })
    assert missing.status_code == 404
    inbound = flow_client.post('/api/flow/instance/submit', json={
        'flow_id': flow_id, 'title': '错误关联', 'biz_type': 'inbound', 'biz_id': 1,
    })
    assert inbound.status_code == 400


def test_reject_requires_reason_and_cannot_be_replayed(flow_client):
    flow_id = _add_flow(flow_client)
    instance_id = _submit_workorder(flow_client, flow_id).get_json()['data']['id']
    task_id = _db_row('SELECT id FROM flow_task WHERE instance_id=?', (instance_id,))['id']
    _login_as(flow_client, flow_client.approver_id, 'approver')
    assert flow_client.post('/api/flow/task/reject', json={'id': task_id}).status_code == 400
    assert flow_client.post('/api/flow/task/reject', json={
        'id': task_id, 'comment': '资料不完整',
    }).status_code == 200
    assert flow_client.post('/api/flow/task/reject', json={
        'id': task_id, 'comment': '重复驳回',
    }).status_code == 409
    assert _db_row('SELECT status FROM prod_workorder WHERE id=?', (flow_client.workorder_id,))['status'] == 0
