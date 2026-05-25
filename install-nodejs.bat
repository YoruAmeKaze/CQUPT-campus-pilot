@echo off
chcp 65001 >nul 2>&1
echo.
echo ============================================
echo   Node.js 快速安装工具
echo ============================================
echo.
echo 检测 Node.js 安装状态...
echo.

node --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%v in ('node --version') do set NODE_VER=%%v
    echo [OK] Node.js 已安装: %NODE_VER%
    goto :check_npm
)

echo [INFO] 未检测到 Node.js
echo.
echo 正在通过 winget 安装 Node.js LTS 版本...
echo.

:: 尝试使用 winget 安装
winget install OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements

if %errorlevel% neq 0 (
    echo.
    echo [WARNING] winget 安装失败
    echo.
    echo 请手动安装 Node.js:
    echo.
    echo   下载地址: https://nodejs.org/
    echo   推荐版本: LTS (长期支持版)
    echo   ⚠️  安装时务必勾选 "Add to PATH"!
    echo.
    start https://nodejs.org/en/download
    pause
    exit /b 1
)

echo.
echo [SUCCESS] Node.js 安装完成！
echo [IMPORTANT] 请关闭此窗口并重新打开 CMD 以生效
pause
exit /b 0

:check_npm
npm --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%v in ('npm --version') do set NPM_VER=%%v
    echo [OK] npm 已安装: %NPM_VER%
) else (
    echo [WARNING] npm 未找到
)

echo.
echo ============================================
echo       环境检查完成！
echo ============================================
echo.
echo Node.js: %NODE_VER%
echo npm: %NPM_VER%
echo.
echo 现在可以运行前端了:
echo   cd frontend
echo   npm install
echo   npm run dev
echo.
pause
