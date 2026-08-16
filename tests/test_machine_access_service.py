import csv
import io
import os
import sqlite3
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from services.machine_access import (  # noqa: E402
    evaluate_access,
    import_inspection_report,
    record_failed_inspection,
    retry_inspection_report,
)
from services.machine_protocol import MachineRequest  # noqa: E402
from services.quality_disposition import create_quality_disposition_tables  # noqa: E402


def build_db():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.executescript('''
    CREATE TABLE eqp_ledger(id INTEGER PRIMARY KEY, code TEXT, status INTEGER);
    CREATE TABLE prod_serial(id INTEGER PRIMARY KEY, serial_no TEXT UNIQUE, product_id INTEGER, workorder_id INTEGER, status INTEGER DEFAULT 0);
    CREATE TABLE prod_workorder(id INTEGER PRIMARY KEY, order_no TEXT, product_id INTEGER, status INTEGER, planned_qty REAL);
    CREATE TABLE prod_workorder_route_snapshot(id INTEGER PRIMARY KEY, workorder_id INTEGER, product_id INTEGER);
    CREATE TABLE prod_workorder_route_step(id INTEGER PRIMARY KEY, snapshot_id INTEGER, process_id INTEGER, process_name TEXT, step_no INTEGER);
    CREATE TABLE prod_task(id INTEGER PRIMARY KEY, task_no TEXT, workorder_id INTEGER, process_id INTEGER, route_step_id INTEGER, planned_qty REAL, completed_qty REAL DEFAULT 0, defect_qty REAL DEFAULT 0, status INTEGER DEFAULT 0);
    CREATE TABLE prod_transfer(id INTEGER PRIMARY KEY, workorder_id INTEGER, to_route_step_id INTEGER, quantity REAL, status INTEGER);
    CREATE TABLE prod_station_flow(id INTEGER PRIMARY KEY, flow_no TEXT, sn TEXT, product_id INTEGER, workorder_id INTEGER, current_station TEXT, current_process TEXT, status INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE prod_station_record(id INTEGER PRIMARY KEY, flow_id INTEGER, sn TEXT, station TEXT, process_name TEXT, action TEXT, operator INTEGER, result TEXT, remark TEXT, route_step_id INTEGER, machine_request_id INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE prod_report(id INTEGER PRIMARY KEY, report_no TEXT UNIQUE, task_id INTEGER, workorder_id INTEGER, process_id INTEGER, user_id INTEGER, qualified_qty REAL, defect_qty REAL, approval_status INTEGER DEFAULT 0, remark TEXT, client_operation_id TEXT, report_time TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE iot_machine_request(id INTEGER PRIMARY KEY, endpoint_id INTEGER, session_id INTEGER, request_no TEXT, protocol_version INTEGER, station_code TEXT, cavity_code TEXT, sn TEXT, workorder_id INTEGER, task_id INTEGER, route_step_id INTEGER, decision TEXT, reason_code TEXT, reason_message TEXT, laser_template TEXT, inspection_template TEXT, elapsed_ms INTEGER, dedupe_key TEXT UNIQUE, requested_at TEXT DEFAULT CURRENT_TIMESTAMP, responded_at TEXT DEFAULT CURRENT_TIMESTAMP, report_status TEXT DEFAULT 'pending');
    CREATE TABLE iot_inspection_report(id INTEGER PRIMARY KEY, request_id INTEGER, endpoint_id INTEGER, sn TEXT, inspected_at TEXT, result TEXT, original_filename TEXT, archive_path TEXT, file_hash TEXT, import_status TEXT, failure_reason TEXT, retry_count INTEGER DEFAULT 0, prod_report_id INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(endpoint_id,file_hash));
    CREATE TABLE iot_inspection_value(id INTEGER PRIMARY KEY, report_id INTEGER, item_code TEXT, item_name TEXT, measured_value TEXT, unit TEXT, lower_limit REAL, upper_limit REAL, result TEXT);
    ''')
    db.execute("INSERT INTO eqp_ledger VALUES(1,'AIM001',1)")
    db.execute("INSERT INTO prod_workorder VALUES(1,'WO001',10,1,5)")
    db.execute("INSERT INTO prod_serial VALUES(1,'SN001',10,1,0)")
    db.execute("INSERT INTO prod_workorder_route_snapshot VALUES(1,1,10)")
    db.executemany("INSERT INTO prod_workorder_route_step VALUES(?,?,?,?,?)", [
        (101, 1, 11, '扫码检测', 1), (102, 1, 12, '字符检测', 2)])
    db.executemany("INSERT INTO prod_task(id,task_no,workorder_id,process_id,route_step_id,planned_qty,status) VALUES(?,?,?,?,?,?,?)", [
        (201, 'TK1', 1, 11, 101, 5, 1), (202, 'TK2', 1, 12, 102, 5, 1)])
    create_quality_disposition_tables(db)
    db.commit()
    return db


