"""生产环境AIM Socket子进程生命周期管理。"""
import os
import sqlite3
import subprocess
import sys

from utils.database import DB_PATH


class MachineGatewayManager:
    def __init__(self, db_path=DB_PATH, popen=subprocess.Popen):
        self.db_path = str(db_path)
        self._popen = popen
        self.processes = []

    def start(self):
        if self.processes:
            return len(self.processes)
        db = sqlite3.connect(self.db_path)
        endpoints = [row[0] for row in db.execute(
            'SELECT id FROM iot_machine_endpoint WHERE enabled=1 ORDER BY id'
        ).fetchall()]
        db.close()
        server_script = os.path.join(os.path.dirname(__file__), 'machine_socket_server.py')
        for endpoint_id in endpoints:
            command = [sys.executable, server_script, '--db', self.db_path,
                       '--endpoint-id', str(endpoint_id)]
            self.processes.append(self._popen(command))
        return len(self.processes)

    def stop(self):
        for process in self.processes:
            try:
                process.terminate()
            except OSError:
                pass
        for process in self.processes:
            try:
                process.wait(timeout=5)
            except Exception:
                try:
                    process.kill()
                except (AttributeError, OSError):
                    pass
        self.processes.clear()

