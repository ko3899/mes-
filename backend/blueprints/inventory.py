"""库存管理蓝图。"""
import sqlite3

from flask import Blueprint, jsonify, request, session

from utils.database import get_db
from utils.helpers import crud_list, gen_no_in_transaction, login_required
from utils.db_errors import INTEGRITY_ERRORS


inventory_bp = Blueprint('inventory', __name__)


def _error(message, status=400, data=None):
    payload = {'code': status, 'message': message}
    if data is not None:
        payload['data'] = data
    return jsonify(payload), status


def _document_config(kind):
    if kind == 'inbound':
        return {
            'header': 'inv_inbound',
            'item': 'inv_inbound_item',
            'foreign_key': 'inbound_id',
            'number_column': 'inbound_no',
            'number_prefix': 'RK',
            'party_column': 'supplier',
            'type_column': 'inbound_type',
            'transaction_type': '入库',
        }
    return {
        'header': 'inv_outbound',
        'item': 'inv_outbound_item',
        'foreign_key': 'outbound_id',
        'number_column': 'outbound_no',
        'number_prefix': 'CK',
        'party_column': 'customer',
        'type_column': 'outbound_type',
        'transaction_type': '出库',
    }


def _normalize_items(data):
    raw_items = data.get('items')
    if raw_items is None:
        raw_items = [{
            'product_id': data.get('product_id'),
            'quantity': data.get('quantity'),
            'unit_price': data.get('unit_price', 0),
            'remark': data.get('item_remark'),
        }]
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError('单据至少需要一条明细')

    items = []
    for index, raw in enumerate(raw_items, 1):
        if not isinstance(raw, dict):
            raise ValueError(f'第{index}条明细格式错误')
        try:
            product_id = int(raw.get('product_id'))
            quantity = float(raw.get('quantity'))
            unit_price = float(raw.get('unit_price') or 0)
        except (TypeError, ValueError):
            raise ValueError(f'第{index}条明细的产品、数量或单价格式错误')
        if product_id <= 0:
            raise ValueError(f'第{index}条明细必须选择产品')
        if quantity <= 0:
            raise ValueError(f'第{index}条明细数量必须大于0')
        if unit_price < 0:
            raise ValueError(f'第{index}条明细单价不能小于0')
        items.append({
            'product_id': product_id,
            'quantity': quantity,
            'unit_price': unit_price,
            'amount': round(quantity * unit_price, 2),
            'remark': str(raw.get('remark') or '').strip() or None,
        })
    return items


def _validate_products(db, items):
    product_ids = sorted({item['product_id'] for item in items})
    placeholders = ','.join('?' for _ in product_ids)
    rows = db.execute(
        f'SELECT id FROM base_product WHERE id IN ({placeholders})',
        product_ids,
    ).fetchall()
    existing = {row['id'] for row in rows}
    missing = [product_id for product_id in product_ids if product_id not in existing]
    if missing:
        raise ValueError(f'产品不存在: {", ".join(map(str, missing))}')


def _insert_items(db, config, document_id, items):
    for item in items:
        db.execute(
            f'''INSERT INTO {config['item']}
                ({config['foreign_key']}, product_id, quantity, unit_price, amount, remark)
                VALUES (?,?,?,?,?,?)''',
            (document_id, item['product_id'], item['quantity'], item['unit_price'],
             item['amount'], item['remark']),
        )


def _enrich_document_list(kind, result):
    if result.get('code') != 0:
        return result
    rows = result['data']['list']
    if not rows:
        return result
    config = _document_config(kind)
    ids = [row['id'] for row in rows]
    placeholders = ','.join('?' for _ in ids)
    details = get_db().execute(
        f'''SELECT i.{config['foreign_key']} AS document_id,
                   COUNT(*) AS item_count,
                   COALESCE(SUM(i.quantity), 0) AS total_quantity,
                   GROUP_CONCAT(p.product_name, '、') AS product_summary
            FROM {config['item']} i
            LEFT JOIN base_product p ON p.id=i.product_id
            WHERE i.{config['foreign_key']} IN ({placeholders})
            GROUP BY i.{config['foreign_key']}''',
        ids,
    ).fetchall()
    by_id = {row['document_id']: dict(row) for row in details}
    for row in rows:
        row.update(by_id.get(row['id'], {
            'item_count': 0,
            'total_quantity': 0,
            'product_summary': '',
        }))
    return result


