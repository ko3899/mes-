@echo off
chcp 65001 >nul
title MES工厂管家 - HTTPS启动

cd /d "%~dp0"

echo ========================================
echo   MES工厂管家 HTTPS 模式启动
echo ========================================
echo.

:: 检查证书文件
if not exist "certs\server.crt" (
    echo [提示] 未找到SSL证书，正在生成自签名证书...
    mkdir certs 2>nul
    openssl req -x509 -newkey rsa:2048 -keyout certs\server.key -out certs\server.crt -days 365 -nodes -subj "/CN=localhost" 2>nul
    if errorlevel 1 (
        echo [错误] 未安装 OpenSSL，请先安装: https://slproweb.com/products/Win32OpenSSL.html
        echo [提示] 或使用 HTTP 模式启动: start_production.bat
        pause
        exit /b 1
    )
    echo   自签名证书已生成: certs\server.crt
)


:: Production requires a strong SECRET_KEY
if "%SECRET_KEY%"=="" (
    echo [ERROR] SECRET_KEY environment variable is required in production.
    pause
    exit /b 1
)
set MES_ENV=production
echo 启动 HTTPS 服务器...
py -3.13 -c "
import ssl
from production import main
from waitress import serve
from app import app, init_db, _init_extra_tables
from utils.database import _create_indexes

init_db()
_init_extra_tables()
_create_indexes()

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info('MES工厂管家 HTTPS 模式启动中...')
logger.info('访问地址: https://localhost:8443')
logger.info('Default admin credentials removed; use your changed admin password')

# 使用 waitress + SSL
import subprocess
subprocess.run(['waitress-serve', '--host=0.0.0.0', '--port=8443', '--threads=8',
    '--certfile=certs/server.crt', '--keyfile=certs/server.key', 'app:app'])
"

pause
