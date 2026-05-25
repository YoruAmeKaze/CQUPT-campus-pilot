# CampusPilot — 重庆邮电大学个人学业智能助理
## 完整项目技术要求与开发指令文档

> 本文档面向 AI 编程助手（Trae/Cursor）直接使用，包含所有技术细节、接口信息与开发阶段划分。

---

## 1. 项目目标

构建一个运行在个人服务器/虚拟机上的智能 Agent，帮助重庆邮电大学学生：

- 自动抓取**教务系统课表**、**学习通作业**、**数你最灵作业**
- 通过 **Telegram Bot** 主动推送通知（作业截止提醒、新作业提醒）
- 支持 Telegram 双向自然语言查询（"今天作业""本周课表"等）
- 可选：同步课程与作业截止时间至**苹果 iCloud 日历**

---

## 2. 已确认的目标平台信息

### 2.1 教务系统课表

| 项目 | 详情 |
|------|------|
| 访问地址 | `https://jwzx.cqupt.edu.cn/kebiao/kb_stu.php?xh=学号` |
| 是否需要登录 | **不需要**，直接传学号参数即可访问 |
| 页面格式 | HTML 表格，文字可复制 |
| 网络要求 | 需连接校园网或学校 VPN |
| VPN 类型 | 深信服 EasyConnect，地址 `vpn.cqupt.edu.cn` |
| 统一身份认证 | `https://ids.cqupt.edu.cn/authserver/login`（学习通登录需要） |

### 2.2 数你最灵（smartestu.cn）

| 项目 | 详情 |
|------|------|
| 网站地址 | `https://smartestu.cn` |
| 登录接口 | `POST https://smartestu.cn/api/auth/login` |
| 认证方式 | **JWT Bearer Token**，登录后服务器返回 access token，后续请求携带 `Authorization: Bearer <token>` |
| Token 刷新 | `POST https://smartestu.cn/api/auth/refresh`（access token 过期时调用） |
| 作业查询接口 | `POST https://smartestu.cn/api/homework/student/mark/queryHomeworks` |
| 登录字段 | 需抓包确认，预计为 `{ "schoolId": "学校标识", "studentId": "学号", "password": "密码" }` |
| 网络要求 | 公网可访问，**不需要** VPN |

> **开发前置任务**：在浏览器登录 smartestu.cn，F12 → Network → 找到 `POST /api/auth/login` 请求，记录完整的请求体字段名和 `queryHomeworks` 的请求体结构，写入 `config/api_schemas.json`。

### 2.3 学习通（chaoxing.com）

| 项目 | 详情 |
|------|------|
| 登录方式 | 重邮统一身份认证 CAS（`ids.cqupt.edu.cn`） |
| 网络要求 | 需要 VPN 或校园网 |
| 难度提示 | 可能存在图形验证码，优先尝试无验证码路径；若失败降级使用 Playwright |

---

## 3. 技术栈

### 3.1 完整技术选型

| 模块 | 技术选型 | 说明 |
|------|---------|------|
| 后端语言 | Python 3.11+ | 所有核心逻辑 |
| 任务调度 | APScheduler 3.x | 定时轮询，单进程，无需 Celery/Redis |
| 数据库 | SQLite + SQLAlchemy 2.0 | 自用量小，SQLite 完全够用 |
| HTTP 客户端 | httpx（异步）| 爬虫、API 调用 |
| 浏览器自动化 | Playwright（备用）| 仅在 httpx 无法处理验证码时使用 |
| HTML 解析 | BeautifulSoup4 | 解析教务系统课表 HTML 表格 |
| API 服务 | FastAPI + uvicorn | 对外暴露查询接口，Telegram Bot webhook 接收 |
| 通知与交互 | python-telegram-bot 20.x | 主动推送 + 双向自然语言查询 |
| LLM 意图识别 | DeepSeek API（直接调用，不用 LangChain）| 解析用户自然语言指令 |
| 日历同步 | caldav Python 库 | 写入 iCloud 日历（可选 Phase） |
| VPN 接入 | docker-easyconnect（CLI 模式）| 访问教务系统和学习通 |
| 容器化 | Docker + Docker Compose | 一键部署 |
| 配置管理 | python-dotenv + `.env` 文件 | 所有密钥通过环境变量注入，严禁硬编码 |

### 3.2 不使用的技术（及原因）

