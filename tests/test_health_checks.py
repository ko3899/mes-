"""测试 utils.health_checks 的三个健康检查端点。"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

import sqlite3

import pytest

from app import create_app
from utils import database


@pytest.fixture()
def client(tmp_path, monkeypatch):
    path = tmp_path / 'health.db'
    monkeypatch.setattr(database, 'DB_PATH', str(path))
    database.init_db()
    database._init_extra_tables()
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY='health-test')
    return app.test_client()


def test_healthz_returns_ok(client):
    resp = client.get('/healthz')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'ok'
    assert data['service'] == 'mes'
    assert data['db']['status'] == 'ok'
    assert 'latency_ms' in data['db']


def test_readyz_returns_ok(client):
    resp = client.get('/readyz')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'ok'
    assert data['checks']['database']['status'] == 'ok'
    tables = data['checks']['tables']
    assert tables['sys_user'] is True
    assert tables['prod_workorder'] is True
    assert tables['iot_device_event'] is True


def test_full_health_returns_checks(client):
    resp = client.get('/healthz/full')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['service'] == 'mes'
    assert 'database' in data['checks']
    assert 'edge_gateway' in data['checks']
    assert 'machine_endpoints' in data['checks']
    assert 'mqtt_consumer' in data['checks']
    # 初始化后没有失败事件,整体应 ok 或 degraded(无端点时)
    assert data['status'] in ('ok', 'degraded')
