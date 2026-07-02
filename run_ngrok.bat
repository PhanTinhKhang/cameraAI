@echo off
echo Starting ngrok tunnel on port 8000...
"%~dp0ngrok.exe" http --domain=linoleum-devourer-kindred.ngrok-free.dev 8000
pause
