# -*- coding: utf-8 -*-
"""验证 services 层 BusinessError 被全局 errorhandler 正确映射为业务状态码（而非 500）。"""
import os
import sys
import sqlite3

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

from app import create_app
from services.production_flow import BusinessError as ProdBusinessError
from services.procurement_flow import BusinessError as PurchBusinessError
from utils import database


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(database, 'DB_PATH', str(tmp_path / 't.db'))
    database.init_db()
    database._init_extra_tables()
    conn = sqlite3.connect(str(tmp_path / 't.db'))
    conn.execute(
        "INSERT OR IGNORE INTO sys_role(role_name,role_key,menu_ids,status) "
        "VALUES('超级管理员','admin','',1)"
    )
    role = conn.execute("SELECT id FROM sys_role WHERE role_key='admin'").fetchone()[0]
    conn.execute(
        "INSERT INTO sys_user(username,password,real_name,status,role_id) VALUES('adm','x','A',1,?)",
        (role,),
    )
    conn.commit()
    conn.close()
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY='be-test')

    @app.route('/api/_test/biz-error/production')
    def _prod_err():
        raise ProdBusinessError('任务不存在或未关联冻结路线', 404)

    @app.route('/api/_test/biz-error/procurement')
    def _purch_err():
        raise PurchBusinessError('采购单状态不允许此操作', 409)

    return app.test_client()


def test_production_business_error_maps_to_404(client):
    r = client.get('/api/_test/biz-error/production')
    assert r.status_code == 404
    body = r.get_json()
    assert body['code'] == 404
    assert '任务不存在' in body['message']


def test_procurement_business_error_maps_to_409(client):
    r = client.get('/api/_test/biz-error/procurement')
    assert r.status_code == 409
    body = r.get_json()
    assert body['code'] == 409
    assert '采购单状态' in body['message']
