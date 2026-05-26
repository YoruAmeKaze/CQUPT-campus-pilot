@echo off
chcp 65001 >nul 2>&1

echo ============================================
echo   Node.js 安装辅助脚本
echo ============================================
echo.
echo 本脚本将帮助你在 Windows 上安装 Node.js。
echo.
echo 步骤 1：访问 https://nodejs.org/ 下载 LTS 版本
echo 步骤 2：运行下载的安装程序
echo 步骤 3：安装时勾选 "Add to PATH"
echo.
echo 安装完成后，关闭并重新打开终端，运行以下命令验证：
echo   node --version
echo   npm --version
echo.
echo 或者你也可以使用 winget 安装：
echo   winget install OpenJS.NodeJS.LTS
echo.

where node >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=2 delims=" %%v in ('node --version') do set NODE_VER=%%v
    echo [OK] Node.js 已安装：%NODE_VER%
) else (
    echo [!] Node.js 未安装，请按上述步骤安装。
)

pause
