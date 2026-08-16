import os
import sqlite3
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from utils import database  # noqa: E402


def test_default_departments_and_menus_are_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / 'seed-idempotency.db'
    monkeypatch.setattr(database, 'DB_PATH', str(db_path))

    database.init_db()
    database.init_db()

    db = sqlite3.connect(db_path)
    assert db.execute('SELECT COUNT(*) FROM sys_dept').fetchone()[0] == 5
    assert db.execute('SELECT COUNT(*) FROM sys_menu').fetchone()[0] == 40
    admin_role_id = db.execute(
        "SELECT id FROM sys_role WHERE role_key='admin'"
    ).fetchone()[0]
    assert db.execute(
        "SELECT role_id FROM sys_user WHERE username='admin'"
    ).fetchone()[0] == admin_role_id

    child = db.execute(
        "SELECT parent_id FROM sys_menu WHERE path='/prod/workorder'"
    ).fetchone()
    parent = db.execute(
        "SELECT id FROM sys_menu WHERE path='/production'"
    ).fetchone()
    assert child[0] == parent[0]
    db.close()


def test_legacy_user_table_gets_tenant_and_admin_role(tmp_path, monkeypatch):
    db_path = tmp_path / 'legacy-user.db'
    db = sqlite3.connect(db_path)
    db.execute(
        '''CREATE TABLE sys_user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE,password TEXT,
            real_name TEXT,phone TEXT,email TEXT,dept_id INTEGER,role_id INTEGER,
            status INTEGER DEFAULT 1,avatar TEXT,created_at TEXT,updated_at TEXT
        )'''
    )
    db.execute("INSERT INTO sys_user(username,password,real_name) VALUES('admin','x','admin')")
    db.commit()
    db.close()
    monkeypatch.setattr(database, 'DB_PATH', str(db_path))

    database.init_db()

    db = sqlite3.connect(db_path)
    assert 'tenant_id' in {row[1] for row in db.execute('PRAGMA table_info(sys_user)')}
    assert db.execute(
        '''SELECT r.role_key,u.tenant_id FROM sys_user u
           JOIN sys_role r ON r.id=u.role_id WHERE u.username='admin' '''
    ).fetchone() == ('admin', 1)
    db.close()
