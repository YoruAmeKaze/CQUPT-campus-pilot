# CampusPilot

**重庆邮电大学个人学业智能助理** — 自动抓取课表、作业，空教室查询，通过 Web 界面和飞书机器人管理学业

---

## 功能

- 📅 **课表管理** — 自动从教务系统抓取课表，周视图展示，支持多周次/多地点
- 📝 **作业提醒** — 自动抓取学习通、数你最灵作业，截止时间前自动推送提醒
- ✅ **待办管理** — Web 端和飞书端双向创建，支持自然语言、到期提醒
- 🏫 **空教室查询** — 查询任意时段空闲教室，支持按教学楼/容量/类型筛选
- 🧠 **AI 智能查询** — 自然语言问："这周有什么作业？""今天上午有空教室吗？"
- 🗺️ **行程规划** — 说"今天上午想去自习"，自动查课表+推荐空教室
- 🤖 **飞书机器人** — 双向对话，查询课表/作业/待办/空教室
- 🔔 **自定义提醒** — 设置每天/每周/每月的定时推送（如"早上8点提醒我吃药"）
- ⚙️ **自定义 AI 提供商** — 支持 DeepSeek、Ollama 本地模型、任意 OpenAI 兼容 API
- 📊 **Web 仪表盘** — 可视化学业概览，9 个功能页面

---

## 快速开始

### 前置条件

| 软件 | 版本要求 | 下载 |
|------|----------|------|
| Python | 3.11+ | https://www.python.org/downloads/ |
| Node.js | 18+（可选，仅前端需要） | https://nodejs.org/ |

### 一键启动

```bat
# 双击 start.bat，或在项目目录终端执行
start.bat
```

脚本自动完成：
1. 检测 Python 和 Node.js 环境
2. 创建虚拟环境并安装依赖
3. 自动生成加密密钥
4. 启动后端 API (http://localhost:8000)
5. 启动前端界面 (http://localhost:3000)

启动后浏览器打开 **http://localhost:3000** 即可使用。

### 如果双击闪退

在终端手动运行查看错误：

```cmd
# 打开 cmd（Win+R → 输入 cmd）
cd /d D:\vibeCoding\campusPilot
start.bat
```

常见问题：
- **"Python not found"**：安装 Python 后，在系统设置中搜索"应用执行别名"，关闭 `python.exe` 和 `python3.exe` 的开关，重启
- **"No module named uvicorn"**：依赖安装失败，运行以下命令手动安装：

```cmd
cd /d D:\vibeCoding\campusPilot
venv\Scripts\activate
pip install fastapi uvicorn python-dotenv pydantic-settings sqlalchemy aiosqlite alembic httpx beautifulsoup4 lxml playwright ddddocr apscheduler cryptography openai
```

---

## 首次使用配置

打开 http://localhost:3000，进入 **设置** 页面：

### 必填配置

| 配置项 | 说明 |
|--------|------|
| 学号 | 用于教务系统课表抓取 |
| DeepSeek API Key | AI 查询功能（[获取](https://platform.deepseek.com/)）|

### 数据源（按需）

| 数据源 | 说明 |
|--------|------|
| 学习通账号/密码 | 自动抓取学习通作业 |
| 数你最灵账号/密码 | 自动抓取数你最灵作业 |

### 推送配置

#### 飞书群机器人（推荐，最简单）

1. 打开飞书，进入任意群聊 → 群设置 → 群机器人 → 添加自定义机器人
2. 复制 Webhook URL，粘贴到 CampusPilot 设置页面

#### Bark iOS 推送

1. App Store 搜索 Bark 下载
2. 打开 App 复制 Key，粘贴到设置页面

#### 飞书应用双向对话（高级，需公网服务器）

支持在飞书里直接和机器人对话查询课表/作业/待办/空教室。
需要一台有公网 IP 的服务器做 SSH 隧道中转。
配置步骤见设置页面引导。

---

## 页面说明

| 页面 | 路由 | 功能 |
|------|------|------|
| 仪表盘 | `/` | 今日概览、课表、作业统计、数据源状态 |
| 课表 | `/courses` | 周视图课表网格，支持切换周次 |
| 作业 | `/assignments` | 作业列表，筛选、标记完成、删除 |
| 待办 | `/todos` | 待办列表，创建、完成、筛选、提醒开关 |
| 空教室 | `/rooms` | 按教学楼/时段筛选空闲教室 |
| 行程安排 | `/schedules` | 每日/每周行程规划 |
| 工具 | `/tools` | 功能入口集合 |
| 通知 | `/notifications` | 推送历史记录 |
| 设置 | `/settings` | 数据源、AI 配置、提醒设置、系统配置 |

---

## 关闭服务

| 启动方式 | 关闭方法 |
|----------|----------|
| start.bat | 关闭 CampusPilot-Backend 和 CampusPilot-Frontend 的终端窗口 |
| Docker | `docker compose down` |

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy (asyncio) / APScheduler |
| 前端 | React 18 / TypeScript / Vite / Tailwind CSS / shadcn/ui |
| 数据库 | SQLite（零配置） |
| AI | DeepSeek / Ollama / 任意 OpenAI 兼容 API |
| 爬虫 | Playwright / httpx / BeautifulSoup |
| 推送 | 飞书机器人 / 飞书 App / Bark iOS |
| 部署 | Docker / Docker Compose |

---

## 项目结构

```
CampusPilot/
├── start.bat                # Windows 一键启动
├── docker-start.bat         # Docker 一键启动
├── .env                     # 环境变量
│
├── app/                     # 后端代码
│   ├── main.py              # FastAPI 入口
│   ├── api/                 # 11 个 API 路由模块
│   ├── crawlers/            # 4 个爬虫模块
│   ├── db/                  # 9 个数据模型
│   ├── llm/                 # AI 模块（12 个工具 + Text-to-SQL）
│   ├── notifications/       # 推送服务
│   ├── scheduler/           # 8 个定时任务
│   └── services/            # 7 个业务服务
│
├── frontend/                # React 前端
├── docs/                    # 开发文档
├── scripts/                 # 部署脚本
└── tests/                   # 测试
```

---

## 定时任务

| 任务 | 频率 | 说明 |
|------|------|------|
| 课表同步 | 每天 06:00 | 从教务系统抓取最新课表 |
| 每日课表推送 | 每天 07:50 | 推送今日课表到手机 |
| 作业同步 | 每 30 分钟 | 同步学习通 + 数你最灵作业 |
| 作业截止检查 | 每小时 | 即将截止时推送提醒 |
| 教室数据刷新 | 每天 04:00 | 全量刷新空教室数据 |
| 自定义提醒 | 每分钟 | 检查到期的自定义定时提醒 |
| 待办提醒 | 每 5 分钟 | 检查启用了提醒的待办事项 |
| 作业清理 | 每天 03:00 | 清理过期的已完成作业 |

---

## 开发参考

详细技术文档见 [docs/AI_开发指南.md](docs/AI_开发指南.md)。
