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
