import os
import sqlite3
import sys

import pytest


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from services.quality_disposition import (  # noqa: E402
    approve_disposition,
    create_quality_disposition_tables,
    reject_disposition,
    validate_rework_task_start,
)
from services.production_flow import post_report  # noqa: E402


def build_db(sn='SN-RW'):
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.executescript(
        '''
        CREATE TABLE prod_serial(id INTEGER PRIMARY KEY,serial_no TEXT UNIQUE,product_id INTEGER,workorder_id INTEGER,status INTEGER DEFAULT 0);
        CREATE TABLE prod_workorder(id INTEGER PRIMARY KEY,order_no TEXT,product_id INTEGER,status INTEGER,planned_qty REAL,completed_qty REAL DEFAULT 0,defect_qty REAL DEFAULT 0,updated_at TEXT);
        CREATE TABLE prod_workorder_route_step(id INTEGER PRIMARY KEY,process_id INTEGER,process_name TEXT);
        CREATE TABLE prod_task(id INTEGER PRIMARY KEY,task_no TEXT UNIQUE,workorder_id INTEGER,process_id INTEGER,route_step_id INTEGER,planned_qty REAL,completed_qty REAL DEFAULT 0,defect_qty REAL DEFAULT 0,status INTEGER DEFAULT 0,start_time TEXT,end_time TEXT,remark TEXT);
        CREATE TABLE prod_report(id INTEGER PRIMARY KEY,report_no TEXT UNIQUE,task_id INTEGER,workorder_id INTEGER,process_id INTEGER,user_id INTEGER,qualified_qty REAL,defect_qty REAL,approval_status INTEGER,posted_at TEXT);
        CREATE TABLE sys_business_status_log(id INTEGER PRIMARY KEY,entity_type TEXT,entity_id INTEGER,from_status INTEGER,to_status INTEGER,action TEXT,operator_id INTEGER,remark TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE iot_machine_request(id INTEGER PRIMARY KEY,endpoint_id INTEGER,sn TEXT,station_code TEXT,workorder_id INTEGER,task_id INTEGER,route_step_id INTEGER,decision TEXT,report_status TEXT);
        CREATE TABLE iot_inspection_report(id INTEGER PRIMARY KEY,request_id INTEGER,endpoint_id INTEGER,sn TEXT,result TEXT,prod_report_id INTEGER,import_status TEXT);
        CREATE TABLE prod_station_flow(id INTEGER PRIMARY KEY,flow_no TEXT UNIQUE,sn TEXT,product_id INTEGER,workorder_id INTEGER,current_station TEXT,current_process TEXT,status INTEGER DEFAULT 0);
        CREATE TABLE prod_station_record(id INTEGER PRIMARY KEY,flow_id INTEGER,sn TEXT,station TEXT,process_name TEXT,action TEXT,operator INTEGER,result TEXT,remark TEXT,route_step_id INTEGER,machine_request_id INTEGER);
        INSERT INTO prod_serial VALUES(1,'SN-RW',2,40,0);
        INSERT INTO prod_workorder(id,order_no,product_id,status,planned_qty,completed_qty,defect_qty)
            VALUES(40,'WO-40',2,2,2,1,1);
        INSERT INTO prod_workorder_route_step VALUES(30,3,'AIM检测');
        INSERT INTO prod_task(id,task_no,workorder_id,process_id,route_step_id,planned_qty,completed_qty,defect_qty,status)
            VALUES(10,'TASK-10',40,3,30,2,1,1,1);
        INSERT INTO prod_report(id,report_no,task_id,workorder_id,process_id,user_id,qualified_qty,defect_qty,approval_status)
            VALUES(13,'REPORT-NG',10,40,3,1,0,1,2);
        INSERT INTO iot_machine_request VALUES(20,5,'SN-RW','AIM-01',40,10,30,'L1','received');
        INSERT INTO iot_inspection_report VALUES(4,20,5,'SN-RW','NG',13,'imported');
        '''
    )
    create_quality_disposition_tables(db)
    db.commit()
    return db


def test_rework_approval_is_idempotent_and_requires_explicit_start():
    db = build_db()
    disposition_id = db.execute('SELECT id FROM prod_quality_disposition').fetchone()[0]
    approved = approve_disposition(db, disposition_id, 'rework', 7, '可返修')
    repeated = approve_disposition(db, disposition_id, 'rework', 7, '重复请求')
    assert repeated['rework_task_id'] == approved['rework_task_id']
    task = db.execute('SELECT * FROM prod_task WHERE id=?', (approved['rework_task_id'],)).fetchone()
    assert task['task_no'] == 'RW-QD-BACKFILL-4'
    assert task['task_type'] == 'rework'
    assert task['source_task_id'] == 10
    assert task['target_sn'] == 'SN-RW'
    assert task['planned_qty'] == 1
    assert task['status'] == 0
    assert db.execute("SELECT quality_status FROM prod_serial WHERE id=1").fetchone()[0] == 'rework'
    assert validate_rework_task_start(db, task['id'])['id'] == task['id']
    assert db.execute("SELECT COUNT(*) FROM prod_task WHERE task_type='rework'").fetchone()[0] == 1


