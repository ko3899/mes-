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
from blueprints.equipment import _next_maintenance_date  # noqa: E402
from utils import database  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    path = tmp_path / 'equipment-site.db'
    monkeypatch.setattr(database, 'DB_PATH', str(path))
    database.init_db()
    database._init_extra_tables()
    db = sqlite3.connect(path)
    equipment_a = db.execute(
        "INSERT INTO eqp_ledger(equipment_name,code,status) VALUES('设备A','EQ-A',1)"
    ).lastrowid
    equipment_b = db.execute(
        "INSERT INTO eqp_ledger(equipment_name,code,status) VALUES('设备B','EQ-B',1)"
    ).lastrowid
    station = db.execute(
        "INSERT INTO base_workstation(station_name,code,status) VALUES('工位A','ST-A',1)"
    ).lastrowid
    product = db.execute(
        "INSERT INTO base_product(product_name,code,unit) VALUES('产品A','PD-A','个')"
    ).lastrowid
    workorder = db.execute(
        "INSERT INTO prod_workorder(order_no,product_id,planned_qty,status) VALUES('WO-A',?,10,1)",
        (product,),
    ).lastrowid
    db.commit()
    db.close()
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY='equipment-site-test')
    test_client = app.test_client()
    with test_client.session_transaction() as user_session:
        user_session['user_id'] = 1
        user_session['username'] = 'admin'
    test_client.ids = {
        'equipment_a': equipment_a,
        'equipment_b': equipment_b,
        'station': station,
        'workorder': workorder,
    }
    return test_client


def _row(sql, params=()):
    db = sqlite3.connect(database.DB_PATH)
    db.row_factory = sqlite3.Row
    row = db.execute(sql, params).fetchone()
    db.close()
    return dict(row) if row else None


def test_repair_state_machine_updates_equipment_and_is_idempotent(client):
    created = client.post('/api/eqp/repair/add', json={
        'equipment_id': client.ids['equipment_a'], 'fault_desc': '主轴异响',
    })
    assert created.status_code == 200
    repair_id = created.get_json()['data']['id']
    assert _row('SELECT status FROM eqp_ledger WHERE id=?', (client.ids['equipment_a'],))['status'] == 2
    assert client.post('/api/eqp/repair/add', json={
        'equipment_id': client.ids['equipment_a'], 'fault_desc': '重复报修',
    }).status_code == 409
    assert client.post(f'/api/eqp/repair/{repair_id}/start', json={}).status_code == 200
    assert client.post(f'/api/eqp/repair/{repair_id}/start', json={}).status_code == 409
    assert client.post(f'/api/eqp/repair/{repair_id}/complete', json={}).status_code == 400
    assert client.post(f'/api/eqp/repair/{repair_id}/complete', json={
        'repair_desc': '更换轴承，试机正常',
    }).status_code == 200
    assert _row('SELECT status FROM eqp_ledger WHERE id=?', (client.ids['equipment_a'],))['status'] == 1
    assert client.post('/api/eqp/repair/delete', json={'id': repair_id}).status_code == 409


def test_maintenance_derives_equipment_and_uses_calendar_frequency(client):
    plan = client.post('/api/eqp/maintenance/add', json={
        'plan_name': '月度保养', 'equipment_id': client.ids['equipment_a'],
        'frequency': '月', 'next_date': datetime.date.today().isoformat(),
    })
    assert plan.status_code == 200
    plan_id = plan.get_json()['data']['id']
    mismatch = client.post('/api/eqp/check/add', json={
        'plan_id': plan_id, 'equipment_id': client.ids['equipment_b'], 'check_result': '正常',
    })
    assert mismatch.status_code == 409
    checked = client.post('/api/eqp/check/add', json={
        'plan_id': plan_id, 'equipment_id': client.ids['equipment_a'], 'check_result': '正常',
    })
    assert checked.status_code == 200
    record = _row('SELECT equipment_id,status FROM eqp_check_workorder WHERE plan_id=?', (plan_id,))
    assert record == {'equipment_id': client.ids['equipment_a'], 'status': 1}
    assert client.post('/api/eqp/maintenance/delete', json={'id': plan_id}).status_code == 409
    assert _next_maintenance_date(datetime.date(2025, 1, 31), '月') == datetime.date(2025, 2, 28)
    assert _next_maintenance_date(datetime.date(2024, 2, 29), '年') == datetime.date(2025, 2, 28)


def test_andon_validates_and_persists_priority_with_strict_transitions(client):
    invalid = client.post('/api/site/andon/call', json={
        'workstation_id': 9999, 'andon_type': 'quality', 'priority': 2, 'description': '异常',
    })
    assert invalid.status_code == 404
    created = client.post('/api/site/andon/call', json={
        'workstation_id': client.ids['station'], 'andon_type': 'quality',
        'priority': 3, 'description': '尺寸连续超差',
    })
    assert created.status_code == 200
    andon_id = created.get_json()['data']['id']
    assert _row('SELECT priority,status FROM prod_andon WHERE id=?', (andon_id,)) == {
        'priority': 3, 'status': 0,
    }
    duplicate = client.post('/api/site/andon/call', json={
        'workstation_id': client.ids['station'], 'andon_type': 'quality',
        'priority': 1, 'description': '重复呼叫',
    })
    assert duplicate.status_code == 409
    assert client.post('/api/site/andon/resolve', json={'id': andon_id}).status_code == 409
    assert client.post('/api/site/andon/respond', json={'id': andon_id}).status_code == 200
    assert client.post('/api/site/andon/respond', json={'id': andon_id}).status_code == 409
    assert client.post('/api/site/andon/resolve', json={'id': andon_id, 'remark': '已处理'}).status_code == 200
    blocked_delete = client.post('/api/site/workstation/delete', json={'id': client.ids['station']})
    assert blocked_delete.status_code == 409


def test_site_lists_reject_invalid_pagination(client):
    assert client.get('/api/site/andon/list?page=bad').status_code == 400
    assert client.get('/api/site/rework/list?size=none').status_code == 400


def test_rework_maps_disposition_checks_total_and_completes_once(client):
    first = client.post('/api/site/rework/add', json={
        'workorder_id': client.ids['workorder'], 'quantity': 4,
        'disposition': '返工', 'reason': '尺寸超差',
    })
    assert first.status_code == 200
    record_id = first.get_json()['data']['id']
    assert _row('SELECT disposition,quantity FROM prod_rework WHERE id=?', (record_id,)) == {
        'disposition': '返工', 'quantity': 4.0,
    }
    overflow = client.post('/api/site/rework/add', json={
        'workorder_id': client.ids['workorder'], 'quantity': 7,
        'disposition': '报废', 'reason': '不可修复',
    })
    assert overflow.status_code == 409
    assert client.post(f'/api/site/rework/{record_id}/complete', json={}).status_code == 200
    assert client.post(f'/api/site/rework/{record_id}/complete', json={}).status_code == 409
