"""独立AIM TCP Socket接入服务。"""
import argparse
import ipaddress
import os
import socketserver
import sqlite3
import threading
import time

from services.machine_access import evaluate_access
from services.machine_protocol import (
    AccessDecision,
    MachineRequest,
    ProtocolError,
    format_response,
    parse_request,
)
from utils.database import DB_PATH


def _row_dict(row):
    return dict(row) if row else None


class MachineRequestHandler(socketserver.StreamRequestHandler):
    def setup(self):
        super().setup()
        self.session_id = None
        self._connection_slot = self.server.connection_slots.acquire(blocking=False)
        if not self._connection_slot:
            raise ConnectionRefusedError('通讯端点连接数已达上限')
        self.db = sqlite3.connect(self.server.db_path, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA busy_timeout=900')
        self.endpoint = _row_dict(self.db.execute(
            '''SELECT e.*,q.code AS device_code,q.status AS equipment_status,
                      q.equipment_name,p.process_name
               FROM iot_machine_endpoint e
               JOIN eqp_ledger q ON q.id=e.equipment_id
               LEFT JOIN base_process p ON p.id=e.process_id WHERE e.id=?''',
            (self.server.endpoint_id,),
        ).fetchone())
        if not self.endpoint:
            self.db.close()
            raise ConnectionRefusedError('通讯端点不存在')
        allowed_remote = str(self.endpoint.get('allowed_remote_ip') or '').strip()
        if allowed_remote and not self._remote_allowed(self.client_address[0], allowed_remote):
            remote = f'{self.client_address[0]}:{self.client_address[1]}'
            self.db.execute(
                '''INSERT INTO iot_machine_session
                   (endpoint_id,remote_address,status,last_heartbeat_at,disconnected_at,last_error)
                   VALUES(?,?,'rejected',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,?)''',
                (self.server.endpoint_id, remote, '远端IP不在端点白名单'),
            )
            self.db.commit()
            self.db.close()
            raise ConnectionRefusedError('远端IP不在端点白名单')
        remote = f'{self.client_address[0]}:{self.client_address[1]}'
        self.session_id = self.db.execute(
            '''INSERT INTO iot_machine_session(endpoint_id,remote_address,status,last_heartbeat_at)
               VALUES(?,?,"online",CURRENT_TIMESTAMP)''',
            (self.server.endpoint_id, remote),
        ).lastrowid
        self.db.execute(
            'UPDATE iot_machine_endpoint SET last_seen_at=CURRENT_TIMESTAMP,last_error=NULL WHERE id=?',
            (self.server.endpoint_id,),
        )
        self.db.commit()
        heartbeat = max(5, int(self.endpoint.get('heartbeat_seconds') or 30))
        self.request.settimeout(heartbeat * 2)

    @staticmethod
    def _remote_allowed(remote, allowlist):
        try:
            address = ipaddress.ip_address(remote)
            return any(address in ipaddress.ip_network(item.strip(), strict=False)
                       for item in str(allowlist).split(',') if item.strip())
        except ValueError:
            return False

    def _protocol_failure(self, frame, error):
        text = ''
        try:
            text = frame.decode(self.endpoint.get('encoding') or 'utf-8', errors='ignore').strip()
        except Exception:
            pass
        parts = text.split('|')
        if int(self.endpoint.get('protocol_version') or 1) == 2:
            request = MachineRequest(2, self.endpoint['device_code'], self.endpoint['station_code'],
                                     self.endpoint['cavity_code'],
                                     parts[5] if len(parts) > 5 and parts[5] else 'UNKNOWN', '')
        else:
            request = MachineRequest(1, self.endpoint['device_code'], self.endpoint['station_code'],
                                     self.endpoint['cavity_code'], 'UNKNOWN', '')
        return format_response(request, AccessDecision.reject('PROTOCOL_ERROR', str(error)))

    def handle(self):
        while True:
            try:
                frame = self.rfile.readline(4099)
            except OSError as exc:
                try:
                    reason = '机台心跳超时' if type(exc).__name__ == 'TimeoutError' else str(exc)
                    self.db.execute(
                        'UPDATE iot_machine_session SET last_error=? WHERE id=?',
                        (reason[:500], self.session_id),
                    )
                    self.db.commit()
                except sqlite3.Error:
                    self.db.rollback()
                break
            if not frame:
                break
            if len(frame) >= 4099 and not frame.endswith(b'\n'):
                self.wfile.write(self._protocol_failure(frame, ProtocolError('报文过长')))
                self.wfile.flush()
                break
            try:
                heartbeat_frame = frame.decode(
                    self.endpoint.get('encoding') or 'utf-8'
                ).strip().upper()
            except (LookupError, UnicodeDecodeError):
                heartbeat_frame = ''
            if heartbeat_frame == 'PING':
                self.wfile.write(b'PONG\r\n')
                self.wfile.flush()
                self.db.execute(
                    'UPDATE iot_machine_session SET last_heartbeat_at=CURRENT_TIMESTAMP WHERE id=?',
                    (self.session_id,),
                )
                self.db.commit()
                continue
            try:
                machine_request = parse_request(frame, self.endpoint)
                decision = evaluate_access(
                    self.db, self.endpoint, machine_request, session_id=self.session_id
                )
                response = format_response(machine_request, decision)
            except ProtocolError as exc:
                response = self._protocol_failure(frame, exc)
                self.db.execute(
                    'UPDATE iot_machine_session SET last_error=? WHERE id=?',
                    (str(exc)[:500], self.session_id),
                )
                self.db.commit()
            except Exception as exc:
                self.db.rollback()
                response = self._protocol_failure(frame, f'服务异常:{type(exc).__name__}')
                try:
                    self.db.execute(
                        'UPDATE iot_machine_endpoint SET last_error=? WHERE id=?',
                        (str(exc)[:500], self.server.endpoint_id),
                    )
                    self.db.commit()
                except Exception:
                    self.db.rollback()
            self.wfile.write(response)
            self.wfile.flush()
            self.db.execute(
                '''UPDATE iot_machine_session SET request_count=request_count+1,
                   last_heartbeat_at=CURRENT_TIMESTAMP WHERE id=?''', (self.session_id,)
            )
            self.db.execute(
                'UPDATE iot_machine_endpoint SET last_seen_at=CURRENT_TIMESTAMP WHERE id=?',
                (self.server.endpoint_id,),
            )
            self.db.commit()

    def finish(self):
        if getattr(self, 'db', None):
            try:
                if self.session_id is not None:
                    self.db.execute(
                        '''UPDATE iot_machine_session SET status='offline',
                           disconnected_at=CURRENT_TIMESTAMP WHERE id=?''', (self.session_id,)
                    )
                    self.db.commit()
            finally:
                try:
                    self.db.close()
                except sqlite3.Error:
                    pass
        if getattr(self, '_connection_slot', False):
            self.server.connection_slots.release()
            self._connection_slot = False
        super().finish()


class MachineSocketServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, endpoint_id, db_path=DB_PATH):
        self.endpoint_id = int(endpoint_id)
        self.db_path = str(db_path)
        self.connection_slots = threading.BoundedSemaphore(100)
        super().__init__(server_address, MachineRequestHandler)


