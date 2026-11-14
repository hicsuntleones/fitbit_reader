@echo off
rem Apre la dashboard nel browser (Ctrl+C in questa finestra per chiuderla).
cd /d "%~dp0"
.venv\Scripts\python -m streamlit run src\fitbit_reader\dashboard.py --browser.gatherUsageStats false
