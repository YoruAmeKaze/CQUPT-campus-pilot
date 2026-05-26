@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: ============================================================
:: CampusPilot Windows 部署工具 v2.1 (修复版)
:: 解决 Bash 兼容性问题
:: ============================================================

title CampusPilot Deploy Tool

:main_menu
cls
echo.
echo ============================================
echo    CampusPilot Auto Deployment Tool v2.1
echo ============================================
echo.
echo   [1] Run Tests
echo   [2] Setup SSH Keys (First Time)
echo   [3] Deploy to Server
echo   [4] Check Server Status
echo   [5] View Logs
echo   [6] Rollback Version
echo   [7] Start Local Dev Server
echo   [0] Exit
echo.
set /p "choice=Enter option (0-7): "

if "%choice%"=="1" goto run_tests
if "%choice%"=="2" goto ssh_setup
if "%choice%"=="3" goto do_deploy
if "%choice%"=="4" goto show_status
if "%choice%"=="5" goto view_logs
if "%choice%"=="6" goto do_rollback
if "%choice%"=="7" goto start_dev
if "%choice%"=="0" goto end_exit
goto main_menu

:: ============================================================
:: 1. 运行测试 (使用 Python 直接运行)
:: ============================================================
:run_tests
echo.
echo [INFO] Running test suite...
echo.

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.11+
    pause
    goto main_menu
)

:: 检查虚拟环境
if not exist "..\venv" (
    echo [INFO] Creating virtual environment...
    python -m venv ..\venv
)

:: 安装测试依赖并运行
call ..\venv\Scripts\activate.bat >nul 2>&1
pip install -q pytest pytest-asyncio httpx 2>nul

echo.
echo [1/3] Running backend tests...
cd ..
python -m pytest tests/ -v --tb=short --cov=app --cov-report=term-missing
set TEST_RESULT=%errorlevel%
cd scripts

echo.
if %TEST_RESULT% equ 0 (
    echo [SUCCESS] All tests passed!
) else (
    echo [WARNING] Some tests failed. Check output above.
)

pause
goto main_menu

:: ============================================================
:: 2. SSH 设置向导 (纯 Windows 实现)
:: ============================================================
:ssh_setup
cls
echo.
echo ============================================
echo       SSH Key Setup Wizard
echo ============================================
echo.
echo This wizard will help you:
echo   1. Generate SSH key pair
echo   2. Configure connection settings
echo   3. Deploy public key to server
echo.
pause

:: Step 1: Generate SSH keys
echo.
echo [Step 1/3] Generating SSH key pair...
echo.

set "SSH_KEY_PATH=%USERPROFILE%\.ssh\campuspilot_deploy"

if exist "%SSH_KEY_PATH%" (
    echo [INFO] Existing key found at: %SSH_KEY_PATH%
    set /p "REGEN=Regenerate key? (y/N): "
    if /i not "%REGEN%"=="y" (
        echo [INFO] Using existing key.
        goto ssh_step2
    )
    move "%SSH_KEY_PATH%" "%SSH_KEY_PATH%.bak.%date:~0,4%%date:~5,2%%date:~8,2%%time:~0,2%%time:~3,2%"
)

:: 使用 ssh-keygen 生成密钥
where ssh-keygen >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] ssh-keygen not found. Please install Git for Windows or OpenSSH.
    echo         Download: https://git-for-windows.github.io/
    pause
    goto main_menu
)

ssh-keygen -t rsa -b 4096 -f "%SSH_KEY_PATH%" -N "" -C "campus-pilot-deploy@%COMPUTERNAME%"
if %errorlevel% equ 0 (
    echo [SUCCESS] SSH key pair generated!
    echo          Private: %SSH_KEY_PATH%
    echo          Public:  %SSH_KEY_PATH%.pub
) else (
    echo [ERROR] Failed to generate SSH key.
    pause
    goto main_menu
)

:: 显示公钥内容
echo.
echo ===== PUBLIC KEY (copy this) =====
type "%SSH_KEY_PATH%.pub"
echo ===================================
echo.
pause

:ssh_step2
:: Step 2: 配置连接信息
echo.
echo [Step 2/3] Configure server connection...
echo.

:: 创建或更新配置文件
if not exist "deploy.config" (
    echo # CampusPilot Deployment Config > deploy.config
    echo REMOTE_HOST= >> deploy.config
    echo REMOTE_USER=root >> deploy.config
    echo REMOTE_PORT=22 >> deploy.config
)

echo Current configuration:
if exist "deploy.config" (
    type deploy.config
) else (
    echo [WARNING] No config file found
)

echo.
set /p "NEW_HOST=Server IP or domain (required): "
if not "%NEW_HOST%"=="" (
    echo REMOTE_HOST=%NEW_HOST%> deploy.config
)

