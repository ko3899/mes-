import sqlite3


def create_legacy_db(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript('''
        CREATE TABLE base_process (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            process_name TEXT NOT NULL,
            code TEXT NOT NULL UNIQUE,
            workshop_id INTEGER,
            description TEXT,
            standard_time REAL,
            status INTEGER DEFAULT 1
        );
        CREATE TABLE base_process_route (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            route_name TEXT NOT NULL,
            description TEXT,
            status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE base_process_route_detail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_id INTEGER NOT NULL,
            process_id INTEGER NOT NULL,
            step_no INTEGER NOT NULL,
            standard_time REAL,
            description TEXT
        );
        CREATE TABLE prod_workorder (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no TEXT NOT NULL UNIQUE,
            product_id INTEGER NOT NULL,
            planned_qty REAL NOT NULL,
            status INTEGER DEFAULT 0
        );
        CREATE TABLE prod_task (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_no TEXT NOT NULL UNIQUE,
            workorder_id INTEGER NOT NULL,
            process_id INTEGER NOT NULL,
            planned_qty REAL NOT NULL,
            status INTEGER DEFAULT 0
        );
        CREATE TABLE prod_report (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_no TEXT NOT NULL UNIQUE,
            task_id INTEGER NOT NULL,
            workorder_id INTEGER NOT NULL,
            process_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            qualified_qty REAL NOT NULL,
            defect_qty REAL DEFAULT 0,
            client_operation_id TEXT
        );
        CREATE TABLE prod_material_req (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            req_no TEXT NOT NULL UNIQUE,
            workorder_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            req_type TEXT,
            status INTEGER DEFAULT 0
        );
        CREATE TABLE prod_plan_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            planned_qty REAL NOT NULL,
            completed_qty REAL DEFAULT 0,
            workshop_id INTEGER
        );
    ''')
    db.commit()
    return db


def column_names(db, table):
    return {row[1] for row in db.execute(f'PRAGMA table_info("{table}")')}


def table_names(db):
    return {row[0] for row in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}


def seed_reference_data(db):
    db.execute(
        "INSERT INTO base_process(process_name, code, workshop_id) VALUES(?,?,?)",
        ('测试工序', 'PROC-TEST', 1),
    )
    db.commit()


def authenticated_test_client(path):
    from app import app
    from utils import database

    database.DB_PATH = str(path)
    app.config.update(TESTING=True, SECRET_KEY='production-chain-test')
    client = app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = 1
        session['username'] = 'admin'
    return client
