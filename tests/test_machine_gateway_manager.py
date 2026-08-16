import os
import sqlite3
import sys
import time


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from machine_gateway_manager import MachineGatewayManager  # noqa: E402


class FakeProcess:
    def __init__(self, command):
        self.command = command
        self.terminated = False
        self.waited = False
        self.exit_code = None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        self.waited = True

    def poll(self):
        return self.exit_code


def test_starts_one_process_per_enabled_endpoint_and_stops_all(tmp_path):
    path = tmp_path / 'manager.db'
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE iot_machine_endpoint(id INTEGER PRIMARY KEY,enabled INTEGER)')
    db.executemany('INSERT INTO iot_machine_endpoint VALUES(?,?)', [(1, 1), (2, 0), (3, 1)])
    db.commit(); db.close()
    processes = []
    manager = MachineGatewayManager(str(path), popen=lambda command: processes.append(FakeProcess(command)) or processes[-1], supervise=False)
    assert manager.start() == 2
    assert [process.command[-1] for process in processes] == ['1', '3']
    manager.stop()
    assert all(process.terminated and process.waited for process in processes)


def test_start_is_idempotent(tmp_path):
    path = tmp_path / 'manager.db'
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE iot_machine_endpoint(id INTEGER PRIMARY KEY,enabled INTEGER)')
    db.execute('INSERT INTO iot_machine_endpoint VALUES(1,1)')
    db.commit(); db.close()
    calls = []
    manager = MachineGatewayManager(str(path), popen=lambda command: calls.append(command) or FakeProcess(command), supervise=False)
    manager.start(); manager.start(); manager.stop()
    assert len(calls) == 1


def test_sync_applies_runtime_toggle_and_restarts_failed_process(tmp_path):
    path = tmp_path / 'manager.db'
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE iot_machine_endpoint(id INTEGER PRIMARY KEY,enabled INTEGER)')
    db.execute('INSERT INTO iot_machine_endpoint VALUES(1,1)')
    db.commit(); db.close()
    created = []
    manager = MachineGatewayManager(
        str(path), popen=lambda cmd: created.append(FakeProcess(cmd)) or created[-1],
        supervise=False, interval=0.05,
    )
    manager.start()
    created[0].exit_code = 1
    manager.sync()
    assert len(created) == 1
    time.sleep(0.06)
    manager.sync()
    assert len(created) == 2
    db = sqlite3.connect(path)
    db.execute('UPDATE iot_machine_endpoint SET enabled=0 WHERE id=1')
    db.commit(); db.close()
    manager.sync()
    assert created[-1].terminated
    manager.stop()


def test_sync_restarts_process_when_endpoint_configuration_changes(tmp_path):
    path = tmp_path / 'manager.db'
    db = sqlite3.connect(path)
    db.execute('''CREATE TABLE iot_machine_endpoint(
        id INTEGER PRIMARY KEY,enabled INTEGER,bind_ip TEXT,listen_port INTEGER)''')
    db.execute("INSERT INTO iot_machine_endpoint VALUES(1,1,'127.0.0.1',2004)")
    db.commit(); db.close()
    created = []
    manager = MachineGatewayManager(
        str(path), popen=lambda command: created.append(FakeProcess(command)) or created[-1],
        supervise=False,
    )
    manager.start()
    db = sqlite3.connect(path)
    db.execute('UPDATE iot_machine_endpoint SET listen_port=2005 WHERE id=1')
    db.commit(); db.close()
    manager.sync()
    assert len(created) == 2
    assert created[0].terminated and created[0].waited
    manager.stop()


def test_failed_process_restart_uses_backoff_and_preserves_error(tmp_path):
    path = tmp_path / 'manager.db'
    db = sqlite3.connect(path)
    db.execute('''CREATE TABLE iot_machine_endpoint(
        id INTEGER PRIMARY KEY,enabled INTEGER,listener_status TEXT,
        listener_pid INTEGER,last_error TEXT)''')
    db.execute('''CREATE TABLE iot_machine_session(
        id INTEGER PRIMARY KEY,endpoint_id INTEGER,status TEXT,
        disconnected_at TEXT,last_error TEXT)''')
    db.execute("INSERT INTO iot_machine_endpoint VALUES(1,1,'starting',NULL,NULL)")
    db.commit(); db.close()
    created = []
    manager = MachineGatewayManager(
        str(path), popen=lambda command: created.append(FakeProcess(command)) or created[-1],
        supervise=False, interval=0.2,
    )
    manager.start()
    created[0].exit_code = 98
    manager.sync()
    assert len(created) == 1
    db = sqlite3.connect(path)
    status, error = db.execute(
        'SELECT listener_status,last_error FROM iot_machine_endpoint WHERE id=1'
    ).fetchone()
    assert status == 'error' and '0.2秒后重试' in error
    time.sleep(0.25)
    manager.sync()
    assert len(created) == 2
    manager.stop()
