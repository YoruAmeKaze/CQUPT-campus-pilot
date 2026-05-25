# CampusPilot — 重庆邮电大学个人学业智能助理
## 完整项目技术要求与开发指令文档 v2.0

> 本文档面向 AI 编程助手（Trae/Cursor）直接使用，包含所有技术细节、接口信息与开发阶段划分。

---

## 1. 项目目标

构建一个运行在**个人笔记本或服务器虚拟机**上的智能 Agent + Web 管理界面，帮助重庆邮电大学学生：

- 自动抓取**教务系统课表**、**学习通作业**、**数你最灵作业**
- 通过**企业微信应用**主动推送通知（作业截止提醒、新作业提醒、每日课表）
- 支持企业微信双向自然语言查询（"今天作业""本周课表"等）
- 提供**Web 管理仪表盘**，可视化查看课表、作业，自助添加/管理数据源配置
- 可选：同步课程与作业截止时间至**苹果 iCloud 日历**

---

## 2. 运行环境说明

### 模式 A：笔记本运行（推荐个人使用）

- 直接在笔记本上安装 Docker Desktop
- 校园网访问：连接学校 WiFi 或手动开启深信服 EasyConnect 客户端
- **不需要** docker-easyconnect 容器（笔记本本身挂 VPN 即可）
- 企业微信回调需要公网地址：使用 **cpolar** 或 **frp** 内网穿透

### 模式 B：服务器/虚拟机运行

- Linux 服务器（Ubuntu 20.04+）
- 使用 **docker-easyconnect** 容器自动维持 VPN 连接
- 若有公网 IP 则直接配置；否则同样需要内网穿透

> `docker-compose.yml` 提供两个 profile：`laptop` 和 `server`，通过环境变量 `DEPLOY_MODE` 切换。

---

## 3. 已确认的目标平台信息

### 3.1 教务系统课表

| 项目 | 详情 |
|------|------|
| 访问地址 | `https://jwzx.cqupt.edu.cn/kebiao/kb_stu.php?xh=学号` |
| 是否需要登录 | **不需要**，直接传学号参数即可访问 |
| 页面格式 | HTML 表格，文字可复制 |
| 网络要求 | 需连接校园网或学校 VPN（`vpn.cqupt.edu.cn`，深信服 EasyConnect） |
| 统一身份认证 | `https://ids.cqupt.edu.cn/authserver/login` |

### 3.2 数你最灵（smartestu.cn）

| 项目 | 详情 |
|------|------|
| 网站地址 | `https://smartestu.cn` |
| 登录接口 | `POST https://smartestu.cn/api/auth/login` |
| 认证方式 | **JWT Bearer Token**，登录后获取 access_token，后续请求携带 `Authorization: Bearer <token>` |
| Token 刷新 | `POST https://smartestu.cn/api/auth/refresh`（401 时调用） |
| 作业查询接口 | `POST https://smartestu.cn/api/homework/student/mark/queryHomeworks` |
| 网络要求 | 公网可访问，**不需要 VPN** |

> **开发前置**：登录 smartestu.cn，F12 → Network → Fetch/XHR，抓取登录请求体字段和作业查询请求体/响应结构，填入 `config/api_schemas.json`。

### 3.3 学习通（chaoxing.com）

| 项目 | 详情 |
|------|------|
| 登录方式 | **公网独立账号密码**（非统一身份认证，直接登录 chaoxing.com） |
| 验证码类型 | **滑块验证码**（非图形验证码） |
| 滑块处理方案 | 优先用 `playwright` + `ddddocr` 计算滑块偏移量自动滑动；若识别率低，接入打码平台（超级鹰或 2captcha） |
| 网络要求 | 公网可访问，**不需要 VPN** |
| 登录接口 | `https://passport2.chaoxing.com/fanyalogin`（手机号/邮箱登录） |

---

## 4. 通知与交互通道：企业微信

### 为什么选企业微信

