import datetime
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
from blueprints import sys_ext  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    path = tmp_path / 'user-tenant.db'
    monkeypatch.setattr(database, 'DB_PATH', str(path))
    database.init_db()
    database._init_extra_tables()
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    tenant_id = db.execute(
        "INSERT INTO sys_tenant(tenant_name,tenant_code,status) VALUES('测试租户','T-001',1)"
    ).lastrowid
    user_role = db.execute("SELECT id FROM sys_role WHERE role_key='user'").fetchone()[0]
    operator_id = db.execute(
        "INSERT INTO sys_user(username,password,real_name,role_id,tenant_id,status) VALUES(?,?,?,?,?,1)",
        ('operator', hash_password('operator123'), '操作员', user_role, tenant_id),
    ).lastrowid
    db.commit()
    db.close()
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY='user-tenant-test')
    test_client = app.test_client()
    test_client.db_path = str(path)
    test_client.tenant_id = tenant_id
    test_client.operator_id = operator_id
    return test_client


def set_session(client, user_id, username):
    with client.session_transaction() as current:
        current['user_id'] = user_id
        current['username'] = username


def test_disabled_and_deleted_sessions_are_rejected(client):
    set_session(client, client.operator_id, 'operator')
    db = sqlite3.connect(client.db_path)
    db.execute('UPDATE sys_user SET status=0 WHERE id=?', (client.operator_id,))
    db.commit()
    assert client.get('/api/user/info').status_code == 403
    db.execute('DELETE FROM sys_user WHERE id=?', (client.operator_id,))
    db.commit()
    db.close()
    assert client.get('/api/user/info').status_code == 401


def test_tenant_mutations_are_admin_only_and_bound_tenant_cannot_delete(client):
    set_session(client, client.operator_id, 'operator')
    assert client.post('/api/tenant/add', json={
        'tenant_name': 'blocked', 'tenant_code': 'BLOCKED',
    }).status_code == 403

    set_session(client, 1, 'admin')
    response = client.post('/api/tenant/delete', json={'id': client.tenant_id})
    assert response.status_code == 409


def test_user_defaults_and_reference_validation(client):
    set_session(client, 1, 'admin')
    created = client.post('/api/sys/user/add', json={
        'username': 'new-user', 'password': 'password123',
    })
    assert created.status_code == 200
    new_id = created.get_json()['data']['id']
    db = sqlite3.connect(client.db_path)
    db.row_factory = sqlite3.Row
    row = db.execute('SELECT role_id FROM sys_user WHERE id=?', (new_id,)).fetchone()
    user_role = db.execute("SELECT id FROM sys_role WHERE role_key='user'").fetchone()['id']
    assert row['role_id'] == user_role
    db.close()
    assert client.post('/api/sys/user/update', json={
        'id': new_id, 'username': 'renamed', 'role_id': 999999,
    }).status_code == 400
    db = sqlite3.connect(client.db_path)
    username = db.execute('SELECT username FROM sys_user WHERE id=?', (new_id,)).fetchone()[0]
    db.close()
    assert username == 'new-user'


def test_online_activity_is_refreshed_and_logout_removes_entry(client):
    sys_ext._online_users.clear()
    set_session(client, client.operator_id, 'operator')
    assert client.get('/api/user/info').status_code == 200
    assert str(client.operator_id) in sys_ext._online_users
    before = sys_ext._online_users[str(client.operator_id)]['last_active']
    sys_ext._online_users[str(client.operator_id)]['last_active'] = before - datetime.timedelta(minutes=31)
    assert client.get('/api/user/info').status_code == 200
    assert sys_ext._online_users[str(client.operator_id)]['last_active'] > before - datetime.timedelta(minutes=1)
    assert client.post('/api/logout').status_code == 200
    assert str(client.operator_id) not in sys_ext._online_users


def test_disabled_role_cannot_pass_permission_check(client):
    db = sqlite3.connect(client.db_path)
    role_id = db.execute("SELECT id FROM sys_role WHERE role_key='user'").fetchone()[0]
    db.execute("UPDATE sys_role SET menu_ids='perm.read', status=0 WHERE id=?", (role_id,))
    db.commit()
    db.close()
    set_session(client, client.operator_id, 'operator')
    from utils.helpers import permission_required
    @permission_required('perm.read')
    def protected():
        return 'ok'
    with client.application.test_request_context('/'):
        from flask import session as flask_session
        flask_session['user_id'] = client.operator_id
        flask_session['username'] = 'operator'
        response = protected()
    assert response[1] == 403
