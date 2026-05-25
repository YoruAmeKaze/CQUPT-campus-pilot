# CampusPilot 自动化测试与部署指南

## 📋 目录

- [快速开始](#快速开始)
- [自动化测试](#自动化测试)
- [虚拟机部署](#虚拟机部署)
- [CI/CD 集成](#cicd-集成)
- [常见问题](#常见问题)

---

## 快速开始

### 1️⃣ 环境准备

**本地开发环境：**
```bash
# Python 3.11+
python --version

# Node.js 18+ (前端需要)
node --version

# Docker (可选，用于容器化部署)
docker --version
```

**服务器环境（Ubuntu 20.04+）：**
```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 安装 Docker Compose
sudo apt-get install docker-compose-plugin
```

---

## 自动化测试

### 运行完整测试套件

**Windows:**
```bash
# 方式1: 使用批处理脚本
deploy.bat test

# 方式2: 使用 Git Bash
bash test.sh --all --ci
```

**Linux/Mac:**
```bash
chmod +x test.sh
./test.sh --all --ci
```

### 测试选项

| 命令 | 说明 |
|------|------|
| `--backend` | 仅运行后端单元测试 |
| `--frontend` | 仅运行前端构建和类型检查 |
| `--docker` | 仅运行 Docker 构建和集成测试 |
| `--all` | 运行所有测试（默认） |
| `--ci` | CI 模式，无交互式输出 |

**示例：**
```bash
# 只测试后端
./test.sh --backend

# 完整测试 + CI 模式
./test.sh --all --ci

# 仅 Docker 测试
./test.sh --docker
```

### 测试内容详解

#### ✅ 后端测试 (`tests/`)
- **健康检查接口**: `/health` 和 `/` 路由测试
- **CORS 配置**: 跨域请求头验证
- **数据库模型**: User、Course、Assignment、DataSource、Notification 模型创建测试
- **配置模块**: Settings 类默认值、环境变量加载、属性方法测试
- **API 路由框架**: 为 Phase 2+ 预留的 API 测试（当前标记为 skip）

#### ✅ 前端测试
- TypeScript 编译检查
- ESLint 代码质量验证
- 生产环境构建测试

#### ✅ Docker 集成测试
- Dockerfile 存在性验证
- 镜像构建测试
- docker-compose 配置 YAML 验证
- 服务启动健康检查
- 容器运行状态检测
- 镜像大小合理性检查

### 添加新测试

在 `tests/` 目录下创建新的测试文件：

```python
# tests/test_example.py
import pytest
from httpx import AsyncClient


class TestExampleFeature:
    """示例功能测试"""

    @pytest.mark.asyncio
    async def test_new_feature(self, client: AsyncClient):
        """测试新功能"""
        response = await client.get("/api/new-endpoint")
        assert response.status_code == 200
        data = response.json()
        assert "expected_field" in data
```

运行特定测试文件：
```bash
pytest tests/test_example.py -v
```

---

## 虚拟机部署

### 🔧 第一步：SSH 密钥配置

#### Windows 用户：
```bash
# 运行设置向导
deploy.bat setup

# 或手动执行各步骤
bash setup-ssh.sh --generate      # 1. 生成密钥对
bash setup-ssh.sh --config        # 2. 配置 SSH 别名
bash setup-ssh.sh --deploy-key    # 3. 上传公钥到服务器
bash setup-ssh.sh --test          # 4. 测试连接
```

#### Linux/Mac 用户：
```bash
chmod +x setup-ssh.sh
./setup-ssh.sh --all              # 一键完成所有步骤
```

**设置向导会引导你：**
1. 生成 RSA 4096 位 SSH 密钥对
2. 配置 SSH 客户端别名（`campuspilot`）
3. 将公钥自动部署到服务器的 `~/.ssh/authorized_keys`
4. 测试 SSH 连接是否正常
5. 自动更新 `deploy.sh` 的配置

### 🚀 第二步：部署到服务器

#### 方法 A: 使用 Windows 批处理脚本（推荐）
```bash
deploy.bat deploy
```

#### 方法 B: 使用 Bash 脚本
```bash
chmod +x deploy.sh
./deploy.sh --deploy
```

**部署流程：**
1. ✅ 检查 SSH 连接和环境依赖
2. ✅ 备份当前版本（数据库、配置文件）
3. ✅ 上传代码到服务器（rsync 同步，排除 node_modules 等）
4. ✅ 安全上传 .env 文件（权限 600）
5. ✅ 在服务器上构建 Docker 镜像
6. ✅ 启动/重启服务（docker-compose up -d）
7. ✅ 健康检查（最多等待 60 秒）
8. ✅ 输出访问地址和管理命令

**如果健康检查失败且 `ROLLBACK_ON_FAILURE=true`，将自动回滚！**

### 📊 第三步：管理已部署的服务

```bash
# 查看状态
./deploy.sh --status
# 或
deploy.bat status

# 查看实时日志
./deploy.sh --logs
# 或
deploy.bat logs

# 快速更新代码（不重新构建镜像）
./deploy.sh --update

# 回滚到上一版本
./deploy.sh --rollback
# 或
deploy.bat rollback

# 停止服务
./deploy.sh --stop

# 清理旧版本和缓存
./deploy.sh --clean
```

### ⚙️ 配置说明

编辑 `deploy.sh` 顶部的配置区域：

```bash
# 远程服务器配置
REMOTE_HOST="your_server_ip"           # 必填：服务器 IP 或域名
REMOTE_USER="root"                      # SSH 用户名
REMOTE_PORT=22                          # SSH 端口
REMOTE_DIR="/opt/campus-pilot"          # 部署目录
SSH_KEY="$HOME/.ssh/id_rsa"            # SSH 私钥路径

# 部署选项
DEPLOY_MODE="server"                    # laptop 或 server
BACKUP_COUNT=3                          # 保留的备份版本数
HEALTH_CHECK_TIMEOUT=60                 # 健康检查超时（秒）
ROLLBACK_ON_FAILURE=true               # 失败时是否自动回滚
```

**首次部署前必须修改 `REMOTE_HOST` 为你的服务器地址！**

---

## CI/CD 集成

### GitHub Actions 工作流

项目已包含 `.github/workflows/deploy.yml`，支持：

#### ✅ 自动触发
- **Push 到 main 分支** → 运行测试 → 部署到生产环境
- **Pull Request** → 运行测试（不部署）
- **手动回滚** → 触发 rollback job

#### ✅ 流水线阶段
1. **后端测试** - pytest 单元测试 + 覆盖率报告
2. **前端构建** - TypeScript 类型检查 + 生产构建
3. **Docker 构建** - 验证 Dockerfile 可用性
4. **自动部署** - SSH 连接服务器并执行部署脚本
5. **健康检查** - 验证服务正常运行
6. **通知推送** - 成功/失败通知（企业微信 Webhook）

#### 🔐 配置 Secrets

在 GitHub 仓库的 **Settings → Secrets and variables → Actions** 中添加：

| Secret 名称 | 说明 | 示例 |
|-------------|------|------|
| `SERVER_IP` | 服务器 IP 地址 | `123.45.67.89` |
| `SERVER_HOST` | 服务器主机名 | `my-server` |
| `REMOTE_USER` | SSH 用户名 | `root` |
| `REMOTE_PORT` | SSH 端口 | `22` |
| `SSH_PRIVATE_KEY` | SSH 私钥内容 | （完整私钥内容） |
| `WEBHOOK_URL` | 企业微信通知 Webhook | `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx` |

**添加 SSH_PRIVATE_KEY 时注意：**
- 包含完整的私钥内容（包括 `-----BEGIN...` 和 `-----END...`）
- 不要有多余的空格或换行

### 手动触发工作流

1. 进入 GitHub 仓库的 **Actions** 页面
2. 选择 **CampusPilot CI/CD** 工作流
3. 点击 **Run workflow**
4. 选择分支和事件类型（push 或 rollback）

---

## 常见问题

### ❌ SSH 连接失败

**错误信息：** `Permission denied (publickey)`

**解决方案：**
```bash
# 1. 检查公钥是否已添加到服务器
ssh-copy-id -i ~/.ssh/campuspilot_deploy.pub root@your_server_ip

# 2. 检查私钥权限
chmod 600 ~/.ssh/campuspilot_deploy

# 3. 测试连接
ssh -i ~/.ssh/campuspilot_deploy root@your_server_ip
```

### ❌ Docker 构建失败

**错误信息：** `failed to solve: ...`

**解决方案：**
```bash
# 在服务器上手动构建查看详细日志
ssh campuspilot
cd /opt/campus-pilot
docker compose build backend --no-cache

# 查看具体错误
docker compose logs backend
```

### ❌ 健康检查超时

**错误信息：** `Health check failed (timeout 60s)`

**解决方案：**
```bash
# 1. 检查容器状态
ssh campuspilot
cd /opt/campus-pilot
docker compose ps

# 2. 查看日志
docker compose logs --tail=100

# 3. 手动检查端口
curl http://localhost:8000/health

# 4. 如果是首次启动，可能需要更长时间初始化数据库
# 修改 deploy.sh 中的 HEALTH_CHECK_TIMEOUT=120
```

### ❌ rsync 排除文件过多

**现象：** 上传速度慢或传输不需要的文件

**解决方案：** 编辑 `deploy.sh` 中的 `upload_code()` 函数，调整 rsync 的排除规则：

```bash
rsync -avz \
    --exclude='node_modules' \
    --exclude='.git' \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='data/*.db' \
    # 添加更多排除项...
```

### ❌ .env 文件权限问题

**警告：** `.env 文件权限应设置为 600`

**解决方案：**
```bash
# 脚本已自动处理，如需手动修复：
ssh campuspilot
chmod 600 /opt/campus-pilot/.env
```

### 💡 性能优化建议

1. **首次部署较慢？** 
   - 后端镜像包含 Playwright 浏览器（约 500MB），首次构建较慢
   - 后续构建利用 Docker 层缓存会快很多

2. **频繁更新代码？**
   - 使用 `./deploy.sh --update` 仅同步代码并重启，跳过镜像重建

3. **多环境部署？**
   - 创建多个部署脚本副本（如 `deploy-prod.sh`, `deploy-staging.sh`）
   - 分别配置不同的 `REMOTE_HOST` 和 `REMOTE_DIR`

4. **备份策略？**
   - 默认保留最近 3 个版本的备份
   - 修改 `BACKUP_COUNT=5` 可增加备份数量
   - 备份存储在 `$REMOTE_DIR/backups/` 目录下

---

## 📞 技术支持

遇到问题时：

1. **查看日志：** `./deploy.sh --logs`
2. **检查状态：** `./deploy.sh --status`
3. **本地测试：** `./test.sh --all`
4. **手动回滚：** `./deploy.sh --rollback`

**祝部署顺利！🎉**
