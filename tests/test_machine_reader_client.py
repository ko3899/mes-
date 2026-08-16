import os
import socket
import sqlite3
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PROJECT_ROOT / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from machine_reader_client import _run_connection  # noqa: E402
from services.machine_protocol import AccessDecision, format_response  # noqa: E402
from utils import database  # noqa: E402


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def test_direct_reader_client_reads_idle_framed_sn_and_returns_bare_l1(tmp_path, monkeypatch):
    db_path = tmp_path / 'reader.db'
    monkeypatch.setattr(database, 'DB_PATH', str(db_path))
    database.init_db(); database._init_extra_tables(); database._create_indexes()
    db = sqlite3.connect(db_path)
    equipment = db.execute(
        "INSERT INTO eqp_ledger(equipment_name,code,status) VALUES('直连读码器','READER-AIM',1)"
    ).lastrowid
    process = db.execute(
        "INSERT INTO base_process(process_name,code,status) VALUES('直连检测','READER-PROC',1)"
    ).lastrowid
    product = db.execute(
        "INSERT INTO base_product(product_name,code,unit) VALUES('直连产品','READER-PD','个')"
    ).lastrowid
    workorder = db.execute(
        "INSERT INTO prod_workorder(order_no,product_id,planned_qty,status) VALUES('READER-WO',?,1,1)",
        (product,),
    ).lastrowid
    snapshot = db.execute(
        "INSERT INTO prod_workorder_route_snapshot(workorder_id,route_name,product_id,workshop_id) VALUES(?, '直连路线', ?, 1)",
        (workorder, product),
    ).lastrowid
    step = db.execute(
        "INSERT INTO prod_workorder_route_step(snapshot_id,process_id,process_name,workshop_id,step_no) VALUES(?,?, '直连检测',1,1)",
        (snapshot, process),
    ).lastrowid
    db.execute(
        "INSERT INTO prod_task(task_no,workorder_id,process_id,route_step_id,planned_qty,status) VALUES('READER-TASK',?,?,?,?,1)",
        (workorder, process, step, 1),
    )
    db.execute(
        "INSERT INTO prod_serial(serial_no,product_id,workorder_id,status) VALUES('READER-SN',?,?,0)",
        (product, workorder),
    )
    port = free_port()
    endpoint_id = db.execute(
        '''INSERT INTO iot_machine_endpoint
           (equipment_id,protocol_version,transport_mode,bind_ip,listen_port,reader_ip,reader_port,
            reader_frame_idle_ms,station_code,process_id,cavity_code,encoding,timeout_ms,
            heartbeat_seconds,laser_template,inspection_template,enabled)
           VALUES(?,1,'reader_client','127.0.0.1',2004,'127.0.0.1',?,80,'READER-ST',?,'C1','utf-8',1000,5,NULL,NULL,1)''',
        (equipment, port, process),
    ).lastrowid
    db.commit(); db.close()

    ready = threading.Event()
    received = {}

    def fake_reader():
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(('127.0.0.1', port)); listener.listen(1)
            ready.set()
            connection, _ = listener.accept()
            with connection:
                connection.sendall(b'READER-SN')
                connection.settimeout(3)
                received['response'] = connection.recv(64)

    reader_thread = threading.Thread(target=fake_reader, daemon=True)
    reader_thread.start(); assert ready.wait(2)
    worker = threading.Thread(
        target=_run_connection,
        args=(str(db_path), {
                'id': endpoint_id, 'device_code': 'READER-AIM', 'equipment_status': 1,
                'station_code': 'READER-ST', 'cavity_code': 'C1', 'encoding': 'utf-8',
                'reader_ip': '127.0.0.1', 'reader_port': port, 'reader_frame_idle_ms': 80,
                'enabled': 1, 'protocol_version': 1, 'process_id': process,
        }, os.getpid()),
        daemon=True,
    )
    worker.start(); reader_thread.join(5)
    assert received['response'] == b'<L1>'
    db = sqlite3.connect(db_path)
    assert db.execute("SELECT decision FROM iot_machine_request WHERE sn='READER-SN'").fetchone()[0] == 'L1'
    db.close()
