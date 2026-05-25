#!/bin/bash

# ============================================================
# CampusPilot 自动化测试脚本
# 功能：后端单元测试 + 前端构建测试 + Docker 集成测试
# 用法：./test.sh [选项]
#   选项：
#     --backend      仅运行后端测试
#     --frontend     仅运行前端测试
#     --docker       仅运行 Docker 测试
#     --all          运行所有测试（默认）
#     --ci           CI 模式（无交互，详细输出）
# ============================================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 计数器
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
    ((TESTS_PASSED++))
    ((TESTS_TOTAL++))
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
    ((TESTS_FAILED++))
    ((TESTS_TOTAL++))
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# 解析参数
MODE="all"
CI_MODE=false

for arg in "$@"; do
    case $arg in
        --backend)
            MODE="backend"
            shift
            ;;
        --frontend)
            MODE="frontend"
            shift
            ;;
        --docker)
            MODE="docker"
            shift
            ;;
        --all)
            MODE="all"
            shift
            ;;
        --ci)
            CI_MODE=true
            shift
            ;;
        *)
            log_error "未知参数: $arg"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "  CampusPilot 自动化测试套件 v2.0"
echo "=========================================="
echo "模式: $MODE | CI模式: $CI_MODE"
echo ""

# ============================================================
# 前置检查
# ============================================================
check_prerequisites() {
    log_info "检查前置依赖..."

    # 检查 Python
    if command -v python &> /dev/null; then
        PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
        log_success "Python 已安装 (版本: $PYTHON_VERSION)"
    else
        log_error "Python 未安装"
        exit 1
    fi

    # 检查 Node.js（前端测试需要）
    if [[ "$MODE" == "all" || "$MODE" == "frontend" ]]; then
        if command -v node &> /dev/null; then
            NODE_VERSION=$(node --version)
            log_success "Node.js 已安装 (版本: $NODE_VERSION)"
        else
            log_warning "Node.js 未安装，跳过前端测试"
        fi
    fi

    # 检查 Docker（Docker 测试需要）
    if [[ "$MODE" == "all" || "$MODE" == "docker" ]]; then
        if command -v docker &> /dev/null; then
            DOCKER_VERSION=$(docker --version | awk '{print $3}' | tr -d ',')
            log_success "Docker 已安装 (版本: $DOCKER_VERSION)"
        else
            log_warning "Docker 未安装，跳过 Docker 测试"
        fi
    fi

    echo ""
}

# ============================================================
# 后端测试
# ============================================================
run_backend_tests() {
    echo "=========================================="
    echo "  📦 后端测试"
    echo "=========================================="

    cd "$(dirname "$0")"

    # 创建虚拟环境（如果不存在）
    if [ ! -d "venv" ]; then
        log_info "创建 Python 虚拟环境..."
        python -m venv venv
    fi

    # 激活虚拟环境
    source venv/Scripts/activate 2>/dev/null || source venv/bin/activate

    # 安装依赖
    log_info "安装 Python 依赖..."
    pip install -q -r requirements.txt pytest pytest-asyncio httpx pytest-cov

    # 运行单元测试
    log_info "运行后端单元测试..."
    if python -m pytest tests/ -v --tb=short --cov=app --cov-report=term-missing; then
        log_success "后端单元测试通过 ✓"
    else
        log_error "后端单元测试失败 ✗"
        return 1
    fi

    # 类型检查
    log_info "运行类型检查..."
    if command -v mypy &> /dev/null || pip install mypy -q; then
        if mypy app/ --ignore-missing-imports --no-error-summary; then
            log_success "类型检查通过 ✓"
        else
            log_warning "类型检查有警告（非阻塞）"
        fi
    fi

    deactivate
    echo ""
}