| 对比项 | 企业微信应用 | 个人微信机器人 | Telegram Bot |
|--------|------------|--------------|-------------|
| 合规性 | ✅ 官方 API | ❌ 违反服务条款 | ✅ 合规 |
| 国内可用 | ✅ 直接使用 | ✅ | ❌ 需翻墙 |
| 双向交互 | ✅ | ⚠️ 不稳定 | ✅ |
| 主动推送 | ✅ | ⚠️ 风险高 | ✅ |
| 封号风险 | 无 | 极高 | 无 |

### 企业微信配置步骤（用户手动完成）

1. 访问 `work.weixin.qq.com`，注册企业（个人也可注册，填写任意企业名）
2. 进入「应用管理」→「自建应用」→ 创建应用，记录：
   - `CORP_ID`（企业 ID）
   - `AGENT_ID`（应用 ID）
   - `AGENT_SECRET`（应用密钥）
3. 在应用设置中配置「接收消息」的回调 URL（需要公网 HTTPS 地址）
4. 将自己的企业微信账号加入应用可见范围

### 企业微信 API 使用

```
获取 access_token：
  GET https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid=ID&corpsecret=SECRET

发送消息：
  POST https://qyapi.weixin.qq.com/cgi-bin/message/send
  Body: { "touser": "@all", "msgtype": "text", "agentid": AGENT_ID, "text": {"content": "..."} }

接收用户消息（回调）：
  企业微信推送 POST 到你配置的回调 URL，需要验证签名
  使用官方 Python SDK：pip install wechatpy[crypto]
```

---

## 5. 技术栈

### 5.1 后端

| 模块 | 技术选型 | 说明 |
|------|---------|------|
| 语言 | Python 3.11+ | 所有核心逻辑 |
| Web 框架 | FastAPI + uvicorn | API 服务 + 企业微信回调 Webhook |
| 任务调度 | APScheduler 3.x | 定时轮询，单进程，无需 Celery/Redis |
| 数据库 | SQLite + SQLAlchemy 2.0 | 自用量小，SQLite 完全够用 |
| 数据库迁移 | Alembic | 管理数据库版本 |
| HTTP 客户端 | httpx（异步）| 爬虫、API 调用 |
| 浏览器自动化 | Playwright | 处理学习通滑块验证码 |
| 滑块识别 | ddddocr | 计算滑块偏移量 |
| HTML 解析 | BeautifulSoup4 | 解析教务系统课表 HTML |
| 企业微信 | wechatpy[crypto] | 消息发送与回调验签 |
| LLM 意图识别 | DeepSeek API（直接 HTTP 调用）| 自然语言指令解析，不使用 LangChain |
| 日历同步 | caldav | 写入 iCloud（可选 Phase） |
| 配置管理 | python-dotenv | 环境变量注入 |
| 密码加密 | cryptography（Fernet）| 存储账号密码 |

### 5.2 前端（Web 管理界面）

| 模块 | 技术选型 | 说明 |
|------|---------|------|
| 框架 | React 18 + TypeScript | |
| 构建工具 | Vite | |
| 组件库 | shadcn/ui | 基于 Radix UI，高度可定制 |
| 样式 | Tailwind CSS | |
| 图表 | Recharts | 作业统计、截止时间分布 |
| 路由 | React Router v6 | |
| 状态管理 | Zustand | 轻量，够用 |
| HTTP | axios | 请求后端 API |
| 主题 | 深色系仪表盘风格（Dark Mode 为默认）| |

### 5.3 基础设施

| 模块 | 技术 | 说明 |
|------|------|------|
| 容器化 | Docker + Docker Compose | |
| VPN（服务器模式）| docker-easyconnect CLI 版 | `hagb/docker-easyconnect:cli` |
| 内网穿透 | cpolar 或 frp | 企业微信回调需要公网 HTTPS |
| 反向代理 | Nginx（可选）| 前后端统一端口 |

### 5.4 不使用的技术

