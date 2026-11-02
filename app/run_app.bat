@echo off
REM Dengue Forecasting System - web app (http://127.0.0.1:5001)
cd /d "%~dp0"
set PY=..\pipeline\.venv\Scripts\python.exe
if not exist "%PY%" (
  echo Python environment not found: %PY%
  echo Create it first: see ..\pipeline\requirements.txt and README.md
  pause
  exit /b 1
)
start "" http://127.0.0.1:5001
"%PY%" app.py
pause
