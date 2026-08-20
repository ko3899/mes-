"""验证 utils.db_errors 跨库异常助手。"""
import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, 'backend')
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from utils.db_errors import INTEGRITY_ERRORS, is_unique_violation  # noqa: E402


def test_integrity_errors_is_a_tuple_of_exception_classes():
    assert isinstance(INTEGRITY_ERRORS, tuple)
    assert sqlite3.IntegrityError in INTEGRITY_ERRORS


def test_is_unique_violation_detects_sqlite_message():
    exc = sqlite3.IntegrityError('UNIQUE constraint failed: sys_user.username')
    assert is_unique_violation(exc) is True


def test_is_unique_violation_detects_postgresql_message():
    # 未安装 psycopg2 时,用普通异常模拟 PostgreSQL 的错误信息
    exc = Exception('duplicate key value violates unique constraint "sys_user_username_key"')
    assert is_unique_violation(exc) is True


def test_is_unique_violation_returns_false_for_other_errors():
    assert is_unique_violation(sqlite3.IntegrityError('FOREIGN KEY constraint failed')) is False
    assert is_unique_violation(ValueError('not a db error')) is False