set /p "NEW_USER=SSH username (default: root): "
if not "%NEW_USER%"=="" (
    echo REMOTE_USER=%NEW_USER%>> deploy.config
) else (
    echo REMOTE_USER=root>> deploy.config
)

set /p "NEW_PORT=SSH port (default: 22): "
if not "%NEW_PORT%"=="" (
    echo REMOTE_PORT=%NEW_PORT%>> deploy.config
) else (
    echo REMOTE_PORT=22>> deploy.config
)

echo [SUCCESS] Configuration saved to deploy.config
echo.

:ssh_step3
:: Step 3: 部署公钥到服务器
echo [Step 3/3] Deploying public key to server...
echo.

:: 读取配置
for /f "tokens=2 delims=" %%a in ('findstr "REMOTE_HOST" deploy.config') do set REMOTE_HOST=%%a
for /f "tokens=2 delims=" %%a in ('findstr "REMOTE_USER" deploy.config') do set REMOTE_USER=%%a
for /f "tokens=2 delims=" %%a in ('findstr "REMOTE_PORT" deploy.config') do set REMOTE_PORT=%%a

:: 去除可能的空格
set REMOTE_HOST=%REMOTE_HOST: =%
set REMOTE_USER=%REMOTE_USER: =%
set REMOTE_PORT=%REMOTE_PORT: =%

echo Target: %REMOTE_USER%@%REMOTE_HOST%:%REMOTE_PORT%
echo.

:: 尝试使用 ssh-copy-id 或手动方式
where ssh-copy-id >nul 2>&1
if %errorlevel% equ 0 (
    echo Using ssh-copy-id...
    ssh-copy-id -i "%SSH_KEY_PATH%.pub" -p %REMOTE_PORT% "%REMOTE_USER%@%REMOTE_HOST%"
) else (
    echo [INFO] ssh-copy-id not available. Manual deployment:
    echo.
    echo Please run this command manually in Git Bash:
    echo.
    echo   ssh-copy-id -i "%SSH_KEY_PATH%.pub" -p %REMOTE_PORT% %REMOTE_USER%@%REMOTE_HOST%
    echo.
    echo Or copy the public key content above to server's ~/.ssh/authorized_keys
    echo.
    set /p "MANUAL_DONE=Have you deployed the key? (y/N): "
    if /i not "%MANUAL_DONE%"=="y" (
        echo [ABORTED] Please complete manual deployment first.
        pause
        goto main_menu
    )
)

:: 测试连接
echo.
echo Testing SSH connection...
ssh -i "%SSH_KEY_PATH%" -p %REMOTE_PORT% -o StrictHostKeyChecking=no -o ConnectTimeout=10 "%REMOTE_USER%@%REMOTE_HOST%" "echo CONNECTION_OK"
if %errorlevel% equ 0 (
    echo.
    echo [SUCCESS] SSH connection successful!
    echo.
    echo Next steps:
    echo   1. Edit scripts/deploy.sh and update these values:
    echo      REMOTE_HOST="%REMOTE_HOST%"
    echo      REMOTE_USER="%REMOTE_USER%"
    echo      REMOTE_PORT=%REMOTE_PORT%
    echo      SSH_KEY="%SSH_KEY_PATH%"
    echo.
    echo   2. Run: deploy.bat
) else (
    echo [ERROR] Connection failed. Please check:
    echo   1. Server address and port are correct
    echo   2. Public key is added to server
    echo   3. SSH service is running on server
    echo   4. Firewall allows port %REMOTE_PORT%
)

pause
goto main_menu

:: ============================================================
:: 3. 部署到服务器
:: ============================================================
:do_deploy
echo.
echo [INFO] Starting deployment...
echo.

:: 检查配置
if not exist "deploy.config" (
    echo [ERROR] No deploy.config found. Run option [2] first.
    pause
    goto main_menu
)

:: 读取配置
for /f "tokens=2 delims=" %%a in ('findstr "REMOTE_HOST" deploy.config') do set REMOTE_HOST=%%a
for /f "tokens=2 delims=" %%a in ('findstr "REMOTE_USER" deploy.config') do set REMOTE_USER=%%a
for /f "tokens=2 delims=" %%a in ('findstr "REMOTE_PORT" deploy.config') do set REMOTE_PORT=%%a

set REMOTE_HOST=%REMOTE_HOST: =%
set REMOTE_USER=%REMOTE_USER: =%
set REMOTE_PORT=%REMOTE_PORT: =%

echo Target server: %REMOTE_USER%@%REMOTE_HOST%:%REMOTE_PORT%
echo.
set /p "CONFIRM=Start deployment? (Y/n): "
if /i "%CONFIRM%"=="n" goto main_menu

echo.
echo [1/5] Checking SSH connection...