def _add_document(kind):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error('请求数据必须是JSON对象')
    try:
        items = _normalize_items(data)
    except ValueError as exc:
        return _error(str(exc))

    config = _document_config(kind)
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        _validate_products(db, items)
        number = gen_no_in_transaction(db, config['number_prefix'])
        total_amount = round(sum(item['amount'] for item in items), 2)
        cursor = db.execute(
            f'''INSERT INTO {config['header']}
                ({config['number_column']}, {config['type_column']},
                 {config['party_column']}, total_amount, status, remark, created_by)
                VALUES (?,?,?,?,0,?,?)''',
            (number, str(data.get(config['type_column']) or '').strip() or None,
             str(data.get(config['party_column']) or '').strip() or None,
             total_amount, str(data.get('remark') or '').strip() or None,
             session.get('user_id')),
        )
        _insert_items(db, config, cursor.lastrowid, items)
        db.commit()
        return jsonify({
            'code': 0,
            'message': '草稿保存成功',
            'data': {'id': cursor.lastrowid, config['number_column']: number},
        })
    except ValueError as exc:
        db.rollback()
        return _error(str(exc))
    except INTEGRITY_ERRORS as exc:
        db.rollback()
        return _error(f'单据保存失败: {exc}', 409)
    except Exception:
        db.rollback()
        raise


def _update_document(kind):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error('请求数据必须是JSON对象')
    try:
        document_id = int(data.get('id'))
        items = _normalize_items(data)
    except (TypeError, ValueError) as exc:
        return _error(str(exc) if str(exc) else '缺少有效单据ID')

    config = _document_config(kind)
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        document = db.execute(
            f'SELECT status FROM {config["header"]} WHERE id=?',
            (document_id,),
        ).fetchone()
        if not document:
            db.rollback()
            return _error('单据不存在', 404)
        if document['status'] != 0:
            db.rollback()
            return _error('已过账单据不能修改', 409)
        _validate_products(db, items)
        total_amount = round(sum(item['amount'] for item in items), 2)
        db.execute(
            f'''UPDATE {config['header']}
                SET {config['type_column']}=?, {config['party_column']}=?,
                    total_amount=?, remark=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?''',
            (str(data.get(config['type_column']) or '').strip() or None,
             str(data.get(config['party_column']) or '').strip() or None,
             total_amount, str(data.get('remark') or '').strip() or None,
             document_id),
        )
        db.execute(
            f'DELETE FROM {config["item"]} WHERE {config["foreign_key"]}=?',
            (document_id,),
        )
        _insert_items(db, config, document_id, items)
        db.commit()
        return jsonify({'code': 0, 'message': '草稿修改成功'})
    except ValueError as exc:
        db.rollback()
        return _error(str(exc))
    except Exception:
        db.rollback()
        raise


def _delete_document(kind):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data.get('id'):
        return _error('缺少单据ID')
    config = _document_config(kind)
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        document = db.execute(
            f'SELECT status FROM {config["header"]} WHERE id=?',
            (data['id'],),
        ).fetchone()
        if not document:
            db.rollback()
            return _error('单据不存在', 404)
        if document['status'] != 0:
            db.rollback()
            return _error('已过账单据不能删除', 409)
        db.execute(
            f'DELETE FROM {config["item"]} WHERE {config["foreign_key"]}=?',
            (data['id'],),
        )
        db.execute(f'DELETE FROM {config["header"]} WHERE id=?', (data['id'],))
        db.commit()
        return jsonify({'code': 0, 'message': '删除成功'})
    except Exception:
        db.rollback()
        raise


