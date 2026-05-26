#!/bin/bash

# ============================================================
# CampusPilot SSH 密钥管理工具
# 功能：生成密钥、配置SSH、测试连接、部署公钥
# 用法：./setup-ssh.sh [选项]
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 默认配置
KEY_NAME="campuspilot_deploy"
KEY_DIR="$HOME/.ssh"
REMOTE_USER="root"
REMOTE_HOST=""
REMOTE_PORT=22

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# ============================================================
# 生成 SSH 密钥对
# ============================================================
generate_keypair() {
    log_step "生成 SSH 密钥对"

    PRIVATE_KEY="${KEY_DIR}/${KEY_NAME}"
    PUBLIC_KEY="${PRIVATE_KEY}.pub"

    if [ -f "$PRIVATE_KEY" ]; then
        log_warning "密钥已存在: $PRIVATE_KEY"
        read -p "是否重新生成？(y/N) " confirm
        
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            log_info "使用现有密钥"
            return
        fi
        
        # 备份旧密钥
        mv "$PRIVATE_KEY" "${PRIVATE_KEY}.bak.$(date +%s)"
        mv "$PUBLIC_KEY" "${PUBLIC_KEY}.bak.$(date +%s)"
    fi

    # 生成新密钥（RSA 4096位，无密码）
    ssh-keygen -t rsa -b 4096 \
        -f "$PRIVATE_KEY" \
        -N "" \
        -C "campus-pilot-deploy@$(hostname)"

    if [ $? -eq 0 ]; then
        chmod 600 "$PRIVATE_KEY"
        chmod 644 "$PUBLIC_KEY"
        
        log_success "密钥对生成成功！"
        log_info "私钥: $PRIVATE_KEY"
        log_info "公钥: $PUBLIC_KEY"
        echo ""
        echo "公钥内容（需要添加到服务器）："
        cat "$PUBLIC_KEY"
    else
        log_error "密钥生成失败"
        exit 1
    fi
}

# ============================================================
# 配置 SSH 客户端
# ============================================================
configure_ssh_client() {
    log_step "配置 SSH 客户端"

    SSH_CONFIG="$HOME/.ssh/config"

    if [ -z "$REMOTE_HOST" ]; then
        read -p "请输入服务器 IP 或域名: " REMOTE_HOST
    fi

    read -p "请输入 SSH 用户名 (默认: root): " input_user
    REMOTE_USER=${input_user:-root}

    read -p "请输入 SSH 端口 (默认: 22): " input_port
    REMOTE_PORT=${input_port:-22}

    # 添加或更新配置块
    CONFIG_BLOCK="
Host campuspilot
    HostName ${REMOTE_HOST}
    User ${REMOTE_USER}
    Port ${REMOTE_PORT}
    IdentityFile ${KEY_DIR}/${KEY_NAME}
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    ConnectTimeout 10
    ServerAliveInterval 60
    ServerAliveCountMax 3
"

    # 检查是否已存在该 Host 配置
    if grep -q "^Host campuspilot$" "$SSH_CONFIG" 2>/dev/null; then
        log_warning "已存在 campuspilot 的 SSH 配置，是否覆盖？(y/N)"
        read confirm
        
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            # 删除旧配置块
            sed -i '/^Host campuspilot$/,/^$/d' "$SSH_CONFIG"
            echo "$CONFIG_BLOCK" >> "$SSH_CONFIG"
            log_success "SSH 配置已更新"
        fi
    else
        echo "$CONFIG_BLOCK" >> "$SSH_CONFIG"
        log_success "SSH 配置已添加"
    fi

    chmod 600 "$SSH_CONFIG"
    
    echo ""
    log_info "SSH 配置完成！"
    log_info "现在可以使用以下命令连接："
    echo "  ssh campuspilot"
}

# ============================================================
# 部署公钥到服务器
# ============================================================
deploy_public_key() {
    log_step "部署公钥到服务器"

    PUBLIC_KEY="${KEY_DIR}/${KEY_NAME}.pub"

    if [ ! -f "$PUBLIC_KEY" ]; then
        log_error "公钥文件不存在，请先生成密钥"
        return 1
    fi

    if [ -z "$REMOTE_HOST" ]; then
        read -p "请输入服务器 IP 或域名: " REMOTE_HOST
    fi

    read -p "请输入 SSH 用户名 (默认: root): " input_user
    REMOTE_USER=${input_user:-root}

    read -p "请输入 SSH 端口 (默认: 22): " input_port
    REMOTE_PORT=${input_port:-22}

    log_info "正在部署公钥到 ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PORT}..."

    # 使用 ssh-copy-id 部署公钥
    if command -v ssh-copy-id &> /dev/null; then
        ssh-copy-id -i "$PUBLIC_KEY" -p $REMOTE_PORT "${REMOTE_USER}@${REMOTE_HOST}"
    else
        # 手动复制公钥
        PUB_KEY_CONTENT=$(cat "$PUBLIC_KEY")
        
        ssh -o StrictHostKeyChecking=no -p $REMOTE_PORT "${REMOTE_USER}@${REMOTE_HOST}" "
            mkdir -p ~/.ssh
            chmod 700 ~/.ssh
            echo '${PUB_KEY_CONTENT}' >> ~/.ssh/authorized_keys
            chmod 600 ~/.ssh/authorized_keys
            echo 'done'
        "
    fi

    if [ $? -eq 0 ]; then
        log_success "公钥部署成功！"
        
        # 测试连接
        log_info "测试 SSH 连接..."
        if ssh -i "${KEY_DIR}/${KEY_NAME}" -p $REMOTE_PORT "${REMOTE_USER}@${REMOTE_HOST}" "echo '连接成功'" > /dev/null 2>&1; then
            log_success "SSH 连接测试通过 ✓"
            
            # 更新 deploy.sh 中的配置
            update_deploy_config
        else
            log_error "SSH 连接失败，请检查配置"
        fi
    else
        log_error "公钥部署失败"
    fi
}