:: 简单的 SSH 连接测试
ssh -o BatchMode=yes -o ConnectTimeout=5 "%REMOTE_USER%@%REMOTE_HOST%" "echo OK" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Cannot connect to server. Check your SSH configuration.
    pause
    goto main_menu
)
echo [OK] Connection established.

echo [2/5] Uploading code via rsync...

:: 检查 rsync
where rsync >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] rsync not found, using scp instead...
    
    :: 创建远程目录
    ssh "%REMOTE_USER%@%REMOTE_HOST%" "mkdir -p /opt/campus-pilot/{data,config,alembic/versions}" >nul 2>&1
    
    :: 上传文件（排除不需要的）
    scp -r -P %REMOTE_PORT% ^
        --exclude="node_modules" ^
        --exclude=".git" ^
        --exclude="venv" ^
        --exclude="__pycache__" ^
        --exclude="*.pyc" ^
        --exclude=".env" ^
        --exclude="data/*.db" ^
        "*" "%REMOTE_USER%@%REMOTE_HOST%:/opt/campus-pilot/"
) else (
    rsync -avz --progress ^
        -e "ssh -p %REMOTE_PORT%" ^
        --exclude='node_modules' ^
        --exclude='.git' ^
        --exclude='venv' ^
        --exclude='__pycache__' ^
        --exclude='*.pyc' ^
        --exclude='.env' ^
        --exclude='data/*.db' ^
        "../" "%REMOTE_USER%@%REMOTE_HOST%:/opt/campus-pilot/"
)

if %errorlevel% equ 0 (
    echo [OK] Code uploaded.
) else (
    echo [ERROR] Upload failed.
    pause
    goto main_menu
)

echo [3/5] Uploading .env file...
if exist "..\.env" (
    scp -P %REMOTE_PORT% "..\.env" "%REMOTE_USER%@%REMOTE_HOST%:/opt/campus-pilot/.env"
    ssh -p %REMOTE_PORT% "%REMOTE_USER%@%REMOTE_HOST%" "chmod 600 /opt/campus-pilot/.env"
    echo [OK] .env uploaded with permissions 600.
) else (
    echo [SKIP] No .env file found.
)

echo [4/5] Building and starting services on remote server...
ssh -p %REMOTE_PORT% "%REMOTE_USER%@%REMOTE_HOST%" "cd /opt/campus-pilot && docker compose up -d --build"
if %errorlevel% equ 0 (
    echo [OK] Services started.
) else (
    echo [ERROR] Failed to start services.
    pause
    goto main_menu
)

echo [5/5] Health check...
timeout /t 15 /nobreak >nul

:: 健康检查
for /l %%i in (1,1,12) do (
    ssh -p %REMOTE_PORT% "%REMOTE_USER%@%REMOTE_HOST%" "curl -s -o /dev/null -w '%%{http_code}' http://localhost:8000/health" >temp_status.txt 2>nul
    set /p HTTP_STATUS=<temp_status.txt
    del temp_status.txt 2>nul
    
    if "!HTTP_STATUS!"=="200" (
        echo [SUCCESS] Health check passed! (HTTP 200)
        goto deploy_success
    )
    echo [WAIT] Waiting for service... (attempt %%i/12)
    timeout /t 5 /nobreak >nul
)

echo [WARNING] Health check timed out. Service may need more time.

:deploy_success
echo.
echo ============================================
echo       DEPLOYMENT COMPLETED
echo ============================================
echo.
echo Access URLs:
echo   Backend API: http://%REMOTE_HOST%:8000/docs
echo   Frontend:    http://%REMOTE_HOST%
echo   Health:      http://%REMOTE_HOST%:8000/health
echo.
echo Management commands:
echo   deploy.bat status   - Check status
echo   deploy.bat logs     - View logs
echo   deploy.bat rollback - Rollback version
echo.
pause
goto main_menu

:: ============================================================
:: 4. 查看状态
:: ============================================================
:show_status
echo.
echo [INFO] Fetching server status...
echo.

if not exist "deploy.config" (
    echo [ERROR] No deploy.config found. Run option [2] first.
    pause
    goto main_menu
)

for /f "tokens=2 delims=" %%a in ('findstr "REMOTE_HOST" deploy.config') do set REMOTE_HOST=%%a
for /f "tokens=2 delims=" %%a in ('findstr "REMOTE_USER" deploy.config') do set REMOTE_USER=%%a
for /f "tokens=2 delims=" %%a in ('findstr "REMOTE_PORT" deploy.config') do set REMOTE_PORT=%%a

set REMOTE_HOST=%REMOTE_HOST: =%
set REMOTE_USER=%REMOTE_USER: =%
set REMOTE_PORT=%REMOTE_PORT: =%

