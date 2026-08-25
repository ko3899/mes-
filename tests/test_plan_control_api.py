"""计划控制模块测试：init 幂等 / list 带出产品与 TOTAL / 增减调整校验 / HTTP 权限。

使用 tmp_path 独立数据库 + admin 角色用户 fixture，风格与 test_receiving_flow.py 一致。
"""
import os
import sqlite3
import sys

import pytest


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from utils import database  # noqa: E402
from services.procurement_flow import BusinessError  # noqa: E402
from services.plan_control_service import (  # noqa: E402
    adjust_plan_control,
    init_plan_control,
    list_plan_control,
)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / 'plan-control.db'
    monkeypatch.setattr(database, 'DB_PATH', str(path))
    database.init_db()
    database._init_extra_tables()
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    yield connection
    connection.close()


@pytest.fixture()
def products(db):
    ids = [
        db.execute(
            'INSERT INTO base_product(product_name, code) VALUES(?,?)',
            ('计划控制产品%d' % index, 'PLC-P%d' % index),
        ).lastrowid
        for index in (1, 2)
    ]
    db.commit()
    return ids


def _set_ok_qty(db, product_id, ok_qty, stage_code=''):
    db.execute(
        '''UPDATE prod_plan_control SET ok_qty=?, updated_at=CURRENT_TIMESTAMP
           WHERE product_id=? AND stage_code=?''',
        (ok_qty, product_id, stage_code),
    )
    db.commit()


def _control_row(db, product_id, stage_code=''):
    return db.execute(
        '''SELECT id, plan_qty, ok_qty, adjust_qty FROM prod_plan_control
           WHERE product_id=? AND stage_code=?''',
        (product_id, stage_code),
    ).fetchone()


# ==================== init 初始化 ====================

def test_init_plan_control_creates_rows_and_is_idempotent(db, products):
    created = init_plan_control(db)
    assert created == 2
    for product_id in products:
        row = _control_row(db, product_id)
        assert row is not None
        assert row['plan_qty'] == 0
        assert row['ok_qty'] == 0

    # 第二次初始化：幂等，不新建
    assert init_plan_control(db) == 0
    assert db.execute(
        'SELECT COUNT(*) AS c FROM prod_plan_control'
    ).fetchone()['c'] == 2


def test_init_plan_control_only_creates_missing_rows(db, products):
    init_plan_control(db)
    # 手动新增一个产品后再初始化
    extra = db.execute(
        "INSERT INTO base_product(product_name,code) VALUES('新物料','PLC-NEW')"
    ).lastrowid
    db.commit()
    assert init_plan_control(db) == 1
    assert _control_row(db, extra) is not None


# ==================== list 列表 ====================

def test_list_plan_control_joins_product_and_totals(db, products):
    init_plan_control(db)
    adjust_plan_control(db, products[0], '', 5, 1)
    adjust_plan_control(db, products[1], '', 10, 1)
    _set_ok_qty(db, products[0], 2)  # balance = 5 - 2 = 3

    result = list_plan_control(db)
    assert result['count'] == 2
    by_product = {row['product_id']: row for row in result['list']}
    first = by_product[products[0]]
    assert first['product_name'] == '计划控制产品1'
    assert first['product_code'] == 'PLC-P1'
    assert first['plan_qty'] == 5
    assert first['ok_qty'] == 2
    assert first['balance_qty'] == 3

    assert result['total']['plan_qty'] == 15
    assert result['total']['ok_qty'] == 2
    assert result['total']['balance_qty'] == 13


