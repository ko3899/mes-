"""计划控制领域服务。

背景（客户 OPPO Trace 配置端需求映射）：客户码镭雕工站余量被多版本共用导致
多做返工，需要计划员按 产品+阶段码 控制「计划镭雕数量」。

核心概念：
- 计划数量 plan_qty = 原值 + 增减 adjust_qty（正数=增加、负数=减少）
- 余量 balance_qty = plan_qty - ok_qty（计算值，不落库）

提交校验（与需求一致）：
- R1 增加时：plan_qty + adjust_qty > 999999999 → 拒绝
- R2 减少时：|adjust_qty| > balance_qty → 拒绝
- adjust_qty 为 0 → 拒绝；product 不存在 → 拒绝

数据表契约（由 backend/utils/database.py 初始化）：prod_plan_control。
所有写操作都在单一事务内完成，任一步失败整体回滚。
"""
from contextlib import contextmanager

from services.procurement_flow import BusinessError


# 计划镭雕数量的上限（9 位数）
MAX_PLAN_QTY = 999999999


@contextmanager
def _atomic(db):
    """事务上下文：支持嵌套（SAVEPOINT），与 procurement_flow 语义一致。"""
    nested = db.in_transaction
    if nested:
        db.execute('SAVEPOINT plan_control')
    else:
        db.execute('BEGIN IMMEDIATE')
    try:
        yield
        if nested:
            db.execute('RELEASE SAVEPOINT plan_control')
        else:
            db.commit()
    except Exception:
        if nested:
            db.execute('ROLLBACK TO SAVEPOINT plan_control')
            db.execute('RELEASE SAVEPOINT plan_control')
        else:
            db.rollback()
        raise


def _as_int(value, message):
    """把输入转换为整数；布尔值/小数/非数字一律拒绝。"""
    if isinstance(value, bool):
        raise BusinessError(message)
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise BusinessError(message)
    if not number.is_integer():
        raise BusinessError(message)
    return int(number)


def _row_detail(db, row_id):
    """返回单行计划控制详情（含产品信息与计算余量）。"""
    row = db.execute(
        '''SELECT pc.*, p.product_name, p.code AS product_code,
                  (pc.plan_qty - pc.ok_qty) AS balance_qty
           FROM prod_plan_control pc
           LEFT JOIN base_product p ON p.id=pc.product_id
           WHERE pc.id=?''',
        (row_id,),
    ).fetchone()
    if row is None:
        raise BusinessError('计划控制记录不存在', 404)
    return dict(row)


def list_plan_control(db, product_id=None, stage_code=None, keyword=None):
    """计划控制行列表（JOIN base_product 带出 product_name/product_code）+ TOTAL 统计。

    返回 {list: [...], total: {plan_qty, ok_qty, balance_qty}, count: n}。
    每行含计算值 balance_qty = plan_qty - ok_qty。
    """
    where = ' WHERE 1=1'
    params = []
    if product_id not in (None, ''):
        try:
            pid = int(product_id)
        except (TypeError, ValueError):
            pid = 0  # 非法过滤条件：返回空结果，避免 500
        where += ' AND pc.product_id=?'
        params.append(pid)
    if stage_code not in (None, ''):
        where += ' AND pc.stage_code=?'
        params.append(str(stage_code))
    if keyword:
        like = f'%{keyword}%'
        where += ' AND (p.product_name LIKE ? OR p.code LIKE ?)'
        params.extend([like, like])
    rows = db.execute(
        '''SELECT pc.*, p.product_name, p.code AS product_code,
                  (pc.plan_qty - pc.ok_qty) AS balance_qty
           FROM prod_plan_control pc
           LEFT JOIN base_product p ON p.id=pc.product_id''' + where
        + ' ORDER BY pc.id DESC',
        params,
    ).fetchall()
    result = [dict(row) for row in rows]
    total = {
        'plan_qty': sum(int(row['plan_qty'] or 0) for row in rows),
        'ok_qty': sum(int(row['ok_qty'] or 0) for row in rows),
        'balance_qty': sum(int(row['balance_qty'] or 0) for row in rows),
    }
    return {'list': result, 'total': total, 'count': len(result)}


def adjust_plan_control(db, product_id, stage_code, adjust_qty, user_id):
    """增减计划镭雕数量（单事务）。

    计划数量 = 原值 + adjust_qty；余量 = 计划数量 - OK数量。
    增加超出 9 位数（R1）或减少超过余量（R2）时抛 BusinessError，整笔回滚；
    记录不存在时按 plan_qty=0 初始化后再调整。
    """
    try:
        product_id = int(product_id)
    except (TypeError, ValueError):
        raise BusinessError('产品不存在')
    product = db.execute(
        'SELECT id, product_name, code FROM base_product WHERE id=?',
        (product_id,),
    ).fetchone()
    if product is None:
        raise BusinessError('产品不存在')
    adjust_qty = _as_int(adjust_qty, '增减计划数量必须为整数')
    if adjust_qty == 0:
        raise BusinessError('增减计划数量不能为0')
    stage_code = str(stage_code or '').strip()

    with _atomic(db):
        row = db.execute(
            '''SELECT id, plan_qty, ok_qty FROM prod_plan_control
               WHERE product_id=? AND stage_code=?''',
            (product_id, stage_code),
        ).fetchone()
        if row is None:
            cursor = db.execute(
                '''INSERT INTO prod_plan_control
                   (product_id, stage_code, plan_qty, ok_qty, adjust_qty, created_by)
                   VALUES (?,?,0,0,0,?)''',
                (product_id, stage_code, user_id),
            )
            row_id = cursor.lastrowid
            plan_qty = 0
            ok_qty = 0
        else:
            row_id = row['id']
            plan_qty = int(row['plan_qty'] or 0)
            ok_qty = int(row['ok_qty'] or 0)

        balance_qty = plan_qty - ok_qty
        new_plan_qty = plan_qty + adjust_qty
        if adjust_qty > 0:
            if new_plan_qty > MAX_PLAN_QTY:
                raise BusinessError('增加数量最大不可使计划镭雕数量超过9位数')
        else:  # adjust_qty < 0
            if abs(adjust_qty) > balance_qty:
                raise BusinessError('减少数量最小不可小于对应栏位的余量')

        db.execute(
            '''UPDATE prod_plan_control
               SET plan_qty=?, adjust_qty=?, updated_at=CURRENT_TIMESTAMP
               WHERE id=?''',
            (new_plan_qty, adjust_qty, row_id),
        )

    return _row_detail(db, row_id)


def init_plan_control(db):
    """从 base_product 批量初始化：每个产品一行 plan_qty=0（幂等）。

    使用 INSERT OR IGNORE，已存在的 (product_id, stage_code='') 不会被覆盖，
    返回本次新建的条数。
    """
    with _atomic(db):
        cursor = db.execute(
            '''INSERT OR IGNORE INTO prod_plan_control
               (product_id, stage_code, plan_qty)
               SELECT id, '', 0 FROM base_product'''
        )
        created = cursor.rowcount
    return created
