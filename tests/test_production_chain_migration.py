import os
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from utils import database  # noqa: E402
from production_chain_support import (  # noqa: E402
    column_names,
    create_legacy_db,
    table_names,
)


def test_extra_migration_preserves_legacy_rows_and_adds_snapshots(tmp_path, monkeypatch):
    path = tmp_path / 'legacy.db'
    db = create_legacy_db(path)
    db.execute("INSERT INTO base_process(process_name,code) VALUES('旧工序','OLD')")
    db.commit()
    db.close()

    monkeypatch.setattr(database, 'DB_PATH', str(path))
    database._init_extra_tables()

    db = create_connection(path)
    assert db.execute('SELECT process_name FROM base_process').fetchone()[0] == '旧工序'
    assert {
        'prod_batch', 'prod_workorder_route_snapshot',
        'prod_workorder_route_step', 'prod_workorder_bom_snapshot',
        'sys_business_status_log',
    } <= table_names(db)
    assert {'workshop_id', 'version'} <= column_names(db, 'base_process_route')
    assert {'workshop_id', 'is_inspection_point'} <= column_names(db, 'base_process_route_detail')
    assert {'production_batch_id', 'route_version', 'bom_version'} <= column_names(db, 'prod_workorder')
    assert 'route_step_id' in column_names(db, 'prod_task')
    assert {'approval_status', 'defect_id', 'posted_at'} <= column_names(db, 'prod_report')
    assert {
        'production_batch_id', 'bom_snapshot_id', 'required_qty', 'requested_qty',
        'issued_qty', 'received_qty', 'returned_qty', 'warehouse_id', 'location_id',
        'material_batch_no', 'issued_at', 'received_at', 'remark',
    } <= column_names(db, 'prod_material_req')
    db.close()


def test_extra_migration_is_idempotent(tmp_path, monkeypatch):
    path = tmp_path / 'legacy-twice.db'
    create_legacy_db(path).close()
    monkeypatch.setattr(database, 'DB_PATH', str(path))
    database._init_extra_tables()
    database._init_extra_tables()

    db = create_connection(path)
    indexes = {row[0] for row in db.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    )}
    assert 'idx_prod_batch_plan_item' in indexes
    assert 'idx_prod_route_step_snapshot' in indexes
    db.close()


def test_production_batch_is_registered_for_manual_ordering():
    from utils.table_order import ORDERABLE_TABLES
    assert ORDERABLE_TABLES['prod/batch'] == 'prod_batch'


def create_connection(path):
    import sqlite3
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    return db
