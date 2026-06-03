#!/bin/bash
set -e

# 如果 .env 不存在（首次运行），自动创建
if [ ! -f ".env" ]; then
    echo "[entrypoint] 首次运行，自动生成 .env 文件..."
    FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    cat > .env << EOF
FERNET_KEY=${FERNET_KEY}
TZ=Asia/Shanghai
DATABASE_URL=sqlite+aiosqlite:///data/campus.db
FRONTEND_URL=http://localhost:3000
EOF
    echo "[entrypoint] .env 已创建，FERNET_KEY 已生成"
fi

exec "$@"
