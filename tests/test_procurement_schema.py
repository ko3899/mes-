import os
import sqlite3
import sys

import pytest


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from utils import database  # noqa: E402


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / 'procurement-schema.db'
    monkeypatch.setattr(database, 'DB_PATH', str(db_path))
    database.init_db()
    database._init_extra_tables()
    connection = sqlite3.connect(db_path)
    try:
        yield connection
    finally:
        connection.close()


def _columns(db, table):
    return {row[1] for row in db.execute(f'PRAGMA table_info("{table}")')}


def _indexes(db, table):
    return {row[1] for row in db.execute(f'PRAGMA index_list("{table}")')}


def _index_contract(db, table, index):
    metadata = {
        row[1]: bool(row[2]) for row in db.execute(f'PRAGMA index_list("{table}")')
    }
    columns = [row[2] for row in db.execute(f'PRAGMA index_info("{index}")')]
    return metadata.get(index), columns


def _foreign_keys(db, table):
    return {(row[3], row[2], row[4]) for row in db.execute(
        f'PRAGMA foreign_key_list("{table}")'
    )}


def _seed_procurement_references(db):
    supplier_id = db.execute(
        "INSERT INTO base_supplier(supplier_name,code) VALUES('采购测试供应商','SCM-TEST-SUP')"
    ).lastrowid
    product_id = db.execute(
        "INSERT INTO base_product(product_name,code) VALUES('采购测试物料','SCM-TEST-PROD')"
    ).lastrowid
    warehouse_id = db.execute(
        "INSERT INTO inv_warehouse(warehouse_name,code) VALUES('采购测试仓','SCM-TEST-WH')"
    ).lastrowid
    area_id = db.execute(
        "INSERT INTO inv_area(warehouse_id,area_name,code) VALUES(?,'采购测试区','SCM-TEST-AREA')",
        (warehouse_id,),
    ).lastrowid
    location_id = db.execute(
        "INSERT INTO inv_location(area_id,location_name,code) VALUES(?,'采购测试位','SCM-TEST-LOC')",
        (area_id,),
    ).lastrowid
    return supplier_id, product_id, warehouse_id, area_id, location_id


