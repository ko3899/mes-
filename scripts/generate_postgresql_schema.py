"""Generate PostgreSQL DDL from an in-memory SQLite schema.

This script runs the SQLite ``init_db()`` and ``_init_extra_tables()`` functions,
then reads ``sqlite_master`` and emits a PostgreSQL-compatible schema file.

Usage:
    python scripts/generate_postgresql_schema.py > database/mes_postgresql.sql
"""

import os
import re
import sqlite3
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

from utils import database  # noqa: E402


_FK_RE = re.compile(
    r'\s*,?\s*FOREIGN\s+KEY\s*\(([^)]+)\)\s*REFERENCES\s+(\w+)\s*\(([^)]+)\)',
    re.IGNORECASE,
)


def _translate_type(sql):
    """Convert SQLite type/constraint fragments to PostgreSQL."""
    sql = re.sub(
        r'\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b',
        'SERIAL PRIMARY KEY',
        sql,
        flags=re.IGNORECASE,
    )
    sql = re.sub(
        r'\bINTEGER\s+PRIMARY\s+KEY\b',
        'SERIAL PRIMARY KEY',
        sql,
        flags=re.IGNORECASE,
    )
    sql = re.sub(r'\bAUTOINCREMENT\b', '', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bBLOB\b', 'BYTEA', sql, flags=re.IGNORECASE)
    return sql


def _extract_foreign_keys(sql):
    """Return list of (columns, ref_table, ref_columns) and the CREATE TABLE without FKs."""
    fks = []
    body_match = re.match(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\((.*)\)', sql, re.IGNORECASE | re.DOTALL)
    if not body_match:
        return fks, sql
    table_name = body_match.group(1)
    body = body_match.group(2)
    cleaned_lines = []
    for line in body.split(','):
        if _FK_RE.search(line):
            m = _FK_RE.search(line)
            cols = [c.strip() for c in m.group(1).split(',')]
            ref_table = m.group(2)
            ref_cols = [c.strip() for c in m.group(3).split(',')]
            fks.append((table_name, cols, ref_table, ref_cols))
            # Remove the FK clause but keep any leading/trailing content on the same line
            line = _FK_RE.sub('', line).strip().rstrip(',').strip()
            if not line:
                continue
        cleaned_lines.append(line)
    cleaned_body = ','.join(cleaned_lines)
    cleaned_sql = f'CREATE TABLE IF NOT EXISTS {table_name} ({cleaned_body})'
    return fks, cleaned_sql


def main():
    fd, db_path = tempfile.mkstemp(suffix='.sqlite-schema.db')
    os.close(fd)
    try:
        database.DB_PATH = db_path
        database.init_db()
        database._init_extra_tables()
        database._create_indexes()
        conn = sqlite3.connect(db_path)
        try:
            rows = conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name"
            ).fetchall()
        finally:
            conn.close()
    finally:
        os.unlink(db_path)

    table_statements = []
    index_statements = []
    foreign_keys = []

    for name, sql in rows:
        sql = sql.strip()
        if not sql:
            continue
        if sql.upper().startswith('CREATE TABLE'):
            fks, cleaned = _extract_foreign_keys(sql)
            table_statements.append(_translate_type(cleaned))
            foreign_keys.extend(fks)
        elif sql.upper().startswith('CREATE INDEX') or sql.upper().startswith('CREATE UNIQUE INDEX'):
            index_statements.append(_translate_type(sql))

    print('-- Auto-generated PostgreSQL schema from SQLite DDL')
    print('-- Do not edit by hand; run scripts/generate_postgresql_schema.py')
    print('BEGIN;')

    for stmt in table_statements:
        print(stmt.rstrip(';') + ';')

    for stmt in index_statements:
        print(stmt.rstrip(';') + ';')

    for table, cols, ref_table, ref_cols in foreign_keys:
        col_list = ', '.join(cols)
        ref_col_list = ', '.join(ref_cols)
        print(
            f'ALTER TABLE {table} ADD CONSTRAINT {table}_{"_".join(cols)}_fk '
            f'FOREIGN KEY ({col_list}) REFERENCES {ref_table}({ref_col_list});'
        )

    print('COMMIT;')


if __name__ == '__main__':
    main()