def endpoint(process_id=11, **values):
    data = {'id': 301, 'equipment_id': 1, 'device_code': 'AIM001', 'station_code': 'ST01',
            'process_id': process_id, 'cavity_code': 'C1', 'enabled': 1,
            'equipment_status': 1, 'laser_template': 'LASER-T1', 'inspection_template': 'CCD-T1'}
    data.update(values)
    return data


def request(no='1', sn='SN001', process_id=11):
    return MachineRequest(2, 'AIM001', 'ST01', 'C1', no, sn)


def test_allows_sn_at_first_unfinished_frozen_route_step():
    db = build_db()
    decision = evaluate_access(db, endpoint(), request())
    assert decision.decision == 'L1'
    row = db.execute('SELECT * FROM iot_machine_request').fetchone()
    assert row['task_id'] == 201
    assert row['route_step_id'] == 101


def test_rejects_noread_unknown_sn_disabled_equipment_and_wrong_step():
    cases = [
        (endpoint(), request(sn='NoRead'), 'NO_READ'),
        (endpoint(), request(sn='MISSING'), 'UNKNOWN_SN'),
        (endpoint(enabled=0), request(), 'ENDPOINT_DISABLED'),
        (endpoint(equipment_status=2), request(), 'EQUIPMENT_UNAVAILABLE'),
        (endpoint(process_id=12), request(process_id=12), 'WRONG_STEP'),
    ]
    for ep, req, reason in cases:
        db = build_db()
        decision = evaluate_access(db, ep, req)
        assert decision.decision == 'L3'
        assert decision.reason_code == reason


def test_next_step_requires_previous_sn_pass_record():
    db = build_db()
    assert evaluate_access(db, endpoint(process_id=12), request(process_id=12)).reason_code == 'WRONG_STEP'
    db.execute("INSERT INTO prod_station_flow(id,flow_no,sn,product_id,workorder_id) VALUES(1,'SF1','SN001',10,1)")
    db.execute("INSERT INTO prod_station_record(flow_id,sn,station,process_name,action,result,route_step_id) VALUES(1,'SN001','ST01','扫码检测','过站','PASS',101)")
    db.commit()
    decision = evaluate_access(db, endpoint(process_id=12, station_code='ST02'), MachineRequest(2, 'AIM001', 'ST02', 'C1', '2', 'SN001'))
    assert decision.decision == 'L1'
    assert decision.reason_code == 'OK'


def test_duplicate_request_returns_original_decision_once():
    db = build_db()
    first = evaluate_access(db, endpoint(), request('same'))
    db.execute('UPDATE prod_workorder SET status=6 WHERE id=1')
    db.commit()
    second = evaluate_access(db, endpoint(), request('same'))
    assert second == first
    assert db.execute('SELECT COUNT(*) FROM iot_machine_request').fetchone()[0] == 1


def test_v1_repeat_scan_reuses_outstanding_l1_for_same_sn():
    db = build_db()
    first = evaluate_access(db, endpoint(), MachineRequest(1, 'AIM001', 'ST01', 'C1', 'legacy-1', 'SN001'))
    second = evaluate_access(db, endpoint(), MachineRequest(1, 'AIM001', 'ST01', 'C1', 'legacy-2', 'SN001'))
    assert first == second
    assert db.execute("SELECT COUNT(*) FROM iot_machine_request WHERE decision='L1'").fetchone()[0] == 1


def test_v2_repeat_scan_reuses_pending_step_and_paused_task_is_rejected():
    db = build_db()
    assert evaluate_access(db, endpoint(), request('first')).decision == 'L1'
    assert evaluate_access(db, endpoint(), request('second')).decision == 'L1'
    assert db.execute("SELECT COUNT(*) FROM iot_machine_request WHERE decision='L1'").fetchone()[0] == 1
    db = build_db()
    db.execute('UPDATE prod_task SET status=2 WHERE id=201')
    db.commit()
    assert evaluate_access(db, endpoint(), request()).reason_code == 'TASK_UNAVAILABLE'


def test_v2_requires_processing_templates():
    db = build_db()
    decision = evaluate_access(db, endpoint(laser_template=''), request())
    assert decision.reason_code == 'TEMPLATE_MISSING'


