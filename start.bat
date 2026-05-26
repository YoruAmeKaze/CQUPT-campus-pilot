@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

title CampusPilot

:: ============================================================
:: CampusPilot 一键启动脚本
:: 支持：Windows 10/11
:: 用途：自动检测环境、安装依赖、启动前后端服务
:: ============================================================

call :print_banner

:: ─── 检测 Python ──────────────────────────────────────────
call :check_python
if %errorlevel% neq 0 goto :end_error

:: ─── 检测 Node.js（前端需要）───────────────────────────────
call :check_nodejs

:: ─── 确保 .env 文件存在 ────────────────────────────────────
if not exist ".env" (
    echo [!] 未找到 .env 文件，正在创建默认配置...
    (
        echo FERNET_KEY=
        echo TZ=Asia/Shanghai
        echo DATABASE_URL=sqlite+aiosqlite:///data/campus.db
        echo FRONTEND_URL=http://localhost:3000
    ) > .env
    echo [OK] .env 已创建
)

:: ─── 自动生成 FERNET_KEY ──────────────────────────────────
for /f "tokens=2 delims==" %%a in ('findstr "^FERNET_KEY=" .env') do set "FERNET_VAL=%%a"
if "%FERNET_VAL%"=="" (
    echo [INFO] 首次运行，正在自动生成加密密钥...
    for /f %%i in ('%PYTHON_CMD% -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2^>nul') do set "NEW_KEY=%%i"
    if not "!NEW_KEY!"=="" (
        :: 替换 .env 中的 FERNET_KEY 行
        powershell -Command "(Get-Content .env) -replace '^FERNET_KEY=$', 'FERNET_KEY=!NEW_KEY!' | Set-Content .env"
        echo [OK] 加密密钥已生成
    ) else (
        echo [WARN] 无法自动生成加密密钥（可手动设置 FERNET_KEY）
    )
)

:: ─── 创建/激活虚拟环境 ───────────────────────────────────
if not exist "venv" (
    echo [INFO] 正在创建 Python 虚拟环境...
    %PYTHON_CMD% -m venv venv
    if !errorlevel! neq 0 (
        echo [ERROR] 创建虚拟环境失败
        goto :end_error
    )
    echo [OK] 虚拟环境已创建
)

:: ─── 安装后端依赖 ──────────────────────────────────────
echo [INFO] 正在安装后端依赖...
call venv\Scripts\activate.bat >nul 2>&1
pip install -q -r requirements.txt
if !errorlevel! equ 0 (
    echo [OK] 后端依赖安装完成
) else (
    echo [WARN] 部分依赖安装可能失败，尝试继续...
)

:: ─── 安装 Playwright Chromium ───────────────────────────
echo [INFO] 检查 Playwright 浏览器...
python -c "from playwright.sync_api import sync_playwright; sync_playwright().__enter__()" >nul 2>&1
if !errorlevel! neq 0 (
    echo [INFO] 首次运行，正在安装 Playwright Chromium 浏览器...
    python -m playwright install chromium
    if !errorlevel! equ 0 (
        echo [OK] Playwright Chromium 安装完成
    ) else (
        echo [WARN] Playwright Chromium 安装失败
        echo        爬虫功能将不可用，其他功能正常
    )
) else (
    echo [OK] Playwright 浏览器已就绪
)

:: ─── 启动后端服务 ──────────────────────────────────────
echo.
echo [1/2] 启动后端 API 服务...
echo        http://localhost:8000
echo        http://localhost:8000/docs  （API 文档）
echo.
start "CampusPilot-Backend" cmd /k "cd /d %~dp0 && call venv\Scripts\activate.bat && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

:: ─── 等待后端启动 ──────────────────────────────────────
echo [WAIT] 等待后端启动...
ping -n 8 127.0.0.1 >nul 2>&1

:: ─── 安装前端依赖并启动 ─────────────────────────────────
echo.
echo [2/2] 启动前端服务...

if exist "frontend\package.json" (
    if not exist "frontend\node_modules" (
        echo [INFO] 初次启动，正在安装前端依赖...
        start "CampusPilot-Frontend" cmd /k "cd /d %~dp0frontend && npm install && npm run dev"
    ) else (
        start "CampusPilot-Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
    )
    ping -n 10 127.0.0.1 >nul 2>&1
) else (
    echo [INFO] 未找到前端项目，仅启动后端服务
)