| 排除项 | 原因 |
|--------|------|
| Celery + Redis | 个人自用，APScheduler 单进程调度已足够 |
| LangChain | 过重，直接调 DeepSeek API 更轻便可控 |
| NoneBot2 / NapCatQQ | QQ 群监听功能推迟至后期，先跑通核心闭环 |
| 微信接入（iLink / wechat-agent-channel）| 合规风险高，用 Telegram Bot 替代 |
| PushPlus / 企业微信机器人 | Telegram Bot 已覆盖推送需求 |

---

## 4. 系统架构

```
┌──────────────────────────────────────────────────────┐
│                  Docker Compose                       │
│                                                       │
│  ┌─────────────────────────────────────────────────┐  │
│  │                   app 容器                       │  │
│  │                                                  │  │
│  │   FastAPI (uvicorn)                              │  │
│  │     └── /webhook  ← Telegram Bot 回调            │  │
│  │     └── /api/*    ← 内部查询接口                 │  │
│  │                                                  │  │
│  │   APScheduler                                    │  │
│  │     ├── 每30分钟  → 数你最灵爬虫                 │  │
│  │     ├── 每1小时   → 学习通爬虫                   │  │
│  │     ├── 每天6:00  → 教务课表爬虫（变动时更新）   │  │
│  │     └── 每天8:00  → 推送今日课表和待办作业       │  │
│  │                                                  │  │
│  │   SQLite (data/campus.db)                        │  │
│  │     ├── users                                    │  │
│  │     ├── courses                                  │  │
│  │     ├── assignments                              │  │
│  │     └── notifications                            │  │
│  └─────────────────────────────────────────────────┘  │
│                                                       │
│  ┌──────────────────────┐                             │
│  │  easyconnect 容器    │  ← 提供校园网 VPN           │
│  │  (hagb/docker-       │                             │
│  │   easyconnect:cli)   │                             │
│  └──────────────────────┘                             │
└──────────────────────────────────────────────────────┘
         ↑↓ Webhook (需公网 IP 或 frp 内网穿透)
    Telegram Bot API
         ↑↓
      用户手机 Telegram
```

---

## 5. 项目目录结构

```
campus-pilot/
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── .env                    # 本地实际配置，不提交 Git
├── requirements.txt
│
├── app/
│   ├── main.py             # FastAPI 入口 + APScheduler 启动
│   ├── config.py           # 从环境变量加载配置
│   │
│   ├── db/
│   │   ├── models.py       # SQLAlchemy 数据模型
│   │   └── session.py      # 数据库连接
│   │
│   ├── spiders/
│   │   ├── jwxt.py         # 教务系统课表爬虫
│   │   ├── chaoxing.py     # 学习通爬虫
│   │   └── smartestu.py    # 数你最灵爬虫
│   │
│   ├── scheduler/
│   │   └── jobs.py         # APScheduler 定时任务定义
│   │
│   ├── bot/
│   │   ├── telegram_bot.py # Telegram Bot 初始化与 webhook 处理
│   │   ├── handlers.py     # 用户消息处理逻辑
│   │   └── notifier.py     # 主动推送逻辑
│   │
│   ├── llm/
│   │   └── intent.py       # DeepSeek API 意图识别
│   │
│   ├── calendar/
│   │   └── caldav_sync.py  # iCloud CalDAV 同步（可选）
│   │
│   └── api/
│       └── routes.py       # 内部查询 API 路由
│
├── data/                   # SQLite 文件存放（挂载为 Docker volume）
└── config/
    └── api_schemas.json    # 各平台接口字段记录（开发前手动填写）
```

---

## 6. 数据模型

```python
# app/db/models.py

class User(Base):
    __tablename__ = "users"
    id              = Column(Integer, primary_key=True)
    telegram_id     = Column(String, unique=True)   # Telegram chat_id
    student_id      = Column(String)                # 学号
    cqupt_password  = Column(String)                # 统一身份认证密码（加密存储）
    smartestu_token = Column(String)                # 数你最灵 JWT token（动态刷新）
    caldav_url      = Column(String, nullable=True)
    caldav_password = Column(String, nullable=True) # Apple 应用专用密码
    created_at      = Column(DateTime, default=datetime.utcnow)

class Course(Base):
    __tablename__ = "courses"
    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey("users.id"))
    name        = Column(String)        # 课程名
    teacher     = Column(String)
    location    = Column(String)        # 教室
    day_of_week = Column(Integer)       # 1=周一, 7=周日
    start_week  = Column(Integer)
    end_week    = Column(Integer)
    start_slot  = Column(Integer)       # 第几节开始
    end_slot    = Column(Integer)       # 第几节结束
    start_time  = Column(String)        # "08:30"
    end_time    = Column(String)        # "10:05"

class Assignment(Base):
    __tablename__ = "assignments"
    id           = Column(Integer, primary_key=True)
    user_id      = Column(Integer, ForeignKey("users.id"))
    title        = Column(String)
    description  = Column(Text, nullable=True)
    source       = Column(String)       # "chaoxing" / "smartestu" / "qq"
    course_name  = Column(String, nullable=True)
    due_time     = Column(DateTime, nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)
    notified     = Column(Boolean, default=False)
    remote_id    = Column(String, nullable=True)  # 平台原始 ID，用于去重

class Notification(Base):
    __tablename__ = "notifications"
    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"))
    content    = Column(Text)
    sent_at    = Column(DateTime)
    type       = Column(String)         # "new_assignment" / "deadline_reminder" / "daily_summary"
```

