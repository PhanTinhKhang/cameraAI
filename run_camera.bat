@echo off
pushd "%~dp0ML"
call ".%~dp0.venv\Scripts\activate"
python arlert.py
pause
