import os
import sqlite3
import sys


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

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        self.waited = True


def test_starts_one_process_per_enabled_endpoint_and_stops_all(tmp_path):
    path = tmp_path / 'manager.db'
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE iot_machine_endpoint(id INTEGER PRIMARY KEY,enabled INTEGER)')
    db.executemany('INSERT INTO iot_machine_endpoint VALUES(?,?)', [(1, 1), (2, 0), (3, 1)])
    db.commit(); db.close()
    processes = []
    manager = MachineGatewayManager(str(path), popen=lambda command: processes.append(FakeProcess(command)) or processes[-1])
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
    manager = MachineGatewayManager(str(path), popen=lambda command: calls.append(command) or FakeProcess(command))
    manager.start(); manager.start()
    assert len(calls) == 1

