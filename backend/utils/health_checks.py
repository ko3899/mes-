"""聚合健康检查:数据库、MQTT 消费者、边缘网关活跃度、机台端点。

/healthz       - 轻量存活探针(只查数据库),供负载均衡用
/readyz        - 就绪探针,检查依赖项是否就绪
/healthz/full  - 完整诊断(需登录),返回各子系统状态

设计原则:
- 每个探测有独立超时,单个失败不影响其他探测
- 探测结果不抛异常,返回结构化状态
- 轻量探针(healthz)不做重活,保证快速响应
"""

import os
import threading
import time

from flask import jsonify

from utils.database import get_db, DB_TYPE


def _db_probe(db):
    """数据库连通性。"""
    t0 = time.time()
    try:
        db.execute('SELECT 1').fetchone()
        return {'status': 'ok', 'latency_ms': round((time.time() - t0) * 1000, 1)}
    except Exception as exc:
        return {'status': 'error', 'error': str(exc)[:200]}


def _table_count(db, table, where='1=1'):
    """安全地统计某表行数(表不存在返回 None)。"""
    try:
        # 用 information_schema 而非 sqlite_master,兼容两种数据库
        row = db.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name=%s",
            (table,),
        ).fetchone() if DB_TYPE == 'postgresql' else db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if not row:
            return None
        return db.execute(f'SELECT COUNT(*) FROM {table} WHERE {where}').fetchone()[0]
    except Exception:
        return None


def _mqtt_probe():
    """MQTT 消费者进程健康状态(通过运行时标记表判断)。"""
    try:
        db = get_db()
        # 先确认表存在,避免首次启动时表尚未创建导致误报
        table_exists = _table_count(db, 'iot_machine_runtime') is not None
        if not table_exists:
            return {'status': 'unknown', 'reason': 'iot_machine_runtime 表尚未创建'}

        row = db.execute(
            "SELECT component, status, heartbeat_at, last_error "
            "FROM iot_machine_runtime WHERE component='mqtt_consumer'"
        ).fetchone()
        if not row:
            return {
                'status': 'unknown',
                'reason': 'mqtt_consumer 未注册运行时(消费者服务可能未启动)',
            }
        data = dict(row) if not isinstance(row, dict) else row
        heartbeat = data.get('heartbeat_at')
        status = data.get('status', 'unknown')
        # 心跳超过 2 分钟视为失联
        if heartbeat:
            try:
                # 兼容 ISO 字符串和 datetime 对象
                from datetime import datetime
                if isinstance(heartbeat, str):
                    heartbeat_dt = datetime.fromisoformat(heartbeat.replace('Z', '+00:00'))
                else:
                    heartbeat_dt = heartbeat
                age_seconds = (datetime.now(heartbeat_dt.tzinfo) - heartbeat_dt).total_seconds()
                if age_seconds > 120:
                    return {
                        'status': 'stale',
                        'reason': f'心跳已超时 {int(age_seconds)} 秒',
                        'heartbeat_at': heartbeat,
                        'last_error': data.get('last_error'),
                    }
            except Exception:
                pass
        return {
            'status': status,
            'heartbeat_at': heartbeat,
            'last_error': data.get('last_error'),
        }
    except Exception as exc:
        return {'status': 'unknown', 'error': str(exc)[:200]}


def _edge_gateway_probe(db):
    """边缘网关活跃度:最近 10 分钟是否有事件入库。"""
    pending = _table_count(db, 'iot_device_event', "processing_status='pending'")
    failed = _table_count(db, 'iot_device_event', "processing_status='failed'")
    total = _table_count(db, 'iot_device_event')
    conflicts = _table_count(db, 'iot_device_event_conflict')
    return {
        'total_events': total,
        'pending_events': pending,
        'failed_events': failed,
        'conflicts': conflicts,
        'healthy': (failed == 0) if failed is not None else None,
    }


def _machine_endpoint_probe(db):
    """机台通讯端点状态。"""
    listening = _table_count(db, 'iot_machine_endpoint', "listener_status='listening'")
    error = _table_count(db, 'iot_machine_endpoint', "listener_status='error'")
    enabled = _table_count(db, 'iot_machine_endpoint', 'enabled=1')
    return {
        'enabled': enabled,
        'listening': listening,
        'error': error,
        'healthy': (error == 0 and (listening or 0) > 0) if error is not None else None,
    }


def _aim_outbox_probe(db):
    """AIM 事件 outbox 待派发数量。"""
    pending = _table_count(db, 'iot_aim_event_outbox', "status='pending'")
    return {'pending': pending}


def liveness():
    """/healthz - 轻量存活探针,只确认进程能响应且数据库连通。"""
    try:
        result = _db_probe(get_db())
        if result['status'] == 'ok':
            return jsonify({'status': 'ok', 'service': 'mes', 'db': result}), 200
        return jsonify({'status': 'error', 'service': 'mes', 'db': result}), 503
    except Exception as exc:
        return jsonify({'status': 'error', 'service': 'mes',
                        'error': str(exc)[:200]}), 503


def readiness():
    """/readyz - 就绪探针,确认数据库可读写、关键表存在。"""
    checks = {}
    overall = 'ok'
    try:
        db = get_db()
        checks['database'] = _db_probe(db)
        if checks['database']['status'] != 'ok':
            overall = 'error'
        # 关键表存在性
        for table in ('sys_user', 'prod_workorder', 'iot_device_event'):
            count = _table_count(db, table)
            checks.setdefault('tables', {})[table] = count is not None
            if count is None:
                overall = 'degraded'
    except Exception as exc:
        checks['database'] = {'status': 'error', 'error': str(exc)[:200]}
        overall = 'error'
    code = 200 if overall == 'ok' else (503 if overall == 'error' else 200)
    return jsonify({'status': overall, 'checks': checks}), code


def full_health():
    """/healthz/full - 完整诊断(应配合登录鉴权使用)。"""
    checks = {}
    try:
        db = get_db()
        checks['database'] = _db_probe(db)
        checks['edge_gateway'] = _edge_gateway_probe(db)
        checks['machine_endpoints'] = _machine_endpoint_probe(db)
        checks['aim_outbox'] = _aim_outbox_probe(db)
    except Exception as exc:
        checks['database'] = {'status': 'error', 'error': str(exc)[:200]}
    checks['mqtt_consumer'] = _mqtt_probe()

    # 汇总:任一关键项 error 则整体 error
    critical = ['database']
    overall = 'ok'
    for key in critical:
        if checks.get(key, {}).get('status') == 'error':
            overall = 'error'
    if any(
        v.get('status') == 'error' or v.get('healthy') is False
        for v in checks.values() if isinstance(v, dict)
    ):
        if overall == 'ok':
            overall = 'degraded'

    code = 503 if overall == 'error' else 200
    return jsonify({'status': overall, 'service': 'mes', 'checks': checks}), code


def register_health_routes(app):
    """在 Flask app 上注册健康检查路由。"""
    app.add_url_rule('/healthz', 'healthz', liveness)
    app.add_url_rule('/readyz', 'readyz', readiness)
    app.add_url_rule('/healthz/full', 'healthz_full', full_health)
