"""MES工厂管家生产环境启动入口。"""
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
import os
import sys
import time


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# 结构化 JSON 日志(便于接入 ELK/Loki),可通过 MES_LOG_FORMAT=text 回退纯文本
_log_format = os.environ.get('MES_LOG_FORMAT', 'json').lower()
log_file = os.path.join(LOG_DIR, f'mes_{datetime.now().strftime("%Y%m%d")}.log')
file_handler = RotatingFileHandler(
    log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding='utf-8'
)
console_handler = logging.StreamHandler()

if _log_format == 'json':
    sys.path.insert(0, os.path.join(BASE_DIR, 'backend'))
    from utils.json_logger import JsonFormatter
    _fmt = JsonFormatter()
else:
    _fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

file_handler.setFormatter(_fmt)
console_handler.setFormatter(_fmt)
logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
logger = logging.getLogger(__name__)


def _ensure_secret_key():
    """生产环境必须配置随机 SECRET_KEY，拒绝使用默认或空密钥启动。"""
    secret = os.environ.get('FLASK_SECRET_KEY') or os.environ.get('SECRET_KEY')
    env = os.environ.get('MES_ENV', '').lower()
    if not secret and env == 'production':
        raise RuntimeError(
            '生产环境必须设置 FLASK_SECRET_KEY 或 SECRET_KEY 环境变量。'
            '可用 python -c "import secrets; print(secrets.token_hex(32))" 生成。'
        )
    if not secret:
        logger.warning('未配置 FLASK_SECRET_KEY/SECRET_KEY，将使用临时随机密钥（重启后会话失效）')
    return secret


def main():
    sys.path.insert(0, os.path.join(BASE_DIR, 'backend'))

    from app import app, init_db, _init_extra_tables
    from init_sample_data import init_sample_data
    from machine_runtime import MachineCommunicationRuntime
    from utils.database import _create_indexes

    secret_key = _ensure_secret_key()
    app.secret_key = secret_key or os.urandom(32).hex()

    logger.info('正在初始化数据库')
    t0 = time.time()
    init_db()
    _init_extra_tables()
    _create_indexes()
    logger.info('数据库结构初始化完成，耗时 %.3fs', time.time() - t0)

    t1 = time.time()
    init_sample_data()
    logger.info('示例/种子数据初始化完成，耗时 %.3fs', time.time() - t1)

    machine_runtime = MachineCommunicationRuntime()
    owns_runtime = machine_runtime.start()
    logger.info(
        'AIM机台通讯运行时：%s', '已启动' if owns_runtime else '已由其他进程托管'
    )

    host = os.environ.get('MES_HOST', '0.0.0.0')
    port = int(os.environ.get('MES_PORT', '8080'))
    workers = int(os.environ.get('MES_WORKERS', '4'))
    logger.info('MES Web服务监听：%s:%s', host, port)

    try:
        try:
            from waitress import serve
            logger.info('使用Waitress WSGI服务器')
            serve(app, host=host, port=port, threads=workers * 2)
        except ImportError:
            logger.warning('Waitress未安装，使用Flask内置服务器')
            app.run(host=host, port=port, debug=False)
    finally:
        machine_runtime.stop()
        logger.info('AIM机台通讯运行时已停止')


if __name__ == '__main__':
    raise SystemExit(main())
