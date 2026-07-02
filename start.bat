@echo off
echo ================================
echo STARTING AI CAMERA SYSTEM
echo ================================

set ROOT_DIR=%~dp0
echo Root Directory: %ROOT_DIR%

REM ===== FastAPI Backend =====
echo Starting FastAPI Alert Server...
start "FastAPI" cmd /k ^
call "%ROOT_DIR%run_fastapi.bat"

REM ===== AI Camera =====
echo Starting AI Camera...
start "AI Camera" cmd /k ^
call "%ROOT_DIR%run_camera.bat"

REM ===== Web Frontend =====
echo Starting Web UI...
start "Web UI" cmd /k ^
call "%ROOT_DIR%run_web.bat"

REM ===== Web Frontend =====
echo Starting cleaning service...
start "start cleaning service" cmd /k ^
call "%ROOT_DIR%run_clean.bat"

REM ===== Ngrok Tunnel =====
echo Starting ngrok tunnel...
start "Ngrok" cmd /k ^
call "%ROOT_DIR%run_ngrok.bat"

echo ================================
echo SYSTEM STARTED SUCCESSFULLY
echo ================================
pause
