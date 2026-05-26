#!/bin/bash
# ============================================================
# CampusPilot 一键启动脚本 (Linux/Mac)
# 自动检测环境、安装依赖、启动前后端服务
# ============================================================

set -e

print_banner() {
    clear 2>/dev/null || true
    echo ""
    echo "  ╔══════════════════════════════════════╗"
    echo "  ║         CampusPilot v2.0             ║"
    echo "  ║   重庆邮电大学个人学业智能助理        ║"
    echo "  ╚══════════════════════════════════════╝"
    echo ""
}

# ─── 检测 Python ──────────────────────────────────────────
check_python() {
    PYTHON_CMD=""
    if command -v python3 &>/dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &>/dev/null; then
        PYTHON_CMD="python"
    else
        echo "[ERROR] 未找到 Python！"
        echo "请安装 Python 3.11+：https://www.python.org/downloads/"
        exit 1
    fi
    
    PYVER=$($PYTHON_CMD --version 2>&1)
    echo "[OK] Python 版本：$PYVER"
}

# ─── 检测 Node.js ──────────────────────────────────────
check_nodejs() {
    if command -v node &>/dev/null; then
        NODE_VER=$(node --version)
        echo "[OK] Node.js 版本：$NODE_VER"
    else
        echo "[WARN] 未检测到 Node.js，前端界面不可用"
        echo "      如需前端界面，请安装 Node.js：https://nodejs.org/"
    fi
}

# ─── 自动生成 FERNET_KEY ────────────────────────────────
ensure_fernet_key() {
    if [ ! -f ".env" ]; then
        echo "[INFO] 创建默认 .env 文件..."
        cat > .env << 'EOF'
FERNET_KEY=
TZ=Asia/Shanghai
DATABASE_URL=sqlite+aiosqlite:///data/campus.db
FRONTEND_URL=http://localhost:3000
EOF
    fi
    
    # 检查 FERNET_KEY 是否为空
    if grep -q "^FERNET_KEY=$" .env 2>/dev/null; then
        echo "[INFO] 首次运行，正在自动生成加密密钥..."
        NEW_KEY=$($PYTHON_CMD -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null)
        if [ -n "$NEW_KEY" ]; then
            if [[ "$OSTYPE" == "darwin"* ]]; then
                sed -i '' "s/^FERNET_KEY=$/FERNET_KEY=$NEW_KEY/" .env
            else
                sed -i "s/^FERNET_KEY=$/FERNET_KEY=$NEW_KEY/" .env
            fi
            echo "[OK] 加密密钥已生成"
        fi
    fi
}

# ─── 主流程 ──────────────────────────────────────────────
print_banner
check_python
check_nodejs
ensure_fernet_key

# 创建虚拟环境
if [ ! -d "venv" ]; then
    echo "[INFO] 正在创建 Python 虚拟环境..."
    $PYTHON_CMD -m venv venv
    echo "[OK] 虚拟环境已创建"
fi

# 安装后端依赖
echo "[INFO] 正在安装后端依赖..."
source venv/bin/activate
pip install -q -r requirements.txt
echo "[OK] 后端依赖安装完成"

# 安装 Playwright Chromium
echo "[INFO] 检查 Playwright 浏览器..."
$PYTHON_CMD -c "from playwright.sync_api import sync_playwright; sync_playwright().__enter__()" 2>/dev/null || {
    echo "[INFO] 安装 Playwright Chromium 浏览器..."
    $PYTHON_CMD -m playwright install chromium
}

# 启动后端
echo ""
echo "[1/2] 启动后端 API 服务..."
echo "       http://localhost:8000"
echo "       http://localhost:8000/docs"
echo ""

cd "$(dirname "$0")"
$PYTHON_CMD -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "[OK] 后端已启动 (PID: $BACKEND_PID)"

# 等待后端启动
sleep 5

# 启动前端
if [ -f "frontend/package.json" ]; then
    echo ""
    echo "[2/2] 启动前端服务..."
    cd frontend
    if [ ! -d "node_modules" ]; then
        echo "[INFO] 安装前端依赖..."
        npm install
    fi
    npm run dev &
    FRONTEND_PID=$!
    echo "[OK] 前端已启动 (PID: $FRONTEND_PID)"
    cd ..
fi

# ─── 完成 ──────────────────────────────────────────────
sleep 3
print_banner
echo ""
echo "============================================"
echo "         CampusPilot 已成功启动！"
echo "============================================"
echo ""
echo "  Web 管理界面: http://localhost:3000"
echo "  后端 API:     http://localhost:8000"
echo "  API 文档:     http://localhost:8000/docs"
echo "  健康检查:     http://localhost:8000/health"
echo ""
echo "============================================"
echo "  首次使用？请访问 Web 界面配置："
echo "  1. 打开 http://localhost:3000"
echo "  2. 进入"设置"页面"
echo "  3. 配置学号、DeepSeek Key 等"
echo "============================================"
echo ""
echo "按下 Ctrl+C 停止所有服务"

# 等待子进程
wait
