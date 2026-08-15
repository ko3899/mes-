"""生产环境AIM Socket子进程生命周期管理。"""
import os
import sqlite3
import subprocess
import sys
import threading
import time

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
        self._signatures = {}
        self._spawned_at = {}
        self._failure_counts = {}
        self._restart_after = {}

    def _enabled_endpoints(self):
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        try:
            rows = db.execute(
                'SELECT id FROM iot_machine_endpoint WHERE enabled=1'
            ).fetchall()
            columns = {
                row[1] for row in db.execute('PRAGMA table_info(iot_machine_endpoint)')
            }
            signature_columns = [
                name for name in (
                    'transport_mode', 'reader_ip', 'reader_port', 'reader_frame_idle_ms',
                    'bind_ip', 'listen_port', 'protocol_version', 'allowed_remote_ip',
                    'station_code', 'process_id', 'cavity_code', 'encoding', 'timeout_ms',
                    'heartbeat_seconds', 'shared_secret', 'laser_template',
                    'inspection_template',
                ) if name in columns
            ]
            if signature_columns:
                rows = db.execute(
                    f"SELECT id,{','.join(signature_columns)} "
                    'FROM iot_machine_endpoint WHERE enabled=1'
                ).fetchall()
            return {
                int(row['id']): tuple(row[name] for name in signature_columns)
                for row in rows
            }
        finally:
            db.close()

    def _update_runtime(self, endpoint_id, status, error=None):
        db = sqlite3.connect(self.db_path, timeout=5)
        try:
            columns = {
                row[1] for row in db.execute('PRAGMA table_info(iot_machine_endpoint)')
            }
            if 'listener_status' not in columns:
                return
            db.execute(
                '''UPDATE iot_machine_endpoint SET listener_status=?,listener_pid=NULL,
                   last_error=CASE WHEN ? IS NULL THEN last_error ELSE ? END WHERE id=?''',
                (status, error, str(error)[:500] if error else None, endpoint_id),
            )
            db.execute(
                '''UPDATE iot_machine_session SET status='offline',
                   disconnected_at=COALESCE(disconnected_at,CURRENT_TIMESTAMP),
                   last_error=COALESCE(last_error,?)
                   WHERE endpoint_id=? AND status='online' ''',
                (str(error)[:500] if error else '通讯监听已停止', endpoint_id),
            )
            db.commit()
        except sqlite3.Error:
            db.rollback()
        finally:
            db.close()

    def _spawn(self, endpoint_id):
        db = sqlite3.connect(self.db_path, timeout=5)
        try:
            columns = {row[1] for row in db.execute('PRAGMA table_info(iot_machine_endpoint)')}
            mode = 'server'
            if 'transport_mode' in columns:
                value = db.execute(
                    'SELECT transport_mode FROM iot_machine_endpoint WHERE id=?', (endpoint_id,)
                ).fetchone()
                mode = str(value[0] or 'server') if value else 'server'
        finally:
            db.close()
        script_name = 'machine_reader_client.py' if mode == 'reader_client' else 'machine_socket_server.py'
        server_script = os.path.join(os.path.dirname(__file__), script_name)
        command = [sys.executable, server_script, '--db', self.db_path,
                   '--parent-pid', str(os.getpid()),
                   '--endpoint-id', str(endpoint_id)]
        db = sqlite3.connect(self.db_path, timeout=5)
        try:
            columns = {
                row[1] for row in db.execute('PRAGMA table_info(iot_machine_endpoint)')
            }
            if 'listener_status' in columns:
                db.execute(
                    '''UPDATE iot_machine_endpoint SET listener_status='starting',
                       listener_pid=NULL,last_error=NULL WHERE id=?''', (endpoint_id,)
                )
                db.commit()
        finally:
            db.close()
        self.processes[endpoint_id] = self._popen(command)
        self._spawned_at[endpoint_id] = time.monotonic()

    def _terminate(self, endpoint_id, status='stopped', error=None):
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
        self._update_runtime(endpoint_id, status, error)

    def sync(self):
        enabled = self._enabled_endpoints()
        now = time.monotonic()
        for endpoint_id in list(self.processes):
            process = self.processes[endpoint_id]
            exit_code = process.poll()
            if endpoint_id not in enabled:
                self._terminate(endpoint_id)
                self._signatures.pop(endpoint_id, None)
                self._failure_counts.pop(endpoint_id, None)
                self._restart_after.pop(endpoint_id, None)
            elif exit_code is not None:
                failures = self._failure_counts.get(endpoint_id, 0) + 1
                self._failure_counts[endpoint_id] = failures
                delay = min(60.0, max(float(self.interval), float(self.interval) * (2 ** (failures - 1))))
                self._restart_after[endpoint_id] = now + delay
                self._terminate(
                    endpoint_id, 'error',
                    f'Socket监听进程异常退出（代码 {exit_code}），{delay:g}秒后重试'
                )
            elif self._signatures.get(endpoint_id) != enabled[endpoint_id]:
                self._terminate(endpoint_id)
                self._failure_counts.pop(endpoint_id, None)
                self._restart_after.pop(endpoint_id, None)
            elif now - self._spawned_at.get(endpoint_id, now) >= 10:
                self._failure_counts.pop(endpoint_id, None)
                self._restart_after.pop(endpoint_id, None)
        ready = {
            endpoint_id for endpoint_id in enabled
            if now >= self._restart_after.get(endpoint_id, 0)
        }
        for endpoint_id in sorted(ready - set(self.processes)):
            self._spawn(endpoint_id)
            self._signatures[endpoint_id] = enabled[endpoint_id]
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
        db = sqlite3.connect(self.db_path, timeout=5)
        try:
            if db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='iot_machine_session'"
            ).fetchone():
                db.execute(
                    '''UPDATE iot_machine_session SET status='offline',
                       disconnected_at=COALESCE(disconnected_at,CURRENT_TIMESTAMP),
                       last_error=COALESCE(last_error,'通讯服务已重启')
                       WHERE status='online' ''')
                db.commit()
        finally:
            db.close()
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
        self._signatures.clear()
        self._spawned_at.clear()
        self._failure_counts.clear()
        self._restart_after.clear()
