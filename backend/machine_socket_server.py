"""独立AIM TCP Socket接入服务。"""
import argparse
import socketserver
import sqlite3

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
        allowed_remote = str(self.endpoint.get('allowed_remote_ip') or '').strip()
        if allowed_remote and self.client_address[0] != allowed_remote:
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
        timeout = max(0.5, int(self.endpoint.get('timeout_ms') or 1000) / 1000)
        self.request.settimeout(timeout)

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
            except OSError:
                break
            if not frame:
                break
            if len(frame) >= 4099 and not frame.endswith(b'\n'):
                self.wfile.write(self._protocol_failure(frame, ProtocolError('报文过长')))
                self.wfile.flush()
                break
            try:
                machine_request = parse_request(frame, self.endpoint)
                decision = evaluate_access(self.db, self.endpoint, machine_request)
                response = format_response(machine_request, decision)
            except ProtocolError as exc:
                response = self._protocol_failure(frame, exc)
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
        if hasattr(self, 'db'):
            try:
                self.db.execute(
                    '''UPDATE iot_machine_session SET status='offline',
                       disconnected_at=CURRENT_TIMESTAMP WHERE id=?''', (self.session_id,)
                )
                self.db.commit()
            finally:
                self.db.close()
        super().finish()


class MachineSocketServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, endpoint_id, db_path=DB_PATH):
        self.endpoint_id = int(endpoint_id)
        self.db_path = str(db_path)
        super().__init__(server_address, MachineRequestHandler)


def main():
    parser = argparse.ArgumentParser(description='AIM机台Socket接入服务')
    parser.add_argument('--endpoint-id', type=int, required=True)
    parser.add_argument('--db', default=DB_PATH)
    args = parser.parse_args()
    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    endpoint = db.execute(
        'SELECT * FROM iot_machine_endpoint WHERE id=? AND enabled=1', (args.endpoint_id,)
    ).fetchone()
    db.close()
    if not endpoint:
        raise SystemExit('通讯端点不存在或未启用')
    with MachineSocketServer((endpoint['bind_ip'], endpoint['listen_port']), endpoint['id'], args.db) as server:
        print(f"AIM Socket监听 {endpoint['bind_ip']}:{endpoint['listen_port']}")
        server.serve_forever()


if __name__ == '__main__':
    main()
