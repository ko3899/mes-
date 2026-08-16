import os
import sqlite3
import sys

import pytest


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)


def _columns(db, table):
    return {row[1] for row in db.execute('PRAGMA table_info(%s)' % table)}


def _legacy_database():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.executescript(
        '''
        CREATE TABLE prod_serial (
            id INTEGER PRIMARY KEY, serial_no TEXT UNIQUE, product_id INTEGER,
            workorder_id INTEGER, status INTEGER DEFAULT 0
        );
        CREATE TABLE prod_task (
            id INTEGER PRIMARY KEY, task_no TEXT UNIQUE, workorder_id INTEGER,
            process_id INTEGER, route_step_id INTEGER, planned_qty REAL,
            completed_qty REAL DEFAULT 0, defect_qty REAL DEFAULT 0,
            status INTEGER DEFAULT 0
        );
        CREATE TABLE prod_workorder (id INTEGER PRIMARY KEY, order_no TEXT);
        CREATE TABLE prod_workorder_route_step (
            id INTEGER PRIMARY KEY, process_id INTEGER, process_name TEXT
        );
        CREATE TABLE prod_report (
            id INTEGER PRIMARY KEY, task_id INTEGER, workorder_id INTEGER,
            defect_qty REAL DEFAULT 0, approval_status INTEGER DEFAULT 0
        );
        CREATE TABLE iot_machine_request (
            id INTEGER PRIMARY KEY, endpoint_id INTEGER, sn TEXT,
            workorder_id INTEGER, task_id INTEGER, route_step_id INTEGER,
            decision TEXT, report_status TEXT
        );
        CREATE TABLE iot_inspection_report (
            id INTEGER PRIMARY KEY, request_id INTEGER, endpoint_id INTEGER,
            sn TEXT, result TEXT, prod_report_id INTEGER, import_status TEXT
        );
        CREATE TABLE prod_station_record (
            id INTEGER PRIMARY KEY, flow_id INTEGER, sn TEXT, station TEXT,
            action TEXT, result TEXT
        );
        INSERT INTO prod_serial(id,serial_no,product_id,workorder_id)
            VALUES(1,'NG-SN-001',2,40);
        INSERT INTO prod_task(id,task_no,workorder_id,process_id,route_step_id,planned_qty)
            VALUES(10,'TASK-10',40,3,30,2);
        INSERT INTO prod_workorder(id,order_no) VALUES(40,'WO-40');
        INSERT INTO prod_workorder_route_step(id,process_id,process_name)
            VALUES(30,3,'检测');
        INSERT INTO prod_report(id,task_id,workorder_id,defect_qty,approval_status)
            VALUES(13,10,40,1,2);
        INSERT INTO iot_machine_request
            (id,endpoint_id,sn,workorder_id,task_id,route_step_id,decision,report_status)
            VALUES(20,5,'NG-SN-001',40,10,30,'L1','received');
        INSERT INTO iot_inspection_report
            (id,request_id,endpoint_id,sn,result,prod_report_id,import_status)
            VALUES(4,20,5,'NG-SN-001','NG',13,'imported');
        '''
    )
    return db


def test_migration_is_idempotent_and_backfills_existing_ng():
    from services.quality_disposition import create_quality_disposition_tables

    db = _legacy_database()
    create_quality_disposition_tables(db)
    create_quality_disposition_tables(db)

    assert 'quality_status' in _columns(db, 'prod_serial')
    assert {
        'task_type', 'source_task_id', 'quality_disposition_id', 'target_sn'
    } <= _columns(db, 'prod_task')
    assert 'quality_disposition_id' in _columns(db, 'prod_station_record')

    disposition = db.execute(
        "SELECT * FROM prod_quality_disposition WHERE inspection_report_id=4"
    ).fetchone()
    assert disposition['disposition_no'] == 'QD-BACKFILL-4'
    assert disposition['sn'] == 'NG-SN-001'
    assert disposition['status'] == 'pending_review'
    assert disposition['source_task_id'] == 10
    assert disposition['route_step_id'] == 30
    assert db.execute(
        "SELECT quality_status FROM prod_serial WHERE serial_no='NG-SN-001'"
    ).fetchone()[0] == 'quality_hold'
    assert db.execute(
        'SELECT COUNT(*) FROM prod_quality_disposition'
    ).fetchone()[0] == 1

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            '''INSERT INTO prod_quality_disposition
               (disposition_no,sn,workorder_id,source_task_id,route_step_id,status)
               VALUES('QD-DUP','NG-SN-001',40,10,30,'approved')'''
        )


def test_migration_supports_default_sqlite_tuple_rows():
    from services.quality_disposition import create_quality_disposition_tables

    db = _legacy_database()
    db.row_factory = None
    create_quality_disposition_tables(db)
    assert db.execute('SELECT COUNT(*) FROM prod_quality_disposition').fetchone()[0] == 1
