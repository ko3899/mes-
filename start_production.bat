@echo off
chcp 65001 >nul
title MES工厂管家 - 生产环境

echo ========================================
echo   MES工厂管家 生产环境启动
echo ========================================
echo.

cd /d "%~dp0"

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

:: 检查依赖
echo [1/3] 检查依赖...
pip show flask >nul 2>&1
if errorlevel 1 (
    echo [2/3] 安装依赖...
    pip install flask openpyxl waitress -i https://pypi.tuna.tsinghua.edu.cn/simple
) else (
    pip show waitress >nul 2>&1
    if errorlevel 1 (
        echo [2/3] 安装 waitress...
        pip install waitress -i https://pypi.tuna.tsinghua.edu.cn/simple
    ) else (
        echo [2/3] 依赖已就绪
    )
)

:: 创建必要目录
if not exist "logs" mkdir logs
if not exist "backups" mkdir backups
if not exist "uploads\documents" mkdir uploads\documents


:: Production requires a strong SECRET_KEY
if "%SECRET_KEY%"=="" (
    echo [ERROR] SECRET_KEY environment variable is required in production.
    pause
    exit /b 1
)
set MES_ENV=production
echo [3/3] 启动服务...
echo.
echo ========================================
echo   服务已启动！
echo   访问地址: http://localhost:8080
echo   管理后台: http://localhost:8081/admin
echo   Default admin credentials removed; use your changed admin password
echo   按 Ctrl+C 停止服务
echo ========================================
echo.

python production.py

pause
