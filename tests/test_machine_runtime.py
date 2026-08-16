import hashlib
import hmac
import os
from pathlib import Path
import socket
import sqlite3
import sys
import time


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PROJECT_ROOT / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from machine_runtime import MachineCommunicationRuntime  # noqa: E402
from utils import database  # noqa: E402


def wait_until(check, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError('timed out waiting for machine communication runtime')


def scalar(db_path, sql, params=()):
    db = sqlite3.connect(db_path)
    try:
        row = db.execute(sql, params).fetchone()
        return row[0] if row else None
    finally:
        db.close()


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def make_runtime_db(db_path, input_dir, port, monkeypatch):
    monkeypatch.setattr(database, 'DB_PATH', str(db_path))
    database.init_db(); database._init_extra_tables(); database._create_indexes()
    db = sqlite3.connect(db_path)
    equipment = db.execute(
        "INSERT INTO eqp_ledger(equipment_name,code,status) VALUES('运行时测试机','RUNTIME-AIM',1)"
    ).lastrowid
    process = db.execute(
        "INSERT INTO base_process(process_name,code,status) VALUES('运行时检测','RUNTIME-PROC',1)"
    ).lastrowid
    product = db.execute(
        "INSERT INTO base_product(product_name,code,unit) VALUES('运行时产品','RUNTIME-PD','个')"
    ).lastrowid
    workorder = db.execute(
        "INSERT INTO prod_workorder(order_no,product_id,planned_qty,status) VALUES('RUNTIME-WO',?,1,1)",
        (product,),
    ).lastrowid
    snapshot = db.execute(
        "INSERT INTO prod_workorder_route_snapshot(workorder_id,route_name,product_id,workshop_id) VALUES(?,'运行时路线',?,1)",
        (workorder, product),
    ).lastrowid
    step = db.execute(
        "INSERT INTO prod_workorder_route_step(snapshot_id,process_id,process_name,workshop_id,step_no) VALUES(?,?,'运行时检测',1,1)",
        (snapshot, process),
    ).lastrowid
    db.execute(
        "INSERT INTO prod_task(task_no,workorder_id,process_id,route_step_id,planned_qty,status) VALUES('RUNTIME-TASK',?,?,?,?,1)",
        (workorder, process, step, 1),
    )
    db.execute(
        'INSERT INTO prod_serial(serial_no,product_id,workorder_id,status) VALUES(?,?,?,0)',
        ('RUNTIME-SN', product, workorder),
    )
    endpoint_id = db.execute(
        '''INSERT INTO iot_machine_endpoint
           (equipment_id,protocol_version,bind_ip,allowed_remote_ip,listen_port,station_code,
            process_id,cavity_code,encoding,timeout_ms,heartbeat_seconds,laser_template,
            inspection_template,shared_secret,csv_input_dir,csv_stable_seconds,enabled)
           VALUES(?,2,'127.0.0.1','127.0.0.1',?,'RUNTIME-ST',?,'C1','utf-8',1000,5,
                  'RUNTIME-LASER','RUNTIME-CCD','runtime-secret',?,1,1)''',
        (equipment, port, process, str(input_dir)),
    ).lastrowid
    db.commit(); db.close()
    return endpoint_id


def test_real_runtime_socket_csv_event_and_single_instance(tmp_path, monkeypatch):
    db_path = tmp_path / 'runtime.db'
    input_dir = tmp_path / 'input'; input_dir.mkdir()
    archive = tmp_path / 'archive'
    port = free_port()
    endpoint_id = make_runtime_db(db_path, input_dir, port, monkeypatch)
    runtime = MachineCommunicationRuntime(db_path, archive, scan_interval=0.2)
    contender = MachineCommunicationRuntime(db_path, archive, scan_interval=0.2)
    try:
        assert runtime.start() is True
        assert contender.start() is False
        wait_until(lambda: scalar(
            db_path,
            "SELECT listener_status='listening' FROM iot_machine_endpoint WHERE id=?",
            (endpoint_id,),
        ))
        unsigned = 'REQ|2|RUNTIME-AIM|RUNTIME-ST|C1|RUNTIME-REQ|RUNTIME-SN'
        signature = hmac.new(
            b'runtime-secret', unsigned.encode(), hashlib.sha256
        ).hexdigest()
        with socket.create_connection(('127.0.0.1', port), timeout=2) as client:
            client.sendall((unsigned + '|' + signature + '\r\n').encode())
            assert b'|RUNTIME-REQ|L1|OK|' in client.makefile('rb').readline()
        assert scalar(
            db_path,
            "SELECT COUNT(*) FROM iot_machine_request WHERE session_id IS NOT NULL AND decision='L1'",
        ) == 1
        (input_dir / 'runtime.csv').write_text(
            '2D Barcode,Date,Time,OK(1)/NG(0),WIDTH\n'
            'RUNTIME-SN,2026/8/13,20:00:01,OK,12.5\n',
            encoding='utf-8',
        )
        wait_until(lambda: scalar(
            db_path,
            "SELECT COUNT(*) FROM iot_inspection_report WHERE import_status='imported'",
        ) == 1)
        assert scalar(db_path, 'SELECT COUNT(*) FROM iot_device_event') == 1
        assert scalar(
            db_path, "SELECT COUNT(*) FROM iot_aim_event_outbox WHERE status='dispatched'"
        ) == 1
        assert len(list(archive.rglob('*.csv'))) == 1
    finally:
        contender.stop()
        runtime.stop()
    assert scalar(
        db_path, "SELECT status='stopped' FROM iot_machine_runtime WHERE component='csv_collector'"
    ) == 1
    assert scalar(
        db_path, 'SELECT listener_pid IS NULL FROM iot_machine_endpoint WHERE id=?',
        (endpoint_id,),
    ) == 1