def test_repeated_process_name_is_tracked_by_frozen_route_step_id():
    db = build_db()
    db.execute("UPDATE prod_workorder_route_step SET process_name='重复检测' WHERE id IN (101,102)")
    db.execute("INSERT INTO prod_station_flow(id,flow_no,sn,product_id,workorder_id) VALUES(1,'SF1','SN001',10,1)")
    db.execute("INSERT INTO prod_station_record(flow_id,sn,station,process_name,action,result,route_step_id) VALUES(1,'SN001','ST01','重复检测','过站','PASS',101)")
    db.commit()
    decision = evaluate_access(db, endpoint(process_id=12, station_code='ST02'), MachineRequest(2, 'AIM001', 'ST02', 'C1', 'R2', 'SN001'))
    assert decision.decision == 'L1'
    assert db.execute('SELECT route_step_id FROM iot_machine_request WHERE request_no="R2"').fetchone()[0] == 102


def make_csv(sn='SN001', result='OK'):
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['2D Barcode', 'Date', 'Time', 'OK(1)/NG(0)', 'TP_X1_4', 'TP_X2_4'])
    writer.writerow([sn, '2026/8/12', '10:01:02', result, '74.273', '74.294'])
    return output.getvalue().encode('utf-8-sig')


def test_imports_dynamic_csv_archives_and_creates_pending_report(tmp_path):
    db = build_db()
    evaluate_access(db, endpoint(), request())
    result = import_inspection_report(db, endpoint(), make_csv(), 'SN001.csv', tmp_path)
    assert result['result'] == 'OK'
    assert os.path.exists(result['archive_path'])
    report = db.execute('SELECT * FROM iot_inspection_report').fetchone()
    assert report['import_status'] == 'imported'
    assert db.execute('SELECT COUNT(*) FROM iot_inspection_value').fetchone()[0] == 2
    prod = db.execute('SELECT * FROM prod_report').fetchone()
    assert prod['approval_status'] == 0
    assert prod['qualified_qty'] == 1
    assert db.execute("SELECT COUNT(*) FROM prod_station_record WHERE result='PASS'").fetchone()[0] == 1


def test_ng_report_creates_defect_pending_report_and_no_pass(tmp_path):
    db = build_db()
    evaluate_access(db, endpoint(), request())
    result = import_inspection_report(db, endpoint(), make_csv(result='NG'), 'ng.csv', tmp_path)
    assert result['result'] == 'NG'
    prod = db.execute('SELECT * FROM prod_report').fetchone()
    assert prod['qualified_qty'] == 0
    assert prod['defect_qty'] == 1
    assert db.execute("SELECT COUNT(*) FROM prod_station_record WHERE result='PASS'").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM prod_station_record WHERE result='FAIL'").fetchone()[0] == 1
    disposition = db.execute('SELECT * FROM prod_quality_disposition').fetchone()
    assert disposition['status'] == 'pending_review'
    assert disposition['sn'] == 'SN001'
    assert db.execute(
        "SELECT quality_status FROM prod_serial WHERE serial_no='SN001'"
    ).fetchone()[0] == 'quality_hold'

    duplicate = import_inspection_report(
        db, endpoint(), make_csv(result='NG'), 'same-ng.csv', tmp_path
    )
    assert duplicate['id'] == result['id']
    assert db.execute('SELECT COUNT(*) FROM prod_quality_disposition').fetchone()[0] == 1


def test_quality_held_sn_is_rejected_before_ordinary_task_selection():
    db = build_db()
    db.execute("UPDATE prod_serial SET quality_status='quality_hold' WHERE serial_no='SN001'")
    db.execute(
        '''INSERT INTO prod_quality_disposition
           (disposition_no,sn,workorder_id,source_task_id,route_step_id,status)
           VALUES('QD-HOLD','SN001',1,201,101,'pending_review')'''
    )
    db.commit()
    decision = evaluate_access(db, endpoint(), request('HELD'))
    assert decision.decision == 'L3'
    assert decision.reason_code == 'QUALITY_HOLD'


def test_report_rejects_missing_l1_sn_mismatch_bad_header_and_duplicate(tmp_path):
    db = build_db()
    for payload, message in [
        (make_csv(), '准入'),
        (b'a,b,c\n1,2,3\n', '表头'),
    ]:
        try:
            import_inspection_report(db, endpoint(), payload, 'bad.csv', tmp_path)
            assert False, 'expected ValueError'
        except ValueError as exc:
            assert message in str(exc)
    evaluate_access(db, endpoint(), request())
    try:
        import_inspection_report(db, endpoint(), make_csv('OTHER'), 'other.csv', tmp_path)
        assert False, 'expected mismatch'
    except ValueError as exc:
        assert 'SN' in str(exc)
    first = import_inspection_report(db, endpoint(), make_csv(), 'one.csv', tmp_path)
    second = import_inspection_report(db, endpoint(), make_csv(), 'renamed.csv', tmp_path)
    assert second['id'] == first['id']
    assert db.execute('SELECT COUNT(*) FROM iot_inspection_report').fetchone()[0] == 1