| 排除项 | 原因 |
|--------|------|
| Celery + Redis | 个人自用，APScheduler 单进程足够 |
| LangChain | 过重，直接调 API 更轻便 |
| NoneBot2 / NapCatQQ | QQ 群监听推迟至后期 |
| 个人微信机器人 | 合规风险极高 |
| Telegram Bot | 国内需翻墙，改用企业微信 |

---

## 6. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Docker Compose                          │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                     app 容器                          │   │
│  │                                                      │   │
│  │   FastAPI (port 8000)                                │   │
│  │     ├── /webhook/wxwork   ← 企业微信回调              │   │
│  │     ├── /api/courses      ← 课表查询                  │   │
│  │     ├── /api/assignments  ← 作业查询                  │   │
│  │     └── /api/config       ← 数据源配置 CRUD           │   │
│  │                                                      │   │
│  │   APScheduler                                        │   │
│  │     ├── 每30分钟  → 数你最灵爬虫                      │   │
│  │     ├── 每1小时   → 学习通爬虫                        │   │
│  │     ├── 每天6:00  → 教务课表爬虫                      │   │
│  │     ├── 每天8:00  → 推送今日日报                      │   │
│  │     └── 每小时    → 截止提醒扫描                      │   │
│  │                                                      │   │
│  │   SQLite (data/campus.db)                            │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────┐   ┌──────────────────────────────┐    │
│  │  frontend 容器   │   │  easyconnect 容器             │    │
│  │  React (port     │   │  (仅 server 模式启用)         │    │
│  │  3000 → 80)      │   │                              │    │
│  └──────────────────┘   └──────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
         ↕ HTTPS 回调（cpolar/frp 内网穿透）
    企业微信服务器
         ↕
      用户手机企业微信 App
```

---

## 7. 项目目录结构

```
campus-pilot/
├── docker-compose.yml
├── docker-compose.laptop.yml    # 笔记本模式覆盖配置（无 easyconnect）
├── Dockerfile                   # 后端
├── frontend/
│   ├── Dockerfile               # 前端
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── pages/
│       │   ├── Dashboard.tsx    # 仪表盘首页
│       │   ├── Courses.tsx      # 课表页面
│       │   ├── Assignments.tsx  # 作业列表页面
│       │   └── Settings.tsx     # 数据源配置页面
│       ├── components/
│       │   ├── ui/              # shadcn/ui 组件
│       │   ├── CourseTable.tsx  # 周课表组件
│       │   ├── AssignmentCard.tsx
│       │   └── SourceConfigForm.tsx  # 数据源配置表单
│       └── store/
│           └── useAppStore.ts   # Zustand 全局状态
│
├── .env.example
├── .env
├── requirements.txt
├── alembic/                     # 数据库迁移
│   └── versions/
│
├── app/
│   ├── main.py                  # FastAPI 入口 + APScheduler 启动
│   ├── config.py                # 环境变量加载
│   │
│   ├── db/
│   │   ├── models.py            # SQLAlchemy 数据模型
│   │   └── session.py           # 数据库连接
│   │
│   ├── spiders/
│   │   ├── base.py              # 爬虫基类（重试、异常处理）
│   │   ├── jwxt.py              # 教务系统课表
│   │   ├── chaoxing.py          # 学习通（滑块验证码）
│   │   └── smartestu.py         # 数你最灵（JWT）
│   │
│   ├── scheduler/
│   │   └── jobs.py              # APScheduler 任务定义
│   │
│   ├── wxwork/
│   │   ├── client.py            # 企业微信消息发送
│   │   ├── webhook.py           # 回调验签与消息解析
│   │   └── notifier.py          # 推送逻辑（日报、新作业、截止提醒）
│   │
│   ├── llm/
│   │   └── intent.py            # DeepSeek 意图识别
│   │
│   ├── calendar/
│   │   └── caldav_sync.py       # iCloud CalDAV 同步（可选）
│   │
│   └── api/
│       ├── courses.py           # 课表 CRUD 接口
│       ├── assignments.py       # 作业 CRUD 接口
│       └── config.py            # 数据源配置接口
│
├── data/                        # SQLite 文件（Docker volume 挂载）
└── config/
    └── api_schemas.json         # 各平台接口字段（开发前手动填写）
