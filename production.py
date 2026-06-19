"""MES工厂管家 - 生产环境启动脚本"""
import os
import sys
import logging
from datetime import datetime

# 设置日志
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, f'mes_{datetime.now().strftime("%Y%m%d")}.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def main():
    # 添加 backend 到路径
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))
    
    from app import app, init_db, _init_extra_tables
    from utils.database import _create_indexes
    from init_sample_data import init_sample_data
    
    # 初始化数据库
    logger.info("正在初始化数据库...")
    init_db()
    _init_extra_tables()
    _create_indexes()
    init_sample_data()
    logger.info("数据库初始化完成")
    
    # 获取配置
    host = os.environ.get('MES_HOST', '0.0.0.0')
    port = int(os.environ.get('MES_PORT', '8080'))
    workers = int(os.environ.get('MES_WORKERS', '4'))
    
    logger.info(f"MES工厂管家 生产环境启动中...")
    logger.info(f"监听地址: {host}:{port}")
    logger.info(f"工作进程: {workers}")
    
    try:
        from waitress import serve
        logger.info("使用 Waitress WSGI 服务器")
        serve(app, host=host, port=port, threads=workers * 2)
    except ImportError:
        logger.warning("waitress 未安装，使用 Flask 内置服务器（不推荐用于生产）")
        app.run(host=host, port=port, debug=False)


if __name__ == '__main__':
    main()
