@echo off
rem Crea l'ambiente Python (.venv) e installa fitbit_reader. Da eseguire una volta.
cd /d "%~dp0"
if not exist .venv (
    py -3 -m venv .venv || exit /b 1
)
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e ".[dashboard]" || exit /b 1
echo.
echo Ambiente pronto. Prossimo passo:  fitbit.bat auth
