"""Shared test fixtures and session-level database templates.

The MES schema has many tables; running ``init_db()`` + ``_init_extra_tables()``
for every test costs ~3.4 seconds.  We build pristine template databases once
per session and let each test copy them, which is orders of magnitude faster.

We keep two templates:

* ``_BASE_TEMPLATE`` – result of ``init_db()`` only.
* ``_FULL_TEMPLATE`` – result of ``init_db()`` + ``_init_extra_tables()``.

Tests that call ``init_db()`` on a fresh path get the base template.  Tests
that also call ``_init_extra_tables()`` get the full template copied on top.
If a database file already exists when ``init_db()`` is called (some migration
and idempotency tests pre-seed a partial database), we fall back to the
original slow implementation so those tests remain valid.
"""

import os
import shutil
import sqlite3
import sys
import tempfile

import pytest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from utils import database  # noqa: E402


# Keep references to the original slow initializers before we patch them.
_original_init_db = database.init_db
_original_init_extra_tables = database._init_extra_tables


def _build_templates():
    """Create base-only and fully-initialized template database files."""
    fd, base_path = tempfile.mkstemp(suffix='.mes-base-template.db')
    os.close(fd)
    original_path = database.DB_PATH
    try:
        database.DB_PATH = base_path
        _original_init_db()
    finally:
        database.DB_PATH = original_path

    fd, full_path = tempfile.mkstemp(suffix='.mes-full-template.db')
    os.close(fd)
    try:
        database.DB_PATH = full_path
        _original_init_db()
        _original_init_extra_tables()
    finally:
        database.DB_PATH = original_path

    return base_path, full_path


_BASE_TEMPLATE, _FULL_TEMPLATE = _build_templates()


@pytest.fixture(scope='session')
def _template_paths():
    return {'base': _BASE_TEMPLATE, 'full': _FULL_TEMPLATE}


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Return a fresh sqlite3 connection initialised from the full template."""
    target = tmp_path / 'test.db'
    shutil.copy(_FULL_TEMPLATE, target)
    monkeypatch.setattr(database, 'DB_PATH', str(target))
    conn = sqlite3.connect(str(target))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Fast database initialisation used by tests that call init_db() themselves.
# ---------------------------------------------------------------------------

def _has_extra_tables(path):
    """Heuristic: does the database already contain the extra tables?"""
    try:
        conn = sqlite3.connect(path)
        try:
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            # prod_workorder_route_step is created by _init_extra_tables
            return 'prod_workorder_route_step' in tables
        finally:
            conn.close()
    except Exception:
        return False


def _fast_init_db():
    """Copy the base template for fresh DBs; fall back if DB already exists."""
    if database.DB_PATH == _BASE_TEMPLATE or database.DB_PATH == _FULL_TEMPLATE:
        return
    if os.path.exists(database.DB_PATH):
        # Some tests pre-create a partial database and rely on init_db() to
        # migrate it.  In that case we must run the real DDL.
        _original_init_db()
        return
    directory = os.path.dirname(database.DB_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    shutil.copy(_BASE_TEMPLATE, database.DB_PATH)


def _fast_init_extra_tables():
    """Copy the full template for fresh DBs; fall back if DB already exists."""
    if database.DB_PATH == _BASE_TEMPLATE or database.DB_PATH == _FULL_TEMPLATE:
        return
    if not os.path.exists(database.DB_PATH):
        return
    # If the database already exists it may contain legacy/partial data that
    # must be migrated by the real implementation.  Only use the fast copy when
    # the file is empty/new.
    try:
        if os.path.getsize(database.DB_PATH) == 0:
            shutil.copy(_FULL_TEMPLATE, database.DB_PATH)
            return
    except OSError:
        pass
    _original_init_extra_tables()


@pytest.fixture(scope='session', autouse=True)
def _patch_database_initialization():
    """Replace slow initializers with template-based versions for all tests."""
    database.init_db = _fast_init_db
    database._init_extra_tables = _fast_init_extra_tables
    yield
