import os
import sqlite3
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from machine_csv_collector import MachineCsvCollector  # noqa: E402


def make_db(path, input_dir):
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE eqp_ledger(id INTEGER PRIMARY KEY,code TEXT,status INTEGER)')
    db.execute('''CREATE TABLE iot_machine_endpoint(
        id INTEGER PRIMARY KEY,equipment_id INTEGER,enabled INTEGER,csv_input_dir TEXT,csv_stable_seconds INTEGER,
        last_error TEXT,last_seen_at TEXT)''')
    db.execute("INSERT INTO eqp_ledger VALUES(1,'AIM001',1)")
    db.execute('INSERT INTO iot_machine_endpoint VALUES(1,1,1,?,2,NULL,NULL)', (str(input_dir),))
    db.commit(); db.close()


def test_waits_for_two_stable_observations_then_imports_once(tmp_path):
    input_dir = tmp_path / 'input'; input_dir.mkdir()
    db_path = tmp_path / 'collector.db'; make_db(db_path, input_dir)
    source = input_dir / 'ok.csv'; source.write_bytes(b'payload')
    imported = []
    clock = [100.0]
    collector = MachineCsvCollector(
        db_path, tmp_path / 'archive', now=lambda: clock[0],
        importer=lambda db, endpoint, payload, filename, archive: imported.append((payload, filename)) or {},
        failure_recorder=lambda *args: None,
    )
    assert collector.scan_once()['imported'] == 0
    clock[0] = 101.0
    assert collector.scan_once()['imported'] == 0
    clock[0] = 102.1
    assert collector.scan_once()['imported'] == 1
    assert imported == [(b'payload', 'ok.csv')]
    assert not source.exists()
    assert collector.scan_once()['imported'] == 0


def test_failed_file_moves_to_failed_and_missing_directory_does_not_stop_scan(tmp_path):
    input_dir = tmp_path / 'input'; input_dir.mkdir()
    db_path = tmp_path / 'collector.db'; make_db(db_path, input_dir)
    source = input_dir / 'bad.csv'; source.write_bytes(b'bad')
    failures = []
    clock = [100.0]

    def fail_import(*args):
        raise ValueError('坏表头')

    collector = MachineCsvCollector(
        db_path, tmp_path / 'archive', now=lambda: clock[0], importer=fail_import,
        failure_recorder=lambda db, ep, payload, name, path, reason: failures.append((name, path.name, reason)),
    )
    collector.scan_once(); clock[0] = 103.0
    result = collector.scan_once()
    assert result['failed'] == 1
    assert failures == [('bad.csv', 'bad.csv', '坏表头')]
    assert (input_dir / '_failed' / 'bad.csv').exists()
    input_dir.rename(tmp_path / 'gone')
    result = collector.scan_once()
    assert result['missing_directories'] == 1


def test_ignores_hidden_non_csv_subdirectories_and_oversized_files(tmp_path):
    input_dir = tmp_path / 'input'; input_dir.mkdir()
    db_path = tmp_path / 'collector.db'; make_db(db_path, input_dir)
    (input_dir / '.hidden.csv').write_text('x')
    (input_dir / 'temp.tmp').write_text('x')
    (input_dir / 'folder').mkdir()
    (input_dir / 'large.csv').write_bytes(b'x' * (5 * 1024 * 1024 + 1))
    failures = []
    collector = MachineCsvCollector(
        db_path, tmp_path / 'archive', now=lambda: 100.0,
        importer=lambda *args: (_ for _ in ()).throw(AssertionError('must not import')),
        failure_recorder=lambda db, ep, payload, name, path, reason: failures.append(reason),
    )
    collector.scan_once()
    assert failures == ['CSV文件不得超过5MB']
    assert (input_dir / '_failed' / 'large.csv').exists()


def test_recovers_processing_file_after_restart(tmp_path):
    input_dir = tmp_path / 'input'; (input_dir / '_processing').mkdir(parents=True)
    db_path = tmp_path / 'collector.db'; make_db(db_path, input_dir)
    (input_dir / '_processing' / 'recovered.csv').write_bytes(b'payload')
    imported = []; clock = [100.0]
    collector = MachineCsvCollector(
        db_path, tmp_path / 'archive', now=lambda: clock[0],
        importer=lambda db, ep, payload, name, root: imported.append(name) or {},
        failure_recorder=lambda *args: None,
    )
    collector.scan_once(); clock[0] = 103.0; collector.scan_once()
    assert imported == ['recovered.csv']


def test_prunes_stale_observed_entries_to_avoid_memory_leak(tmp_path):
    input_dir = tmp_path / 'input'; input_dir.mkdir()
    db_path = tmp_path / 'collector.db'; make_db(db_path, input_dir)
    (input_dir / 'stale.csv').write_bytes(b'payload')
    clock = [100.0]
    collector = MachineCsvCollector(
        db_path, tmp_path / 'archive', now=lambda: clock[0],
        importer=lambda *args: (_ for _ in ()).throw(AssertionError('must not import')),
        failure_recorder=lambda *args: None,
    )
    # first scan observes the file
    collector.scan_once()
    assert (1, str((input_dir / 'stale.csv').resolve())) in collector._observed
    # advance beyond 1 hour stale threshold
    clock[0] = 3700.0
    collector.scan_once()
    # stale entry should be pruned
    assert (1, str((input_dir / 'stale.csv').resolve())) not in collector._observed