---

## 7. 各爬虫模块实现规范

### 7.1 教务系统课表爬虫（`spiders/jwxt.py`）

```
目标 URL：https://jwzx.cqupt.edu.cn/kebiao/kb_stu.php?xh={student_id}
方法：httpx.AsyncClient GET 请求
解析：BeautifulSoup4 解析 HTML 表格
网络：通过 docker-easyconnect 容器的网络（在 docker-compose 中配置 network_mode 或代理）
频率：每天早上 6:00 执行一次（学期初可能变动）
去重：对比现有 Course 记录，仅在内容变化时更新
输出：写入 courses 表
```

课表 HTML 表格解析要点：
- 表头为节次（第1-2节、第3-4节……）
- 列为周一至周日
- 单元格内容格式通常为：课程名\n教师\n地点\n周次

### 7.2 数你最灵爬虫（`spiders/smartestu.py`）

```
登录流程：
  1. POST https://smartestu.cn/api/auth/login
     请求体：根据 config/api_schemas.json 中记录的字段
     响应：获取 access_token 和 refresh_token，存入 users.smartestu_token

  2. 后续请求统一添加 Header：
     Authorization: Bearer {access_token}

  3. Token 刷新：当任意接口返回 401 时，
     调用 POST https://smartestu.cn/api/auth/refresh
     更新 access_token

作业查询：
  POST https://smartestu.cn/api/homework/student/mark/queryHomeworks
  请求体：根据 config/api_schemas.json 中记录的字段
  响应：解析作业列表，提取 title、due_time、course_name

去重：使用 remote_id 字段，已存在则跳过
频率：每 30 分钟执行一次
```

### 7.3 学习通爬虫（`spiders/chaoxing.py`）

```
登录流程（CAS 方式）：
  1. GET https://ids.cqupt.edu.cn/authserver/login?service=...
     获取登录页面，提取 lt、dllt、execution 等隐藏字段
  
  2. POST https://ids.cqupt.edu.cn/authserver/login
     提交 username、password 及隐藏字段
     若有图形验证码，先 GET 验证码图片，用 ddddocr 库识别
  
  3. 跟随重定向，最终获得学习通 session cookie

作业查询：
  GET https://mooc1.chaoxing.com/mooc-ans/visit/courses/list（或相似接口）
  解析课程列表 → 遍历每门课获取未完成作业

网络：需要 VPN（通过 docker-easyconnect）
频率：每 1 小时执行一次
容错：登录失效时自动重新登录，重试 3 次后发送 Telegram 告警
```

---

## 8. Telegram Bot 规范（`bot/`）

### 8.1 交互命令

| 命令 / 自然语言 | 功能 |
|---------------|------|
| `/start` | 初始化用户，引导绑定学号 |
| `/today` | 今日课表 + 今日截止作业 |
| `/week` | 本周课表 |
| `/assignments` | 所有未完成作业列表 |
| `/upcoming` | 未来 3 天截止的作业 |
| 自然语言（任意文本）| 传入 DeepSeek API 识别意图后路由到对应查询 |

### 8.2 主动推送策略

| 时机 | 内容 |
|------|------|
| 每天 08:00 | 今日课表 + 今日/明日截止作业摘要 |
| 新作业被抓取到 | 立即推送"【新作业】课程名 - 标题，截止 xx月xx日" |
| 作业截止前 24 小时 | 推送截止提醒 |
| 作业截止前 1 小时 | 再次提醒 |

### 8.3 Webhook 部署

