@echo off
chcp 65001 >nul
title SRT Flow

echo ========================================
echo   SRT Flow - Starting Services
echo ========================================
echo.

:: Read PORT from .env
set PORT=8081
for /f "tokens=1,2 delims==" %%a in (.env) do (
    if "%%a"=="PORT" set PORT=%%b
)

:: Start backend
echo [1/2] Starting backend (port %PORT%)...
start "SRT-Flow Backend" cmd /k "cd /d %~dp0 && venv\Scripts\activate && uvicorn backend.app.main:app --host 0.0.0.0 --port %PORT% --log-level info"

:: Wait a moment for backend to initialize
timeout /t 2 /nobreak >nul

:: Start frontend
echo [2/2] Starting frontend...
start "SRT-Flow Frontend" cmd /k "cd /d %~dp0\frontend && npm run dev"

echo.
echo ========================================
echo   Backend:  http://localhost:%PORT%
echo   Frontend: http://localhost:5173
echo ========================================
echo.
echo Close this window or press any key to exit.
echo (Backend and Frontend will keep running in their own windows)
pause >nul
