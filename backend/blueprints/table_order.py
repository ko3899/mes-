"""Unified API for persistent manual ordering of record tables."""

from flask import Blueprint, jsonify, request

from utils.database import get_db
from utils.helpers import login_required
from utils.table_order import move_record, ordered_ids, positions_for, step_record


table_order_bp = Blueprint('table_order', __name__)


def _success(ids):
    return jsonify({
        'code': 0,
        'data': {
            'ordered_ids': ids,
            'positions': positions_for(ids),
            'total': len(ids),
        },
    })


def _error(message, status=400):
    return jsonify({'code': status, 'message': str(message)}), status


@table_order_bp.route('/api/table-order/<path:table_key>')
@login_required
def table_order_get(table_key):
    try:
        return _success(ordered_ids(get_db(), table_key))
    except (ValueError, LookupError) as exc:
        return _error(exc)


@table_order_bp.route('/api/table-order/move', methods=['POST'])
@login_required
def table_order_move():
    data = request.get_json(silent=True) or {}
    try:
        table_key = str(data.get('table_key') or '')
        record_id = int(data.get('record_id'))
        target = int(data.get('target_position'))
        db = get_db()
        ids = move_record(db, table_key, record_id, target)
        db.commit()
        return _success(ids)
    except LookupError as exc:
        return _error(exc, 404)
    except (TypeError, ValueError) as exc:
        return _error(exc)


@table_order_bp.route('/api/table-order/step', methods=['POST'])
@login_required
def table_order_step():
    data = request.get_json(silent=True) or {}
    try:
        table_key = str(data.get('table_key') or '')
        record_id = int(data.get('record_id'))
        direction = str(data.get('direction') or '')
        db = get_db()
        ids = step_record(db, table_key, record_id, direction)
        db.commit()
        return _success(ids)
    except LookupError as exc:
        return _error(exc, 404)
    except (TypeError, ValueError) as exc:
        return _error(exc)
