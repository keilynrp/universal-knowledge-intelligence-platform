@echo off
setlocal
title UKIP - Universal Knowledge Intelligence Platform
color 0A

set "MODE=%~1"
if "%MODE%"=="" set "MODE=start-all"

echo.
echo  ============================================
echo   UKIP - Local Development Control
echo  ============================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo  [ERROR] Python virtual environment not found.
    echo  Run: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.lock
    pause
    exit /b 1
)

if not exist "frontend\node_modules" (
    echo  [ERROR] Frontend dependencies not installed.
    echo  Run: cd frontend ^&^& npm install
    pause
    exit /b 1
)

if not exist "frontend\.env.local" (
    echo  [INFO] Creating frontend\.env.local from example...
    copy "frontend\.env.local.example" "frontend\.env.local" >nul
)

set "DOCKER_READY=0"
set "REQUIRES_LOCAL_PG=0"

findstr /I /C:"127.0.0.1:5432" ".env" >nul 2>&1
if %errorlevel%==0 set "REQUIRES_LOCAL_PG=1"
findstr /I /C:"localhost:5432" ".env" >nul 2>&1
if %errorlevel%==0 set "REQUIRES_LOCAL_PG=1"
findstr /I /C:"POSTGRES_HOST=127.0.0.1" ".env" >nul 2>&1
if %errorlevel%==0 set "REQUIRES_LOCAL_PG=1"
findstr /I /C:"POSTGRES_HOST=localhost" ".env" >nul 2>&1
if %errorlevel%==0 set "REQUIRES_LOCAL_PG=1"

where docker >nul 2>&1
if %errorlevel%==0 (
    docker info >nul 2>&1
    if %errorlevel%==0 (
        set "DOCKER_READY=1"
        echo  [INFO] Ensuring local PostgreSQL is running via docker-compose.dev.yml...
        docker compose -f docker-compose.dev.yml up -d postgres
    ) else (
        echo  [WARN] Docker is installed but the Docker daemon is not running.
        echo  [WARN] Start Docker Desktop before launching backend services that depend on local PostgreSQL.
    )
) else (
    echo  [WARN] Docker not found in Windows PATH.
    echo  [WARN] If Docker runs inside WSL Ubuntu, start PostgreSQL there before starting UKIP.
)

if /I "%MODE%"=="help" goto usage
if /I "%MODE%"=="backend" goto backend
if /I "%MODE%"=="frontend" goto frontend
if /I "%MODE%"=="restart-backend" goto backend
if /I "%MODE%"=="restart-frontend" goto frontend
if /I "%MODE%"=="restart-all" goto startall
if /I "%MODE%"=="start-all" goto startall

echo  [ERROR] Unknown option: %MODE%
goto usage

:kill8000
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-local-backend.ps1" -Port 8000
if errorlevel 1 exit /b 1
goto :eof

:kill3004
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3004 " ^| findstr "LISTENING"') do (
    echo  [INFO] Stopping process on port 3004 ^(PID %%a^)...
    taskkill /F /PID %%a >nul 2>&1
)
goto :eof

:checkdb
if not "%REQUIRES_LOCAL_PG%"=="1" goto :eof
set "PG_READY=0"
set "_RETRY=0"
:checkdb_loop
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5432 " ^| findstr "LISTENING"') do set "PG_READY=1"
if "%PG_READY%"=="1" goto :eof
set /a "_RETRY+=1"
if %_RETRY% GEQ 12 goto checkdb_fail
echo  [INFO] Waiting for PostgreSQL on port 5432... ^(attempt %_RETRY%/12^)
timeout /t 5 /nobreak >nul
goto checkdb_loop
:checkdb_fail
echo.
echo  [ERROR] Local PostgreSQL is not reachable on port 5432 after 60 seconds.
if "%DOCKER_READY%"=="0" (
    echo  [ERROR] Docker Desktop is not ready, so UKIP could not auto-start the local database.
    echo  [ERROR] Start Docker Desktop and try again.
) else (
    echo  [ERROR] The local database did not come up as expected.
    echo  [ERROR] Check: docker compose -f docker-compose.dev.yml ps
)
echo  [ERROR] Backend startup aborted to avoid a misleading login failure.
echo.
exit /b 1

:backend
set "PG_READY=0"
call :checkdb
if errorlevel 1 goto end
call :kill8000
echo  [INFO] Starting Backend ^(FastAPI on port 8000^)...
start "UKIP Backend" cmd /k "title UKIP Backend && cd /d %~dp0 && .venv\Scripts\alembic upgrade head && .venv\Scripts\python -m uvicorn backend.main:app --port 8000"
echo.
echo  [OK] Backend launch requested.
goto end

:frontend
call :kill3004
echo  [INFO] Starting Frontend ^(Next.js on port 3004^)...
start "UKIP Frontend" cmd /k "title UKIP Frontend && cd /d %~dp0\frontend && npm run dev"
echo.
echo  [OK] Frontend launch requested.
goto end

:startall
set "PG_READY=0"
call :checkdb
if errorlevel 1 goto end
call :kill8000
call :kill3004
echo  [1/2] Launching backend...
start "UKIP Backend" cmd /k "title UKIP Backend && cd /d %~dp0 && .venv\Scripts\alembic upgrade head && .venv\Scripts\python -m uvicorn backend.main:app --port 8000"
echo  [2/2] Launching frontend...
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
goto end

:usage
echo  Usage:
echo    start.bat                 ^> start backend + frontend
echo    start.bat start-all       ^> start backend + frontend
echo    start.bat restart-all     ^> restart backend + frontend
echo    start.bat backend         ^> start backend only
echo    start.bat frontend        ^> start frontend only
echo    start.bat restart-backend ^> restart backend only
echo    start.bat restart-frontend^> restart frontend only
echo    start.bat help            ^> show this help
goto end

:end
endlocal