def _set_endpoint_runtime(db_path, endpoint_id, status, error=None, listening=False):
    db = sqlite3.connect(db_path, timeout=5)
    try:
        if listening:
            db.execute(
                '''UPDATE iot_machine_endpoint SET listener_status='listening',listener_pid=?,
                   listener_started_at=CURRENT_TIMESTAMP,last_error=NULL WHERE id=?''',
                (os.getpid(), endpoint_id),
            )
        else:
            db.execute(
                '''UPDATE iot_machine_endpoint SET listener_status=?,listener_pid=NULL,
                   last_error=CASE WHEN ? IS NULL THEN last_error ELSE ? END WHERE id=?''',
                (status, error, str(error)[:500] if error else None, endpoint_id),
            )
        db.commit()
    except sqlite3.OperationalError:
        db.rollback()
    finally:
        db.close()


def _parent_alive(parent_pid):
    if not parent_pid:
        return True
    if os.name == 'nt':
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(parent_pid))
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(int(parent_pid), 0)
        return True
    except OSError:
        return False


def _watch_parent(server, parent_pid):
    while _parent_alive(parent_pid):
        time.sleep(2)
    server.shutdown()


def main():
    parser = argparse.ArgumentParser(description='AIM机台Socket接入服务')
    parser.add_argument('--endpoint-id', type=int, required=True)
    parser.add_argument('--db', default=DB_PATH)
    parser.add_argument('--parent-pid', type=int)
    args = parser.parse_args()
    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    endpoint = db.execute(
        'SELECT * FROM iot_machine_endpoint WHERE id=? AND enabled=1', (args.endpoint_id,)
    ).fetchone()
    db.close()
    if not endpoint:
        raise SystemExit('通讯端点不存在或未启用')
    failed = False
    try:
        with MachineSocketServer(
            (endpoint['bind_ip'], endpoint['listen_port']), endpoint['id'], args.db
        ) as server:
            _set_endpoint_runtime(args.db, endpoint['id'], 'listening', listening=True)
            if args.parent_pid:
                threading.Thread(
                    target=_watch_parent, args=(server, args.parent_pid), daemon=True
                ).start()
            print(
                f"AIM Socket监听 {endpoint['bind_ip']}:{endpoint['listen_port']}",
                flush=True,
            )
            server.serve_forever()
    except Exception as exc:
        failed = True
        _set_endpoint_runtime(args.db, endpoint['id'], 'error', exc)
        raise
    finally:
        if not failed:
            _set_endpoint_runtime(args.db, endpoint['id'], 'stopped')


if __name__ == '__main__':
    main()
