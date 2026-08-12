import os
import socket
import sqlite3
import sys
import threading


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from machine_socket_server import MachineSocketServer  # noqa: E402


SCHEMA = '''
CREATE TABLE eqp_ledger(id INTEGER PRIMARY KEY, equipment_name TEXT, code TEXT, status INTEGER);
CREATE TABLE base_process(id INTEGER PRIMARY KEY, process_name TEXT);
CREATE TABLE iot_machine_endpoint(id INTEGER PRIMARY KEY, equipment_id INTEGER, protocol_version INTEGER, bind_ip TEXT, listen_port INTEGER, station_code TEXT, process_id INTEGER, cavity_code TEXT, encoding TEXT, timeout_ms INTEGER, enabled INTEGER, laser_template TEXT, inspection_template TEXT, last_seen_at TEXT, last_error TEXT);
CREATE TABLE iot_machine_session(id INTEGER PRIMARY KEY, endpoint_id INTEGER, remote_address TEXT, connected_at TEXT DEFAULT CURRENT_TIMESTAMP, last_heartbeat_at TEXT, disconnected_at TEXT, status TEXT, request_count INTEGER DEFAULT 0, last_error TEXT);
CREATE TABLE prod_serial(id INTEGER PRIMARY KEY, serial_no TEXT, product_id INTEGER, workorder_id INTEGER, status INTEGER);
CREATE TABLE prod_workorder(id INTEGER PRIMARY KEY, product_id INTEGER, status INTEGER);
CREATE TABLE prod_workorder_route_snapshot(id INTEGER PRIMARY KEY, workorder_id INTEGER);
CREATE TABLE prod_workorder_route_step(id INTEGER PRIMARY KEY, snapshot_id INTEGER, process_id INTEGER, process_name TEXT, step_no INTEGER);
CREATE TABLE prod_task(id INTEGER PRIMARY KEY, workorder_id INTEGER, process_id INTEGER, route_step_id INTEGER, status INTEGER);
CREATE TABLE prod_station_record(id INTEGER PRIMARY KEY, sn TEXT, process_name TEXT, action TEXT, result TEXT, route_step_id INTEGER);
CREATE TABLE iot_machine_request(id INTEGER PRIMARY KEY, endpoint_id INTEGER, session_id INTEGER, request_no TEXT, protocol_version INTEGER, station_code TEXT, cavity_code TEXT, sn TEXT, workorder_id INTEGER, task_id INTEGER, route_step_id INTEGER, decision TEXT, reason_code TEXT, reason_message TEXT, laser_template TEXT, inspection_template TEXT, elapsed_ms INTEGER, dedupe_key TEXT UNIQUE, requested_at TEXT DEFAULT CURRENT_TIMESTAMP, responded_at TEXT DEFAULT CURRENT_TIMESTAMP, report_status TEXT);
'''


def make_db(path):
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    db.execute("INSERT INTO eqp_ledger VALUES(1,'AIM测试机','AIM001',1)")
    db.execute("INSERT INTO base_process VALUES(11,'扫码检测')")
    db.execute("INSERT INTO iot_machine_endpoint VALUES(1,1,2,'127.0.0.1',0,'ST01',11,'C1','utf-8',1000,1,'','','','')")
    db.execute("INSERT INTO prod_serial VALUES(1,'SN001',10,1,0)")
    db.execute("INSERT INTO prod_workorder VALUES(1,10,1)")
    db.execute("INSERT INTO prod_workorder_route_snapshot VALUES(1,1)")
    db.execute("INSERT INTO prod_workorder_route_step VALUES(101,1,11,'扫码检测',1)")
    db.execute("INSERT INTO prod_task VALUES(201,1,11,101,1)")
    db.commit()
    db.close()


def start_server(tmp_path):
    path = tmp_path / 'socket.db'
    make_db(path)
    server = MachineSocketServer(('127.0.0.1', 0), 1, str(path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def exchange(address, chunks, reads=1):
    with socket.create_connection(address, timeout=2) as client:
        for chunk in chunks:
            client.sendall(chunk)
        stream = client.makefile('rb')
        return [stream.readline() for _ in range(reads)]


def test_v2_real_socket_handles_split_frame_and_identity(tmp_path):
    server, thread = start_server(tmp_path)
    try:
        response = exchange(server.server_address, [
            b'REQ|2|AIM001|ST01|C1|R1|', b'SN001\r\n'])
        assert response[0].startswith(b'ACK|2|R1|L1|OK|')
    finally:
        server.shutdown(); server.server_close(); thread.join(2)


def test_two_frames_in_one_connection_and_bad_identity_fail_closed(tmp_path):
    server, thread = start_server(tmp_path)
    try:
        responses = exchange(server.server_address, [
            b'REQ|2|OTHER|ST01|C1|BAD|SN001\r\n'
            b'REQ|2|AIM001|ST01|C1|R2|MISSING\r\n'], reads=2)
        assert b'|BAD|L3|PROTOCOL_ERROR|' in responses[0]
        assert b'|R2|L3|UNKNOWN_SN|' in responses[1]
    finally:
        server.shutdown(); server.server_close(); thread.join(2)


def test_noread_and_clean_session_shutdown(tmp_path):
    server, thread = start_server(tmp_path)
    try:
        response = exchange(server.server_address, [b'NoRead\r\n'])[0]
        assert response == b'<L3>\r\n'
    finally:
        server.shutdown(); server.server_close(); thread.join(2)
    db = sqlite3.connect(server.db_path)
    session = db.execute('SELECT status,request_count FROM iot_machine_session').fetchone()
    assert session == ('offline', 1)
