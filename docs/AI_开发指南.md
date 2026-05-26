# CampusPilot — 重庆邮电大学个人学业智能助理

## 项目技术要求与开发指令文档 v3.0

> 本文档面向 AI 编程助手（Trae/Cursor）直接使用，包含项目当前完整技术细节。

---

## 1. 项目目标

构建一个运行在**个人笔记本**上的智能 Agent + Web 管理界面，帮助重庆邮电大学学生：

- 自动抓取**教务系统课表**、**学习通作业**、**数你最灵作业**
- 通过**飞书应用（App）**主动推送和双向对话
- 支持**Text-to-SQL 自然语言查询**：用自然语言查询课表、作业、待办
- 提供 **Web 管理仪表盘**，可视化查看课表、作业、待办
- 支持通过飞书自然语言**创建待办事项**

---

## 2. 运行环境

| 项目 | 说明 |
|------|------|
| 操作系统 | Windows / Linux 均可 |
| 部署位置 | 个人笔记本（推荐）或公网服务器 |
| Python | 3.11+ |
| 数据库 | SQLite（`data/campus.db`）|
| 内网穿透 | SSH 反向隧道（使用公网服务器中转）|
| 校园网访问 | 需连接校园 WiFi 或深信服 EasyConnect VPN |

---

## 3. 通知与交互通道：飞书应用

### 飞书应用配置步骤

1. 访问 `open.feishu.cn` →「开发者后台」→「创建企业自建应用」
2. 获取 **App ID** 和 **App Secret**
3. 配置事件订阅：
   - 订阅「接收消息」事件（`im.message.receive_v1`）
   - 设置回调 URL（需要使用 SSH 隧道暴露的公网地址）
4. 发布应用并设置机器人权限：
   - `im:message`（读写消息）
   - `im:resource`（获取消息资源）
5. 在 Web 设置页面配置：
   - FEISHU_APP_ID
   - FEISHU_APP_SECRET

### 消息去重机制

飞书在消息高峰时可能重复推送同一事件，项目中通过**内存缓存 + 30 秒 TTL** 去重：

```python
# app/api/feishu_app.py
_processed_messages: dict = {}
_DEDUP_TTL = 30  # 30秒内同一 message_id 不再处理
```

---

## 4. 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                       本地笔记本                              │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                  FastAPI (port 8000)                   │   │
│  │                                                        │   │
│  │  ┌────────────────────────────────────────────────┐   │   │
│  │  │           LLM 模块                              │   │   │
│  │  │  ┌──────────┐  ┌──────────────┐  ┌──────────┐ │   │   │
│  │  │  │ client.py │  │ text_to_sql │  │ tools.py │ │   │   │
│  │  │  │ (DeepSeek)│  │ (SQL生成)    │  │ (工具集) │ │   │   │
│  │  │  └──────────┘  └──────────────┘  └──────────┘ │   │   │
│  │  └────────────────────────────────────────────────┘   │   │
│  │                                                        │   │
│  │  API 路由:                                              │   │
│  │  ├── /api/feishu/app/event  ← 飞书事件回调              │   │
│  │  ├── /api/courses             ← 课表 CRUD               │   │
│  │  ├── /api/assignments         ← 作业 CRUD               │   │
│  │  ├── /api/todos               ← 待办 CRUD               │   │
│  │  ├── /api/config              ← 系统配置                │   │
│  │  ├── /api/data-sources        ← 数据源管理              │   │
│  │  └── /api/notification        ← 通知记录                │   │
│  │                                                        │   │
│  │  APScheduler 定时任务:                                   │   │
│  │  ├── 数你最灵爬虫  (每30分钟)                            │   │
│  │  ├── 学习通爬虫    (每1小时)                             │   │
│  │  ├── 教务课表爬虫  (每天06:00)                           │   │
│  │  ├── 每日日报      (每天08:00)                           │   │
│  │  └── 截止提醒扫描  (每小时)                              │   │
│  │                                                        │   │
│  │  SQLite (data/campus.db)                               │   │
│  └──────────────────────────────────────────────────────┘   │
│                         ↕ SSH 反向隧道                       │
│                   公网服务器 (SERVER_IP:9999)            │
│                         ↕ HTTPS                             │
│                   飞书服务器 → 用户飞书 App                  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Frontend (Vite, port 3000)                          │   │
│  │  React + TypeScript + shadcn/ui                      │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

