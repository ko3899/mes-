"""PostgreSQL compatibility layer that mimics the sqlite3 connection API used
throughout the MES blueprints.

The blueprints call ``db.execute(sql, params)``, read ``row['col']`` and
``row[N]``, use ``cursor.lastrowid`` and ``cursor.rowcount``, and call
``db.commit()`` / ``db.rollback()``.  This module wraps psycopg2 so the same
call sites work on PostgreSQL with minimal changes.

Automatic SQL translations applied:
* ``?`` placeholders -> ``%s``.
* ``PRAGMA foreign_keys = ON`` and similar -> ``SELECT 1`` (no-op).
* ``INSERT OR IGNORE INTO t ...`` -> ``INSERT INTO t ... ON CONFLICT DO NOTHING``.
* ``PRAGMA table_info(t)`` -> a query returning rows indexable as ``row[1]``
  (column name), matching the SQLite layout.
* ``SELECT ... FROM sqlite_master WHERE type='table' AND name=?`` ->
  ``information_schema.tables`` equivalent.
* ``datetime('now','-N minutes')`` -> ``now() - interval 'N minutes'``.
* ``GROUP_CONCAT(x)`` -> ``string_agg(x::text, ',')``.

Known limitations:
* ``lastrowid`` only works for INSERT on tables with an ``id`` column.
* ``INSERT OR REPLACE`` is not translated (none in the codebase).
* Complex SQLite-specific pragmas beyond ``table_info`` are not supported.
"""

import os
import re

import psycopg2
import psycopg2.extras


_CONNECTION = None


class _DualRow:
    """A row that supports both ``row['col']`` and ``row[N]`` access.

    SQLite's Row supports both dict-style and integer-index access.  psycopg2's
    RealDictRow only supports dict-style.  This wrapper restores integer access
    so legacy call sites using ``row[0]`` / ``row[1]`` keep working.
    """

    __slots__ = ('_data', '_keys')

    def __init__(self, data):
        # data is a RealDictRow (dict-like) or a tuple
        if isinstance(data, dict):
            self._data = data
            self._keys = list(data.keys())
        else:
            # tuple: build positional mapping; no column names
            self._data = {i: v for i, v in enumerate(data)}
            self._keys = list(range(len(data)))

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._data[self._keys[key]]
        return self._data[key]

    def __iter__(self):
        return iter(self._data.values())

    def __len__(self):
        return len(self._data)

    def keys(self):
        return self._keys

    def values(self):
        return [self._data[k] for k in self._keys]

    def items(self):
        return [(k, self._data[k]) for k in self._keys]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __contains__(self, key):
        return key in self._data

    def __repr__(self):
        return repr(self._data)


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


# Regex helpers for translation
_PRAGMA_TABLE_INFO_RE = re.compile(
    r"PRAGMA\s+table_info\(\s*['\"]?(\w+)['\"]?\s*\)", re.IGNORECASE
)
_SQLITE_MASTER_RE = re.compile(
    r"FROM\s+sqlite_master\s+WHERE\s+type\s*=\s*'table'\s+AND\s+name\s*=\s*\?",
    re.IGNORECASE,
)
_SQLITE_MASTER_LITERAL_RE = re.compile(
    r"FROM\s+sqlite_master\s+WHERE\s+type\s*=\s*'table'\s+AND\s+name\s*=\s*'([^']+)'",
    re.IGNORECASE,
)
_DATETIME_NOW_RE = re.compile(
    r"datetime\(\s*'now'\s*,\s*'(-?\d+)\s*(minute|minutes|second|seconds|hour|hours|day|days|month|months|year|years)'\s*\)",
    re.IGNORECASE,
)
_INSERT_OR_IGNORE_RE = re.compile(
    r"^\s*INSERT\s+OR\s+IGNORE\s+INTO\b", re.IGNORECASE
)
_GROUP_CONCAT_RE = re.compile(r"\bGROUP_CONCAT\(([^)]+)\)", re.IGNORECASE)


