@echo off
title Study Planner Agent Dashboard
echo ========================================================
echo       Starting Study Planner Agent Web Application
echo ========================================================
echo.

:: Check if virtual environment exists
if not exist ".venv\Scripts\python.exe" (
    echo [Error] Python virtual environment was not found.
    echo Please make sure you are running this from the project folder
    echo where the .venv directory is located.
    pause
    exit /b
)

echo [System] Launching FastAPI backend server...
:: Start uvicorn server in background inside this terminal
start /b .venv\Scripts\python.exe -m uvicorn app:app --port 8000 --host 127.0.0.1

echo [System] Server started. Waiting for initialization...
:: Wait 2 seconds for server to start before opening browser
timeout /t 2 >nul

echo [System] Opening web browser...
start http://127.0.0.1:8000

echo.
echo ========================================================
echo  Dashboard running at: http://127.0.0.1:8000
echo  Press Ctrl+C inside this window or close it to shut down.
echo ========================================================
echo.

:: Keep window open
pause >nul