def _post_document(kind, document_id):
    config = _document_config(kind)
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        document = db.execute(
            f'SELECT * FROM {config["header"]} WHERE id=?',
            (document_id,),
        ).fetchone()
        if not document:
            db.rollback()
            return _error('单据不存在', 404)
        if document['status'] != 0:
            db.rollback()
            return _error('单据已经过账，不能重复过账', 409)
        items = db.execute(
            f'SELECT * FROM {config["item"]} WHERE {config["foreign_key"]}=? ORDER BY id',
            (document_id,),
        ).fetchall()
        if not items:
            db.rollback()
            return _error('单据没有明细，不能过账', 409)

        shortages = []
        if kind == 'outbound':
            required = {}
            for item in items:
                required[item['product_id']] = required.get(item['product_id'], 0) + item['quantity']
            for product_id, quantity in required.items():
                balance = db.execute(
                    'SELECT quantity FROM inv_balance WHERE product_id=?',
                    (product_id,),
                ).fetchone()
                available = float(balance['quantity']) if balance else 0
                if available + 1e-9 < quantity:
                    product = db.execute(
                        'SELECT product_name FROM base_product WHERE id=?',
                        (product_id,),
                    ).fetchone()
                    shortages.append({
                        'product_id': product_id,
                        'product_name': product['product_name'] if product else str(product_id),
                        'required_qty': quantity,
                        'available_qty': available,
                        'shortage_qty': quantity - available,
                    })
        if shortages:
            db.rollback()
            return _error('库存不足，出库单未过账', 409, shortages)

        for item in items:
            balance = db.execute(
                'SELECT quantity, amount FROM inv_balance WHERE product_id=?',
                (item['product_id'],),
            ).fetchone()
            old_quantity = float(balance['quantity']) if balance else 0
            old_amount = float(balance['amount']) if balance else 0
            if kind == 'inbound':
                new_quantity = old_quantity + item['quantity']
                new_amount = old_amount + item['amount']
            else:
                average_cost = old_amount / old_quantity if old_quantity > 0 else 0
                new_quantity = old_quantity - item['quantity']
                new_amount = max(0, old_amount - average_cost * item['quantity'])
                if abs(new_quantity) < 1e-9:
                    new_quantity = 0
                    new_amount = 0
            if balance:
                db.execute(
                    '''UPDATE inv_balance
                       SET quantity=?, amount=?, updated_at=CURRENT_TIMESTAMP
                       WHERE product_id=?''',
                    (new_quantity, round(new_amount, 2), item['product_id']),
                )
            else:
                db.execute(
                    'INSERT INTO inv_balance(product_id, quantity, amount) VALUES(?,?,?)',
                    (item['product_id'], new_quantity, round(new_amount, 2)),
                )
            signed_quantity = item['quantity'] if kind == 'inbound' else -item['quantity']
            db.execute(
                '''INSERT INTO inv_transaction
                   (product_id, trans_type, quantity, balance, ref_no, remark)
                   VALUES (?,?,?,?,?,?)''',
                (item['product_id'], config['transaction_type'], signed_quantity,
                 new_quantity, document[config['number_column']], document['remark']),
            )
            db.execute(
                '''INSERT INTO inv_transaction_log
                   (trans_type, product_id, quantity, ref_no, ref_type, operator, remark)
                   VALUES (?,?,?,?,?,?,?)''',
                (config['transaction_type'], item['product_id'], signed_quantity,
                 document[config['number_column']], kind, session.get('user_id'),
                 document['remark']),
            )

        updated = db.execute(
            f'''UPDATE {config['header']}
                SET status=1, updated_at=CURRENT_TIMESTAMP
                WHERE id=? AND status=0''',
            (document_id,),
        )
        if updated.rowcount != 1:
            db.rollback()
            return _error('单据状态已变化，请刷新后重试', 409)
        db.commit()
        return jsonify({'code': 0, 'message': '过账成功'})
    except Exception:
        db.rollback()
        raise


@inventory_bp.route('/api/inv/inbound/list')
@login_required
def inv_inbound_list():
    return jsonify(_enrich_document_list('inbound', crud_list('inv_inbound', request.args)))


@inventory_bp.route('/api/inv/inbound/add', methods=['POST'])
@login_required
def inv_inbound_add():
    return _add_document('inbound')


@inventory_bp.route('/api/inv/inbound/update', methods=['POST'])
@login_required
def inv_inbound_update():
    return _update_document('inbound')


@inventory_bp.route('/api/inv/inbound/delete', methods=['POST'])
@login_required
def inv_inbound_delete():
    return _delete_document('inbound')


@inventory_bp.route('/api/inv/inbound/<int:document_id>/post', methods=['POST'])
@login_required
def inv_inbound_post(document_id):
    return _post_document('inbound', document_id)


@inventory_bp.route('/api/inv/outbound/list')
@login_required
def inv_outbound_list():
    return jsonify(_enrich_document_list('outbound', crud_list('inv_outbound', request.args)))


@inventory_bp.route('/api/inv/outbound/add', methods=['POST'])
@login_required
def inv_outbound_add():
    return _add_document('outbound')


@inventory_bp.route('/api/inv/outbound/update', methods=['POST'])
@login_required
def inv_outbound_update():
    return _update_document('outbound')


@inventory_bp.route('/api/inv/outbound/delete', methods=['POST'])
@login_required
def inv_outbound_delete():
    return _delete_document('outbound')


@inventory_bp.route('/api/inv/outbound/<int:document_id>/post', methods=['POST'])
@login_required
def inv_outbound_post(document_id):
    return _post_document('outbound', document_id)


@inventory_bp.route('/api/inv/balance/list')
@login_required
def inv_balance_list():
    db = get_db()
    rows = db.execute('''SELECT b.*, p.product_name, p.code, p.unit
        FROM inv_balance b
        LEFT JOIN base_product p ON b.product_id=p.id
        ORDER BY b.id DESC''').fetchall()
    return jsonify({'code': 0, 'data': [dict(row) for row in rows]})
