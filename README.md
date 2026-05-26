# CampusPilot 🎓

**重庆邮电大学个人学业智能助理** — 自动抓取课表、作业，通过 Web 界面和飞书机器人管理学业

## 功能

- 📅 **课表管理** — 自动从教务系统抓取课表，周视图展示
- 📝 **作业提醒** — 自动抓取学习通、数你最灵作业，截止时间提醒
- ✅ **待办管理** — Web 端和飞书端创建待办，支持自然语言
- 🤖 **飞书机器人** — 双向对话，查询课表/作业/待办
- 🧠 **AI 智能查询** — 自然语言问："这周有什么作业？"
- 📊 **Web 仪表盘** — 可视化学业概览

---

## 快速开始

### 方式一：Windows 直接运行（推荐）

#### 前置条件

| 软件 | 版本 | 下载 |
|------|------|------|
| Python | 3.11+ | https://www.python.org/downloads/ |
| Node.js | 18+ | https://nodejs.org/ |

> Python 安装时请勾选 **"Add Python to PATH"**

#### 一键启动

```bat
# 双击运行（或在终端中执行）
start.bat
```

脚本会自动完成：
1. ✅ 检测 Python 和 Node.js 环境
2. ✅ 创建 Python 虚拟环境并安装依赖
3. ✅ 自动生成加密密钥（FERNET_KEY）
4. ✅ 安装 Playwright Chromium 浏览器（爬虫用）
5. ✅ 安装前端依赖并编译
6. ✅ 启动后端服务 (http://localhost:8000)
7. ✅ 启动前端界面 (http://localhost:3000)

启动后，在浏览器打开 **http://localhost:3000** 即可使用。

### 方式二：Docker 运行

#### 前置条件

| 软件 | 下载 |
|------|------|
| Docker Desktop | https://www.docker.com/products/docker-desktop/ |

#### 一键启动

```bat
# Windows
docker-start.bat
```

```bash
# Linux/Mac
docker compose up -d --build
```

脚本会自动完成：
1. ✅ 检测 Docker 环境
2. ✅ 自动生成加密密钥
3. ✅ 构建前后端 Docker 镜像
4. ✅ 启动容器服务

启动后，在浏览器打开 **http://localhost:3000** 即可使用。

---

## 首次使用配置

启动后打开 http://localhost:3000，进入 **"设置"** 页面配置以下内容：

### 基础配置（必填）
| 配置项 | 说明 |
|--------|------|
| 学号 | 用于教务系统课表抓取 |
| DeepSeek API Key | 用于 AI 智能查询功能（[获取 Key](https://platform.deepseek.com/)）|

### 数据源配置（按需）
| 配置项 | 说明 |
|--------|------|
| 学习通账号/密码 | 自动抓取学习通作业 |
| 数你最灵账号/密码 | 自动抓取数你最灵作业 |

### 推送配置（按需）
| 配置项 | 说明 |
|--------|------|
| 飞书 Webhook URL | 飞书群机器人消息推送 |
| Bark Key | iOS 推送（需安装 Bark App）|
| 飞书 App ID/Secret | 飞书应用双向对话（需 SSH 隧道）|

> 所有配置通过 Web 界面保存，无需编辑任何文件。

---

## 开机自启（Windows）

启动 `start.bat` 后，脚本会询问是否设置开机自启，选择 `y` 即可。

或者手动运行以下命令：

```bat
# 设置开机自启（用户登录时自动启动）
schtasks /create /tn "CampusPilot" /tr "'C:\路径\到\start.bat'" /sc onlogon /ru "%USERNAME%" /f

# 取消开机自启
schtasks /delete /tn "CampusPilot" /f

# 查看任务状态
schtasks /query /tn "CampusPilot"
```

---

## 目录结构

```
CampusPilot/
├── start.bat                # Windows 一键启动
├── start.sh                 # Linux/Mac 一键启动
├── docker-start.bat         # Docker 一键启动
├── .env                     # 环境变量（自动管理）
│
├── app/                     # 后端 Python 代码
├── frontend/                # 前端 React 代码
├── docs/                    # 开发文档
├── scripts/                 # 服务器部署脚本
├── tests/                   # 测试
│
├── Dockerfile               # 后端 Docker 构建
├── docker-compose.yml       # Docker Compose 编排
└── requirements.txt         # Python 依赖
```

---

## 管理命令

### 停止服务
- **直接运行模式**：关闭 CampusPilot-Backend 和 CampusPilot-Frontend 的终端窗口
- **Docker 模式**：

  ```bash
  docker compose down
  ```

### 查看日志
- **Docker 模式**：

  ```bash
  docker compose logs -f
  ```

---

## 飞书机器人配置（可选）

如需飞书应用的双向对话功能，需额外配置：

1. 访问 [飞书开放平台](https://open.feishu.cn/) → 创建企业自建应用
2. 获取 App ID 和 App Secret
3. 配置事件订阅（回调 URL 需公网可访问）
4. 在 Web 设置页面填写飞书应用配置
5. 需要一台公网服务器做 SSH 隧道（参考 `scripts/deploy.sh`）

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy / APScheduler |
| 前端 | React 18 / TypeScript / Tailwind CSS / shadcn/ui |
| 数据库 | SQLite（零配置） |
| AI | DeepSeek (Text-to-SQL) |
| 爬虫 | Playwright / BeautifulSoup / httpx |
| 部署 | Docker / Docker Compose |

---

## 开发参考

详细技术文档见 [docs/AI_开发指南.md](docs/AI_开发指南.md) 和 [CampusPilot_技术文档_v3.md](CampusPilot_技术文档_v3.md)。