- 生产环境使用 Telegram Webhook 模式（需要公网 HTTPS 地址）
- 若无公网 IP，使用 frp 内网穿透或 ngrok
- 开发环境可使用 Polling 模式（代码中通过环境变量 `BOT_MODE=polling/webhook` 切换）

---

## 9. LLM 意图识别（`llm/intent.py`）

使用 DeepSeek API，**不使用 LangChain**，直接调用 HTTP 接口。

```python
# 意图分类目标
INTENTS = {
    "query_today":      "查询今天的课表或作业",
    "query_week":       "查询本周或某周的课表",
    "query_tomorrow":   "查询明天的内容",
    "query_deadline":   "查询某门课的作业截止时间",
    "query_all":        "查询所有未完成作业",
    "unknown":          "无法识别"
}

# 调用方式
# POST https://api.deepseek.com/chat/completions
# 使用 system prompt 限定意图分类输出为 JSON 格式
# 模型：deepseek-chat
```

System Prompt 模板（供 Trae 参考）：
```
你是一个大学生学业助手，负责理解用户的查询意图。
用户输入的是中文自然语言，请将其分类为以下意图之一：
query_today / query_week / query_tomorrow / query_deadline / query_all / unknown

同时提取关键实体：
- course_name: 涉及的课程名（如有）
- date: 涉及的日期（如有，转换为 YYYY-MM-DD 格式）

仅返回 JSON，格式：
{"intent": "...", "course_name": null, "date": null}
```

---

## 10. 环境变量配置（`.env.example`）

```env
# 基础配置
STUDENT_ID=STUDENT_ID
CQUPT_PASSWORD=你的统一身份认证密码

# 数你最灵
SMARTESTU_STUDENT_ID=你的学号
SMARTESTU_PASSWORD=你的数你最灵密码
SMARTESTU_SCHOOL_ID=待抓包确认

# Telegram Bot
TELEGRAM_BOT_TOKEN=从 @BotFather 获取
TELEGRAM_WEBHOOK_URL=https://你的域名/webhook
BOT_MODE=webhook   # 或 polling

# DeepSeek API
DEEPSEEK_API_KEY=你的 DeepSeek API Key

# VPN（docker-easyconnect）
VPN_HOST=vpn.cqupt.edu.cn
VPN_USERNAME=你的统一身份认证账号
VPN_PASSWORD=你的统一身份认证密码

# iCloud 日历（可选）
CALDAV_URL=https://caldav.icloud.com/
CALDAV_USERNAME=你的 Apple ID
CALDAV_PASSWORD=应用专用密码（在 Apple ID 设置中生成）

# 应用配置
TZ=Asia/Shanghai
DATABASE_URL=sqlite:///data/campus.db
```

---

## 11. Docker Compose 配置

```yaml
# docker-compose.yml
version: "3.9"

services:
  app:
    build: .
    restart: unless-stopped
    volumes:
      - ./data:/app/data
      - ./.env:/app/.env
    ports:
      - "8000:8000"
    depends_on:
      - easyconnect
    network_mode: "service:easyconnect"   # 共享 VPN 容器网络
    environment:
      - TZ=Asia/Shanghai

  easyconnect:
    image: hagb/docker-easyconnect:cli
    restart: unless-stopped
    devices:
      - /dev/net/tun
    cap_add:
      - NET_ADMIN
    environment:
      - EC_VER=7.6.3
      - CLI_OPTS=-d ${VPN_HOST} -u ${VPN_USERNAME} -p ${VPN_PASSWORD}
    ports:
      - "8000:8000"   # 将 app 端口暴露出来
```

> **注意**：`network_mode: "service:easyconnect"` 使 app 容器通过 VPN 容器访问网络，数你最灵不需要 VPN，httpx 可直接连公网，无影响。

---

## 12. 开发阶段划分

### Phase 1 — 项目骨架（约 1 天）
- 初始化 FastAPI 项目结构
- 实现 `config.py`（读取 `.env` 环境变量）
- 创建 SQLAlchemy 数据模型（`users`, `courses`, `assignments`, `notifications`）
- 数据库初始化脚本（`alembic` 或手动 `create_all`）
- 编写 `docker-compose.yml` 和 `Dockerfile`
- 验收标准：`docker compose up` 能启动，`GET /health` 返回 200

