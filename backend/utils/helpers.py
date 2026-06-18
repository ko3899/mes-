"""辅助函数模块"""
import datetime
from functools import wraps
from flask import session, jsonify, request
from .database import get_db


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'code': 401, 'message': '请先登录'}), 401
        return f(*args, **kwargs)
    return decorated


def gen_no(prefix):
    """生成编号"""
    db = get_db()
    row = db.execute("SELECT * FROM sys_numbering WHERE entity_type=?", (prefix,)).fetchone()
    if not row:
        db.execute("INSERT INTO sys_numbering (prefix, entity_type, current_no, digit_count) VALUES (?,?,1,6)",
                   (prefix, prefix))
        db.commit()
        no = 1
        digits = 6
    else:
        no = row['current_no'] + 1
        db.execute("UPDATE sys_numbering SET current_no=? WHERE entity_type=?", (no, prefix))
        db.commit()
        digits = row['digit_count']
    today = datetime.datetime.now().strftime('%Y%m%d')
    return f"{prefix}{today}{str(no).zfill(digits)}"


def crud_list(table, params):
    """通用列表查询"""
    db = get_db()
    page = int(params.get('page', 1))
    size = int(params.get('size', 20))
    offset = (page - 1) * size

    where = " WHERE 1=1"
    args = []
    keyword = params.get('keyword', '')
    for key, val in params.items():
        if key in ('page', 'size', 'sort', 'order', 'keyword'):
            continue
        if val is not None and val != '':
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
    if sort not in ('id', 'created_at', 'updated_at', 'sort_order'):
        sort = 'id'
    if order not in ('ASC', 'DESC'):
        order = 'DESC'

    rows = db.execute(f"SELECT * FROM {table}{where} ORDER BY {sort} {order} LIMIT ? OFFSET ?",
                      args + [size, offset]).fetchall()

    return {'code': 0, 'data': {'list': [dict(r) for r in rows], 'total': total, 'page': page, 'size': size}}


def crud_add(table, data):
    """通用添加"""
    db = get_db()
    keys = [k for k in data.keys() if k != 'id']
    vals = [data[k] for k in keys]
    placeholders = ','.join(['?'] * len(keys))
    columns = ','.join(keys)

    cursor = db.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", vals)
    db.commit()
    return {'code': 0, 'data': {'id': cursor.lastrowid}, 'message': '添加成功'}


def crud_update(table, data):
    """通用更新"""
    db = get_db()
    id = data.get('id')
    if not id:
        return {'code': 400, 'message': '缺少id'}

    keys = [k for k in data.keys() if k != 'id']
    vals = [data[k] for k in keys]
    sets = ','.join([f"{k}=?" for k in keys])

    db.execute(f"UPDATE {table} SET {sets} WHERE id=?", vals + [id])
    db.commit()
    return {'code': 0, 'message': '修改成功'}


def crud_delete(table, id):
    """通用删除"""
    db = get_db()
    db.execute(f"DELETE FROM {table} WHERE id=?", (id,))
    db.commit()
    return {'code': 0, 'message': '删除成功'}
