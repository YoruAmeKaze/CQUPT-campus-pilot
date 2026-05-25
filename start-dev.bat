@echo off
chcp 65001 >nul 2>&1
setlocal

:: ============================================================
:: CampusPilot Quick Start (Windows) - Fixed Version
:: Compatible with both CMD and PowerShell
:: ============================================================

title CampusPilot - Local Dev Server

echo.
echo ============================================
echo   CampusPilot Local Dev Environment
echo ============================================
echo.

:: Check Python (try multiple commands)
set PYTHON_CMD=
where python >nul 2>&1 && set PYTHON_CMD=python
if "%PYTHON_CMD%"=="" where py >nul 2>&1 && set PYTHON_CMD=py
if "%PYTHON_CMD%"=="" where python3 >nul 2>&1 && set PYTHON_CMD=python3

if "%PYTHON_CMD%"=="" (
    echo [ERROR] Python not found!
    echo.
    echo Please install Python 3.11+ from:
    echo https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

:: Get Python version
for /f "tokens=2 delims=" %%v in ('%PYTHON_CMD% --version 2^>^&1') do set PYVER=%%v
echo [OK] Python version: %PYVER%

:: Create venv if needed
if not exist "venv" (
    echo.
    echo [INFO] Creating virtual environment...
    %PYTHON_CMD% -m venv vvm
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
) else (
    echo [OK] Using existing virtual environment
)

:: Activate and install deps
call venv\Scripts\activate.bat >nul 2>&1
echo [INFO] Installing/updating dependencies...
pip install -q -r requirements.txt >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Backend dependencies ready
) else (
    echo [WARNING] Some dependencies may have failed (non-critical)
    echo          Core dependencies should be installed
)

:: Start Backend
echo.
echo [1/2] Starting Backend API server...
echo        URL: http://localhost:8000
echo        Docs: http://localhost:8000/docs
echo.

start "CampusPilot-Backend" cmd /k "cd /d %~dp0 && call venv\Scripts\activate.bat && %PYTHON_CMD% -m uvicorn app.main:app --reload --port 8000"

:: Wait for backend using ping (compatible with all Windows versions)
echo Waiting for backend to start...
ping -n 7 127.0.0.1 >nul 2>&1

:: Start Frontend (optional)
if exist "frontend\package.json" (
    echo.
    echo [2/2] Starting Frontend dev server...
    
    if not exist "frontend\node_modules" (
        echo        First run - installing dependencies...
        start "CampusPilot-Frontend" cmd /k "cd /d %~dp0frontend && npm install && npm run dev"
    ) else (
        echo        URL: http://localhost:3000
        start "CampusPilot-Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
    )
    
    :: Wait for frontend
    ping -n 10 127.0.0.1 >nul 2>&1
    
    echo.
    echo ============================================
    echo       Development Environment Ready!
    echo ============================================
    echo.
    echo   Backend API:  http://localhost:8000
    echo   API Docs:     http://localhost:8000/docs
    echo   Health Check: http://localhost:8000/health
    echo   Frontend UI:  http://localhost:3000
    echo.
    echo   Press any key in this window to stop info...
    echo   Close individual windows to stop servers
    echo.
) else (
    echo.
    echo ============================================
    echo      Backend Only Mode (No frontend found)
    echo ============================================
    echo.
    echo   Backend API:  http://localhost:8000
    echo   API Docs:     http://localhost:8000/docs
    echo   Health Check: http://localhost:8000/health
    echo.
)

pause >nul
exit /b 0
