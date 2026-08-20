"""Cross-database exception helpers.

The MES runs on SQLite by default and on PostgreSQL via ``postgres_compat``.
Both backends raise integrity errors for unique/foreign-key violations, but
with different exception types (``sqlite3.IntegrityError`` vs
``psycopg2.IntegrityError``) and different messages.  Import these helpers so
call sites work on both backends instead of matching SQLite-only types or
strings.
"""

import sqlite3

try:
    from psycopg2 import IntegrityError as _Psycopg2IntegrityError
    from psycopg2 import errors as _psycopg2_errors
except ImportError:  # pragma: no cover - psycopg2 is optional
    _Psycopg2IntegrityError = sqlite3.IntegrityError
    _psycopg2_errors = None


# Tuple of exception classes to catch for "integrity violation" on either backend.
INTEGRITY_ERRORS = (sqlite3.IntegrityError, _Psycopg2IntegrityError)


def is_unique_violation(exc):
    """Return True when ``exc`` is a unique-constraint violation on either backend.

    SQLite reports ``UNIQUE constraint failed: ...`` while PostgreSQL reports
    ``duplicate key value violates unique constraint ...`` (and raises
    ``psycopg2.errors.UniqueViolation``).
    """
    if isinstance(exc, sqlite3.IntegrityError):
        return 'UNIQUE constraint failed' in str(exc)
    if _psycopg2_errors is not None and isinstance(exc, _psycopg2_errors.UniqueViolation):
        return True
    message = str(exc).lower()
    return 'duplicate key' in message or 'unique constraint' in message
