@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "FIRST_RUN="
if not exist instance\orderpulse.db set "FIRST_RUN=1"
if not exist .venv\Scripts\python.exe py -3.12 -m venv --without-pip .venv
if errorlevel 1 exit /b 1
if exist vendor\wheels (
  .venv\Scripts\python.exe setup_offline.py
) else (
  .venv\Scripts\python.exe -m ensurepip
  .venv\Scripts\python.exe -m pip install -r requirements.txt
)
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe manage.py migrate
if errorlevel 1 exit /b 1
if "%~1"=="demo" if defined FIRST_RUN .venv\Scripts\python.exe manage.py seed
if errorlevel 1 exit /b 1
echo Для демонстрационных записей один раз выполните: .venv\Scripts\python.exe manage.py seed
echo Откройте http://127.0.0.1:5065
.venv\Scripts\python.exe manage.py run