def _translate_sql(sql):
    """Convert SQLite-style SQL to PostgreSQL-compatible SQL."""
    # PRAGMA table_info(t) -> information_schema query with positional columns
    m = _PRAGMA_TABLE_INFO_RE.search(sql)
    if m:
        table = m.group(1)
        # Return rows shaped like SQLite: (cid, name, type, notnull, dflt_value, pk)
        # Callers use row[1] for the column name.
        replacement = (
            "SELECT 0 AS cid, column_name AS name, data_type AS type, "
            "0 AS notnull, NULL AS dflt_value, 0 AS pk "
            f"FROM information_schema.columns WHERE table_name='{table}' "
            "ORDER BY ordinal_position"
        )
        sql = _PRAGMA_TABLE_INFO_RE.sub(replacement, sql)

    # sqlite_master with parameterized name
    if _SQLITE_MASTER_RE.search(sql):
        sql = _SQLITE_MASTER_RE.sub(
            "FROM information_schema.tables WHERE table_schema='public' AND table_name=%s",
            sql,
        )

    # sqlite_master with literal name
    def _literal_sub(match):
        name = match.group(1)
        return (
            "FROM information_schema.tables WHERE table_schema='public' "
            f"AND table_name='{name}'"
        )

    sql = _SQLITE_MASTER_LITERAL_RE.sub(_literal_sub, sql)

    # datetime('now', '-N minutes') -> now() - interval 'N minutes'
    # SQLite's '-N' already means subtraction; PostgreSQL uses now() - interval 'N'.
    def _dt_sub(match):
        n = match.group(1).lstrip('-')
        unit = match.group(2).lower()
        if unit.endswith('s'):
            unit = unit[:-1]
        return f"now() - interval '{n} {unit}'"

    sql = _DATETIME_NOW_RE.sub(_dt_sub, sql)

    # INSERT OR IGNORE -> INSERT ... ON CONFLICT DO NOTHING
    # Only append ON CONFLICT to statements that originally used OR IGNORE,
    # so plain INSERTs that should raise on conflict are left alone.
    _was_or_ignore = bool(_INSERT_OR_IGNORE_RE.match(sql))
    if _was_or_ignore:
        sql = _INSERT_OR_IGNORE_RE.sub("INSERT INTO", sql)
        if not re.search(r"\bON\s+CONFLICT\b", sql, re.IGNORECASE):
            sql = sql.rstrip().rstrip(';') + " ON CONFLICT DO NOTHING"

    # GROUP_CONCAT(x) -> string_agg(x::text, ',')
    sql = _GROUP_CONCAT_RE.sub(r"string_agg(\1::text, ',')", sql)

    # BEGIN IMMEDIATE / EXCLUSIVE -> BEGIN (PostgreSQL has no IMMEDIATE/EXCLUSIVE modifier)
    sql = re.sub(r"\bBEGIN\s+(?:IMMEDIATE|EXCLUSIVE)\b", "BEGIN", sql, flags=re.IGNORECASE)

    # Remaining bare PRAGMAs (e.g. foreign_keys, foreign_key_check) -> no-op
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
        self.row_factory = None

    def execute(self, sql, params=()):
        sql_t = _translate_sql(sql)
        if _INSERT_RE.match(sql_t) and not _RETURNING_RE.search(sql_t):
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
        for stmt in script.split(';'):
            stmt = stmt.strip()
            if stmt:
                self._cursor.execute(stmt)
        return self

    def _wrap(self, row):
        return _DualRow(row) if row is not None else None

    def fetchone(self):
        return self._wrap(self._cursor.fetchone())

    def fetchall(self):
        return [self._wrap(r) for r in self._cursor.fetchall()]

    def fetchmany(self, size=1):
        return [self._wrap(r) for r in self._cursor.fetchmany(size)]

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