@pytest.mark.parametrize('action,expected_status', [
    ('scrap', 'scrapped'),
    ('concession', 'concession'),
])
def test_terminal_dispositions_update_sn_and_concession_creates_one_pass(action, expected_status):
    db = build_db()
    disposition_id = db.execute('SELECT id FROM prod_quality_disposition').fetchone()[0]
    approve_disposition(db, disposition_id, action, 7, '审核处置')
    approve_disposition(db, disposition_id, action, 7, '重复请求')
    assert db.execute("SELECT quality_status FROM prod_serial WHERE id=1").fetchone()[0] == expected_status
    pass_count = db.execute(
        "SELECT COUNT(*) FROM prod_station_record WHERE result='PASS'"
    ).fetchone()[0]
    assert pass_count == (1 if action == 'concession' else 0)


def test_reject_keeps_hold_and_decided_disposition_cannot_be_changed():
    db = build_db()
    disposition_id = db.execute('SELECT id FROM prod_quality_disposition').fetchone()[0]
    rejected = reject_disposition(db, disposition_id, 7, '误上传')
    assert rejected['status'] == 'rejected'
    assert db.execute("SELECT quality_status FROM prod_serial WHERE id=1").fetchone()[0] == 'quality_hold'
    with pytest.raises(ValueError):
        approve_disposition(db, disposition_id, 'scrap', 7, '不能再审批')


def test_posted_rework_ok_completes_source_without_erasing_defect_history():
    db = build_db()
    disposition_id = db.execute('SELECT id FROM prod_quality_disposition').fetchone()[0]
    approved = approve_disposition(db, disposition_id, 'rework', 7, '返工')
    rework_task_id = approved['rework_task_id']
    db.execute('UPDATE prod_task SET status=1 WHERE id=?', (rework_task_id,))
    db.execute(
        "UPDATE prod_quality_disposition SET status='task_started' WHERE id=?",
        (disposition_id,),
    )
    report_id = db.execute(
        '''INSERT INTO prod_report
           (report_no,task_id,workorder_id,process_id,user_id,qualified_qty,defect_qty,approval_status)
           VALUES('REPORT-RW-OK',?,40,3,1,1,0,1)''',
        (rework_task_id,),
    ).lastrowid
    db.commit()
    post_report(db, report_id, 7)
    rework = db.execute('SELECT completed_qty,defect_qty,status FROM prod_task WHERE id=?', (rework_task_id,)).fetchone()
    source = db.execute('SELECT completed_qty,defect_qty,status FROM prod_task WHERE id=10').fetchone()
    workorder = db.execute('SELECT completed_qty,defect_qty FROM prod_workorder WHERE id=40').fetchone()
    disposition = db.execute('SELECT status FROM prod_quality_disposition WHERE id=?', (disposition_id,)).fetchone()
    assert tuple(rework) == (1, 0, 3)
    assert tuple(source) == (2, 1, 3)
    assert tuple(workorder) == (2, 1)
    assert disposition['status'] == 'completed'
    assert db.execute("SELECT quality_status FROM prod_serial WHERE id=1").fetchone()[0] == 'normal'


def test_posted_rework_ng_opens_next_review_cycle_and_keeps_task_running():
    db = build_db()
    disposition_id = db.execute('SELECT id FROM prod_quality_disposition').fetchone()[0]
    approved = approve_disposition(db, disposition_id, 'rework', 7, '返工')
    rework_task_id = approved['rework_task_id']
    db.execute('UPDATE prod_task SET status=1 WHERE id=?', (rework_task_id,))
    db.execute("UPDATE prod_quality_disposition SET status='task_started' WHERE id=?", (disposition_id,))
    report_id = db.execute(
        '''INSERT INTO prod_report
           (report_no,task_id,workorder_id,process_id,user_id,qualified_qty,defect_qty,approval_status)
           VALUES('REPORT-RW-NG',?,40,3,1,0,1,1)''',
        (rework_task_id,),
    ).lastrowid
    db.commit()
    post_report(db, report_id, 7)
    assert tuple(db.execute(
        'SELECT defect_qty,status FROM prod_task WHERE id=?', (rework_task_id,)
    ).fetchone()) == (1, 1)
    cycles = db.execute(
        'SELECT cycle_no,status FROM prod_quality_disposition ORDER BY cycle_no'
    ).fetchall()
    assert [tuple(row) for row in cycles] == [(1, 'completed'), (2, 'pending_review')]
    assert db.execute("SELECT quality_status FROM prod_serial WHERE id=1").fetchone()[0] == 'quality_hold'