---

## 5. 项目目录结构

```
campus-pilot/
├── README.md                     # 快速上手指南
├── start.bat                     # Windows 一键启动
├── start.sh                      # Linux/Mac 一键启动
├── docker-start.bat              # Docker 一键启动
├── .env                          # 环境变量（4项固定）
│
├── app/
│   ├── main.py                   # FastAPI 入口 + 生命周期管理
│   ├── config.py                 # 从环境变量加载配置
│   ├── api/                      # API 路由层
│   ├── crawlers/                 # 爬虫模块
│   ├── db/                       # 数据库
│   ├── llm/                      # AI 模块
│   ├── notifications/            # 推送通知
│   ├── scheduler/                # 定时任务
│   └── services/                 # 业务逻辑层
│
├── frontend/                     # Web 前端
├── docs/                         # 文档
│   └── AI_开发指南.md            # AI 开发参考
│
├── scripts/                      # 部署脚本
│   ├── deploy.bat
│   ├── deploy.sh
│   └── ...
│
├── tests/                        # 测试
├── docker-compose.yml
├── requirements.txt
└── Dockerfile
```

---

## 6. 数据模型

```python
# app/db/models.py

class User(Base):
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True)
    wxwork_userid = Column(String(64), unique=True)
    student_id    = Column(String(32))
    created_at    = Column(DateTime, default=func.now())
    data_sources  = relationship("DataSource", back_populates="user")
    courses       = relationship("Course", back_populates="user")
    assignments   = relationship("Assignment", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    todos         = relationship("Todo", back_populates="user")

class DataSource(Base):
    __tablename__ = "data_sources"
    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, ForeignKey("users.id"))
    type          = Column(String(20))    # "jwxt"|"chaoxing"|"smartestu"
    name          = Column(String(100))
    enabled       = Column(Boolean, default=True)
    credentials   = Column(Text)          # Fernet 加密后的 JSON
    last_sync     = Column(DateTime)
    sync_status   = Column(String(20), default="pending")
    error_message = Column(Text)

class Course(Base):
    __tablename__ = "courses"
    id              = Column(Integer, primary_key=True)
    user_id         = Column(Integer, ForeignKey("users.id"))
    source_id       = Column(Integer, ForeignKey("data_sources.id"))
    name            = Column(String(200))
    teacher         = Column(String(100))
    location        = Column(String(200))
    location_schedule = Column(Text)
    day_of_week     = Column(Integer)
    start_week      = Column(Integer)
    end_week        = Column(Integer)
    week_mask       = Column(String(30))
    start_slot      = Column(Integer)
    end_slot        = Column(Integer)
    start_time      = Column(String(10))
    end_time        = Column(String(10))

class Assignment(Base):
    __tablename__ = "assignments"
    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, ForeignKey("users.id"))
    source_id     = Column(Integer, ForeignKey("data_sources.id"))
    remote_id     = Column(String(100))
    title         = Column(String(500))
    description   = Column(Text)
    course_name   = Column(String(200))
    due_time      = Column(DateTime)
    is_completed  = Column(Boolean, default=False)
    notified_new  = Column(Boolean, default=False)
    notified_24h  = Column(Boolean, default=False)
    notified_1h   = Column(Boolean, default=False)

class Todo(Base):
    __tablename__ = "todos"
    id           = Column(Integer, primary_key=True)
    user_id      = Column(Integer, ForeignKey("users.id"))
    title        = Column(String(500))
    description  = Column(Text)
    due_time     = Column(DateTime)
    priority     = Column(String(20), default="normal")
    is_completed = Column(Boolean, default=False)
    source       = Column(String(50), default="manual")
    created_at   = Column(DateTime, default=func.now())
    updated_at   = Column(DateTime, default=func.now(), onupdate=func.now())

class Notification(Base):
    __tablename__ = "notifications"
    id       = Column(Integer, primary_key=True)
    user_id  = Column(Integer, ForeignKey("users.id"))
    type     = Column(String(50))
    content  = Column(Text)
    sent_at  = Column(DateTime, default=func.now())
    success  = Column(Boolean, default=True)

class SystemConfig(Base):
    __tablename__ = "system_configs"
    id          = Column(Integer, primary_key=True)
    key         = Column(String(100), unique=True, index=True)
    value       = Column(Text)
    description = Column(String(200))
    updated_at  = Column(DateTime, default=func.now(), onupdate=func.now())
```

