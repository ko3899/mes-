"""数据库抽象层 - 支持 SQLite/MySQL/PostgreSQL"""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, 'database', 'mes.db')

# 数据库类型配置（通过环境变量或config）
DB_TYPE = os.environ.get('MES_DB_TYPE', 'sqlite')  # sqlite / mysql / postgresql
DB_HOST = os.environ.get('MES_DB_HOST', 'localhost')
DB_PORT = int(os.environ.get('MES_DB_PORT', '3306'))
DB_NAME = os.environ.get('MES_DB_NAME', 'mes_factory')
DB_USER = os.environ.get('MES_DB_USER', 'root')
DB_PASS = os.environ.get('MES_DB_PASS', '')

_connection = None


def get_connection():
    """获取数据库连接"""
    global _connection
    
    if DB_TYPE == 'mysql':
        import pymysql
        if _connection is None or not _connection.open:
            _connection = pymysql.connect(
                host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS,
                database=DB_NAME, charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
            )
        return _connection
    elif DB_TYPE == 'postgresql':
        import psycopg2
        if _connection is None or _connection.closed:
            _connection = psycopg2.connect(
                host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS,
                database=DB_NAME
            )
        return _connection
    else:
        # SQLite
        if _connection is None:
            _connection = sqlite3.connect(DB_PATH)
            _connection.row_factory = sqlite3.Row
            _connection.execute("PRAGMA foreign_keys = ON")
        return _connection


def get_db():
    """获取数据库游标（Flask g 对象兼容）"""
    from flask import g
    if 'db' not in g:
        if DB_TYPE == 'sqlite':
            g.db = sqlite3.connect(DB_PATH)
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        else:
            g.db = get_connection()
    return g.db


def close_db(exception):
    """关闭数据库连接"""
    from flask import g
    db = g.pop('db', None)
    if db and DB_TYPE == 'sqlite':
        db.close()


def execute_sql(sql, params=None):
    """执行SQL语句（兼容不同数据库）"""
    conn = get_connection()
    if DB_TYPE == 'mysql':
        import pymysql
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        conn.commit()
        return cursor
    elif DB_TYPE == 'postgresql':
        import psycopg2
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        conn.commit()
        return cursor
    else:
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        conn.commit()
        return cursor


def query_sql(sql, params=None):
    """查询SQL（返回字典列表）"""
    conn = get_connection()
    if DB_TYPE == 'mysql':
        import pymysql
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        return cursor.fetchall()
    elif DB_TYPE == 'postgresql':
        import psycopg2.extras
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(sql, params or ())
        return cursor.fetchall()
    else:
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        cursor.row_factory = sqlite3.Row
        return [dict(row) for row in cursor.fetchall()]


# Flask g 对象兼容的辅助函数
def get_db():
    from flask import g
    if 'db' not in g:
        if DB_TYPE == 'sqlite':
            g.db = sqlite3.connect(DB_PATH)
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        else:
            g.db = get_connection()
    return g.db


def close_db(exception):
    from flask import g
    db = g.pop('db', None)
    if db and DB_TYPE == 'sqlite':
        db.close()
