"""MES工厂管家生产环境启动入口。"""
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
import os
import sys


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

log_file = os.path.join(LOG_DIR, f'mes_{datetime.now().strftime("%Y%m%d")}.log')
handler = RotatingFileHandler(
    log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding='utf-8'
)
handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
console = logging.StreamHandler()
console.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logging.basicConfig(level=logging.INFO, handlers=[handler, console])
logger = logging.getLogger(__name__)


def main():
    sys.path.insert(0, os.path.join(BASE_DIR, 'backend'))

    from app import app, init_db, _init_extra_tables
    from init_sample_data import init_sample_data
    from machine_gateway_manager import MachineGatewayManager
    from machine_csv_collector import MachineCsvCollector
    from utils.database import _create_indexes

    logger.info('正在初始化数据库')
    init_db()
    _init_extra_tables()
    _create_indexes()
    init_sample_data()
    logger.info('数据库初始化完成')

    gateway_manager = MachineGatewayManager()
    gateway_count = gateway_manager.start()
    logger.info('AIM机台Socket服务已启动：%s个端点', gateway_count)

    csv_collector = MachineCsvCollector(
        archive_root=os.environ.get(
            'MES_MACHINE_ARCHIVE_DIR', os.path.join(BASE_DIR, 'machine_archive')
        ),
        interval=float(os.environ.get('MES_MACHINE_SCAN_SECONDS', '2')),
    )
    csv_collector.start()
    logger.info('AIM机台CSV目录采集服务已启动')

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
        csv_collector.stop()
        logger.info('AIM机台CSV目录采集服务已停止')
        gateway_manager.stop()
        logger.info('AIM机台Socket服务已停止')


if __name__ == '__main__':
    main()
