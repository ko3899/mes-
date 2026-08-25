@echo off
cd /d "%~dp0"

echo Starting MES Collector on port 8080...
start "MES Collector" cmd /c "cd frontend && python run.py"

timeout /t 2 >nul

echo Starting MES Admin on port 8081...
start "MES Admin" cmd /c "cd admin && python run.py"

echo.
echo Both systems started!
echo.
echo Collector: http://localhost:8080
echo Admin: http://localhost:8081/admin
echo.
echo Default admin credentials removed; use your changed admin password
echo.
pause
