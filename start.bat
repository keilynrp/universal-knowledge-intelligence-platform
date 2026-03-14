@echo off
title UKIP - Universal Knowledge Intelligence Platform
color 0A

echo.
echo  ============================================
echo   UKIP - Starting Local Development Server
echo  ============================================
echo.

REM ── Check .venv exists ──────────────────────────────────────────────────────
if not exist ".venv\Scripts\python.exe" (
    echo  [ERROR] Python virtual environment not found.
    echo  Run: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

REM ── Check frontend deps ─────────────────────────────────────────────────────
if not exist "frontend\node_modules" (
    echo  [ERROR] Frontend dependencies not installed.
    echo  Run: cd frontend ^&^& npm install
    pause
    exit /b 1
)

REM ── Create .env.local if missing ─────────────────────────────────────────────
if not exist "frontend\.env.local" (
    echo  [INFO] Creating frontend\.env.local from example...
    copy "frontend\.env.local.example" "frontend\.env.local" >nul
)

REM ── Kill any stale process on port 8000 ─────────────────────────────────────
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo  [1/2] Starting Backend  ^(FastAPI on port 8000^)...
start "UKIP Backend" cmd /k "title UKIP Backend && cd /d %~dp0 && .venv\Scripts\python -m uvicorn backend.main:app --reload --port 8000"

echo  [2/2] Starting Frontend ^(Next.js on port 3004^)...
start "UKIP Frontend" cmd /k "title UKIP Frontend && cd /d %~dp0\frontend && npm run dev"

echo.
echo  ============================================
echo   Services starting in separate windows:
echo    Backend  ^>  http://localhost:8000
echo    Frontend ^>  http://localhost:3004
echo    API Docs ^>  http://localhost:8000/docs
echo  ============================================
echo.
echo  Press any key to open the app in your browser...
pause >nul

start http://localhost:3004
