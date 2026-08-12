import io
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
from services.machine_access import evaluate_access  # noqa: E402
from services.machine_protocol import MachineRequest  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    path = tmp_path / 'machine-api.db'
    archive = tmp_path / 'archive'
    monkeypatch.setattr(database, 'DB_PATH', str(path))
    monkeypatch.setenv('MES_MACHINE_ARCHIVE_DIR', str(archive))
    database.init_db()
    database._init_extra_tables()
    db = sqlite3.connect(path)
    equipment = db.execute("INSERT INTO eqp_ledger(equipment_name,code,status) VALUES('AIM测试机','AIM001',1)").lastrowid
    process = db.execute("INSERT INTO base_process(process_name,code,status) VALUES('扫码检测','P001',1)").lastrowid
    product = db.execute("INSERT INTO base_product(product_name,code,unit) VALUES('测试产品','PD001','个')").lastrowid
    workorder = db.execute("INSERT INTO prod_workorder(order_no,product_id,planned_qty,status) VALUES('WO001',?,5,1)", (product,)).lastrowid
    snapshot = db.execute("INSERT INTO prod_workorder_route_snapshot(workorder_id,route_name,product_id,workshop_id) VALUES(?,'测试路线',?,1)", (workorder, product)).lastrowid
    step = db.execute("INSERT INTO prod_workorder_route_step(snapshot_id,process_id,process_name,workshop_id,step_no) VALUES(?,?, '扫码检测',1,1)", (snapshot, process)).lastrowid
    task = db.execute("INSERT INTO prod_task(task_no,workorder_id,process_id,route_step_id,planned_qty,status) VALUES('TK001',?,?,?,?,1)", (workorder, process, step, 5)).lastrowid
    db.execute("INSERT INTO prod_serial(serial_no,product_id,workorder_id,status) VALUES('SN001',?,?,0)", (product, workorder))
    db.commit()
    db.close()
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY='machine-api-test')
    test_client = app.test_client()
    with test_client.session_transaction() as session:
        session['user_id'] = 1
        session['username'] = 'admin'
    test_client.ids = {'equipment': equipment, 'process': process, 'task': task}
    return test_client


def save_endpoint(client, **overrides):
    body = {'equipment_id': client.ids['equipment'], 'protocol_version': 2,
            'bind_ip': '127.0.0.1', 'listen_port': 2004, 'station_code': 'ST01',
            'allowed_remote_ip': '127.0.0.1',
            'process_id': client.ids['process'], 'cavity_code': 'C1',
            'encoding': 'utf-8', 'timeout_ms': 1000, 'heartbeat_seconds': 30,
            'enabled': 1, 'shared_secret': 'test-secret',
            'laser_template': 'LASER-T1', 'inspection_template': 'CCD-T1'}
    body.update(overrides)
    return client.post('/api/iot/machine/endpoints/save', json=body)


def test_endpoint_crud_enriches_equipment_and_process_and_validates_port(client):
    bad = save_endpoint(client, listen_port=70000)
    assert bad.status_code == 400
    saved = save_endpoint(client)
    assert saved.status_code == 200
    endpoint_id = saved.get_json()['data']['id']
    listing = client.get('/api/iot/machine/endpoints').get_json()['data']['list']
    assert listing[0]['equipment_name'] == 'AIM测试机'
    assert listing[0]['device_code'] == 'AIM001'
    assert listing[0]['process_name'] == '扫码检测'
    assert listing[0]['allowed_remote_ip'] == '127.0.0.1'
    assert 'shared_secret' not in listing[0]
    duplicate = save_endpoint(client)
    assert duplicate.status_code == 409
    address_conflict = save_endpoint(client, station_code='ST02', cavity_code='C2')
    assert address_conflict.status_code == 409
    toggled = client.post(f'/api/iot/machine/endpoints/{endpoint_id}/toggle', json={'enabled': 0})
    assert toggled.get_json()['data']['enabled'] == 0


def test_v1_requires_remote_ip_and_v2_requires_shared_secret(client):
    assert save_endpoint(client, protocol_version=1, allowed_remote_ip='').status_code == 400
    assert save_endpoint(client, protocol_version=2, shared_secret='').status_code == 400


def test_csv_directory_must_be_absolute_unique_and_stable_seconds_bounded(client, tmp_path):
    assert save_endpoint(client, csv_input_dir='relative/results').status_code == 400
    assert save_endpoint(client, csv_input_dir=str(tmp_path / 'aim'), csv_stable_seconds=0).status_code == 400
    saved = save_endpoint(client, csv_input_dir=str(tmp_path / 'aim'), csv_stable_seconds=3)
    assert saved.status_code == 200
    data = saved.get_json()['data']
    assert data['csv_input_dir'] == str((tmp_path / 'aim').resolve())
    assert data['csv_stable_seconds'] == 3
    assert data['csv_directory_exists'] is False
    duplicate = save_endpoint(
        client, bind_ip='127.0.0.2', listen_port=2005, station_code='ST02',
        cavity_code='C2', csv_input_dir=str(tmp_path / 'aim'), csv_stable_seconds=3,
    )
    assert duplicate.status_code == 409


def test_request_report_lists_health_and_multipart_upload(client):
    endpoint_id = save_endpoint(client).get_json()['data']['id']
    db = sqlite3.connect(database.DB_PATH)
    db.row_factory = sqlite3.Row
    endpoint = dict(db.execute('''SELECT e.*,q.code AS device_code,q.status AS equipment_status
                                  FROM iot_machine_endpoint e JOIN eqp_ledger q ON q.id=e.equipment_id
                                  WHERE e.id=?''', (endpoint_id,)).fetchone())
    decision = evaluate_access(db, endpoint, MachineRequest(2, 'AIM001', 'ST01', 'C1', 'R1', 'SN001'))
    assert decision.decision == 'L1'
    db.close()
    csv_data = ('2D Barcode,Date,Time,OK(1)/NG(0),TP_X1_4\n'
                'SN001,2026/8/12,10:01:02,OK,74.273\n').encode()
    uploaded = client.post('/api/iot/machine/reports/upload', data={
        'endpoint_id': str(endpoint_id), 'file': (io.BytesIO(csv_data), 'SN001.csv')
    }, content_type='multipart/form-data')
    assert uploaded.status_code == 200
    assert uploaded.get_json()['data']['result'] == 'OK'
    requests = client.get('/api/iot/machine/requests?decision=L1').get_json()['data']
    reports = client.get('/api/iot/machine/reports?result=OK').get_json()['data']
    assert requests['total'] == 1
    assert reports['total'] == 1
    health = client.get('/api/iot/machine/health').get_json()['data']
    assert health['enabled_endpoints'] == 1
    assert health['pending_reports'] == 0


def test_machine_api_requires_login(client):
    anonymous = create_app().test_client()
    assert anonymous.get('/api/iot/machine/endpoints').status_code == 401


def test_endpoint_secret_is_write_only_and_blank_edit_keeps_existing(client):
    saved = save_endpoint(client, shared_secret='top-secret').get_json()['data']
    assert saved['shared_secret_configured'] is True
    assert 'shared_secret' not in saved
    edited = save_endpoint(client, id=saved['id'], shared_secret='', station_code='ST01B').get_json()['data']
    assert edited['shared_secret_configured'] is True
    db = sqlite3.connect(database.DB_PATH)
    assert db.execute('SELECT shared_secret FROM iot_machine_endpoint WHERE id=?', (saved['id'],)).fetchone()[0] == 'top-secret'
