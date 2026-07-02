@echo off


:loop
pushd "%~dp0ML"
call ".%~dp0.venv\Scripts\activate"
python cleanup_old_videos.py

echo Da xong. Cho 1 gio (3600 giay)...
timeout /t 3600 /nobreak
goto loop