```

---

## 8. 数据模型

```python
# app/db/models.py

class User(Base):
    __tablename__ = "users"
    id                  = Column(Integer, primary_key=True)
    wxwork_userid       = Column(String, unique=True)    # 企业微信用户 ID
    student_id          = Column(String)                 # 学号
    created_at          = Column(DateTime, default=func.now())

class DataSource(Base):
    """用户在 Web UI 中添加的数据源配置"""
    __tablename__ = "data_sources"
    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, ForeignKey("users.id"))
    type          = Column(String)      # "jwxt" | "chaoxing" | "smartestu"
    name          = Column(String)      # 用户自定义名称，如"学习通-大三上"
    enabled       = Column(Boolean, default=True)
    # 加密存储的凭据 JSON，字段因 type 而异
    credentials   = Column(Text)        # Fernet 加密后的 JSON 字符串
    last_sync     = Column(DateTime, nullable=True)
    sync_status   = Column(String, default="pending")  # pending/ok/error
    error_message = Column(String, nullable=True)
    created_at    = Column(DateTime, default=func.now())

class Course(Base):
    __tablename__ = "courses"
    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, ForeignKey("users.id"))
    source_id     = Column(Integer, ForeignKey("data_sources.id"))
    name          = Column(String)
    teacher       = Column(String, nullable=True)
    location      = Column(String, nullable=True)
    day_of_week   = Column(Integer)    # 1=周一 … 7=周日
    start_week    = Column(Integer)
    end_week      = Column(Integer)
    start_slot    = Column(Integer)    # 第几节开始
    end_slot      = Column(Integer)
    start_time    = Column(String)     # "08:30"
    end_time      = Column(String)     # "10:05"

class Assignment(Base):
    __tablename__ = "assignments"
    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, ForeignKey("users.id"))
    source_id     = Column(Integer, ForeignKey("data_sources.id"))
    remote_id     = Column(String, nullable=True)    # 平台原始 ID，用于去重
    title         = Column(String)
    description   = Column(Text, nullable=True)
    course_name   = Column(String, nullable=True)
    due_time      = Column(DateTime, nullable=True)
    is_completed  = Column(Boolean, default=False)
    created_at    = Column(DateTime, default=func.now())
    # 推送状态
    notified_new          = Column(Boolean, default=False)
    notified_24h          = Column(Boolean, default=False)
    notified_1h           = Column(Boolean, default=False)

class Notification(Base):
    __tablename__ = "notifications"
    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, ForeignKey("users.id"))
    type          = Column(String)     # "new_assignment"|"deadline_24h"|"deadline_1h"|"daily_summary"
    content       = Column(Text)
    sent_at       = Column(DateTime, default=func.now())
    success       = Column(Boolean, default=True)

class Todo(Base):
    """待办事项（支持通过企业微信自然语言创建）"""
    __tablename__ = "todos"
    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, ForeignKey("users.id"))
    title         = Column(String, nullable=False)
    description   = Column(Text, nullable=True)
    due_time      = Column(DateTime, nullable=True)
    priority      = Column(String, default="normal")  # "low"|"normal"|"high"
    is_completed  = Column(Boolean, default=False)
    source        = Column(String, default="manual")  # "manual"|"llm"
    created_at    = Column(DateTime, default=func.now())
    updated_at    = Column(DateTime, default=func.now(), onupdate=func.now())
```

---

## 9. Web 管理界面规范

### 9.1 页面结构

```
侧边栏导航：
├── 🏠 仪表盘        Dashboard
├── 📅 课表          Courses
├── 📝 作业          Assignments
├── ✅ 待办          Todos
└── ⚙️  设置          Settings
    ├── 数据源管理
    ├── 通知设置
    └── 账号绑定