# ============================================================
# 前端测试
# ============================================================
run_frontend_tests() {
    echo "=========================================="
    echo "  🎨 前端测试"
    echo "=========================================="

    cd "$(dirname "$0")/frontend"

    # 检查 node_modules
    if [ ! -d "node_modules" ]; then
        log_info "安装前端依赖..."
        npm install
    fi

    # TypeScript 编译检查
    log_info "TypeScript 编译检查..."
    if npx tsc --noEmit; then
        log_success "TypeScript 编译通过 ✓"
    else
        log_error "TypeScript 编译失败 ✗"
        return 1
    fi

    # ESLint 检查
    log_info "ESLint 代码质量检查..."
    if [ -f ".eslintrc" ] || grep -q "eslint" package.json; then
        if npm run lint 2>/dev/null; then
            log_success "ESLint 检查通过 ✓"
        else
            log_warning "ESLint 有警告（非阻塞）"
        fi
    else
        log_warning "跳过 ESLint（未配置）"
    fi

    # 构建测试
    log_info "前端构建测试..."
    if npm run build; then
        log_success "前端构建成功 ✓"
    else
        log_error "前端构建失败 ✗"
        return 1
    fi

    cd ..
    echo ""
}

# ============================================================
# Docker 集成测试
# ============================================================
run_docker_tests() {
    echo "=========================================="
    echo "  🐳 Docker 集成测试"
    echo "=========================================="

    cd "$(dirname "$0")"

    # 检查 Docker 是否可用
    if ! command -v docker &> /dev/null; then
        log_warning "Docker 不可用，跳过 Docker 测试"
        return 0
    fi

    # 构建 Docker 镜像
    log_info "构建后端 Docker 镜像..."
    if docker build -t campuspilot-backend:test .; then
        log_success "后端镜像构建成功 ✓"
    else
        log_error "后端镜像构建失败 ✗"
        return 1
    fi

    log_info "构建前端 Docker 镜像..."
    if docker build -t campuspilot-frontend:test ./frontend; then
        log_success "前端镜像构建成功 ✓"
    else
        log_error "前端镜像构建失败 ✗"
        return 1
    fi

    # 启动容器进行健康检查
    log_info "启动容器进行集成测试..."
    
    # 使用临时配置启动
    DEPLOY_MODE=laptop docker compose up -d --build 2>&1 | tail -20

    # 等待服务启动
    log_info "等待服务启动..."
    sleep 10

    # 健康检查
    HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo "000")
    
    if [ "$HEALTH_STATUS" = "200" ]; then
        log_success "后端健康检查通过 ✓ (HTTP $HEALTH_STATUS)"
        
        # API 文档可访问性检查
        DOCS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs 2>/dev/null || echo "000")
        if [ "$DOCS_STATUS" = "200" ]; then
            log_success "API 文档可访问 ✓ (HTTP $DOCS_STATUS)"
        else
            log_warning "API 文档不可访问 (HTTP $DOCS_STATUS)"
        fi
    else
        log_error "后端健康检查失败 ✗ (HTTP $HEALTH_STATUS)"
    fi

    # 清理容器
    log_info "清理测试容器..."
    docker compose down -v --remove-orphans 2>/dev/null || true
    docker rmi campuspilot-backend:test campuspilot-frontend:test 2>/dev/null || true

    echo ""
}

# ============================================================
# 主流程
# ============================================================
main() {
    START_TIME=$(date +%s)

    check_prerequisites

    case $MODE in
        backend)
            run_backend_tests
            ;;
        frontend)
            run_frontend_tests
            ;;
        docker)
            run_docker_tests
            ;;
        all)
            run_backend_tests && run_frontend_tests && run_docker_tests
            ;;
    esac

    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    # 输出结果摘要
    echo "=========================================="
    echo "  📊 测试结果摘要"
    echo "=========================================="
    echo -e "总测试数: ${TESTS_TOTAL}"
    echo -e "通过: ${GREEN}${TESTS_PASSED}${NC}"
    echo -e "失败: ${RED}${TESTS_FAILED}${NC}"
    echo -e "耗时: ${DURATION}s"
    echo ""

    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}🎉 所有测试通过！${NC}"
        exit 0
    else
        echo -e "${RED}❌ 存在失败的测试项${NC}"
        exit 1
    fi
}

main "$@"
