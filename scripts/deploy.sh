#!/bin/bash

# ============================================================
# CampusPilot 虚拟机自动部署脚本
# 功能：自动上传代码、构建镜像、部署服务到远程服务器
# 用法：./deploy.sh [选项]
#   选项：
#     --deploy       完整部署（默认）
#     --update       仅更新代码并重启
#     --rollback     回滚到上一版本
#     --status       查看部署状态
#     --logs         查看日志
#     --stop         停止服务
#     --clean        清理旧版本和缓存
# ============================================================

set -e

# ============================================================
# 配置区域 - 请根据实际情况修改
# ============================================================

# 远程服务器配置
REMOTE_HOST="your_server_ip"           # 服务器 IP 或域名
REMOTE_USER="root"                      # SSH 用户名
REMOTE_PORT=22                          # SSH 端口
REMOTE_DIR="/opt/campus-pilot"          # 远程部署目录
SSH_KEY="$HOME/.ssh/id_rsa"            # SSH 私钥路径

# 部署配置
DEPLOY_MODE="server"                    # 部署模式: laptop | server
BACKUP_COUNT=3                          # 保留的备份版本数
HEALTH_CHECK_TIMEOUT=60                 # 健康检查超时时间（秒）
ROLLBACK_ON_FAILURE=true               # 部署失败时是否自动回滚

# Docker 配置
DOCKER_REGISTRY=""                      # Docker 镜像仓库（可选，留空则本地构建）
IMAGE_PREFIX="campuspilot"              # 镜像名称前缀

# ============================================================
# 颜色定义
# ============================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_step() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# SSH 命令封装
ssh_exec() {
    ssh -i "$SSH_KEY" -p $REMOTE_PORT -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$REMOTE_USER@$REMOTE_HOST" "$@"
}

scp_upload() {
    scp -i "$SSH_KEY" -P $REMOTE_PORT -o StrictHostKeyChecking=no "$@" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/"
}

# ============================================================
# 前置检查
# ============================================================
check_prerequisites() {
    log_step "前置检查"

    # 检查 SSH 密钥
    if [ ! -f "$SSH_KEY" ]; then
        log_error "SSH 密钥不存在: $SSH_KEY"
        log_info "请生成密钥: ssh-keygen -t rsa -b 4096"
        exit 1
    fi
    log_success "SSH 密钥已找到: $SSH_KEY"

    # 检查 SSH 连接
    if ! ssh_exec "echo 'SSH连接成功'" > /dev/null 2>&1; then
        log_error "无法连接到服务器 $REMOTE_USER@$REMOTE_HOST:$REMOTE_PORT"
        log_info "请检查："
        log_info "  1. 服务器地址和端口是否正确"
        log_info "  2. SSH 公钥是否已添加到服务器 ~/.ssh/authorized_keys"
        log_info "  3. 服务器防火墙是否开放 SSH 端口"
        exit 1
    fi
    log_success "SSH 连接正常"

    # 检查必要工具
    local required_tools=("rsync" "docker" "git")
    for tool in "${required_tools[@]}"; do
        if command -v $tool &> /dev/null; then
            log_success "$tool 已安装"
        else
            log_warning "$tool 未安装（可能影响功能）"
        fi
    done

    # 检查 .env 文件
    if [ ! -f ".env" ]; then
        log_warning ".env 文件不存在，将使用默认配置"
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log_info "已从 .env.example 创建 .env 文件"
            log_warning "请编辑 .env 填入实际配置！"
        fi
    else
        log_success ".env 文件已存在"
    fi
}

# ============================================================
# 备份当前版本
# ============================================================
backup_current_version() {
    log_step "备份当前版本"

    BACKUP_DIR="${REMOTE_DIR}/backups/$(date +%Y%m%d_%H%M%S)"
    
    ssh_exec "
        mkdir -p ${REMOTE_DIR}/backups
        
        if [ -f '${REMOTE_DIR}/docker-compose.yml' ]; then
            mkdir -p ${BACKUP_DIR}
            
            # 备份数据库文件
            cp -r ${REMOTE_DIR}/data/ ${BACKUP_DIR}/data/ 2>/dev/null || true
            
            # 备份配置文件
            cp ${REMOTE_DIR}/.env ${BACKUP_DIR}/.env 2>/dev/null || true
            
            # 记录当前版本信息
            git rev-parse HEAD > ${BACKUP_DIR}/version.txt 2>/dev/null || echo 'unknown' > ${BACKUP_DIR}/version.txt
            
            echo 'backup_created'
        else
            echo 'no_backup_needed'
        fi
    "

    if [ $? -eq 0 ]; then
        log_success "备份完成: $BACKUP_DIR"
        
        # 清理旧备份（保留最近 N 个）
        ssh_exec "cd ${REMOTE_DIR}/backups && ls -dt */ 2>/dev/null | tail -n +$((BACKUP_COUNT + 1)) | xargs rm -rf" || true
    else
        log_warning "备份失败（可能是首次部署）"
    fi
}

