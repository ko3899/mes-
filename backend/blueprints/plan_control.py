"""计划控制蓝图 - 计划员按 产品+阶段码 控制计划镭雕数量。

URL 遵循 /api/prod/plan-control/... 前缀，响应格式 {code, data, message}。
"""
from flask import Blueprint, jsonify, request, session

from utils.database import get_db
from utils.helpers import permission_required
from services.procurement_flow import BusinessError
from services import plan_control_service

plan_control_bp = Blueprint('plan_control', __name__)

_plan_control_read = permission_required('plan:control:read')
_plan_control_write = permission_required('plan:control:write')


def _error(exc):
    return jsonify({'code': exc.status, 'message': str(exc)}), exc.status


@plan_control_bp.route('/api/prod/plan-control/list')
@_plan_control_read
def plan_control_list():
    db = get_db()
    try:
        result = plan_control_service.list_plan_control(
            db,
            product_id=request.args.get('product_id'),
            stage_code=request.args.get('stage_code'),
            keyword=request.args.get('keyword'),
        )
    except BusinessError as exc:
        return _error(exc)
    return jsonify({'code': 0, 'data': result})


@plan_control_bp.route('/api/prod/plan-control/adjust', methods=['POST'])
@_plan_control_write
def plan_control_adjust():
    db = get_db()
    payload = request.get_json(silent=True) or {}
    try:
        row = plan_control_service.adjust_plan_control(
            db,
            payload.get('product_id'),
            payload.get('stage_code'),
            payload.get('adjust_qty'),
            session.get('user_id'),
        )
    except BusinessError as exc:
        return _error(exc)
    return jsonify({'code': 0, 'message': '计划数量调整成功', 'data': row})


@plan_control_bp.route('/api/prod/plan-control/init', methods=['POST'])
@_plan_control_write
def plan_control_init():
    db = get_db()
    created = plan_control_service.init_plan_control(db)
    return jsonify({'code': 0, 'message': '初始化成功', 'data': {'created': created}})