def _create_partial_v1_database(
    db_path, orphan_supplier=False, duplicate_stock_identity=False
):
    database.DB_PATH = str(db_path)
    database.init_db()
    connection = sqlite3.connect(db_path)
    connection.executescript('''
        CREATE TABLE scm_purchase_order (
            id INTEGER PRIMARY KEY AUTOINCREMENT, order_no TEXT NOT NULL UNIQUE,
            supplier_id INTEGER NOT NULL, status INTEGER NOT NULL DEFAULT 0,
            expected_date TEXT, currency TEXT, remark TEXT, created_by INTEGER NOT NULL,
            submitted_by INTEGER, submitted_at TIMESTAMP, approved_by INTEGER,
            approved_at TIMESTAMP, rejected_reason TEXT, closed_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE scm_purchase_order_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL, ordered_qty REAL NOT NULL,
            unit_price REAL DEFAULT 0, tax_rate REAL DEFAULT 0,
            arrived_qty REAL DEFAULT 0, accepted_qty REAL DEFAULT 0,
            returned_qty REAL DEFAULT 0, posted_qty REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES scm_purchase_order(id)
        );
        CREATE TABLE inv_receipt_posting (
            id INTEGER PRIMARY KEY AUTOINCREMENT, posting_no TEXT NOT NULL UNIQUE,
            arrival_item_id INTEGER NOT NULL, inspection_id INTEGER,
            product_id INTEGER NOT NULL, warehouse_id INTEGER NOT NULL,
            area_id INTEGER NOT NULL, location_id INTEGER NOT NULL,
            batch_no TEXT NOT NULL, quantity REAL NOT NULL, operator_id INTEGER NOT NULL,
            client_operation_id TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (arrival_item_id) REFERENCES inv_arrival_notice_item(id),
            FOREIGN KEY (inspection_id) REFERENCES qm_incoming_inspection(id)
        );
        CREATE TABLE inv_stock_balance (
            id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL,
            warehouse_id INTEGER NOT NULL, area_id INTEGER NOT NULL,
            location_id INTEGER NOT NULL, batch_no TEXT NOT NULL,
            quantity REAL NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    supplier, product, warehouse, area, location = _seed_procurement_references(connection)
    purchase_supplier = 999999 if orphan_supplier else supplier
    connection.execute(
        '''INSERT INTO scm_purchase_order
           (id,order_no,supplier_id,status,currency,remark,created_by)
           VALUES(41,'PO-PARTIAL-V1',?,2,'CNY','v1-marker',1)''',
        (purchase_supplier,),
    )
    connection.execute(
        '''INSERT INTO scm_purchase_order_item
           (id,order_id,product_id,ordered_qty,unit_price,arrived_qty)
           VALUES(42,41,?,15.5,8.25,3.5)''',
        (product,),
    )
    notice_id = connection.execute(
        "INSERT INTO inv_arrival_notice(notice_no,supplier_id) VALUES('ARR-PARTIAL-V1',?)",
        (supplier,),
    ).lastrowid
    arrival_item_id = connection.execute(
        '''INSERT INTO inv_arrival_notice_item
           (notice_id,product_id,quantity) VALUES(?,?,3.5)''',
        (notice_id, product),
    ).lastrowid
    inspection_id = connection.execute(
        '''INSERT INTO qm_incoming_inspection(inspect_no,status)
           VALUES('IQC-PARTIAL-V1',1)'''
    ).lastrowid
    connection.execute(
        '''INSERT INTO inv_receipt_posting
           (id,posting_no,arrival_item_id,inspection_id,product_id,warehouse_id,
            area_id,location_id,batch_no,quantity,operator_id,client_operation_id)
           VALUES(43,'POST-PARTIAL-V1',?,?,?,?,?,?,'V1-BATCH',2.5,1,'v1-post')''',
        (arrival_item_id, inspection_id, product, warehouse, area, location),
    )
    connection.execute(
        '''INSERT INTO inv_stock_balance
           (id,product_id,warehouse_id,area_id,location_id,batch_no,quantity)
           VALUES(44,?,?,?,?, 'V1-BATCH',2.5)''',
        (product, warehouse, area, location),
    )
    if duplicate_stock_identity:
        connection.execute(
            '''INSERT INTO inv_stock_balance
               (id,product_id,warehouse_id,area_id,location_id,batch_no,quantity)
               VALUES(45,?,?,?,?, 'V1-BATCH',1.25)''',
            (product, warehouse, area, location),
        )
    connection.commit()
    return connection


def test_procurement_schema_is_additive(db):
    tables = {row[0] for row in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert {
        'scm_purchase_order',
        'scm_purchase_order_item',
        'inv_arrival_notice',
        'inv_arrival_notice_item',
        'inv_receipt_action',
        'qm_incoming_inspection',
        'qm_incoming_inspection_item',
        'inv_receipt_posting',
        'inv_stock_balance',
        'scm_procurement_status_log',
    } <= tables

    expected_columns = {
        'scm_purchase_order': {
            'id', 'order_no', 'supplier_id', 'status', 'expected_date', 'currency',
            'remark', 'created_by', 'submitted_by', 'submitted_at', 'approved_by',
            'approved_at', 'rejected_reason', 'closed_reason', 'created_at', 'updated_at',
        },
        'scm_purchase_order_item': {
            'id', 'order_id', 'product_id', 'ordered_qty', 'unit_price', 'tax_rate',
            'arrived_qty', 'accepted_qty', 'returned_qty', 'posted_qty', 'created_at',
        },
        'inv_arrival_notice': {
            'id', 'notice_no', 'purchase_order_id', 'supplier_id', 'delivery_note_no',
            'arrived_at', 'status', 'exception_code', 'exception_reason', 'created_by',
            'created_at', 'updated_at',
        },
        'inv_arrival_notice_item': {
            'id', 'notice_id', 'purchase_order_item_id', 'product_id', 'quantity',
            'arrived_qty', 'normal_qty', 'excess_qty', 'accepted_qty', 'returned_qty',
            'pending_qty', 'inspection_mode', 'created_at',
        },
        'inv_receipt_action': {
            'id', 'arrival_item_id', 'action_type', 'quantity', 'reason', 'operator_id',
            'client_operation_id', 'created_at',
        },
        'qm_incoming_inspection': {
            'id', 'inspect_no', 'inspection_no', 'arrival_item_id', 'mode', 'status',
            'sampled_qty', 'passed_qty', 'failed_qty', 'pending_qty', 'conclusion',
            'inspector_id', 'inspected_at', 'concession_approved_by',
            'concession_reason', 'created_at',
        },
        'qm_incoming_inspection_item': {
            'id', 'inspection_id', 'item_name', 'standard', 'measured_value', 'result',
            'defect_id', 'defect_qty', 'remark', 'created_at',
        },
        'inv_receipt_posting': {
            'id', 'posting_no', 'arrival_item_id', 'inspection_id', 'product_id',
            'warehouse_id', 'area_id', 'location_id', 'batch_no', 'quantity',
            'operator_id', 'client_operation_id', 'created_at',
        },
        'inv_stock_balance': {
            'id', 'product_id', 'warehouse_id', 'area_id', 'location_id', 'batch_no',
            'quantity', 'updated_at',
        },
        'scm_procurement_status_log': {
            'id', 'entity_type', 'entity_id', 'from_status', 'to_status', 'action',
            'operator_id', 'reason', 'created_at',
        },
    }
    for table, columns in expected_columns.items():
        assert columns <= _columns(db, table), table


def test_procurement_quantity_identity_and_operations_are_unique(db):
    assert _index_contract(
        db, 'inv_stock_balance', 'uq_inv_stock_balance_identity'
    ) == (True, ['product_id', 'warehouse_id', 'area_id', 'location_id', 'batch_no'])
    assert _index_contract(
        db, 'inv_receipt_action', 'uq_inv_receipt_action_operation'
    ) == (True, ['operator_id', 'client_operation_id'])
    assert _index_contract(
        db, 'inv_receipt_posting', 'uq_inv_receipt_posting_operation'
    ) == (True, ['operator_id', 'client_operation_id'])
    assert _index_contract(
        db, 'qm_incoming_inspection', 'uq_qm_incoming_inspection_no'
    ) == (True, ['inspection_no'])


def test_procurement_unique_indexes_enforce_non_null_operations(db):
    supplier, product, warehouse, area, location = _seed_procurement_references(db)
    notice_id = db.execute(
        "INSERT INTO inv_arrival_notice(notice_no,supplier_id) VALUES('ARR-UQ-1',?)",
        (supplier,),
    ).lastrowid
    arrival_item_id = db.execute(
        '''INSERT INTO inv_arrival_notice_item
           (notice_id,product_id,quantity,arrived_qty) VALUES(?,?,10,10)''',
        (notice_id, product),
    ).lastrowid
    inspection_id = db.execute(
        '''INSERT INTO qm_incoming_inspection
           (inspect_no,inspection_no,arrival_item_id) VALUES('IQC-UQ-1','IQC-UQ-1',?)''',
        (arrival_item_id,),
    ).lastrowid

    db.execute(
        "INSERT INTO inv_receipt_action(arrival_item_id,action_type,quantity,operator_id,client_operation_id) VALUES(?,'accept',1,7,'same-action')",
        (arrival_item_id,),
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO inv_receipt_action(arrival_item_id,action_type,quantity,operator_id,client_operation_id) VALUES(?,'accept',1,7,'same-action')",
            (arrival_item_id,),
        )
    for _ in range(2):
        db.execute(
            "INSERT INTO inv_receipt_action(arrival_item_id,action_type,quantity,operator_id,client_operation_id) VALUES(?,'accept',1,7,NULL)",
            (arrival_item_id,),
        )

    posting = (arrival_item_id, inspection_id, product, warehouse, area, location)
    db.execute(
        '''INSERT INTO inv_receipt_posting
           (posting_no,arrival_item_id,inspection_id,product_id,warehouse_id,area_id,
            location_id,batch_no,quantity,operator_id,client_operation_id)
           VALUES('POST-UQ-1',?,?,?,?,?,?,'B1',1,8,'same-post')''',
        posting,
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            '''INSERT INTO inv_receipt_posting
               (posting_no,arrival_item_id,inspection_id,product_id,warehouse_id,area_id,
                location_id,batch_no,quantity,operator_id,client_operation_id)
               VALUES('POST-UQ-2',?,?,?,?,?,?,'B1',1,8,'same-post')''',
            posting,
        )
    for number in ('POST-NULL-1', 'POST-NULL-2'):
        db.execute(
            '''INSERT INTO inv_receipt_posting
               (posting_no,arrival_item_id,inspection_id,product_id,warehouse_id,area_id,
                location_id,batch_no,quantity,operator_id,client_operation_id)
               VALUES(?,?,?,?,?,?,?,'B2',1,8,NULL)''',
            (number,) + posting,
        )

    identity = (product, warehouse, area, location, 'B1')
    db.execute(
        '''INSERT INTO inv_stock_balance
           (product_id,warehouse_id,area_id,location_id,batch_no,quantity)
           VALUES(?,?,?,?,?,1)''',
        identity,
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            '''INSERT INTO inv_stock_balance
               (product_id,warehouse_id,area_id,location_id,batch_no,quantity)
               VALUES(?,?,?,?,?,1)''',
            identity,
        )

    db.execute(
        "INSERT INTO qm_incoming_inspection(inspect_no,inspection_no) VALUES('IQC-IDX-1','IQC-UNIQUE')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO qm_incoming_inspection(inspect_no,inspection_no) VALUES('IQC-IDX-2','IQC-UNIQUE')"
        )
    db.execute(
        "INSERT INTO qm_incoming_inspection(inspect_no,inspection_no) VALUES('IQC-NULL-1',NULL)"
    )
    db.execute(
        "INSERT INTO qm_incoming_inspection(inspect_no,inspection_no) VALUES('IQC-NULL-2',NULL)"
    )


def test_procurement_new_tables_have_business_foreign_keys(db):
    assert {('supplier_id', 'base_supplier', 'id')} <= _foreign_keys(db, 'scm_purchase_order')
    assert {
        ('order_id', 'scm_purchase_order', 'id'),
        ('product_id', 'base_product', 'id'),
    } <= _foreign_keys(db, 'scm_purchase_order_item')
    assert {('arrival_item_id', 'inv_arrival_notice_item', 'id')} <= _foreign_keys(
        db, 'inv_receipt_action'
    )
    assert {
        ('arrival_item_id', 'inv_arrival_notice_item', 'id'),
        ('inspection_id', 'qm_incoming_inspection', 'id'),
        ('product_id', 'base_product', 'id'),
        ('warehouse_id', 'inv_warehouse', 'id'),
        ('area_id', 'inv_area', 'id'),
        ('location_id', 'inv_location', 'id'),
    } <= _foreign_keys(db, 'inv_receipt_posting')
    assert {
        ('product_id', 'base_product', 'id'),
        ('warehouse_id', 'inv_warehouse', 'id'),
        ('area_id', 'inv_area', 'id'),
        ('location_id', 'inv_location', 'id'),
    } <= _foreign_keys(db, 'inv_stock_balance')


def test_legacy_not_null_columns_have_an_explicit_dual_write_contract(db):
    supplier, product, _, _, _ = _seed_procurement_references(db)
    notice_id = db.execute(
        "INSERT INTO inv_arrival_notice(notice_no,supplier_id) VALUES('ARR-DUAL-1',?)",
        (supplier,),
    ).lastrowid
    item_id = db.execute(
        '''INSERT INTO inv_arrival_notice_item
           (notice_id,product_id,quantity,arrived_qty) VALUES(?,?,12.5,12.5)''',
        (notice_id, product),
    ).lastrowid
    assert db.execute(
        'SELECT quantity,arrived_qty FROM inv_arrival_notice_item WHERE id=?', (item_id,)
    ).fetchone() == (12.5, 12.5)

    inspection_id = db.execute(
        '''INSERT INTO qm_incoming_inspection
           (inspect_no,inspection_no,arrival_item_id,mode)
           VALUES('IQC-DUAL-1','IQC-DUAL-1',?,'required')''',
        (item_id,),
    ).lastrowid
    assert db.execute(
        'SELECT inspect_no,inspection_no FROM qm_incoming_inspection WHERE id=?',
        (inspection_id,),
    ).fetchone() == ('IQC-DUAL-1', 'IQC-DUAL-1')


def test_procurement_migration_preserves_legacy_arrival_rows(tmp_path, monkeypatch):
    db_path = tmp_path / 'legacy-arrival.db'
    legacy = sqlite3.connect(db_path)
    legacy.execute('''CREATE TABLE inv_arrival_notice (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        notice_no TEXT NOT NULL UNIQUE,
        supplier_id INTEGER,
        status INTEGER DEFAULT 0,
        expected_date TEXT,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    legacy.execute('''CREATE TABLE inv_arrival_notice_item (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        notice_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity REAL NOT NULL
    )''')
    legacy.execute('''CREATE TABLE qm_incoming_inspection (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inspect_no TEXT NOT NULL UNIQUE,
        inbound_id INTEGER,
        supplier TEXT,
        template_id INTEGER,
        result TEXT,
        status INTEGER DEFAULT 0,
        inspector INTEGER,
        inspect_time TIMESTAMP,
        remark TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    legacy.execute('''CREATE TABLE inv_balance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL UNIQUE,
        quantity REAL DEFAULT 0,
        amount REAL DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    legacy.execute(
        "INSERT INTO inv_arrival_notice(notice_no,supplier_id,expected_date,remark) "
        "VALUES('LEGACY-ARR-1',9,'2026-08-17','keep me')"
    )
    legacy.execute(
        'INSERT INTO inv_arrival_notice_item(notice_id,product_id,quantity) VALUES(1,5,12.5)'
    )
    legacy.execute(
        '''INSERT INTO qm_incoming_inspection
           (inspect_no,inbound_id,supplier,result,status,inspector,remark)
           VALUES('LEGACY-IQC-1',8,'旧供应商','passed',1,6,'keep inspection')'''
    )
    legacy.execute(
        'INSERT INTO inv_balance(product_id,quantity,amount) VALUES(5,23.75,99.5)'
    )
    before_arrival = legacy.execute(
        'SELECT id,notice_no,supplier_id,status,expected_date,remark FROM inv_arrival_notice'
    ).fetchall()
    before_items = legacy.execute(
        'SELECT id,notice_id,product_id,quantity FROM inv_arrival_notice_item'
    ).fetchall()
    before_inspections = legacy.execute(
        '''SELECT id,inspect_no,inbound_id,supplier,result,status,inspector,remark
           FROM qm_incoming_inspection'''
    ).fetchall()
    before_balance = legacy.execute(
        'SELECT id,product_id,quantity,amount FROM inv_balance'
    ).fetchall()
    legacy.commit()
    legacy.close()

    monkeypatch.setattr(database, 'DB_PATH', str(db_path))
    database.init_db()
    database._init_extra_tables()
    database._init_extra_tables()

    migrated = sqlite3.connect(db_path)
    try:
        assert migrated.execute(
            'SELECT id,notice_no,supplier_id,status,expected_date,remark FROM inv_arrival_notice'
        ).fetchall() == before_arrival
        assert migrated.execute(
            'SELECT id,notice_id,product_id,quantity FROM inv_arrival_notice_item'
        ).fetchall() == before_items
        assert migrated.execute(
            '''SELECT id,inspect_no,inbound_id,supplier,result,status,inspector,remark
               FROM qm_incoming_inspection'''
        ).fetchall() == before_inspections
        assert migrated.execute(
            'SELECT id,product_id,quantity,amount FROM inv_balance'
        ).fetchall() == before_balance
    finally:
        migrated.close()


def test_partial_v1_tables_are_rebuilt_with_foreign_keys_without_data_loss(
    tmp_path, monkeypatch
):
    db_path = tmp_path / 'partial-v1.db'
    monkeypatch.setattr(database, 'DB_PATH', str(db_path))
    partial = _create_partial_v1_database(db_path)
    snapshots = {
        table: partial.execute(f'SELECT * FROM "{table}" ORDER BY id').fetchall()
        for table in (
            'scm_purchase_order', 'scm_purchase_order_item',
            'inv_receipt_posting', 'inv_stock_balance',
        )
    }
    partial.close()

    database._init_extra_tables()
    database._init_extra_tables()

    migrated = sqlite3.connect(db_path)
    migrated.execute('PRAGMA foreign_keys = ON')
    try:
        for table, rows in snapshots.items():
            assert migrated.execute(
                f'SELECT * FROM "{table}" ORDER BY id'
            ).fetchall() == rows
        assert {('supplier_id', 'base_supplier', 'id')} <= _foreign_keys(
            migrated, 'scm_purchase_order'
        )
        assert ('product_id', 'base_product', 'id') in _foreign_keys(
            migrated, 'scm_purchase_order_item'
        )
        assert {
            ('product_id', 'base_product', 'id'),
            ('warehouse_id', 'inv_warehouse', 'id'),
            ('area_id', 'inv_area', 'id'),
            ('location_id', 'inv_location', 'id'),
        } <= _foreign_keys(migrated, 'inv_receipt_posting')
        assert {
            ('product_id', 'base_product', 'id'),
            ('warehouse_id', 'inv_warehouse', 'id'),
            ('area_id', 'inv_area', 'id'),
            ('location_id', 'inv_location', 'id'),
        } <= _foreign_keys(migrated, 'inv_stock_balance')
        assert migrated.execute('PRAGMA foreign_key_check').fetchall() == []
        with pytest.raises(sqlite3.IntegrityError):
            migrated.execute(
                '''INSERT INTO scm_purchase_order
                   (order_no,supplier_id,status,created_by)
                   VALUES('PO-ORPHAN-BLOCKED',999999,0,1)'''
            )
    finally:
        migrated.close()


def test_partial_v1_rebuild_rolls_back_when_existing_rows_are_orphaned(
    tmp_path, monkeypatch
):
    db_path = tmp_path / 'partial-v1-orphan.db'
    monkeypatch.setattr(database, 'DB_PATH', str(db_path))
    partial = _create_partial_v1_database(db_path, orphan_supplier=True)
    before = partial.execute(
        'SELECT * FROM scm_purchase_order ORDER BY id'
    ).fetchall()
    partial.close()

    connection = sqlite3.connect(db_path)
    connection.execute('PRAGMA foreign_keys = ON')
    try:
        with pytest.raises(sqlite3.IntegrityError):
            database._init_procurement_schema(connection)
        assert connection.execute(
            'SELECT * FROM scm_purchase_order ORDER BY id'
        ).fetchall() == before
        assert ('supplier_id', 'base_supplier', 'id') not in _foreign_keys(
            connection, 'scm_purchase_order'
        )
        assert not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name LIKE '__procurement_new_%'"
        ).fetchone()
    finally:
        connection.close()


def test_partial_v1_fk_rebuild_and_unique_indexes_commit_atomically(
    tmp_path, monkeypatch
):
    db_path = tmp_path / 'partial-v1-duplicate-stock.db'
    monkeypatch.setattr(database, 'DB_PATH', str(db_path))
    partial = _create_partial_v1_database(
        db_path, duplicate_stock_identity=True
    )
    before = {
        table: partial.execute(f'SELECT * FROM "{table}" ORDER BY id').fetchall()
        for table in (
            'scm_purchase_order', 'scm_purchase_order_item',
            'inv_receipt_posting', 'inv_stock_balance',
        )
    }
    partial.close()

    connection = sqlite3.connect(db_path)
    connection.execute('PRAGMA foreign_keys = ON')
    try:
        with pytest.raises(sqlite3.IntegrityError):
            database._init_procurement_schema(connection)

        for table, rows in before.items():
            assert connection.execute(
                f'SELECT * FROM "{table}" ORDER BY id'
            ).fetchall() == rows
        assert ('supplier_id', 'base_supplier', 'id') not in _foreign_keys(
            connection, 'scm_purchase_order'
        )
        business_indexes = {
            'uq_inv_stock_balance_identity',
            'uq_inv_receipt_action_operation',
            'uq_inv_receipt_posting_operation',
            'uq_qm_incoming_inspection_no',
        }
        actual_indexes = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )}
        assert not business_indexes & actual_indexes
        assert not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name LIKE '__procurement_new_%'"
        ).fetchone()

        connection.execute('DELETE FROM inv_stock_balance WHERE id=45')
        connection.commit()
        database._init_procurement_schema(connection)

        assert ('supplier_id', 'base_supplier', 'id') in _foreign_keys(
            connection, 'scm_purchase_order'
        )
        actual_indexes = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )}
        assert business_indexes <= actual_indexes
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
        assert connection.execute(
            'SELECT COUNT(*) FROM inv_stock_balance'
        ).fetchone()[0] == 1
    finally:
        connection.close()