:: ─── 启动完成 ───────────────────────────────────────────
cls
call :print_banner
echo.
echo ============================================
echo         CampusPilot 已成功启动！
echo ============================================
echo.
echo   Web 管理界面: http://localhost:3000
echo   后端 API:     http://localhost:8000
echo   API 文档:     http://localhost:8000/docs
echo   健康检查:     http://localhost:8000/health
echo.
echo ============================================
echo   首次使用？请访问 Web 界面配置：
echo   1. 打开 http://localhost:3000
echo   2. 进入"设置"页面
echo   3. 配置学号、DeepSeek Key 等
echo ============================================
echo.
echo   提示：关闭此窗口不会停止服务
echo   如需停止，请关闭 CampusPilot-Backend 和
echo   CampusPilot-Frontend 的终端窗口
echo.

:: ─── 询问是否设置开机自启 ──────────────────────────────
echo.
set /p "SET_AUTOSTART=是否设置开机自启？(y/N): "
if /i "!SET_AUTOSTART!"=="y" (
    call :setup_autostart
)

goto :end

:: ============================================================
:: 子程序：检测 Python
:: ============================================================
:check_python
set PYTHON_CMD=
where python >nul 2>&1 && set PYTHON_CMD=python
if "%PYTHON_CMD%"=="" where py >nul 2>&1 && set PYTHON_CMD=py
if "%PYTHON_CMD%"=="" where python3 >nul 2>&1 && set PYTHON_CMD=python3

if "%PYTHON_CMD%"=="" (
    echo [ERROR] 未找到 Python！
    echo.
    echo 请安装 Python 3.11 或更高版本：
    echo   https://www.python.org/downloads/
    echo.
    echo 安装时请勾选 "Add Python to PATH"
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('%PYTHON_CMD% --version 2^>^&1') do set PYVER=%%v
echo [OK] Python 版本：%PYVER%
exit /b 0

:: ============================================================
:: 子程序：检测 Node.js
:: ============================================================
:check_nodejs
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] 未检测到 Node.js
    echo        前端界面将不可用，后端 API 可正常使用
    echo        如需前端界面，请安装 Node.js：
    echo        https://nodejs.org/
    exit /b 1
)
for /f "tokens=2 delims=v" %%v in ('node --version') do set NODE_VER=%%v
echo [OK] Node.js 版本：%NODE_VER%
exit /b 0

:: ============================================================
:: 子程序：设置开机自启（schtasks）
:: ============================================================
:setup_autostart
echo.
echo [INFO] 正在设置开机自启...
set "TASK_NAME=CampusPilot"
set "SCRIPT_PATH=%~dp0start.bat"

:: 检查是否已存在
schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if !errorlevel! equ 0 (
    echo [INFO] 开机自启任务已存在，正在更新...
    schtasks /change /tn "%TASK_NAME%" /tn "%TASK_NAME%" >nul 2>&1
) else (
    echo [INFO] 创建开机自启任务...
    schtasks /create /tn "%TASK_NAME%" /tr "'%SCRIPT_PATH%'" /sc onlogon /ru "%USERNAME%" /f >nul 2>&1
)

if !errorlevel! equ 0 (
    echo [OK] 开机自启设置成功！
    echo     每次登录 Windows 时将自动启动 CampusPilot
    echo.
    echo 如需取消开机自启，请运行：
    echo   schtasks /delete /tn "CampusPilot" /f
) else (
    echo [WARN] 开机自启设置失败
    echo       请以管理员身份运行本脚本后重试
)
echo.
pause
exit /b 0

:: ============================================================
:: 子程序：打印横幅
:: ============================================================
:print_banner
cls
echo.
echo   ╔══════════════════════════════════════╗
echo   ║         CampusPilot v2.0             ║
echo   ║   重庆邮电大学个人学业智能助理         ║
echo   ╚══════════════════════════════════════╝
echo.
goto :eof

:: ============================================================
:: 结束
:: ============================================================
:end
exit /b 0

:end_error
echo.
echo [ERROR] 启动失败，请检查上面的错误信息
pause
exit /b 1
