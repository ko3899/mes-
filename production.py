"""MES工厂管家 - 生产环境启动脚本"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
log_dir = os.path.join(BASE_DIR, 'logs')
os.makedirs(log_dir, exist_ok=True)

# 日志轮转：单文件最大10MB，保留5个备份
log_file = os.path.join(log_dir, f'mes_{datetime.now().strftime("%Y%m%d")}.log')
handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

console = logging.StreamHandler()
console.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

logging.basicConfig(level=logging.INFO, handlers=[handler, console])
logger = logging.getLogger(__name__)

def main():
    sys.path.insert(0, os.path.join(BASE_DIR, 'backend'))
    
    from app import app, init_db, _init_extra_tables
    from utils.database import _create_indexes
    from init_sample_data import init_sample_data
    
    logger.info("正在初始化数据库...")
    init_db()
    _init_extra_tables()
    _create_indexes()
    init_sample_data()
    logger.info("数据库初始化完成")
    
    host = os.environ.get('MES_HOST', '0.0.0.0')
    port = int(os.environ.get('MES_PORT', '8080'))
    workers = int(os.environ.get('MES_WORKERS', '4'))
    
    logger.info(f"MES工厂管家 生产环境启动中...")
    logger.info(f"监听地址: {host}:{port}")
    
    try:
        from waitress import serve
        logger.info("使用 Waitress WSGI 服务器")
        serve(app, host=host, port=port, threads=workers * 2)
    except ImportError:
        logger.warning("waitress 未安装，使用 Flask 内置服务器")
        app.run(host=host, port=port, debug=False)

if __name__ == '__main__':
    main()