# ============================================================
# 上传代码到服务器
# ============================================================
upload_code() {
    log_step "上传代码到服务器"

    log_info "创建远程目录..."
    ssh_exec "mkdir -p $REMOTE_DIR/{data,config,alembic/versions}"

    log_info "同步代码文件（排除不需要的文件）..."
    rsync -avz \
        --progress \
        -e "ssh -i $SSH_KEY -p $REMOTE_PORT" \
        --exclude='node_modules' \
        --exclude='.git' \
        --exclude='venv' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.env' \
        --exclude='data/*.db' \
        --exclude='data/*.db-journal' \
        --exclude='.DS_Store' \
        --exclude='*.log' \
        --exclude='frontend/node_modules' \
        --exclude='frontend/dist' \
        "./" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/"

    log_success "代码上传完成"
}

# ============================================================
# 上传环境变量（安全处理）
# ============================================================
upload_env_file() {
    log_step "上传环境变量配置"

    if [ -f ".env" ]; then
        # 上传 .env 文件（设置权限为仅所有者可读）
        scp -i "$SSH_KEY" -P $REMOTE_PORT .env "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/.env"
        ssh_exec "chmod 600 $REMOTE_DIR/.env"
        log_success ".env 文件已上传（权限已设置为 600）"
    else
        log_warning "未找到 .env 文件，跳过上传"
    fi
}

# ============================================================
# 在远程服务器上构建和部署
# ============================================================
build_and_deploy() {
    log_step "在远程服务器上构建和部署"

    ssh_exec << 'DEPLOY_SCRIPT'
cd /opt/campus-pilot

echo "=========================================="
echo "开始构建 Docker 镜像..."
echo "=========================================="

# 构建后端镜像
echo "[1/3] 构建后端镜像..."
docker compose build backend --no-cache
if [ $? -ne 0 ]; then
    echo "ERROR: 后端镜像构建失败"
    exit 1
fi
echo "✓ 后端镜像构建成功"

# 构建前端镜像
echo "[2/3] 构建前端镜像..."
docker compose build frontend --no-cache
if [ $? -ne 0 ]; then
    echo "ERROR: 前端镜像构建失败"
    exit 1
fi
echo "✓ 前端镜像构建成功"

# 启动服务
echo "[3/3] 启动服务..."
if [ "$DEPLOY_MODE" = "server" ]; then
    docker compose -f docker-compose.yml -f docker-compose.server.yml up -d
else
    docker compose up -d
fi

if [ $? -ne 0 ]; then
    echo "ERROR: 服务启动失败"
    exit 1
fi
echo "✓ 服务启动成功"

echo ""
echo "=========================================="
echo "等待服务就绪..."
echo "=========================================="
DEPLOY_SCRIPT

    log_success "Docker 镜像构建和服务启动完成"
}

# ============================================================
# 健康检查
# ============================================================
health_check() {
    log_step "健康检查"

    log_info "等待服务启动完成..."
    sleep 10

    local max_attempts=$((HEALTH_CHECK_TIMEOUT / 5))
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
            --connect-timeout 5 \
            http://${REMOTE_HOST}:8000/health 2>/dev/null || echo "000")

        if [ "$HTTP_STATUS" = "200" ]; then
            log_success "健康检查通过 ✓ (HTTP 200)"
            return 0
        fi

        log_warning "尝试 $attempt/$max_attempts: 服务未就绪 (HTTP $HTTP_STATUS)"
        sleep 5
        ((attempt++))
    done

    log_error "健康检查失败 ✗ (超时 ${HEALTH_CHECK_TIMEOUT}s)"
    return 1
}

# ============================================================
# 回滚操作
# ============================================================
rollback() {
    log_step "回滚到上一版本"

    LATEST_BACKUP=$(ssh_exec "ls -td ${REMOTE_DIR}/backups/*/ 2>/dev/null | head -1")

    if [ -z "$LATEST_BACKUP" ] || [ "$LATEST_BACKUP" = "" ]; then
        log_error "没有可用的备份进行回滚"
        exit 1
    fi

    log_warning "即将回滚到: $LATEST_BACKUP"
    read -p "确认回滚？(y/N) " confirm
    
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        log_info "取消回滚操作"
        return
    fi

    ssh_exec << ROLLBACK_SCRIPT
cd /opt/campus-pilot

# 停止当前服务
docker compose down

# 恢复数据库
rm -rf data/
cp -r ${LATEST_BACKUP}data/ data/

# 恢复配置文件
cp ${LATEST_BACKUP}.env .env 2>/dev/null || true

# 重启服务
docker compose up -d

echo "回滚完成"
ROLLBACK_SCRIPT

    log_success "回滚完成，正在执行健康检查..."
    health_check
}

