"""PostgreSQL compatibility layer that mimics the sqlite3 connection API used
throughout the MES blueprints.

The blueprints call ``db.execute(sql, params)``, read ``row['col']``, use
``cursor.lastrowid`` and ``cursor.rowcount``, and call ``db.commit()`` /
``db.rollback()``.  This module wraps psycopg2 so the same call sites work on
PostgreSQL with minimal changes.

Known limitations (must be handled per-call-site when encountered):
* ``lastrowid`` only works for INSERT statements on tables with an ``id`` column.
* ``PRAGMA`` statements are no-ops.
* ``sqlite_master`` / ``PRAGMA table_info`` are NOT translated here; callers
  must use the information_schema helpers in this module instead.
* ``INSERT OR IGNORE`` must already be written as ``ON CONFLICT DO NOTHING``.
"""

import os
import re

import psycopg2
import psycopg2.extras


_CONNECTION = None


def get_postgres_connection():
    """Return a shared psycopg2 connection wrapped to look like sqlite3."""
    global _CONNECTION
    if _CONNECTION is None or _CONNECTION.closed:
        conn = psycopg2.connect(
            host=os.environ.get('MES_DB_HOST', 'localhost'),
            port=int(os.environ.get('MES_DB_PORT', '5432')),
            dbname=os.environ.get('MES_DB_NAME', 'mes_factory'),
            user=os.environ.get('MES_DB_USER', 'mes'),
            password=os.environ.get('MES_DB_PASS', ''),
        )
        conn.autocommit = False
        _CONNECTION = _PgConnection(conn)
    return _CONNECTION


def _translate_sql(sql):
    """Convert SQLite-style placeholders and pragmas to PostgreSQL equivalents."""
    # PRAGMA statements are SQLite-specific; make them harmless no-ops.
    if re.match(r'^\s*PRAGMA\b', sql, re.IGNORECASE):
        return 'SELECT 1'
    # Convert ? placeholders to %s (psycopg2 style).
    return sql.replace('?', '%s')


_INSERT_RE = re.compile(r'^\s*INSERT\s+INTO\b', re.IGNORECASE)
_RETURNING_RE = re.compile(r'\bRETURNING\b', re.IGNORECASE)


class _PgCursor:
    """Cursor wrapper exposing sqlite3-like attributes (lastrowid, rowcount)."""

    def __init__(self, real_cursor):
        self._cursor = real_cursor
        self.lastrowid = None
        self.rowcount = real_cursor.rowcount
        self.description = real_cursor.description
        self.row_factory = None  # kept for API compatibility; rows are already dict-like

    def execute(self, sql, params=()):
        sql_t = _translate_sql(sql)
        if _INSERT_RE.match(sql) and not _RETURNING_RE.search(sql):
            # Append RETURNING id so lastrowid works on tables with an id column.
            sql_t = sql_t.rstrip().rstrip(';') + ' RETURNING id'
            self._cursor.execute(sql_t, _as_tuple(params))
            row = self._cursor.fetchone()
            self.lastrowid = row['id'] if row else None
        else:
            self._cursor.execute(sql_t, _as_tuple(params))
            self.lastrowid = None
        self.rowcount = self._cursor.rowcount
        self.description = self._cursor.description
        return self

    def executemany(self, sql, seq_of_params):
        sql_t = _translate_sql(sql)
        self._cursor.executemany(sql_t, [_as_tuple(p) for p in seq_of_params])
        self.rowcount = self._cursor.rowcount
        return self

    def executescript(self, script):
        # psycopg2 has no executescript; split on ';' and run each statement.
        for stmt in script.split(';'):
            stmt = stmt.strip()
            if stmt:
                self._cursor.execute(stmt)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        return row  # RealDictRow supports row['col']

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchmany(self, size=1):
        return self._cursor.fetchmany(size)

    def close(self):
        self._cursor.close()


def _as_tuple(params):
    if params is None:
        return ()
    if isinstance(params, (list, tuple)):
        return tuple(params)
    return (params,)


class _PgConnection:
    """Connection wrapper that returns dict-cursor-backed wrappers."""

    def __init__(self, conn):
        self._conn = conn
        self.row_factory = None
        self.closed = False

    def execute(self, sql, params=()):
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        wrapper = _PgCursor(cur)
        wrapper.execute(sql, params)
        return wrapper

    def executemany(self, sql, seq_of_params):
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        wrapper = _PgCursor(cur)
        wrapper.executemany(sql, seq_of_params)
        return wrapper

    def executescript(self, script):
        cur = self._conn.cursor()
        wrapper = _PgCursor(cur)
        wrapper.executescript(script)
        return wrapper

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        if not self.closed:
            self._conn.close()
            self.closed = True

    @property
    def in_transaction(self):
        return not self._conn.autocommit and self._conn.status == psycopg2.extensions.STATUS_BEGIN


def init_postgresql_schema(db, schema_path):
    """Execute a PostgreSQL schema file (CREATE TABLE / INDEX statements)."""
    with open(schema_path, 'r', encoding='utf-8') as f:
        script = f.read()
    db.executescript(script)
    db.commit()


def table_exists(db, table_name):
    row = db.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name=%s",
        (table_name,),
    ).fetchone()
    return row is not None


def list_columns(db, table_name):
    return [
        row['column_name']
        for row in db.execute(
            """SELECT column_name FROM information_schema.columns
               WHERE table_name=%s ORDER BY ordinal_position""",
            (table_name,),
        ).fetchall()
    ]