---

## 7. LLM 模块详解

### 7.1 架构演进

```
v2: 用户消息 → 固定意图分类 → 预定义工具函数 → 返回结果

v3: 用户消息 → 智能分流判断 → [查询] Text-to-SQL → 执行SQL → AI总结 → 回复
                              [普通] 直接 AI 聊天
                              [创建] 调用 create_todo 工具
```

### 7.2 智能分流（`_is_data_query` in `client.py`）

```python
def _is_data_query(question: str) -> str:
    # 返回: "query" / "create_todo" / "chat"
```

分流逻辑：
- 含"课表""课程""作业""待办""统计"等关键词 → `query`
- 含"添加待办""帮我记""提醒我"等关键词 → `create_todo`
- 其他（你好、谢谢、正常聊天） → `chat`

### 7.3 Text-to-SQL 引擎

```
流程：
1. 用户问题 → 构造 SQL 生成提示（含完整数据库 Schema）
2. 调用 DeepSeek → 生成 SELECT SQL 语句
3. SQL 安全校验（只允许 SELECT）
4. 执行 SQL 查询 SQLite 数据库
5. 格式化查询结果
6. 调用 DeepSeek 用自然语言总结查询结果 → 返回用户
```

### 7.4 预定义工具

| 工具 | 功能 |
|------|------|
| `get_today_courses` | 今天的课表 |
| `get_tomorrow_courses` | 明天的课表 |
| `get_this_week_courses` | 本周课表 |
| `get_pending_assignments` | 待完成作业 |
| `get_overdue_assignments` | 已过期作业 |
| `get_current_week_number` | 当前周数 |
| `get_todos` | 查看待办 |
| `create_todo` | 创建待办 |
| `flex_query` | 灵活查询（Text-to-SQL） |

---

## 8. 前端页面

| 页面 | 路由 | 功能 |
|------|------|------|
| 仪表盘 | `/` | 今日概览、课表、即将截止作业、数据源状态 |
| 课表 | `/courses` | 周视图课表网格，支持切换周次 |
| 作业 | `/assignments` | 作业列表，支持筛选、标记完成 |
| 待办 | `/todos` | 待办列表，支持创建、完成、筛选 |
| 通知 | `/notifications` | 推送历史记录 |
| 设置 | `/settings` | 数据源管理、通知设置 |

---

## 9. 定时任务

| 任务 | 频率 | 说明 |
|------|------|------|
| 教务课表爬虫 | 每天 06:00 | 从 jwzx.cqupt.edu.cn 抓取课表 |
| 学习通爬虫 | 每 1 小时 | 抓取学习通作业（需处理滑块验证码）|
| 数你最灵爬虫 | 每 30 分钟 | 抓取数你最灵作业（JWT 认证）|
| 每日日报 | 每天 08:00 | 推送今日课表和即将截止作业 |
| 截止提醒扫描 | 每小时 | 扫描即将截止作业并推送提醒 |

---

## 10. 后端技术栈

| 模块 | 技术 |
|------|------|
| 语言 | Python 3.11+ |
| Web 框架 | FastAPI + uvicorn |
| 任务调度 | APScheduler 3.x |
| 数据库 | SQLite + SQLAlchemy 2.0 (asyncio) |
| HTTP 客户端 | httpx |
| 浏览器自动化 | Playwright |
| 滑块识别 | ddddocr |
| HTML 解析 | BeautifulSoup4 |
| AI | DeepSeek (OpenAI 兼容接口) |
| 加密 | cryptography (Fernet) |

## 11. 前端技术栈

| 模块 | 技术 |
|------|------|
| 框架 | React 18 + TypeScript |
| 构建 | Vite |
| 组件 | shadcn/ui (Radix UI) |
| 样式 | Tailwind CSS |
| 图表 | Recharts |
| 状态管理 | Zustand |

---

## 12. 安全注意事项

- 所有密码/Token 通过 Web 设置页面配置，自动加密存储到数据库
- 数据库中的账号密码使用 `cryptography.Fernet` 加密存储
- 前端不直接存储任何凭据，所有敏感操作走后端 API
- 飞书消息去重防止重复处理
- Text-to-SQL 只允许 SELECT 查询，禁止写操作
