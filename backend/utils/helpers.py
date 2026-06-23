"""辅助函数模块"""
import datetime
import sqlite3
import re
from functools import wraps
from flask import session, jsonify, request
from .database import get_db


def _validate_column_name(name):
    """验证列名是否安全（只允许字母数字下划线）"""
    return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name))


def _get_table_columns(table):
    """获取表的列名列表"""
    db = get_db()
    try:
        cols = db.execute(f"PRAGMA table_info({table})").fetchall()
        return {c[1] for c in cols}
    except:
        return set()


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'code': 401, 'message': '请先登录'}), 401
        return f(*args, **kwargs)
    return decorated


def permission_required(*perms):
    """权限验证装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'code': 401, 'message': '请先登录'}), 401
            # 管理员拥有所有权限
            if session.get('username') == 'admin':
                return f(*args, **kwargs)
            # 检查用户权限
            db = get_db()
            user = db.execute("SELECT role_id FROM sys_user WHERE id=?", (session['user_id'],)).fetchone()
            if not user:
                return jsonify({'code': 403, 'message': '用户不存在'}), 403
            role = db.execute("SELECT menu_ids FROM sys_role WHERE id=?", (user['role_id'],)).fetchone()
            if not role:
                return jsonify({'code': 403, 'message': '无权限'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


def gen_no(prefix):
    """生成编号（原子操作，防止竞态条件）"""
    db = get_db()
    try:
        # 使用事务保证原子性
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM sys_numbering WHERE entity_type=?", (prefix,)).fetchone()
        if not row:
            db.execute("INSERT INTO sys_numbering (prefix, entity_type, current_no, digit_count) VALUES (?,?,1,6)",
                       (prefix, prefix))
            no = 1
            digits = 6
        else:
            no = row['current_no'] + 1
            db.execute("UPDATE sys_numbering SET current_no=? WHERE entity_type=?", (no, prefix))
            digits = row['digit_count']
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    today = datetime.datetime.now().strftime('%Y%m%d')
    return f"{prefix}{today}{str(no).zfill(digits)}"


def crud_list(table, params):
    """通用列表查询（带列名验证）"""
    db = get_db()
    page = int(params.get('page', 1))
    size = int(params.get('size', 20))
    offset = (page - 1) * size

    # 获取表的列名
    valid_columns = _get_table_columns(table)

    where = " WHERE 1=1"
    args = []
    keyword = params.get('keyword', '')
    for key, val in params.items():
        if key in ('page', 'size', 'sort', 'order', 'keyword'):
            continue
        if val is not None and val != '':
            # 验证列名
            if not _validate_column_name(key) or key not in valid_columns:
                continue
            where += f" AND {key}=?"
            args.append(val)

    if keyword:
        try:
            cols_info = db.execute(f"PRAGMA table_info({table})").fetchall()
            text_cols = [c[1] for c in cols_info if c[2] == 'TEXT']
            if text_cols:
                like_parts = [f"{col} LIKE ?" for col in text_cols[:5]]
                where += f" AND ({' OR '.join(like_parts)})"
                like_val = f"%{keyword}%"
                args.extend([like_val] * len(like_parts))
        except:
            pass

    total = db.execute(f"SELECT COUNT(*) as cnt FROM {table}{where}", args).fetchone()['cnt']

    sort = params.get('sort', 'id')
    order = params.get('order', 'DESC')
    # 验证排序列名
    if not _validate_column_name(sort) or sort not in valid_columns:
        sort = 'id'
    if order not in ('ASC', 'DESC'):
        order = 'DESC'

    rows = db.execute(f"SELECT * FROM {table}{where} ORDER BY {sort} {order} LIMIT ? OFFSET ?",
                      args + [size, offset]).fetchall()

    return {'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total, 'page': page, 'size': size}}


def crud_add(table, data):
    """通用添加（带列名验证）"""
    db = get_db()
    valid_columns = _get_table_columns(table)
    
    # 只允许表中存在的列
    keys = [k for k in data.keys() if k != 'id' and _validate_column_name(k) and k in valid_columns]
    if not keys:
        return {'code': 400, 'message': '无有效字段'}
    
    vals = [data[k] for k in keys]
    placeholders = ','.join(['?'] * len(keys))
    columns = ','.join(keys)

    try:
        cursor = db.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", vals)
        db.commit()
        return {'code': 0, 'data': {'id': cursor.lastrowid}, 'message': '添加成功'}
    except sqlite3.IntegrityError as e:
        if 'UNIQUE constraint failed' in str(e):
            return {'code': 400, 'message': f'数据重复: {str(e).split(":")[-1].strip()}'}
        return {'code': 400, 'message': f'数据约束错误: {str(e)}'}
    except Exception as e:
        return {'code': 500, 'message': '添加失败，请检查数据格式'}


def crud_update(table, data):
    """通用更新（带列名验证）"""
    db = get_db()
    id = data.get('id')
    if not id:
        return {'code': 400, 'message': '缺少id'}

    valid_columns = _get_table_columns(table)
    
    # 只允许表中存在的列
    keys = [k for k in data.keys() if k != 'id' and _validate_column_name(k) and k in valid_columns]
    if not keys:
        return {'code': 400, 'message': '无有效字段'}
    
    vals = [data[k] for k in keys]
    sets = ','.join([f"{k}=?" for k in keys])

    try:
        db.execute(f"UPDATE {table} SET {sets} WHERE id=?", vals + [id])
        db.commit()
        return {'code': 0, 'message': '修改成功'}
    except sqlite3.IntegrityError as e:
        if 'UNIQUE constraint failed' in str(e):
            return {'code': 400, 'message': f'数据重复: {str(e).split(":")[-1].strip()}'}
        return {'code': 400, 'message': f'数据约束错误: {str(e)}'}
    except Exception as e:
        return {'code': 500, 'message': '修改失败，请检查数据格式'}


def crud_delete(table, id):
    """通用删除"""
    db = get_db()
    try:
        db.execute(f"DELETE FROM {table} WHERE id=?", (id,))
        db.commit()
        return {'code': 0, 'message': '删除成功'}
    except Exception as e:
        return {'code': 500, 'message': '删除失败，请检查数据'}


def sanitize_filename(filename):
    """安全处理文件名，防止路径穿越"""
    from werkzeug.utils import secure_filename
    return secure_filename(filename)
