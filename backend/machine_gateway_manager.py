"""生产环境AIM Socket子进程生命周期管理。"""
import os
import sqlite3
import subprocess
import sys
import threading

from utils.database import DB_PATH


class MachineGatewayManager:
    def __init__(self, db_path=DB_PATH, popen=subprocess.Popen, supervise=True, interval=2):
        self.db_path = str(db_path)
        self._popen = popen
        self.processes = {}
        self.supervise = supervise
        self.interval = interval
        self._stopping = threading.Event()
        self._thread = None

    def _enabled_ids(self):
        db = sqlite3.connect(self.db_path)
        try:
            return {row[0] for row in db.execute(
                'SELECT id FROM iot_machine_endpoint WHERE enabled=1'
            ).fetchall()}
        finally:
            db.close()

    def _spawn(self, endpoint_id):
        server_script = os.path.join(os.path.dirname(__file__), 'machine_socket_server.py')
        command = [sys.executable, server_script, '--db', self.db_path,
                   '--endpoint-id', str(endpoint_id)]
        self.processes[endpoint_id] = self._popen(command)

    def _terminate(self, endpoint_id):
        process = self.processes.pop(endpoint_id, None)
        if not process:
            return
        try:
            process.terminate()
        except OSError:
            pass
        try:
            process.wait(timeout=5)
        except Exception:
            try:
                process.kill()
            except (AttributeError, OSError):
                pass

    def sync(self):
        enabled = self._enabled_ids()
        for endpoint_id in list(self.processes):
            process = self.processes[endpoint_id]
            if endpoint_id not in enabled or process.poll() is not None:
                self._terminate(endpoint_id)
        for endpoint_id in sorted(enabled - set(self.processes)):
            self._spawn(endpoint_id)
        return len(self.processes)

    def _monitor(self):
        while not self._stopping.wait(self.interval):
            try:
                self.sync()
            except (OSError, sqlite3.Error):
                continue

    def start(self):
        if self.processes:
            return len(self.processes)
        self._stopping.clear()
        self.sync()
        if self.supervise and not self._thread:
            self._thread = threading.Thread(target=self._monitor, name='aim-gateway-monitor', daemon=True)
            self._thread.start()
        return len(self.processes)

    def stop(self):
        self._stopping.set()
        if self._thread:
            self._thread.join(timeout=self.interval + 1)
            self._thread = None
        for endpoint_id in list(self.processes):
            self._terminate(endpoint_id)