### 9.6 待办事项页面 (Todos)
- 列表视图，支持按状态（全部/未完成/已完成）筛选
- 每条待办显示：标题、描述、截止时间、优先级（低/普通/高）、来源（手动/LLM）
- 支持添加新待办、标记完成、删除待办
- 优先级用不同颜色标识（低/普通/高）
- 支持通过企业微信自然语言创建待办（使用 /api/todos/llm/create 接口）
```

### 9.2 仪表盘（Dashboard）

- **今日概览卡片**：今日课程数、今日截止作业数、本周作业总数
- **今日课表**：时间轴形式展示当天课程
- **即将截止**：按截止时间排序的作业列表（最近 3 天）
- **数据源状态**：每个数据源的上次同步时间和状态（✅ 正常 / ❌ 异常）

### 9.3 课表页面（Courses）

- 周视图：7 列 × 节次行的网格课表
- 支持切换周次
- 数据来源标签（区分教务系统）

### 9.4 作业页面（Assignments）

- 列表视图，支持按课程、来源、截止时间筛选
- 每条作业显示：标题、课程、来源图标、截止时间、距截止倒计时
- 支持手动标记完成

### 9.5 设置页面 — 数据源管理（核心交互）

用户可在此页面**动态添加和配置数据源**，每种类型有独立的配置表单：

#### 添加数据源流程
1. 点击「+ 添加数据源」
2. 选择类型：教务系统 / 学习通 / 数你最灵
3. 填写该类型对应的配置表单
4. 点击「测试连接」验证凭据是否有效
5. 保存后自动触发首次同步

#### 各类型配置表单字段

**教务系统（jwxt）**
```
- 学号（必填）
- 备注名称（可选，默认"教务系统"）
```

**学习通（chaoxing）**
```
- 手机号 / 邮箱（必填）
- 密码（必填，加密存储）
- 备注名称（可选）
```

**数你最灵（smartestu）**
```
- 学校（下拉选择，调后端接口获取学校列表）
- 学号（必填）
- 密码（必填，加密存储）
- 备注名称（可选）
```

### 9.6 前端与后端通信

前端通过 REST API 与后端通信，所有接口以 `/api` 为前缀：

```
GET    /api/courses?week=current        获取本周课程
GET    /api/assignments?status=pending  获取未完成作业
GET    /api/sources                     获取所有数据源
POST   /api/sources                     新增数据源
PUT    /api/sources/:id                 更新数据源配置
DELETE /api/sources/:id                 删除数据源
POST   /api/sources/:id/test            测试数据源连接
POST   /api/sources/:id/sync            手动触发同步
GET    /api/dashboard/summary           仪表盘数据汇总

# 待办事项接口
GET    /api/todos?status=all&priority=  获取待办列表，支持 status (all/pending/completed) 和 priority 筛选
GET    /api/todos/:id                   获取单个待办
POST   /api/todos                       创建待办
PUT    /api/todos/:id                   更新待办
DELETE /api/todos/:id                   删除待办
POST   /api/todos/:id/complete          标记待办完成
POST   /api/todos/llm/create            通过 LLM 创建待办（源自动为 llm）
GET    /api/todos/summary/dashboard     仪表盘待办统计
```

---

## 10. 各爬虫模块实现规范

### 10.1 爬虫基类（`spiders/base.py`）

所有爬虫继承此基类，统一处理：
- 异常捕获与日志
- 失败自动重试（最多 3 次，指数退避）
- 失败后更新 `data_sources.sync_status = "error"` 并记录 `error_message`
- 成功后更新 `last_sync` 时间
- 触发企业微信告警（连续失败 3 次时）

### 10.2 教务系统课表（`spiders/jwxt.py`）

```
目标：https://jwzx.cqupt.edu.cn/kebiao/kb_stu.php?xh={student_id}
方法：httpx.AsyncClient GET
解析：BeautifulSoup4 解析 HTML 表格
网络：笔记本模式直连；服务器模式通过 easyconnect 容器网络
频率：每天 06:00
去重：对比现有 Course 记录的 hash，内容无变化则跳过

课表 HTML 解析要点（待用户确认实际结构后调整）：
  - 表头行：节次（第1-2节 08:30-10:05 等）
  - 表头列：周一至周日
  - 单元格内容：课程名 / 教师 / 地点 / 周次范围
  - 存在合并单元格（rowspan/colspan）
