@echo off
rem Scarico giornaliero, pensato per l'Utilita' di pianificazione di Windows.
rem Il log viene aggiunto a logs\sync.log
cd /d "%~dp0"
if not exist logs mkdir logs
echo ===== %date% %time% ===== >> logs\sync.log
.venv\Scripts\python -m fitbit_reader sync >> logs\sync.log 2>&1
exit /b %errorlevel%
