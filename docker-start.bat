@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

title CampusPilot-Docker

:: ============================================================
:: CampusPilot Docker 一键启动脚本
:: 使用 Docker Compose 启动完整服务
:: 前置条件：已安装 Docker Desktop
:: ============================================================

echo.
echo   ╔══════════════════════════════════════╗
echo   ║    CampusPilot Docker 快速启动       ║
echo   ║   重庆邮电大学个人学业智能助理         ║
echo   ╚══════════════════════════════════════╝
echo.

:: ─── 检测 Docker ──────────────────────────────────────────
where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 Docker！
    echo.
    echo 请先安装 Docker Desktop：
    echo   https://www.docker.com/products/docker-desktop/
    echo.
    pause
    exit /b 1
)

docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker 服务未运行！
    echo 请启动 Docker Desktop 后重试。
    pause
    exit /b 1
)
echo [OK] Docker 已就绪

:: ─── 确保 .env 文件存在 ────────────────────────────────────
if not exist ".env" (
    echo [INFO] 创建默认 .env 文件...
    (
        echo FERNET_KEY=
        echo TZ=Asia/Shanghai
        echo DATABASE_URL=sqlite+aiosqlite:///data/campus.db
        echo FRONTEND_URL=http://localhost:3000
    ) > .env
)

:: ─── 自动生成 FERNET_KEY（如果为空）────────────────────────
for /f "tokens=2 delims==" %%a in ('findstr "^FERNET_KEY=" .env') do set "FERNET_VAL=%%a"
if "!FERNET_VAL!"=="" (
    echo [INFO] 首次运行，正在自动生成加密密钥...
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>nul > .tmp_key
    if !errorlevel! equ 0 (
        set /p NEW_KEY=<.tmp_key
        del .tmp_key
        powershell -Command "(Get-Content .env) -replace '^FERNET_KEY=$', 'FERNET_KEY=!NEW_KEY!' | Set-Content .env"
        echo [OK] 加密密钥已生成
    ) else (
        if exist .tmp_key del .tmp_key
        echo [WARN] Python 未安装，无法生成密钥，将使用默认值
    )
)

:: ─── 确保 data 目录存在 ───────────────────────────────────
if not exist "data" mkdir data

:: ─── 构建并启动 ──────────────────────────────────────────
echo.
echo [INFO] 正在构建 Docker 镜像并启动服务...
echo.
docker compose up -d --build

if !errorlevel! neq 0 (
    echo [ERROR] Docker 启动失败
    pause
    exit /b 1
)

:: ─── 等待服务启动 ──────────────────────────────────────
echo [WAIT] 等待服务启动...
ping -n 20 127.0.0.1 >nul 2>&1

:: ─── 健康检查 ──────────────────────────────────────────
echo [INFO] 检查服务状态...
for /l %%i in (1,1,6) do (
    curl -s -o nul -w "%%{http_code}" http://localhost:8000/health > .health_check.tmp 2>nul
    if exist .health_check.tmp (
        set /p HTTP_STATUS=<.health_check.tmp
        del .health_check.tmp
        if "!HTTP_STATUS!"=="200" (
            echo [OK] 服务已就绪
            goto :success
        )
    )
    ping -n 5 127.0.0.1 >nul 2>&1
)

echo [WARN] 健康检查超时，但服务可能仍在启动中...
echo       请稍后访问 http://localhost:3000 检查

:success
echo.
echo ============================================
echo     CampusPilot Docker 版已成功启动！
echo ============================================
echo.
echo   Web 界面:  http://localhost:3000
echo   后端 API:  http://localhost:8000
echo   API 文档:  http://localhost:8000/docs
echo.
echo   ── 管理命令 ──────────────────────────
echo   查看日志：  docker compose logs -f
echo   停止服务：  docker compose down
echo   重启服务：  docker compose restart
echo.
echo   ── 首次使用 ──────────────────────────
echo   打开 http://localhost:3000
echo   进入"设置"页面配置各项服务
echo.
pause
