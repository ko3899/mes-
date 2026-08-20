"""测试 utils.json_logger 的输出格式。"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

import io
import json
import logging

from utils.json_logger import JsonFormatter, get_logger


def _capture(name):
    """返回一个捕获输出的 logger。"""
    logger = logging.getLogger(name)
    logger.handlers = []
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger, buf


def test_basic_fields():
    logger, buf = _capture('test.basic')
    logger.info('hello')
    line = buf.getvalue().strip()
    obj = json.loads(line)
    assert obj['level'] == 'INFO'
    assert obj['msg'] == 'hello'
    assert obj['logger'] == 'test.basic'
    assert 'ts' in obj and '+' in obj['ts']  # 带时区


def test_extra_fields_flattened():
    logger, buf = _capture('test.extra')
    logger.info('done', extra={'duration_ms': 580, 'phase': 'init'})
    obj = json.loads(buf.getvalue().strip())
    assert obj['duration_ms'] == 580
    assert obj['phase'] == 'init'


def test_exception_stack():
    logger, buf = _capture('test.exc')
    try:
        raise ValueError('boom')
    except ValueError:
        logger.exception('failed')
    obj = json.loads(buf.getvalue().strip())
    assert obj['msg'] == 'failed'
    assert 'ValueError: boom' in obj['stack']


def test_non_serializable_coerced():
    logger, buf = _capture('test.coerce')
    logger.info('ok', extra={'obj': object()})
    obj = json.loads(buf.getvalue().strip())
    assert isinstance(obj['obj'], str)


def test_single_line():
    logger, buf = _capture('test.oneline')
    logger.info('line1\nline2')
    out = buf.getvalue()
    assert out.count('\n') == 1  # 只有一个换行(行尾)


if __name__ == '__main__':
    test_basic_fields()
    test_extra_fields_flattened()
    test_exception_stack()
    test_non_serializable_coerced()
    test_single_line()
    print('json_logger tests passed')
