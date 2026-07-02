@echo off
set PYTHONIOENCODING=utf-8
pushd "%~dp0Arlert_BE"
"%~dp0.venv\Scripts\python.exe" -m uvicorn alert_server:app --host 0.0.0.0 --port 8000 --reload
pause
