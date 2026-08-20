"""结构化 JSON 日志,便于接入 ELK / Loki / Datadog 等日志平台。

用法:
    from utils.json_logger import get_logger
    logger = get_logger('mes.production')
    logger.info('数据库初始化完成', extra={'duration_ms': 580, 'phase': 'init'})

输出示例:
    {"ts":"2026-08-20T09:12:33.001+08:00","level":"INFO","logger":"mes.production",
     "msg":"数据库初始化完成","duration_ms":580,"phase":"init"}

设计要点:
- 时间戳带时区,ISO8601 毫秒精度
- 所有字段单行 JSON,便于日志采集器按行解析
- 异常自动展开为 stack 字段
- extra 里的字段平铺到顶层,与 level/msg 同级
- 非 JSON 友好的字符(换行等)自动转义
"""

import datetime
import json
import logging
import os
import sys
import traceback


class JsonFormatter(logging.Formatter):
    """将 LogRecord 格式化为单行 JSON。"""

    # 标准 LogRecord 属性,不放进 extra 平铺
    _RESERVED = {
        'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
        'module', 'exc_info', 'exc_text', 'stack_info', 'lineno', 'funcName',
        'created', 'msecs', 'relativeCreated', 'thread', 'threadName',
        'processName', 'process', 'message', 'asctime', 'taskName',
    }

    def format(self, record):
        tz = datetime.timezone(datetime.timedelta(hours=8))
        ts = datetime.datetime.fromtimestamp(record.created, tz=tz).isoformat(
            timespec='milliseconds'
        )
        payload = {
            'ts': ts,
            'level': record.levelname,
            'logger': record.name,
            'msg': record.getMessage(),
        }
        # 平铺 extra 字段
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith('_'):
                payload[key] = self._safe(value)
        # 异常栈
        if record.exc_info:
            payload['stack'] = ''.join(
                traceback.format_exception(*record.exc_info)
            ).rstrip()
        return json.dumps(payload, ensure_ascii=False, default=str)

    @staticmethod
    def _safe(value):
        """确保值可 JSON 序列化。"""
        try:
            json.dumps(value)
            return value
        except (TypeError, ValueError):
            return str(value)


def get_logger(name='mes', level=None):
    """获取一个输出 JSON 的 logger。

    level 默认读 MES_LOG_LEVEL 环境变量,再退回 INFO。
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        # 已配置过,直接返回(避免重复 handler)
        return logger
    logger.setLevel(level or os.environ.get('MES_LOG_LEVEL', 'INFO').upper())
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger
