@echo off
echo ===================================================
echo       Starting Easy-Prompt System
echo ===================================================

:: 1. Start Backend Server
echo [1/2] Starting Backend Server (Port 8010)...
start "Easy-Prompt Backend" cmd /k "call venv\Scripts\activate && python main.py"

:: Wait a moment for backend to initialize
timeout /t 3 /nobreak >nul

:: 2. Start Frontend WebUI
echo [2/2] Starting Frontend WebUI...
cd web-client\EasyP-webui
start "Easy-Prompt Frontend" cmd /k "npm run dev"

echo.
echo ===================================================
echo       System Started!
echo       Backend: http://127.0.0.1:8010
echo       Frontend: http://localhost:9000 (or similar)
echo ===================================================
echo.
echo You can minimize these windows, but do not close them.
echo.
pause