ssh -p %REMOTE_PORT% "%REMOTE_USER%@%REMOTE_HOST%" "cd /opt/campus-pilot && docker compose ps && echo. && docker compose logs --tail=20"
pause
goto main_menu

:: ============================================================
:: 5. 查看日志
:: ============================================================
:view_logs
echo.
echo [INFO] Streaming live logs (Ctrl+C to stop)...
echo.

if not exist "deploy.config" (
    echo [ERROR] No deploy.config found.
    pause
    goto main_menu
)

for /f "tokens=2 delims=" %%a in ('findstr "REMOTE_HOST" deploy.config') do set REMOTE_HOST=%%a
for /f "tokens=2 delims=" %%a in ('findstr "REMOTE_USER" deploy.config') do set REMOTE_USER=%%a
for /f "tokens=2 delims=" %%a in ('findstr "REMOTE_PORT" deploy.config') do set REMOTE_PORT=%%a

set REMOTE_HOST=%REMOTE_HOST: =%
set REMOTE_USER=%REMOTE_USER: =%
set REMOTE_PORT=%REMOTE_PORT: =%

ssh -t -p %REMOTE_PORT% "%REMOTE_USER%@%REMOTE_HOST%" "cd /opt/campus-pilot && docker compose logs -f --tail=100"
goto main_menu

:: ============================================================
:: 6. 回滚
:: ============================================================
:do_rollback
echo.
echo [WARNING] This will rollback to previous version!
echo.
set /p "CONFIRM_ROLLBACK=Are you sure? (y/N): "
if /i not "%CONFIRM_ROLLBACK%"=="y" goto main_menu

if not exist "deploy.config" (
    echo [ERROR] No deploy.config found.
    pause
    goto main_menu
)

for /f "tokens=2 delims=" %%a in ('findstr "REMOTE_HOST" deploy.config') do set REMOTE_HOST=%%a
for /f "tokens=2 delims=" %%a in ('findstr "REMOTE_USER" deploy.config') do set REMOTE_USER=%%a
for /f "tokens=2 delims=" %%a in ('findstr "REMOTE_PORT" deploy.config') do set REMOTE_PORT=%%a

set REMOTE_HOST=%REMOTE_HOST: =%
set REMOTE_USER=%REMOTE_USER: =%
set REMOTE_PORT=%REMOTE_PORT: =%

echo Rolling back on %REMOTE_USER%@%REMOTE_HOST%...
ssh -p %REMOTE_PORT% "%REMOTE_USER%@%REMOTE_HOST%" "cd /opt/campus-pilot && LATEST_BACKUP=\$(ls -td backups/*/ 2>/dev/null | head -1) && if [ -z \"\$LATEST_BACKUP\" ]; then echo ERROR: No backups available; exit 1; fi && docker compose down && rm -rf data/ && cp -r \${LATEST_BACKUP}data/ data/ && cp \${LATEST_BACKUP}.env .env 2>/dev/null || true && docker compose up -d && echo ROLLBACK_COMPLETE"

echo.
echo [INFO] Rollback initiated. Use option [4] to verify status.
pause
goto main_menu

:: ============================================================
:: 7. 启动本地开发服务器
:: ============================================================
:start_dev
echo.
echo [INFO] Starting local development environment...
echo.

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not installed
    pause
    goto main_menu
)

:: 创建虚拟环境
if not exist "..\venv" (
    echo Creating virtual environment...
    python -m venv ..\venv
)

:: 安装依赖
call ..\venv\Scripts\activate.bat >nul 2>&1
pip install -q -r ..\requirements.txt >nul 2>&1
echo [OK] Backend dependencies ready.

:: 启动后端
echo Starting backend on http://localhost:8000 ...
start "CampusPilot-Backend" cmd /k "cd /d %~dp0.. && call venv\Scripts\activate.bat && python -m uvicorn app.main:app --reload --port 8000"

:: 等待后端启动
timeout /t 5 /nobreak >nul

:: 启动前端
if exist "..\frontend\node_modules" (
    echo Starting frontend on http://localhost:3000 ...
    start "CampusPilot-Frontend" cmd /k "cd /d %~dp0..\frontend && npm run dev"
) else if exist "..\frontend\package.json" (
    echo Installing frontend dependencies and starting...
    start "CampusPilot-Frontend" cmd /k "cd /d %~dp0..\frontend && npm install && npm run dev"
) else (
    echo [INFO] Frontend not found. Backend only mode.
)

echo.
echo ============================================
echo     Development Environment Started
echo ============================================
echo     Backend:  http://localhost:8000
echo     Docs:     http://localhost:8000/docs
echo     Frontend: http://localhost:3000
echo ============================================
echo.
pause
goto main_menu

:: ============================================================
:: 退出
:: ============================================================
:end_exit
echo.
echo Thank you for using CampusPilot!
timeout /t 2 >nul
exit /b 0
