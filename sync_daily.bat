@echo off
rem Daily download, meant for the Windows Task Scheduler.
rem The log is appended to logs\sync.log
cd /d "%~dp0"
if not exist logs mkdir logs
echo ===== %date% %time% ===== >> logs\sync.log
.venv\Scripts\python -m fitbit_reader sync >> logs\sync.log 2>&1
exit /b %errorlevel%
