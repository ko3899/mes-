import os
from pathlib import Path
import sqlite3
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PROJECT_ROOT / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from machine_csv_collector import MachineCsvCollector  # noqa: E402
from services.machine_access import evaluate_access  # noqa: E402
from services.machine_protocol import MachineRequest  # noqa: E402
from utils import database  # noqa: E402


def test_production_entry_starts_and_stops_csv_collector():
    source = (PROJECT_ROOT / 'production.py').read_text(encoding='utf-8')
    assert 'from machine_csv_collector import MachineCsvCollector' in source
    assert 'csv_collector.start()' in source
    assert 'csv_collector.stop()' in source


def test_real_directory_flow_keeps_ok_and_ng_traceability(tmp_path, monkeypatch):
    db_path = tmp_path / 'flow.db'
    input_dir = tmp_path / 'input'; input_dir.mkdir()
    archive = tmp_path / 'archive'
    monkeypatch.setattr(database, 'DB_PATH', str(db_path))
    database.init_db(); database._init_extra_tables()
    db = sqlite3.connect(db_path); db.row_factory = sqlite3.Row
    equipment = db.execute(
        "INSERT INTO eqp_ledger(equipment_name,code,status) VALUES('TEST AIM文件机','TEST-AIM-DEVICE',1)"
    ).lastrowid
    process = db.execute(
        "INSERT INTO base_process(process_name,code,status) VALUES('TEST AIM检测','TEST-AIM-PROC',1)"
    ).lastrowid
    product = db.execute(
        "INSERT INTO base_product(product_name,code,unit) VALUES('TEST AIM产品','TEST-AIM-PD','个')"
    ).lastrowid
    workorder = db.execute(
        "INSERT INTO prod_workorder(order_no,product_id,planned_qty,status) VALUES('TEST-AIM-WO',?,2,1)", (product,)
    ).lastrowid
    snapshot = db.execute(
        "INSERT INTO prod_workorder_route_snapshot(workorder_id,route_name,product_id,workshop_id) VALUES(?,'TEST AIM路线',?,1)",
        (workorder, product),
    ).lastrowid
    step = db.execute(
        "INSERT INTO prod_workorder_route_step(snapshot_id,process_id,process_name,workshop_id,step_no) VALUES(?,?,'TEST AIM检测',1,1)",
        (snapshot, process),
    ).lastrowid
    task = db.execute(
        "INSERT INTO prod_task(task_no,workorder_id,process_id,route_step_id,planned_qty,status) VALUES('TEST-AIM-TASK',?,?,?,?,1)",
        (workorder, process, step, 2),
    ).lastrowid
    for sn in ('TEST-AIM-CSV-OK', 'TEST-AIM-CSV-NG'):
        db.execute('INSERT INTO prod_serial(serial_no,product_id,workorder_id,status) VALUES(?,?,?,0)',
                   (sn, product, workorder))
    endpoint_id = db.execute(
        '''INSERT INTO iot_machine_endpoint
           (equipment_id,protocol_version,bind_ip,allowed_remote_ip,listen_port,station_code,
            process_id,cavity_code,encoding,timeout_ms,heartbeat_seconds,laser_template,
            inspection_template,shared_secret,csv_input_dir,csv_stable_seconds,enabled)
           VALUES(1,2,'127.0.0.1','127.0.0.1',29004,'TEST-AIM-ST',?,'C1','utf-8',1000,30,
                  'TEST-LASER','TEST-CCD','test-secret',?,1,1)'''.replace('VALUES(1,', 'VALUES(?,', 1),
        (equipment, process, str(input_dir)),
    ).lastrowid
    db.commit()
    endpoint = dict(db.execute(
        '''SELECT e.*,q.code AS device_code,q.status AS equipment_status
           FROM iot_machine_endpoint e JOIN eqp_ledger q ON q.id=e.equipment_id WHERE e.id=?''',
        (endpoint_id,),
    ).fetchone())
    for index, sn in enumerate(('TEST-AIM-CSV-OK', 'TEST-AIM-CSV-NG'), 1):
        assert evaluate_access(
            db, endpoint, MachineRequest(2, 'TEST-AIM-DEVICE', 'TEST-AIM-ST', 'C1', f'TEST-REQ-{index}', sn)
        ).decision == 'L1'
    db.close()
    (input_dir / 'ok.csv').write_text(
        '2D Barcode,Date,Time,OK(1)/NG(0),TEST_VALUE\nTEST-AIM-CSV-OK,2026/8/12,16:00:01,OK,1.23\n', encoding='utf-8'
    )
    (input_dir / 'ng.csv').write_text(
        '2D Barcode,Date,Time,OK(1)/NG(0),TEST_VALUE\nTEST-AIM-CSV-NG,2026/8/12,16:00:02,NG,9.99\n', encoding='utf-8'
    )
    clock = [100.0]
    collector = MachineCsvCollector(db_path, archive, now=lambda: clock[0])
    collector.scan_once(); clock[0] = 102.0; summary = collector.scan_once()
    assert summary['imported'] == 2
    db = sqlite3.connect(db_path)
    assert db.execute("SELECT COUNT(*) FROM iot_inspection_report WHERE import_status='imported'").fetchone()[0] == 2
    assert db.execute("SELECT COUNT(*) FROM prod_report WHERE remark LIKE 'AIM机台检测 TEST-AIM-%'").fetchone()[0] == 2
    assert db.execute("SELECT COUNT(*) FROM prod_station_record WHERE sn LIKE 'TEST-AIM-%' AND result='PASS'").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM prod_station_record WHERE sn LIKE 'TEST-AIM-%' AND result='FAIL'").fetchone()[0] == 1
    assert len(list(archive.rglob('*.csv'))) == 2
    db.close()
