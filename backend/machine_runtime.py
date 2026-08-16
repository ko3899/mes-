"""Own the machine Socket supervisors and CSV collector as one process service."""
import os
from pathlib import Path

from machine_csv_collector import MachineCsvCollector
from machine_gateway_manager import MachineGatewayManager
from utils.database import BASE_DIR, DB_PATH


class MachineCommunicationRuntime:
    def __init__(self, db_path=DB_PATH, archive_root=None, scan_interval=None,
                 gateway_factory=MachineGatewayManager,
                 collector_factory=MachineCsvCollector):
        self.db_path = str(db_path)
        self.archive_root = archive_root or os.environ.get(
            'MES_MACHINE_ARCHIVE_DIR', os.path.join(BASE_DIR, 'machine_archive')
        )
        self.scan_interval = float(
            scan_interval if scan_interval is not None
            else os.environ.get('MES_MACHINE_SCAN_SECONDS', '2')
        )
        self.gateway_factory = gateway_factory
        self.collector_factory = collector_factory
        self.gateway_manager = None
        self.csv_collector = None
        self._lock_file = None

    def _acquire_lock(self):
        lock_path = Path(self.db_path).resolve().with_suffix('.machine-runtime.lock')
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = open(lock_path, 'a+b')
        if lock_file.tell() == 0:
            lock_file.write(b'0')
            lock_file.flush()
        lock_file.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, IOError):
            lock_file.close()
            return False
        self._lock_file = lock_file
        return True

    def _release_lock(self):
        if not self._lock_file:
            return
        try:
            self._lock_file.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self._lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
        finally:
            self._lock_file.close()
            self._lock_file = None

    def start(self):
        if self.gateway_manager or self.csv_collector:
            return True
        if not self._acquire_lock():
            return False
        try:
            self.gateway_manager = self.gateway_factory(self.db_path)
            self.gateway_manager.start()
            self.csv_collector = self.collector_factory(
                self.db_path, self.archive_root, interval=self.scan_interval
            )
            self.csv_collector.start()
            return True
        except Exception:
            self.stop()
            raise

    def stop(self):
        if self.csv_collector:
            self.csv_collector.stop()
            self.csv_collector = None
        if self.gateway_manager:
            self.gateway_manager.stop()
            self.gateway_manager = None
        self._release_lock()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.stop()