```

### 10.3 数你最灵（`spiders/smartestu.py`）

```
登录：
  POST https://smartestu.cn/api/auth/login
  请求体字段：见 config/api_schemas.json（开发前手动抓包填写）
  响应：access_token，存入 data_sources.credentials（加密）

Token 维护：
  每次请求前检查 token 是否过期（JWT decode 检查 exp 字段）
  过期则先调用 POST /api/auth/refresh 获取新 token

作业查询：
  POST https://smartestu.cn/api/homework/student/mark/queryHomeworks
  Header: Authorization: Bearer {access_token}
  请求体字段：见 config/api_schemas.json
  响应解析：提取 title、dueTime、courseName、id（用于去重）

频率：每 30 分钟
```

### 10.4 学习通（`spiders/chaoxing.py`）

```
登录（滑块验证码处理流程）：
  1. httpx GET https://passport2.chaoxing.com/login 获取登录页
  2. 检测是否有滑块验证码
  3. 如有：
     a. 用 Playwright 打开登录页（headless=True）
     b. 截图滑块区域，用 ddddocr 计算偏移量
     c. 模拟鼠标滑动（带随机轨迹，避免检测）
     d. 提交登录表单，获取 cookies
  4. 如无验证码：直接 httpx POST 提交账密

作业查询：
  GET https://mooc1.chaoxing.com/mooc-ans/visit/courses/list
  遍历课程列表 → 每门课获取未完成作业
  接口路径待实测确认（学习通接口常变，封装为独立方法便于维护）

网络：公网可访问，不需要 VPN
频率：每 1 小时
打码平台备用：若 ddddocr 识别率低于 60%，切换至超级鹰 API
```

---

## 11. 企业微信通知规范（`wxwork/`）

### 11.1 主动推送场景

| 触发条件 | 推送内容 | 时机 |
|---------|---------|------|
| 每天 08:00 | 今日课表 + 今日/明日截止作业摘要 | 定时 |
| 新作业入库 | 「新作业」课程名 · 标题 · 截止时间 | 即时 |
| 作业截止前 24h | 截止提醒（24h） | 扫描触发 |
| 作业截止前 1h | 截止提醒（1h，加急） | 扫描触发 |
| 爬虫连续失败 | 告警：数据源同步异常 | 即时 |

### 11.2 消息格式示例

```
【今日课表 · 5月26日 周一】
08:30 高等数学 / A201 / 张老师
10:20 大学英语 / B304 / 李老师
14:00 线性代数 / A105 / 王老师

【即将截止】
⚠️ 今天 23:59 — 物理实验报告（学习通）
📌 明天 23:59 — 英语作文（数你最灵）
```

### 11.3 双向交互（用户发消息 → Agent 回复）

企业微信回调 → FastAPI `/webhook/wxwork` → 意图识别 → 查询数据库 → 回复

```python
# 支持的自然语言示例
"今天有什么课"     → query_today_courses
"明天作业"         → query_tomorrow_assignments
"本周课表"         → query_week_courses
"高数作业截止"     → query_assignment_by_course
"所有作业"         → query_all_pending
```

---

## 12. LLM 意图识别（`llm/intent.py`）

**不使用 LangChain**，直接调用 DeepSeek API HTTP 接口。

```
接口：POST https://api.deepseek.com/chat/completions
模型：deepseek-chat
```

System Prompt：
```
你是一个大学生学业助手，负责理解用户查询意图。
将用户输入分类为以下意图之一：
  query_today_courses / query_week_courses / query_tomorrow_courses /
  query_today_assignments / query_tomorrow_assignments /
  query_all_assignments / query_assignment_by_course /
  create_todo / query_todos / complete_todo / unknown

同时提取：
  course_name: 涉及课程名（无则 null）
  date: 涉及日期（无则 null）
  todo_title: 待办事项标题（create_todo 意图时提取）
  todo_priority: 优先级（low/normal/high，无则 null）
  todo_due_time: 截止时间（无则 null）

