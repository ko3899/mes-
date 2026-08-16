"""轮询采集 AIM 机台输出的稳定 CSV 文件。"""
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import threading
import time
import uuid

from services.machine_access import import_inspection_report, record_failed_inspection
from utils.database import DB_PATH


MAX_FILE_BYTES = 5 * 1024 * 1024


class MachineCsvCollector:
    def __init__(self, db_path=DB_PATH, archive_root='machine_archive', interval=2,
                 max_files=20, now=time.time, importer=import_inspection_report,
                 failure_recorder=record_failed_inspection):
        self.db_path = str(db_path)
        self.archive_root = Path(archive_root)
        self.interval = max(0.2, float(interval))
        self.max_files = max(1, int(max_files))
        self.now = now
        self.importer = importer
        self.failure_recorder = failure_recorder
        self._observed = {}
        self._stopping = threading.Event()
        self._thread = None
        self.last_collection_at = None
        self._ensure_runtime_schema()

    def _ensure_runtime_schema(self):
        """Keep the standalone collector compatible with databases from older releases."""
        db = sqlite3.connect(self.db_path, timeout=5)
        try:
            endpoint_table = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='iot_machine_endpoint'"
            ).fetchone()
            if endpoint_table:
                columns = {
                    row[1] for row in db.execute('PRAGMA table_info(iot_machine_endpoint)')
                }
                if 'csv_last_scan_at' not in columns:
                    db.execute(
                        'ALTER TABLE iot_machine_endpoint ADD COLUMN csv_last_scan_at TIMESTAMP'
                    )
                if 'csv_last_error' not in columns:
                    db.execute(
                        'ALTER TABLE iot_machine_endpoint ADD COLUMN csv_last_error TEXT'
                    )
            db.execute('''CREATE TABLE IF NOT EXISTS iot_machine_runtime (
                component TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                pid INTEGER,
                started_at TIMESTAMP,
                heartbeat_at TIMESTAMP,
                last_error TEXT
            )''')
            db.commit()
        finally:
            db.close()

    @staticmethod
    def _move(source, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(source, target)
            return
        except OSError:
            temporary = target.with_suffix(target.suffix + f'.{uuid.uuid4().hex}.tmp')
            shutil.copy2(source, temporary)
            if hashlib.sha256(temporary.read_bytes()).digest() != hashlib.sha256(source.read_bytes()).digest():
                temporary.unlink(missing_ok=True)
                raise OSError('跨卷复制校验失败')
            os.replace(temporary, target)
            source.unlink()

    @staticmethod
    def _unique_target(directory, filename):
        target = directory / filename
        if not target.exists():
            return target
        return directory / f'{target.stem}_{uuid.uuid4().hex[:8]}{target.suffix}'

    def _fail_file(self, db, endpoint, source, payload, reason):
        failed = self._unique_target(source.parent.parent / '_failed', source.name)
        self._move(source, failed)
        try:
            self.failure_recorder(db, endpoint, payload, source.name, failed, str(reason))
        except Exception:
            recovery = self._unique_target(source.parent.parent, source.name)
            self._move(failed, recovery)
            raise

    def _endpoint_rows(self, db):
        db.row_factory = sqlite3.Row
        return db.execute(
            '''SELECT e.*,q.code AS device_code,q.status AS equipment_status
               FROM iot_machine_endpoint e
               LEFT JOIN eqp_ledger q ON q.id=e.equipment_id
               WHERE e.enabled=1 AND e.csv_input_dir IS NOT NULL
                 AND TRIM(e.csv_input_dir)<>'' ORDER BY e.id'''
        ).fetchall()

    def _recover_processing(self, input_dir):
        processing = input_dir / '_processing'
        if not processing.is_dir():
            return
        for item in list(processing.iterdir())[:self.max_files]:
            if item.is_file() and item.suffix.lower() == '.csv':
                self._move(item, self._unique_target(input_dir, item.name))

    def scan_once(self):
        summary = {'imported': 0, 'failed': 0, 'unstable_files': 0,
                   'missing_directories': 0, 'collector_directories': 0}
        db = sqlite3.connect(self.db_path, timeout=1)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA busy_timeout=900')
        try:
            for endpoint_row in self._endpoint_rows(db):
                endpoint = dict(endpoint_row)
                summary['collector_directories'] += 1
                input_dir = Path(endpoint['csv_input_dir'])
                if not input_dir.is_dir():
                    summary['missing_directories'] += 1
                    db.execute(
                        '''UPDATE iot_machine_endpoint SET csv_last_scan_at=CURRENT_TIMESTAMP,
                           csv_last_error=? WHERE id=?''',
                        ('CSV输入目录不存在', endpoint['id']),
                    )
                    db.commit()
                    continue
                self._recover_processing(input_dir)
                candidates = sorted(
                    (item for item in input_dir.iterdir()
                     if item.is_file() and not item.name.startswith('.')
                     and item.suffix.lower() == '.csv'),
                    key=lambda item: item.name,
                )[:self.max_files]
                for source in candidates:
                    try:
                        stat = source.stat()
                    except OSError:
                        continue
                    payload = None
                    if stat.st_size > MAX_FILE_BYTES:
                        try:
                            processing = self._unique_target(input_dir / '_processing', source.name)
                            self._move(source, processing)
                            self._fail_file(
                                db, endpoint, processing,
                                b'OVERSIZED:' + str(stat.st_size).encode(),
                                'CSV文件不得超过5MB',
                            )
                            summary['failed'] += 1
                        except Exception as exc:
                            db.rollback()
                            db.execute('UPDATE iot_machine_endpoint SET csv_last_error=? WHERE id=?',
                                       (str(exc)[:500], endpoint['id']))
                            db.commit()
                        continue
                    key = (endpoint['id'], str(source.resolve()))
                    signature = (stat.st_size, stat.st_mtime_ns)
                    previous = self._observed.get(key)
                    if not previous or previous[:2] != signature:
                        self._observed[key] = (*signature, self.now())
                        summary['unstable_files'] += 1
                        continue
                    stable_seconds = max(1, int(endpoint['csv_stable_seconds'] or 2))
                    if self.now() - previous[2] < stable_seconds:
                        summary['unstable_files'] += 1
                        continue
                    processing = self._unique_target(input_dir / '_processing', source.name)
                    try:
                        self._move(source, processing)
                        payload = processing.read_bytes()
                        self.importer(db, endpoint, payload, source.name, self.archive_root)
                        processing.unlink(missing_ok=True)
                        summary['imported'] += 1
                        db.execute(
                            '''UPDATE iot_machine_endpoint SET csv_last_scan_at=CURRENT_TIMESTAMP,
                               csv_last_error=NULL WHERE id=?''', (endpoint['id'],),
                        )
                        db.commit()
                    except Exception as exc:
                        db.rollback()
                        if processing.exists():
                            try:
                                payload = payload if payload is not None else processing.read_bytes()
                                self._fail_file(db, endpoint, processing, payload, exc)
                                summary['failed'] += 1
                            except Exception as record_exc:
                                db.rollback()
                                db.execute(
                                    'UPDATE iot_machine_endpoint SET csv_last_error=? WHERE id=?',
                                    (str(record_exc)[:500], endpoint['id']),
                                )
                                db.commit()
                    finally:
                        self._observed.pop(key, None)
                db.execute(
                    '''UPDATE iot_machine_endpoint SET csv_last_scan_at=CURRENT_TIMESTAMP,
                       csv_last_error=NULL WHERE id=?''',
                    (endpoint['id'],),
                )
                db.commit()
            self.last_collection_at = self.now()
            db.execute(
                '''INSERT INTO iot_machine_runtime(component,status,pid,started_at,heartbeat_at,last_error)
                   VALUES('csv_collector','running',?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,NULL)
                   ON CONFLICT(component) DO UPDATE SET status='running',pid=excluded.pid,
                     heartbeat_at=CURRENT_TIMESTAMP,last_error=NULL''',
                (os.getpid(),),
            )
            db.commit()
            return summary
        finally:
            db.close()

    def _run(self):
        while not self._stopping.is_set():
            try:
                self.scan_once()
            except Exception as exc:
                try:
                    db = sqlite3.connect(self.db_path, timeout=1)
                    db.execute(
                        '''UPDATE iot_machine_runtime SET status='error',heartbeat_at=CURRENT_TIMESTAMP,
                           last_error=? WHERE component='csv_collector' ''',
                        (str(exc)[:500],),
                    )
                    db.commit(); db.close()
                except sqlite3.Error:
                    pass
            self._stopping.wait(self.interval)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stopping.clear()
        db = sqlite3.connect(self.db_path, timeout=5)
        db.execute(
            '''INSERT INTO iot_machine_runtime(component,status,pid,started_at,heartbeat_at,last_error)
               VALUES('csv_collector','running',?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,NULL)
               ON CONFLICT(component) DO UPDATE SET status='running',pid=excluded.pid,
                 started_at=CURRENT_TIMESTAMP,heartbeat_at=CURRENT_TIMESTAMP,last_error=NULL''',
            (os.getpid(),),
        )
        db.commit(); db.close()
        self._thread = threading.Thread(target=self._run, name='aim-csv-collector', daemon=True)
        self._thread.start()

    def stop(self):
        self._stopping.set()
        if self._thread:
            self._thread.join(timeout=self.interval + 1)
            self._thread = None
        try:
            db = sqlite3.connect(self.db_path, timeout=5)
            db.execute(
                '''UPDATE iot_machine_runtime SET status='stopped',pid=NULL,
                   heartbeat_at=CURRENT_TIMESTAMP WHERE component='csv_collector' ''')
            db.commit(); db.close()
        except sqlite3.Error:
            pass