### Phase 2 — 教务课表爬虫（约 1 天）
- 实现 `spiders/jwxt.py`
- httpx 请求课表页面（先不走 VPN，测试公网是否可访问；不行再接 VPN）
- BeautifulSoup4 解析 HTML 表格，写入 `courses` 表
- APScheduler 注册定时任务（每天 6:00）
- 添加 `/api/courses/today` 和 `/api/courses/week` 查询接口
- 验收标准：手动触发爬虫，数据库中出现本学期完整课表

### Phase 3 — 数你最灵爬虫（约 1-2 天）
- **前置**：手动抓包，填写 `config/api_schemas.json` 中登录和查询的请求体字段
- 实现 `spiders/smartestu.py`
  - 登录获取 JWT token，持久化到 `users` 表
  - 自动刷新 token（401 时调用 refresh 接口）
  - 定时拉取作业列表，去重后写入 `assignments` 表
- APScheduler 注册任务（每 30 分钟）
- 验收标准：数据库中出现当前学期的数你最灵作业

### Phase 4 — Telegram Bot 基础（约 1-2 天）
- 配置 Telegram Bot（`bot/telegram_bot.py`）
- 实现 `/start` 绑定流程（用户输入学号 → 存入数据库）
- 实现基础命令：`/today`, `/week`, `/assignments`
- 实现主动推送：`notifier.py` 每天 8:00 发送日报
- 新作业入库时立即触发推送
- 验收标准：Telegram 能收到今日课表和作业推送

### Phase 5 — 学习通爬虫（约 2-3 天）
- 实现 `spiders/chaoxing.py`
- CAS 登录流程（处理隐藏字段和可能的图形验证码，使用 `ddddocr` 识别）
- 确认 docker-easyconnect 正常工作
- 拉取作业列表，去重写入 `assignments` 表
- 验收标准：学习通新作业能被自动检测并推送

### Phase 6 — 自然语言查询（约 1 天）
- 实现 `llm/intent.py`（直接调用 DeepSeek API）
- Telegram 收到非命令消息时，走意图识别 → 路由到对应查询函数
- 验收标准：发送"明天有什么课"能得到正确回复

### Phase 7 — 截止时间提醒优化（约 0.5 天）
- APScheduler 添加提醒任务：每小时扫描 24h 内截止的作业
- 推送截止提醒，更新 `notified` 字段避免重复推送
- 验收标准：作业截止前 24h 和 1h 分别收到提醒

### Phase 8 — iCloud 日历同步（可选，约 1-2 天）
- 实现 `calendar/caldav_sync.py`
- 使用 `caldav` 库连接 iCloud（需 Apple 应用专用密码）
- 将 `courses` 表写入重复性日历事件（整学期）
- 将 `assignments` 表截止时间写入单次事件
- 验收标准：iPhone 日历出现课程和作业事件

---

## 13. 注意事项与约束

### 安全性
- 所有密码、Token、API Key **必须通过 `.env` 环境变量注入，严禁硬编码**
- SQLite 中存储的密码应加密（使用 `cryptography` 库的 Fernet 对称加密）
- `.env` 文件加入 `.gitignore`，不得提交到代码仓库

### 时区
- 所有时间处理统一使用北京时间（`UTC+8`，`Asia/Shanghai`）
- 数据库存储 UTC 时间，展示时转换为北京时间
- Docker 容器设置 `TZ=Asia/Shanghai`

### 容错性
- 所有爬虫用 `try/except` 包裹，失败时写日志并发送 Telegram 告警
- 登录失效时自动重试（最多 3 次），仍失败则告警用户
- 日历同步失败不影响主流程，独立重试

### 合规说明
- 本项目仅供个人学习使用
- 爬虫请求间隔不少于 1 秒，避免对服务器造成压力
- 不得用于批量采集、传播他人数据

---

## 14. 待确认事项（开发前需手动完成）

| 事项 | 操作步骤 |
|------|---------|
| 数你最灵登录请求体字段 | 浏览器登录 smartestu.cn，F12 → Network → POST /api/auth/login → 查看 Request Body |
| 数你最灵作业查询请求体 | 登录后访问作业页面，F12 → Network → POST /api/homework/student/mark/queryHomeworks → 查看 Request Body 和 Response 结构 |
| 数你最灵学校 ID 字段 | 登录请求体中选择学校对应的 schoolId 值 |
| 课表 HTML 结构 | 挂 VPN 访问课表页面，F12 → Elements 查看表格结构，或 View Source 确认节次/星期的 HTML 标签和 class |
| VPN 连接测试 | 在服务器上测试 docker-easyconnect 能否成功连接 `vpn.cqupt.edu.cn` |