只返回 JSON，格式：
{"intent": "...", "course_name": null, "date": null, "todo_title": null, "todo_priority": null, "todo_due_time": null}

create_todo 意图示例：
- "明天记得交高数作业" -> todo_title="交高数作业", todo_due_time="明天"
- "下周五之前要完成报告，优先级高" -> todo_title="完成报告", todo_priority="high", todo_due_time="下周五"
```

---

## 13. 环境变量（`.env.example`）

```env
# ===== 基础 =====
STUDENT_ID=STUDENT_ID
DEPLOY_MODE=laptop          # laptop 或 server

# ===== 企业微信 =====
WXWORK_CORP_ID=你的企业ID
WXWORK_AGENT_ID=你的应用AgentID
WXWORK_AGENT_SECRET=你的应用Secret
WXWORK_TOKEN=回调Token（企业微信后台配置）
WXWORK_ENCODING_AES_KEY=回调加密Key

# ===== 学习通 =====
CHAOXING_PHONE=手机号
CHAOXING_PASSWORD=密码

# ===== 数你最灵 =====
SMARTESTU_STUDENT_ID=学号
SMARTESTU_PASSWORD=密码
SMARTESTU_SCHOOL_ID=待抓包确认

# ===== DeepSeek =====
DEEPSEEK_API_KEY=你的APIKey

# ===== 加密密钥（首次运行自动生成）=====
FERNET_KEY=（运行 python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 生成）

# ===== iCloud 日历（可选）=====
CALDAV_URL=https://caldav.icloud.com/
CALDAV_USERNAME=你的AppleID
CALDAV_PASSWORD=应用专用密码

# ===== VPN（仅 server 模式）=====
VPN_HOST=vpn.cqupt.edu.cn
VPN_USERNAME=统一身份认证账号
VPN_PASSWORD=统一身份认证密码

# ===== 应用 =====
TZ=Asia/Shanghai
DATABASE_URL=sqlite:///data/campus.db
FRONTEND_URL=http://localhost:3000   # 开发时前端地址（CORS 用）
```

---

## 14. Docker Compose 配置

```yaml
# docker-compose.yml（通用）
version: "3.9"

services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile
    restart: unless-stopped
    volumes:
      - ./data:/app/data
      - ./.env:/app/.env
    ports:
      - "8000:8000"
    environment:
      - TZ=Asia/Shanghai

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    restart: unless-stopped
    ports:
      - "80:80"
    depends_on:
      - backend

