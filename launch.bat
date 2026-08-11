@echo off
title SoulIllusions AI Video Maker
cd /d "%~dp0"

REM Kill any old instance on port 7860
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":7860" ^| findstr "LISTENING" 2^>nul') do (
    taskkill /F /PID %%a 2>nul
)

REM Start the server
"%APPDATA%\uv\python\cpython-3.11.15-windows-x86_64-none\python.exe" server.py

REM If we get here, the server crashed - keep window open
echo.
echo ============================================
echo  The server stopped. Press any key to close.
echo ============================================
pause >nul