# ============================================================
# 查看部署状态
# ============================================================
show_status() {
    log_step "查看部署状态"

    ssh_exec << STATUS_SCRIPT
cd /opt/campus-pilot

echo "=== 容器状态 ==="
docker compose ps

echo ""
echo "=== 最近日志 (最后20行) ==="
docker compose logs --tail=20

echo ""
echo "=== 数据库文件 ==="
ls -lh data/*.db 2>/dev/null || echo "无数据库文件"

echo ""
echo "=== 磁盘使用情况 ==="
du -sh .

echo ""
echo "=== 备份列表 ==="
ls -lth backups/ 2>/dev/null | head -10 || echo "无备份"
STATUS_SCRIPT
}

# ============================================================
# 查看日志
# ============================================================
show_logs() {
    log_step "查看实时日志"

    LOG_LINES=${1:-100}
    FOLLOW=${2:-false}

    if [ "$FOLLOW" = "true" ]; then
        ssh_exec "cd $REMOTE_DIR && docker compose logs -f --tail=$LOG_LINES"
    else
        ssh_exec "cd $REMOTE_DIR && docker compose logs --tail=$LOG_LINES"
    fi
}

# ============================================================
# 停止服务
# ============================================================
stop_service() {
    log_step "停止服务"

    ssh_exec "cd $REMOTE_DIR && docker compose down"
    log_success "服务已停止"
}

# ============================================================
# 清理旧版本和缓存
# ============================================================
cleanup() {
    log_step "清理旧版本和缓存"

    ssh_exec << CLEANUP_SCRIPT
cd /opt/campus-pilot

echo "清理未使用的 Docker 镜像..."
docker image prune -af

echo "清理停止的容器..."
docker container prune -f

echo "清理未使用的卷..."
docker volume prune -f

echo "清理构建缓存..."
docker builder prune -f

echo ""
echo "磁盘使用情况:"
du -sh .
CLEANUP_SCRIPT

    log_success "清理完成"
}

# ============================================================
# 主流程
# ============================================================
main() {
    START_TIME=$(date +%s)

    echo "=========================================="
    echo "  CampusPilot 自动部署工具 v2.0"
    echo "=========================================="
    echo "目标服务器: $REMOTE_USER@$REMOTE_HOST:$REMOTE_PORT"
    echo "部署目录: $REMOTE_DIR"
    echo "模式: $1"
    echo ""

    case "${1:-deploy}" in
        --deploy)
            check_prerequisites
            backup_current_version
            upload_code
            upload_env_file
            build_and_deploy
            
            if health_check; then
                END_TIME=$(date +%s)
                DURATION=$((END_TIME - START_TIME))
                
                echo ""
                echo "=========================================="
                echo -e "${GREEN}🎉 部署成功！${NC}"
                echo "=========================================="
                echo "耗时: ${DURATION}s"
                echo "访问地址:"
                echo "  - 后端 API: http://$REMOTE_HOST:8000/docs"
                echo "  - 前端界面: http://$REMOTE_HOST"
                echo "  - 健康检查: http://$REMOTE_HOST:8000/health"
                echo ""
                echo "管理命令:"
                echo "  ./deploy.sh --status   # 查看状态"
                echo "  ./deploy.sh --logs     # 查看日志"
                echo "  ./deploy.sh --rollback # 回滚版本"
                echo "  ./deploy.sh --stop     # 停止服务"
            else
                log_error "部署失败！"
                if [ "$ROLLBACK_ON_FAILURE" = "true" ]; then
                    log_warning "正在自动回滚..."
                    rollback
                fi
                exit 1
            fi
            ;;

        --update)
            check_prerequisites
            upload_code
            upload_env_file
            ssh_exec "cd $REMOTE_DIR && docker compose up -d --build"
            health_check
            log_success "更新完成"
            ;;

        --rollback)
            rollback
            ;;

        --status)
            show_status
            ;;

        --logs)
            shift
            show_logs "${1:-100}" "true"
            ;;

        --stop)
            stop_service
            ;;

        --clean)
            cleanup
            ;;

        *)
            echo "用法: $0 {--deploy|--update|--rollback|--status|--logs|--stop|--clean}"
            echo ""
            echo "选项说明:"
            echo "  --deploy     完整部署（测试+上传+构建+启动）"
            echo "  --update     快速更新（仅上传代码并重启）"
            echo "  --rollback   回滚到上一版本"
            echo "  --status     查看部署状态和容器信息"
            echo "  --logs       查看实时日志"
            echo "  --stop       停止所有服务"
            echo "  --clean      清理旧版本和缓存"
            exit 1
            ;;
    esac
}

main "$@"
