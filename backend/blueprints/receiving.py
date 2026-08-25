"""采购收料闭环蓝图 - 到货登记 / 收料过账 / 库存累计 / 采购单状态联动。

URL 遵循 /api/scm/receiving/... 前缀，响应格式 {code, data, message}。
"""
from flask import Blueprint, jsonify, request, session

from utils.database import get_db
from utils.helpers import login_required, permission_required
from services.procurement_flow import BusinessError
from services import receiving_service

receiving_bp = Blueprint('receiving', __name__)

_arrival_write = permission_required('scm:write')
_receipt_post = permission_required('scm:receipt')


def _error(exc):
    return jsonify({'code': exc.status, 'message': str(exc)}), exc.status


@receiving_bp.route('/api/scm/receiving/arrival/add', methods=['POST'])
@_arrival_write
def arrival_add():
    db = get_db()
    try:
        notice = receiving_service.register_arrival(
            db, request.get_json(silent=True), session.get('user_id'),
        )
    except BusinessError as exc:
        return _error(exc)
    return jsonify({'code': 0, 'message': '到货登记成功', 'data': notice})


@receiving_bp.route('/api/scm/receiving/arrival/list')
@login_required
def arrival_list():
    db = get_db()
    try:
        page = max(1, int(request.args.get('page', 1)))
        size = min(500, max(1, int(request.args.get('size', 20))))
    except (TypeError, ValueError):
        return jsonify({'code': 400, 'message': '分页参数必须是整数'}), 400
    result = receiving_service.arrival_list(
        db,
        page=page,
        size=size,
        keyword=request.args.get('keyword', ''),
        status=request.args.get('status'),
    )
    return jsonify({'code': 0, 'data': result})


@receiving_bp.route('/api/scm/receiving/arrival/<int:notice_id>')
@login_required
def arrival_detail(notice_id):
    db = get_db()
    try:
        notice = receiving_service.notice_detail(db, notice_id)
    except BusinessError as exc:
        return _error(exc)
    return jsonify({'code': 0, 'data': notice})


@receiving_bp.route('/api/scm/receiving/post', methods=['POST'])
@_receipt_post
def receipt_post():
    db = get_db()
    try:
        posting = receiving_service.post_receipt(
            db, request.get_json(silent=True), session.get('user_id'),
        )
    except BusinessError as exc:
        return _error(exc)
    return jsonify({'code': 0, 'message': '收料过账成功', 'data': posting})


@receiving_bp.route('/api/scm/receiving/list')
@login_required
def receipt_list():
    db = get_db()
    try:
        page = max(1, int(request.args.get('page', 1)))
        size = min(500, max(1, int(request.args.get('size', 20))))
    except (TypeError, ValueError):
        return jsonify({'code': 400, 'message': '分页参数必须是整数'}), 400
    result = receiving_service.receipt_list(
        db,
        page=page,
        size=size,
        keyword=request.args.get('keyword', ''),
        purchase_order_id=request.args.get('purchase_order_id'),
    )
    return jsonify({'code': 0, 'data': result})


@receiving_bp.route('/api/scm/receiving/order/<int:order_id>/summary')
@login_required
def order_summary(order_id):
    db = get_db()
    try:
        summary = receiving_service.order_receipt_summary(db, order_id)
    except BusinessError as exc:
        return _error(exc)
    return jsonify({'code': 0, 'data': summary})
