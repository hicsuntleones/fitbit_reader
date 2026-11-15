@echo off
rem Opens the dashboard in the browser (Ctrl+C in this window to stop it).
cd /d "%~dp0"
.venv\Scripts\python -m streamlit run src\fitbit_reader\dashboard.py --browser.gatherUsageStats false
