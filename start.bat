@echo off
setlocal enabledelayedexpansion

title CampusPilot

echo ========================================
echo    CampusPilot v2.0
echo    CQUPT Personal Academic Assistant
echo ========================================
echo.

:: ------------------------------------------------------------
:: Step 1: Detect Python
:: ------------------------------------------------------------
set PYTHON_CMD=

:: Try full path first (most reliable)
if exist "C:\Users\ASUS\AppData\Local\Programs\Python\Python313\python.exe" (
    set "PYTHON_CMD=C:\Users\ASUS\AppData\Local\Programs\Python\Python313\python.exe"
    goto :python_found
)

:: Try py launcher
py --version >nul 2>&1
if !errorlevel! equ 0 (
    set PYTHON_CMD=py
    goto :python_found
)

:: Try python
python --version >nul 2>&1
if !errorlevel! equ 0 (
    set PYTHON_CMD=python
    goto :python_found
)

if "%PYTHON_CMD%"=="" (
    echo [ERROR] Python not found!
    echo Please install Python 3.11+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH"
    pause
    exit /b 1
)

:python_found
%PYTHON_CMD% --version

:: ------------------------------------------------------------
:: Step 2: Detect Node.js (optional, for frontend)
:: ------------------------------------------------------------
set NODE_FOUND=0
where node >nul 2>&1 && set NODE_FOUND=1
if %NODE_FOUND% equ 1 (
    for /f "tokens=2 delims=v" %%v in ('node --version') do set NODE_VER=%%v
    echo [OK] Node.js version: %NODE_VER%
) else (
    echo [WARN] Node.js not found. Frontend will be unavailable.
)

:: ------------------------------------------------------------
:: Step 3: Ensure .env exists
:: ------------------------------------------------------------
if not exist ".env" (
    echo [!] Creating default .env...
    (
        echo FERNET_KEY=
        echo TZ=Asia/Shanghai
        echo DATABASE_URL=sqlite+aiosqlite:///data/campus.db
        echo FRONTEND_URL=http://localhost:3000
    ) > .env
    echo [OK] .env created
)

:: ------------------------------------------------------------
:: Step 4: Create virtual environment if needed
:: ------------------------------------------------------------
if not exist "venv" (
    echo [INFO] Creating Python virtual environment...
    %PYTHON_CMD% -m venv venv
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
)

:: ------------------------------------------------------------
:: Step 5: Install backend dependencies (skip version-locked packages, let pip resolve)
:: ------------------------------------------------------------
echo [INFO] Installing backend dependencies...
call venv\Scripts\activate.bat
pip install fastapi uvicorn python-dotenv pydantic-settings sqlalchemy aiosqlite alembic httpx beautifulsoup4 lxml playwright ddddocr apscheduler cryptography openai
if !errorlevel! equ 0 (
    echo [OK] Backend dependencies installed
) else (
    echo [WARN] Some dependencies may have failed, continuing...
)

:: ------------------------------------------------------------
:: Step 6: Start backend server
:: ------------------------------------------------------------
echo.
echo [1/2] Starting backend API server...
echo        http://localhost:8000
echo.
start "CampusPilot-Backend" cmd /k "cd /d %~dp0 && call venv\Scripts\activate.bat && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo [WAIT] Waiting for backend to start...
ping -n 8 127.0.0.1 >nul 2>&1

:: ------------------------------------------------------------
:: Step 7: Start frontend (if Node.js available)
:: ------------------------------------------------------------
if %NODE_FOUND% equ 1 (
    echo.
    echo [2/2] Starting frontend...
    if exist "frontend\package.json" (
        if not exist "frontend\node_modules" (
            echo [INFO] First run, installing frontend dependencies...
            start "CampusPilot-Frontend" cmd /k "cd /d %~dp0frontend && npm install && npm run dev"
        ) else (
            start "CampusPilot-Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
        )
        ping -n 10 127.0.0.1 >nul 2>&1
    ) else (
        echo [INFO] Frontend project not found, backend only mode
    )
) else (
    echo [INFO] Skipping frontend (Node.js not available)
)

:: ------------------------------------------------------------
:: Done
:: ------------------------------------------------------------
cls
echo.
echo ========================================
echo    CampusPilot Started!
echo ========================================
echo.
echo   Web UI:        http://localhost:3000
echo   Backend API:   http://localhost:8000
echo   API Docs:      http://localhost:8000/docs
echo.
echo   Close this window will NOT stop the services.
echo   To stop: close the CampusPilot-Backend and
echo   CampusPilot-Frontend terminal windows.
echo.

:: ------------------------------------------------------------
:: Ask about auto-start
:: ------------------------------------------------------------
set /p "SET_AUTOSTART=Enable auto-start on login? (y/N): "
if /i "!SET_AUTOSTART!"=="y" (
    echo [INFO] Setting up auto-start...
    schtasks /query /tn "CampusPilot" >nul 2>&1
    if !errorlevel! equ 0 (
        echo [INFO] Auto-start task exists, updating...
        schtasks /change /tn "CampusPilot" /tn "CampusPilot" >nul 2>&1
    ) else (
        echo [INFO] Creating auto-start task...
        schtasks /create /tn "CampusPilot" /tr "'%~dp0start.bat'" /sc onlogon /ru "%USERNAME%" /f >nul 2>&1
    )
    if !errorlevel! equ 0 (
        echo [OK] Auto-start enabled!
        echo To disable: schtasks /delete /tn "CampusPilot" /f
    ) else (
        echo [WARN] Auto-start setup failed. Try running as Administrator.
    )
)

echo.
pause
