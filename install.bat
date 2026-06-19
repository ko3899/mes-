@echo off
chcp 65001 >nul
title MES工厂管家 - 一键安装

echo ========================================
echo   MES工厂管家 一键安装脚本
echo ========================================
echo.

cd /d "%~dp0"

:: 检查 Python
echo [1/5] 检查 Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python 3.8+
    echo 请先安装 Python: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do echo   Python 版本: %%i

:: 安装依赖
echo [2/5] 安装依赖...
pip install flask openpyxl psutil waitress -i https://pypi.tuna.tsinghua.edu.cn/simple --quiet
echo   依赖安装完成

:: 创建目录
echo [3/5] 创建目录结构...
if not exist "database" mkdir database
if not exist "logs" mkdir logs
if not exist "backups" mkdir backups
if not exist "uploads\documents" mkdir uploads\documents
if not exist "reports" mkdir reports
if not exist "screenshots" mkdir screenshots
echo   目录创建完成

:: 初始化数据库
echo [4/5] 初始化数据库...
python -c "import sys; sys.path.insert(0, 'backend'); from utils.database import init_db, _init_extra_tables; init_db(); _init_extra_tables(); print('  数据库初始化完成')"

:: 初始化示例数据
echo [5/5] 初始化示例数据...
python backend/init_sample_data.py

echo.
echo ========================================
echo   安装完成！
echo ========================================
echo.
echo   启动方式:
echo     生产模式: python production.py
echo     开发模式: python backend/app.py
echo.
echo   访问地址:
echo     管理后台: http://localhost:8080/admin
echo     采集终端: http://localhost:8080
echo     生产看板: http://localhost:8080/kanban
echo.
echo   默认账号: admin / admin123
echo.
pause
