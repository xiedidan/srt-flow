@echo off
REM Development backend startup script with hot reload (Windows)

REM Activate virtual environment if exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

REM Load PORT from .env file, default to 8031 if not found
set PORT=8031
if exist .env (
    for /f "tokens=1,2 delims==" %%a in ('findstr /i "^PORT=" .env') do set PORT=%%b
)

REM Start backend with hot reload
echo Starting backend on port %PORT%...
uvicorn backend.app.main:app --reload --reload-dir backend --host 0.0.0.0 --port %PORT% --log-level info