def test_list_plan_control_filters_by_product_stage_and_keyword(db, products):
    init_plan_control(db)
    adjust_plan_control(db, products[0], 'DVT', 3, 1)
    adjust_plan_control(db, products[0], 'PVT', 7, 1)
    adjust_plan_control(db, products[1], 'DVT', 9, 1)

    # 按 product_id 过滤（init 生成 '' 行 + DVT/PVT 两行 = 3 行）
    result = list_plan_control(db, product_id=products[0])
    assert result['count'] == 3
    # 按 stage_code 过滤
    result = list_plan_control(db, stage_code='DVT')
    assert result['count'] == 2
    # 按 keyword（产品名/料号）过滤：PLC-P2 有两个阶段行（'' 与 DVT）
    result = list_plan_control(db, keyword='PLC-P2')
    assert result['count'] == 2
    assert result['list'][0]['product_code'] == 'PLC-P2'
    # 产品1 有 3 行（'' + DVT + PVT）
    result = list_plan_control(db, keyword='产品1')
    assert result['count'] == 3


# ==================== adjust 正常调整 ====================

def test_adjust_increase_updates_plan_qty(db, products):
    init_plan_control(db)
    row = adjust_plan_control(db, products[0], '', 5, 1)
    assert row['plan_qty'] == 5
    assert row['adjust_qty'] == 5
    assert row['balance_qty'] == 5

    # 再次增加：累加
    row = adjust_plan_control(db, products[0], '', 3, 1)
    assert row['plan_qty'] == 8
    assert row['adjust_qty'] == 3

    # 减少：计划数量下降、余量随之变化
    _set_ok_qty(db, products[0], 5)
    row = adjust_plan_control(db, products[0], '', -2, 1)
    assert row['plan_qty'] == 6
    assert row['adjust_qty'] == -2
    assert row['balance_qty'] == 1


def test_adjust_creates_row_on_the_fly_for_unknown_stage(db, products):
    # 未 init 时直接对某阶段码调整，自动创建行
    row = adjust_plan_control(db, products[0], 'DVT', 12, 1)
    assert row['plan_qty'] == 12
    assert row['stage_code'] == 'DVT'
    assert _control_row(db, products[0], 'DVT') is not None


# ==================== adjust 校验规则 ====================

def test_adjust_increase_over_nine_digits_rejected(db, products):
    init_plan_control(db)
    adjust_plan_control(db, products[0], '', 999999999, 1)
    with pytest.raises(BusinessError, match='超过9位数'):
        adjust_plan_control(db, products[0], '', 1, 1)
    # 回滚：计划数量保持原值，adjust_qty 不被污染
    row = _control_row(db, products[0])
    assert row['plan_qty'] == 999999999
    assert row['adjust_qty'] == 999999999


def test_adjust_decrease_beyond_balance_rejected(db, products):
    init_plan_control(db)
    adjust_plan_control(db, products[0], '', 10, 1)
    _set_ok_qty(db, products[0], 4)  # balance = 10 - 4 = 6
    with pytest.raises(BusinessError, match='余量'):
        adjust_plan_control(db, products[0], '', -7, 1)
    row = _control_row(db, products[0])
    assert row['plan_qty'] == 10
    assert row['ok_qty'] == 4
    assert row['adjust_qty'] == 10


def test_adjust_zero_rejected(db, products):
    init_plan_control(db)
    with pytest.raises(BusinessError, match='不能为0'):
        adjust_plan_control(db, products[0], '', 0, 1)
    row = _control_row(db, products[0])
    assert row is not None
    assert row['plan_qty'] == 0


def test_adjust_unknown_product_rejected(db):
    with pytest.raises(BusinessError, match='产品不存在'):
        adjust_plan_control(db, 999999, '', 5, 1)


# ==================== HTTP 权限 ====================

