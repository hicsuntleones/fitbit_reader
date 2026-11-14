@echo off
rem Esegue fitbit_reader con l'ambiente del progetto. Esempi:
rem   fitbit.bat auth
rem   fitbit.bat check
rem   fitbit.bat sync --since 2025-01-01
cd /d "%~dp0"
.venv\Scripts\python -m fitbit_reader %*