# docker-compose.server.yml（服务器模式，追加 easyconnect）
# 使用方式：docker compose -f docker-compose.yml -f docker-compose.server.yml up
# 内容：
#   easyconnect:
#     image: hagb/docker-easyconnect:cli
#     devices: [/dev/net/tun]
#     cap_add: [NET_ADMIN]
#     environment:
#       EC_VER: "7.6.3"
#       CLI_OPTS: "-d ${VPN_HOST} -u ${VPN_USERNAME} -p ${VPN_PASSWORD}"
#
#   backend:
#     network_mode: "service:easyconnect"
```

**笔记本模式启动**：
```bash
docker compose up -d
```

**服务器模式启动**：
```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml up -d
```

---

## 15. 开发阶段划分

### Phase 1 — 项目骨架（约 1 天）
- 初始化 FastAPI 项目结构
- 实现 `config.py`（读取 .env）
- 创建 SQLAlchemy 数据模型 + Alembic 迁移
- 初始化 React + Vite + shadcn/ui + Tailwind 前端项目
- 编写 `docker-compose.yml`
- **验收**：`docker compose up` 启动，`GET /health` 返回 200，前端页面可访问

### Phase 2 — 教务课表爬虫 + 基础 UI（约 1-2 天）
- 实现 `spiders/jwxt.py`（httpx + BeautifulSoup4）
- APScheduler 注册课表定时任务
- 实现 `/api/courses` 接口
- 前端实现课表页面（周视图网格）
- **验收**：手动触发爬虫，前端课表页面显示本学期课表

### Phase 3 — 数你最灵爬虫（约 1-2 天）
- **前置**：手动抓包填写 `config/api_schemas.json`
- 实现 `spiders/smartestu.py`（JWT 登录 + 自动刷新）
- 实现 `/api/assignments` 接口
- 前端实现作业列表页面
- **验收**：作业页面显示数你最灵的作业数据

### Phase 4 — 学习通爬虫（约 2-3 天）
- 实现 `spiders/chaoxing.py`（Playwright + ddddocr 滑块）
- 集成超级鹰打码平台作为备用
- **验收**：学习通作业自动入库

### Phase 5 — 企业微信集成（约 1-2 天）
- 注册企业微信，配置回调 URL（cpolar 内网穿透）
- 实现 `wxwork/client.py`（发送消息）
- 实现 `wxwork/webhook.py`（接收用户消息、验签）
- 实现 `wxwork/notifier.py`（日报、新作业、截止提醒推送）
- **验收**：企业微信收到每日推送，发消息能得到回复

### Phase 6 — 自然语言查询（约 1 天）
- 实现 `llm/intent.py`（DeepSeek API）
- 企业微信消息 → 意图识别 → 数据库查询 → 回复
- **验收**：发送"明天有什么课"得到正确回复

### Phase 7 — Web UI 数据源配置（约 1-2 天）
- 前端实现设置页面：数据源列表、添加/编辑/删除表单
- 后端实现 `/api/sources` CRUD + `/api/sources/:id/test` 接口
- 前端仪表盘实现数据源状态卡片
- **验收**：通过 Web UI 添加一个数你最灵账号，触发同步

### Phase 8 — 仪表盘完善（约 1 天）
- 今日概览卡片、即将截止作业、数据源状态
- Recharts 作业统计图表
- **验收**：仪表盘数据与数据库一致

### Phase 9 — iCloud 日历同步（可选，约 1-2 天）
- 实现 `calendar/caldav_sync.py`
- 课程写入重复性日历事件，作业截止写入单次提醒
- **验收**：iPhone 日历显示课程和作业截止节点

---

## 16. 注意事项

### 安全
- 所有密码/Token **必须通过 `.env` 注入，严禁硬编码**
- 数据库中的账号密码使用 `cryptography.Fernet` 加密存储
- `.env` 加入 `.gitignore`
- 前端不直接存储任何凭据，所有敏感操作走后端 API

### 时区
- 所有时间统一 `UTC+8`（`Asia/Shanghai`）
- 数据库存 UTC，前端展示时由后端转换为北京时间字符串

### 容错
- 爬虫失败：记录日志 + 更新 `sync_status` + 3次失败后企业微信告警
- 企业微信发送失败：记录 `notifications.success=False`，不重试（避免刷屏）
- 日历同步失败：独立重试，不影响主流程

### 学习通接口维护
- 学习通接口路径易变，所有接口 URL 集中定义在 `spiders/chaoxing.py` 顶部常量，便于快速修改

### 合规
- 仅供个人学习使用
- 爬虫请求间隔 ≥ 1 秒
- 不得用于批量采集或传播他人数据

---

## 17. 待确认事项（开发前手动完成）

| 事项 | 操作 |
|------|------|
| 数你最灵登录请求体字段 | 浏览器登录 smartestu.cn → F12 → Network → POST /api/auth/login → Request Body |
| 数你最灵作业查询请求体和响应结构 | 同上，找 POST /api/homework/student/mark/queryHomeworks |
| 数你最灵学校 ID 值 | 登录请求体中 schoolId 对应重邮的值 |
| 课表 HTML 表格结构 | 挂 VPN 访问课表页面 → F12 → Elements 查看节次/星期的标签和 class 名 |
| 学习通登录接口路径确认 | F12 → Network → 提交登录表单时的 POST 请求 URL |
| 企业微信回调地址配置 | 注册企业微信应用后，cpolar 生成 HTTPS 地址填入企业微信后台 |
