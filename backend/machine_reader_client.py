"""Direct Hikrobot IDMVS TCP client.

The reader is configured as a TCP server (normally port 2002).  This worker
connects to it, treats a short idle period as the frame boundary when CR/LF
output is disabled, evaluates the SN through the existing MES access service,
and sends the configured legacy ``<L1>``/``<L3>`` response back.
"""
import argparse
import os
import socket
import sqlite3
import threading
import time

from services.machine_access import evaluate_access
from services.machine_protocol import (
    AccessDecision,
    MachineRequest,
    ProtocolError,
    format_response,
    parse_reader_frame,
)
from utils.database import DB_PATH


def _row_dict(row):
    return dict(row) if row else None


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


def _set_runtime(db_path, endpoint_id, status, error=None, listening=False):
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
    except sqlite3.Error:
        db.rollback()
    finally:
        db.close()


def _session_open(db, endpoint_id, address):
    cursor = db.execute(
        '''INSERT INTO iot_machine_session(endpoint_id,remote_address,status,last_heartbeat_at)
           VALUES(?,?,'online',CURRENT_TIMESTAMP)''',
        (endpoint_id, address),
    )
    db.commit()
    return int(cursor.lastrowid)


def _protocol_failure(endpoint, frame, error):
    request = MachineRequest(
        1,
        str(endpoint.get('device_code') or ''),
        str(endpoint.get('station_code') or ''),
        str(endpoint.get('cavity_code') or ''),
        'UNKNOWN',
        '',
    )
    return format_response(request, AccessDecision.reject('PROTOCOL_ERROR', str(error)), b'')


def _frames_from_buffer(buffer, endpoint, timed_out=False):
    """Yield delimiter-framed payloads and one idle-framed payload if needed."""
    frames = []
    while b'\n' in buffer:
        raw, buffer = buffer.split(b'\n', 1)
        frames.append(raw + b'\n')
    if timed_out and buffer.strip(b'\r\x00 '):
        frames.append(buffer)
        buffer = b''
    return buffer, frames


def _handle_frame(db, endpoint, session_id, frame):
    try:
        request = parse_reader_frame(frame, endpoint)
        decision = evaluate_access(db, endpoint, request, session_id=session_id)
        response = format_response(request, decision, b'')
    except ProtocolError as exc:
        response = _protocol_failure(endpoint, frame, exc)
        db.execute(
            'UPDATE iot_machine_session SET last_error=? WHERE id=?',
            (str(exc)[:500], session_id),
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        response = _protocol_failure(endpoint, frame, f'服务异常:{type(exc).__name__}')
        db.execute(
            'UPDATE iot_machine_session SET last_error=? WHERE id=?',
            (str(exc)[:500], session_id),
        )
        db.commit()
    db.execute(
        '''UPDATE iot_machine_session SET request_count=request_count+1,
           last_heartbeat_at=CURRENT_TIMESTAMP WHERE id=?''',
        (session_id,),
    )
    db.execute(
        'UPDATE iot_machine_endpoint SET last_seen_at=CURRENT_TIMESTAMP WHERE id=?',
        (endpoint['id'],),
    )
    db.commit()
    return response


def _run_connection(db_path, endpoint, parent_pid):
    idle_ms = max(20, min(2000, int(endpoint.get('reader_frame_idle_ms') or 80)))
    idle = idle_ms / 1000.0
    while _parent_alive(parent_pid):
        db = sqlite3.connect(db_path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            try:
                reader_ip = str(endpoint.get('reader_ip') or '').strip()
                reader_port = int(endpoint.get('reader_port') or 2002)
                with socket.create_connection((reader_ip, reader_port), timeout=5) as connection:
                    connection.settimeout(idle)
                    _set_runtime(db_path, endpoint['id'], 'listening', listening=True)
                    session_id = _session_open(db, endpoint['id'], f'{reader_ip}:{reader_port}')
                    buffer = b''
                    while _parent_alive(parent_pid):
                        timed_out = False
                        try:
                            chunk = connection.recv(4096)
                            if not chunk:
                                break
                            buffer += chunk
                        except socket.timeout:
                            timed_out = True
                        buffer, frames = _frames_from_buffer(buffer, endpoint, timed_out)
                        for frame in frames:
                            connection.sendall(_handle_frame(db, endpoint, session_id, frame))
                    db.execute(
                        '''UPDATE iot_machine_session SET status='offline',
                           disconnected_at=CURRENT_TIMESTAMP WHERE id=?''',
                        (session_id,),
                    )
                    db.commit()
            except (OSError, ValueError, sqlite3.Error) as exc:
                _set_runtime(db_path, endpoint['id'], 'error', str(exc))
                time.sleep(2)
        finally:
            db.close()


def main():
    parser = argparse.ArgumentParser(description='海康读码器直连客户端')
    parser.add_argument('--endpoint-id', type=int, required=True)
    parser.add_argument('--db', default=DB_PATH)
    parser.add_argument('--parent-pid', type=int)
    args = parser.parse_args()
    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    endpoint = _row_dict(db.execute(
        '''SELECT e.*,q.code AS device_code,q.status AS equipment_status,
                  q.equipment_name,p.process_name
           FROM iot_machine_endpoint e
           JOIN eqp_ledger q ON q.id=e.equipment_id
           LEFT JOIN base_process p ON p.id=e.process_id
           WHERE e.id=? AND e.enabled=1''',
        (args.endpoint_id,),
    ).fetchone())
    db.close()
    if not endpoint:
        raise SystemExit('直连通讯端点不存在或未启用')
    if str(endpoint.get('transport_mode') or 'server') != 'reader_client':
        raise SystemExit('端点不是海康直连模式')
    if not endpoint.get('reader_ip'):
        raise SystemExit('海康直连端点未配置读码器IP')
    try:
        _run_connection(args.db, endpoint, args.parent_pid)
    finally:
        _set_runtime(args.db, endpoint['id'], 'stopped')


if __name__ == '__main__':
    main()
