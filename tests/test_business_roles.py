# -*- coding: utf-8 -*-
"""业务角色初始化与权限校验测试。"""
import json
import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

import pytest

from app import create_app
from init_business_roles import BUSINESS_ROLES, init_business_roles
from utils import database


@pytest.fixture()
def db_path(tmp_path):
    path = str(tmp_path / 'roles.db')
    monkey = pytest.MonkeyPatch()
    monkey.setattr(database, 'DB_PATH', path)
    database.init_db()
    database._init_extra_tables()
    init_business_roles(path)
    yield path
    monkey.undo()


@pytest.fixture()
def client(db_path):
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY='roles-test')
    return app.test_client()


def _connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _login(client, user_id, username):
    with client.session_transaction() as s:
        s['user_id'] = user_id
        s['username'] = username


def _mk_user(db_path, role_key, username):
    conn = _connect(db_path)
    role = conn.execute('SELECT id FROM sys_role WHERE role_key=?', (role_key,)).fetchone()
    cur = conn.execute(
        'INSERT INTO sys_user(username,password,real_name,status,role_id) VALUES(?,?,?,1,?)',
        (username, 'x', username, role['id']),
    )
    conn.commit()
    uid = cur.lastrowid
    conn.close()
    return uid


def test_init_business_roles_idempotent(db_path):
    """重复执行不报错、角色数稳定。"""
    init_business_roles(db_path)
    conn = _connect(db_path)
    n = conn.execute('SELECT COUNT(*) FROM sys_role').fetchone()[0]
    keys = {r['role_key'] for r in conn.execute('SELECT role_key FROM sys_role').fetchall()}
    conn.close()
    assert n == 2 + len(BUSINESS_ROLES)  # admin + user + 业务角色
    assert {'planner', 'operator', 'purchaser'} <= keys


def test_role_menu_ids_are_valid_json(db_path):
    """角色 menu_ids 必须是合法 JSON 数组。"""
    conn = _connect(db_path)
    rows = conn.execute('SELECT role_key, menu_ids FROM sys_role').fetchall()
    conn.close()
    for role_key, menu_ids in rows:
        if role_key in ('admin', 'user'):
            continue
        parsed = json.loads(menu_ids)
        assert isinstance(parsed, list), f'{role_key} menu_ids 非法'
        assert parsed, f'{role_key} 无权限'


def test_planner_can_write_plan_but_not_receipt(db_path, client):
    """计划员有 prod:plan:write,无 scm:receipt。"""
    uid = _mk_user(db_path, 'planner', 'plan1')
    _login(client, uid, 'plan1')
    r = client.post('/api/prod/plan/add', json={'x': 1})  # 应被 permission 放行后走业务校验(非403)
    assert r.status_code != 403
    r = client.post('/api/scm/receiving/post', json={})
    assert r.status_code == 403


def test_operator_cannot_review_report(db_path, client):
    """操作工有报工创建,无审核。"""
    uid = _mk_user(db_path, 'operator', 'op1')
    _login(client, uid, 'op1')
    r = client.post('/api/prod/report/1/approve', json={'id': 1})
    assert r.status_code == 403


def test_admin_role_passthrough(db_path, client):
    """admin 角色权限直通。"""
    conn = _connect(db_path)
    role = conn.execute("SELECT id FROM sys_role WHERE role_key='admin'").fetchone()
    cur = conn.execute(
        "INSERT INTO sys_user(username,password,real_name,status,role_id) VALUES('adm1','x','adm',1,?)",
        (role['id'],),
    )
    conn.commit()
    uid = cur.lastrowid
    conn.close()
    _login(client, uid, 'adm1')
    r = client.get('/api/scm/receiving/list')  # 有 admin 角色即使无 scm:read 也应放行
    assert r.status_code == 200
