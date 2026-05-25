# ============================================================
# CampusPilot Makefile
# 用于 Linux/Mac 用户的快速操作
# ============================================================

.PHONY: help test deploy setup dev clean logs status rollback

# 默认目标
.DEFAULT_GOAL := help

# 颜色定义
GREEN := \033[0;32m
BLUE := \033[0;34m
YELLOW := \033[1;33m
NC := \033[0m

# ============================================================
# 帮助信息
# ============================================================
help:
	@echo ""
	@echo "$(GREEN)CampusPilot 快速命令指南$(NC)"
	@echo "=============================="
	@echo ""
	@echo "$(BLUE)开发命令:$(NC)"
	@echo "  make dev          - 启动本地开发环境"
	@echo "  make test         - 运行所有测试"
	@echo "  make test-backend - 仅运行后端测试"
	@echo "  make test-frontend- 仅运行前端测试"
	@echo "  make test-docker  - 仅运行 Docker 测试"
	@echo ""
	@echo "$(BLUE)部署命令:$(NC)"
	@echo "  make deploy       - 完整部署到服务器"
	@echo "  make update       - 快速更新代码并重启"
	@echo "  make rollback     - 回滚到上一版本"
	@echo "  make status       - 查看服务器状态"
	@echo "  make logs         - 查看实时日志"
	@echo "  make stop         - 停止远程服务"
	@echo ""
	@echo "$(BLUE)配置命令:$(NC)"
	@echo "  make setup        - SSH 密钥设置向导"
	@echo "  make init         - 初始化项目（首次使用）"
	@echo "  make clean        - 清理本地缓存和临时文件"
	@echo ""

# ============================================================
# 开发相关
# ============================================================

dev:
	@echo "$(BLUE)[INFO] 启动本地开发环境...$(NC)"
	@if [ ! -d "venv" ]; then \
		echo "创建虚拟环境..."; \
		python3 -m venv vvm; \
	fi
	@source venv/bin/activate && pip install -q -r requirements.txt
	@echo "$(GREEN)✓ 后端依赖已安装$(NC)"
	@source venv/bin/activate && python -m uvicorn app.main:app --reload --port 8000 &
	@sleep 3
	@if [ -f "frontend/package.json" ]; then \
		if [ ! -d "frontend/node_modules" ]; then \
			cd frontend && npm install; \
		fi; \
		echo "$(GREEN)✓ 前端服务启动中...$(NC)"; \
		cd frontend && npm run dev & \
	else \
		echo "$(YELLOW)! 未找到前端项目，仅启动后端$(NC)"; \
	fi
	@echo ""
	@echo "$(GREEN)╔════════════════════════════════════════╗$(NC)"
	@echo "$(GREEN)║     ✅ 开发环境已启动！                ║$(NC)"
	@echo "$(GREEN)╠════════════════════════════════════════╣$(NC)"
	@echo "$(GREEN)║  后端 API: http://localhost:8000        ║$(NC)"
	@echo "$(GREEN)║  API 文档: http://localhost:8000/docs    ║$(NC)"
	@echo "$(GREEN)║  前端界面: http://localhost:3000         ║$(NC)"
	@echo "$(GREEN)╚════════════════════════════════════════╝$(NC)"

init:
	@echo "$(BLUE)[INFO] 初始化项目...$(NC)"
	@python3 -m venv vvm
	@source venv/bin/activate && pip install -r requirements.txt
	@if [ -f ".env.example" ] && [ ! -f ".env" ]; then \
		cp .env.example .env; \
		echo "$(GREEN)✓ .env 文件已创建，请编辑配置$(NC)"; \
	fi
	@mkdir -p data config alembic/versions
	@echo "$(GREEN)✅ 项目初始化完成！运行 'make dev' 开始开发$(NC)"

# ============================================================
# 测试相关
# ============================================================

test:
	@bash test.sh --all

test-backend:
	@bash test.sh --backend

test-frontend:
	@bash test.sh --frontend

test-docker:
	@bash test.sh --docker

test-ci:
	@bash test.sh --all --ci

# ============================================================
# 部署相关
# ============================================================

deploy:
	@bash deploy.sh --deploy

update:
	@bash deploy.sh --update

rollback:
	@bash deploy.sh --rollback

status:
	@bash deploy.sh --status

logs:
	@bash deploy.sh --logs

stop:
	@bash deploy.sh --stop

clean-deploy:
	@bash deploy.sh --clean

# ============================================================
# SSH 配置
# ============================================================

setup:
	@bash setup-ssh.sh --all

ssh-generate:
	@bash setup-ssh.sh --generate

ssh-config:
	@bash setup-ssh.sh --config

ssh-deploy-key:
	@bash setup-ssh.sh --deploy-key

ssh-test:
	@bash setup-ssh.sh --test

# ============================================================
# 本地清理
# ============================================================

clean:
	@echo "$(BLUE)[INFO] 清理本地缓存...$(NC)"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf .pytest_cache .coverage htmlcov *.egg-info build dist
	@rm -rf frontend/dist
	@echo "$(GREEN)✓ 本地缓存已清理$(NC)"

clean-all: clean
	@echo "$(BLUE)[INFO] 深度清理（包括虚拟环境和数据库）...$(NC)"
	@rm -rf venv node_modules data/*.db data/*.db-journal
	@echo "$(YELLOW)⚠️ 已删除虚拟环境和数据库文件$(NC)"

# ============================================================
# 数据库迁移
# ============================================================

migration-generate:
	@echo "$(BLUE)[INFO] 生成新的数据库迁移...$(NC)"
	@read -p "请输入迁移描述: " desc; \
	source venv/bin/activate && alembic revision --autogenerate -m "$desc"

migration-upgrade:
	@echo "$(BLUE)[INFO] 执行数据库迁移...$(NC)"
	@source venv/bin/activate && alembic upgrade head

migration-downgrade:
	@echo "$(BLUE)[INFO] 回滚上一个迁移...$(NC)"
	@source venv/bin/activate && alembic downgrade -1

migration-history:
	@source venv/bin/activate && alembic history