# ============================================================
# 更新 deploy.sh 配置
# ============================================================
update_deploy_config() {
    log_info "更新 deploy.sh 配置..."

    DEPLOY_SCRIPT="./deploy.sh"

    if [ -f "$DEPLOY_SCRIPT" ]; then
        sed -i "s/^REMOTE_HOST=\".*\"/REMOTE_HOST=\"$REMOTE_HOST\"/" "$DEPLOY_SCRIPT"
        sed -i "s/^REMOTE_USER=\".*\"/REMOTE_USER=\"$REMOTE_USER\"/" "$DEPLOY_SCRIPT"
        sed -i "s/^REMOTE_PORT=.*/REMOTE_PORT=$REMOTE_PORT/" "$DEPLOY_SCRIPT"
        sed -i "s|SSH_KEY=\".*\"|SSH_KEY=\"${KEY_DIR}/${KEY_NAME}\"|" "$DEPLOY_SCRIPT"
        
        log_success "deploy.sh 配置已更新"
    fi
}

# ============================================================
# 测试 SSH 连接
# ============================================================
test_connection() {
    log_step "测试 SSH 连接"

    PRIVATE_KEY="${KEY_DIR}/${KEY_NAME}"

    if [ ! -f "$PRIVATE_KEY" ]; then
        log_error "私钥文件不存在"
        return 1
    fi

    log_info "测试连接到 campuspilot..."

    if ssh -i "$PRIVATE_KEY" campuspilot "echo '✓ SSH 连接成功'; uname -a; df -h / | tail -1; free -h | head -2"; then
        log_success "连接测试完成"
    else
        log_error "连接失败"
        log_info "排查步骤："
        log_info "  1. 检查服务器地址、端口、用户名是否正确"
        log_info "  2. 确认公钥已添加到服务器的 ~/.ssh/authorized_keys"
        log_info "  3. 检查私钥权限是否为 600"
        log_info "  4. 确认服务器 SSH 服务运行正常"
        return 1
    fi
}

# ============================================================
# 显示当前配置
# ============================================================
show_current_config() {
    log_step "当前 SSH 配置"

    PRIVATE_KEY="${KEY_DIR}/${KEY_NAME}"

    echo "=========================================="
    echo "  密钥信息"
    echo "=========================================="
    
    if [ -f "$PRIVATE_KEY" ]; then
        echo "私钥路径: $PRIVATE_KEY"
        ls -lh "$PRIVATE_KEY"
        echo ""
        echo "公钥路径: ${PRIVATE_KEY}.pub"
        cat "${PRIVATE_KEY}.pub"
    else
        log_warning "密钥不存在"
    fi

    echo ""
    echo "=========================================="
    echo "  SSH Config (campuspilot)"
    echo "=========================================="
    
    if grep -A 10 "^Host campuspilot$" "$HOME/.ssh/config" 2>/dev/null; then
        :
    else
        log_warning "未找到 campuspilot 的 SSH 配置"
    fi

    echo ""
    echo "=========================================="
    echo "  deploy.sh 配置"
    echo "=========================================="
    
    if [ -f "./deploy.sh" ]; then
        grep -E "^(REMOTE_HOST|REMOTE_USER|REMOTE_PORT|SSH_KEY)=" ./deploy.sh | head -4
    else
        log_warning "deploy.sh 不存在"
    fi
}

# ============================================================
# 主流程
# ============================================================
log_step() {
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

main() {
    echo "=========================================="
    echo "  CampusPilot SSH 密钥管理工具"
    echo "=========================================="
    echo ""

    case "${1:-help}" in
        --generate)
            generate_keypair
            ;;
        --config)
            configure_ssh_client
            ;;
        --deploy-key)
            deploy_public_key
            ;;
        --test)
            test_connection
            ;;
        --show)
            show_current_config
            ;;
        --all)
            generate_keypair
            configure_ssh_client
            deploy_public_key
            test_connection
            ;;
        --help|*)
            echo "用法: $0 {--generate|--config|--deploy-key|--test|--show|--all|--help}"
            echo ""
            echo "选项说明:"
            echo "  --generate   生成 SSH 密钥对"
            echo "  --config     配置 SSH 客户端（别名）"
            echo "  --deploy-key 部署公钥到远程服务器"
            echo "  --test       测试 SSH 连接"
            echo "  --show       显示当前配置信息"
            echo "  --all        执行所有设置步骤"
            echo "  --help       显示帮助信息"
            echo ""
            echo "示例流程:"
            echo "  1. ./setup-ssh.sh --generate      # 生成密钥"
            echo "  2. ./setup-ssh.sh --deploy-key     # 上传公钥到服务器"
            echo "  3. ./setup-ssh.sh --test           # 测试连接"
            echo "  4. ./deploy.sh --deploy             # 开始部署"
            ;;
    esac
}

main "$@"