def test_duplicate_report_retries_pending_standard_event(tmp_path):
    db = build_db()
    evaluate_access(db, endpoint(), request())
    attempts = []

    def offline(event):
        attempts.append(event.event_id)
        raise RuntimeError('offline')

    first = import_inspection_report(
        db, endpoint(), make_csv(), 'one.csv', tmp_path, event_sink=offline
    )
    assert attempts == [f'AIM:301:REPORT:{first["id"]}']
    received = []
    second = import_inspection_report(
        db, endpoint(), make_csv(), 'renamed.csv', tmp_path, event_sink=received.append
    )
    assert second['id'] == first['id']
    assert [event.event_id for event in received] == [f'AIM:301:REPORT:{first["id"]}']
    assert db.execute(
        'SELECT status FROM iot_aim_event_outbox WHERE event_id=?',
        (f'AIM:301:REPORT:{first["id"]}',),
    ).fetchone()[0] == 'dispatched'


def test_records_unparseable_report_failure_without_production_side_effects(tmp_path):
    db = build_db()
    failed_dir = tmp_path / 'input' / '_failed'
    failed_dir.mkdir(parents=True)
    failed_path = failed_dir / 'broken.csv'
    failed_path.write_bytes(b'bad,header\n1,2\n')
    row = record_failed_inspection(
        db, endpoint(csv_input_dir=str(tmp_path / 'input')),
        failed_path.read_bytes(), failed_path.name, failed_path, 'CSV表头错误',
    )
    assert row['import_status'] == 'failed'
    assert row['sn'] == 'UNKNOWN'
    assert row['failure_reason'] == 'CSV表头错误'
    assert row['archive_path'] == str(failed_path.resolve())
    assert db.execute('SELECT COUNT(*) FROM prod_report').fetchone()[0] == 0
    duplicate = record_failed_inspection(
        db, endpoint(csv_input_dir=str(tmp_path / 'input')),
        failed_path.read_bytes(), 'renamed.csv', failed_path, '仍然失败',
    )
    assert duplicate['id'] == row['id']


def test_retry_updates_same_failed_report_after_l1_becomes_available(tmp_path):
    db = build_db()
    input_dir = tmp_path / 'input'
    failed_dir = input_dir / '_failed'
    archive = tmp_path / 'archive'
    failed_dir.mkdir(parents=True)
    failed_path = failed_dir / 'SN001.csv'
    failed_path.write_bytes(make_csv())
    failed = record_failed_inspection(
        db, endpoint(csv_input_dir=str(input_dir)), make_csv(), failed_path.name,
        failed_path, '没有对应的L1准入请求',
    )
    evaluate_access(db, endpoint(), request('RETRY-L1'))
    retried = retry_inspection_report(
        db, endpoint(csv_input_dir=str(input_dir)), failed['id'], archive,
    )
    assert retried['id'] == failed['id']
    assert retried['import_status'] == 'imported'
    assert retried['retry_count'] == 1
    assert retried['failure_reason'] is None
    assert not failed_path.exists()
    assert db.execute('SELECT COUNT(*) FROM iot_inspection_report').fetchone()[0] == 1
    assert db.execute('SELECT COUNT(*) FROM prod_report').fetchone()[0] == 1


def test_retry_rejects_report_already_claimed_by_another_worker(tmp_path):
    db = build_db()
    input_dir = tmp_path / 'input'; failed_dir = input_dir / '_failed'; failed_dir.mkdir(parents=True)
    source = failed_dir / 'SN001.csv'; source.write_bytes(make_csv())
    failed = record_failed_inspection(db, endpoint(csv_input_dir=str(input_dir)), make_csv(), source.name, source, '等待')
    db.execute("UPDATE iot_inspection_report SET import_status='retrying' WHERE id=?", (failed['id'],)); db.commit()
    try:
        retry_inspection_report(db, endpoint(csv_input_dir=str(input_dir)), failed['id'], tmp_path / 'archive')
        assert False, 'expected occupied retry rejection'
    except ValueError as exc:
        assert '重试' in str(exc)