@pytest.fixture()
def http_env(tmp_path, monkeypatch):
    path = tmp_path / 'plan-control-http.db'
    monkeypatch.setattr(database, 'DB_PATH', str(path))
    database.init_db()
    database._init_extra_tables()
    db = sqlite3.connect(path)
    # admin 角色：init_db 已种子 role_key='admin'，INSERT OR IGNORE 仅为兜底
    db.execute(
        """INSERT OR IGNORE INTO sys_role(role_name,role_key,description,menu_ids,status)
           VALUES('超级管理员','admin','拥有所有权限','',1)"""
    )
    admin_role_id = db.execute(
        "SELECT id FROM sys_role WHERE role_key='admin'"
    ).fetchone()[0]
    # init_db 已种子 admin 用户，INSERT OR IGNORE 兜底，再确保绑定管理员角色
    db.execute(
        """INSERT OR IGNORE INTO sys_user(username,password,real_name,role_id,tenant_id,status)
           VALUES('admin','x','管理员',?,1,1)""",
        (admin_role_id,),
    )
    db.execute(
        "UPDATE sys_user SET role_id=? WHERE username='admin'",
        (admin_role_id,),
    )
    admin_id = db.execute(
        "SELECT id FROM sys_user WHERE username='admin'"
    ).fetchone()[0]
    # 计划员角色：不含任何 plan:control:* 权限，用于验证 403
    db.execute(
        """INSERT INTO sys_role(role_name,role_key,description,menu_ids,status)
           VALUES('计划员','planner','计划操作','[]',1)"""
    )
    planner_role_id = db.execute(
        "SELECT id FROM sys_role WHERE role_key='planner'"
    ).fetchone()[0]
    db.execute(
        """INSERT INTO sys_user(username,password,real_name,role_id,tenant_id,status)
           VALUES('planner','x','计划员',?,1,1)""",
        (planner_role_id,),
    )
    planner_id = db.execute(
        "SELECT id FROM sys_user WHERE username='planner'"
    ).fetchone()[0]
    product_id = db.execute(
        "INSERT INTO base_product(product_name,code) VALUES('HTTP产品','PLC-HTTP')"
    ).lastrowid
    db.commit()
    db.close()

    from app import create_app
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY='plan-control-test')
    return app, admin_id, planner_id, product_id


def _login(client, user_id, username):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['username'] = username


def test_plan_control_endpoints_without_permission_return_403(http_env):
    app, admin_id, planner_id, product_id = http_env
    client = app.test_client()
    _login(client, planner_id, 'planner')

    response = client.get('/api/prod/plan-control/list')
    assert response.status_code == 403
    assert response.get_json()['code'] == 403

    response = client.post('/api/prod/plan-control/adjust', json={
        'product_id': product_id, 'stage_code': '', 'adjust_qty': 5,
    })
    assert response.status_code == 403
    assert response.get_json()['code'] == 403

    response = client.post('/api/prod/plan-control/init', json={})
    assert response.status_code == 403
    assert response.get_json()['code'] == 403


def test_admin_can_init_list_and_adjust(http_env):
    app, admin_id, planner_id, product_id = http_env
    client = app.test_client()
    _login(client, admin_id, 'admin')

    response = client.post('/api/prod/plan-control/init', json={})
    assert response.status_code == 200
    assert response.get_json()['code'] == 0
    assert response.get_json()['data']['created'] == 1

    response = client.post('/api/prod/plan-control/adjust', json={
        'product_id': product_id, 'stage_code': 'DVT', 'adjust_qty': 8,
    })
    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['plan_qty'] == 8
    assert data['balance_qty'] == 8
    assert data['product_name'] == 'HTTP产品'

    response = client.get('/api/prod/plan-control/list?stage_code=DVT')
    assert response.status_code == 200
    body = response.get_json()
    assert body['code'] == 0
    assert body['data']['count'] == 1
    assert body['data']['total']['plan_qty'] == 8


def test_adjust_zero_via_http_returns_400(http_env):
    app, admin_id, planner_id, product_id = http_env
    client = app.test_client()
    _login(client, admin_id, 'admin')

    response = client.post('/api/prod/plan-control/adjust', json={
        'product_id': product_id, 'stage_code': '', 'adjust_qty': 0,
    })
    assert response.status_code == 400
    assert response.get_json()['code'] == 400
    assert '不能为0' in response.get_json()['message']
