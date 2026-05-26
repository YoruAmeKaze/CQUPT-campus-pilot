# CampusPilot — 重庆邮电大学个人学业智能助理
## 项目技术要求与开发指令文档 v3.0

> 本文档面向 AI 编程助手（Trae/Cursor）直接使用，包含项目当前完整技术细节。
>
> 版本历史：v1（初版企业微信方案）→ v2（技术栈明细）→ v3（飞书 + Text-to-SQL 现行方案）

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

### 当前运行模式（2026-05-26）

- **部署模式**: `laptop`（笔记本模式）
- **服务端口**: `8000`（后端 API），`3000`（前端 Vite 开发服务器）
- **飞书机器人**: 通过 SSH 隧道暴露至公网服务器（47.76.188.165:9999）
- **飞书回调端点**: `https://47.76.188.165:9999/api/feishu/app/event`

---

## 3. 通知与交互通道：飞书应用

### 为什么从企业微信切换为飞书

| 对比项 | 飞书应用 | 企业微信应用 |
|--------|---------|------------|
| 配置复杂度 | 仅需 App ID + App Secret | 需 Corp ID + Agent ID + Secret + Token + Encoding AES Key |
| 消息去重 | 事件回调自带 message_id | 需自行维护去重逻辑 |
| 双向交互 | ✅ 原生支持，API 简洁 | ✅ 支持 |
| 主动推送 | ✅ 支持 | ✅ 支持 |
| 个人注册 | ✅ 个人即可注册 | ⚠️ 需企业资质（可填写任意企业名）|
| 事件回调 | v2.0 事件订阅，schema 清晰 | 需 XML 验签，配置繁琐 |

### 飞书应用配置步骤

1. 访问 `open.feishu.cn` →「开发者后台」→「创建企业自建应用」
2. 获取 **App ID** 和 **App Secret**
3. 配置事件订阅：
   - 订阅「接收消息」事件（`im.message.receive_v1`）
   - 设置回调 URL（需要使用 SSH 隧道暴露的公网地址）
4. 发布应用并设置机器人权限：
   - `im:message`（读写消息）
   - `im:resource`（获取消息资源）
5. 在 `.env` 中配置：
   ```env
   FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
   FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
   ```

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
│                   公网服务器 (47.76.188.165:9999)            │
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

## 5. 项目目录结构（v3 实际结构）

```
campus-pilot/
├── app/
│   ├── main.py                   # FastAPI 入口 + 生命周期管理
│   ├── config.py                 # 从环境变量加载配置
│   │
│   ├── api/                      # API 路由层
│   │   ├── courses.py            # 课表 CRUD
│   │   ├── assignments.py        # 作业 CRUD
│   │   ├── todos.py              # 待办 CRUD
│   │   ├── config.py             # 配置管理
│   │   ├── data_sources.py       # 数据源 CRUD
│   │   ├── feishu_app.py         # 飞书事件回调（含消息去重）
│   │   ├── notification.py       # 通知记录
│   │   └── llm.py                # LLM API
│   │
│   ├── crawlers/                 # 爬虫模块
│   │   ├── jwxt_crawler.py       # 教务系统课表
│   │   ├── chaoxing_crawler.py   # 学习通（滑块验证码）
│   │   └── smartestu_crawler.py  # 数你最灵（JWT）
│   │
│   ├── db/                       # 数据库
│   │   ├── models.py             # SQLAlchemy 数据模型
│   │   └── session.py            # 数据库连接与会话
│   │
│   ├── llm/                      # AI 模块
│   │   ├── client.py             # DeepSeek API 客户端
│   │   │                         #   - chat_with_tools (Function Calling)
│   │   │                         #   - chat_text_to_sql (Text-to-SQL)
│   │   │                         #   - chat_or_reply (智能分流)
│   │   ├── tools.py              # 工具定义 + 执行器
│   │   └── text_to_sql.py        # Text-to-SQL 引擎
│   │
│   ├── notifications/            # 推送通知
│   │   ├── bark_notifier.py      # Bark iOS 推送
│   │   └── feishu_notifier.py    # 飞书消息推送
│   │
│   ├── scheduler/                # 定时任务
│   │   └── jobs.py               # APScheduler 任务定义
│   │   └── task_scheduler.py     # 调度器封装
│   │
│   └── services/                 # 业务逻辑层
│       ├── course_service.py     # 课表服务
│       ├── assignment_service.py # 作业服务
│       ├── todo_service.py       # 待办服务
│       ├── feishu_app_service.py # 飞书服务
│       ├── config_store.py       # 数据库配置存储
│       └── tunnel.py             # SSH 隧道管理
│
├── frontend/                     # Web 前端
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── index.css
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx     # 仪表盘
│   │   │   ├── Courses.tsx       # 课表
│   │   │   ├── Assignments.tsx   # 作业
│   │   │   ├── Todos.tsx         # 待办
│   │   │   ├── Notifications.tsx # 通知记录
│   │   │   └── Settings.tsx      # 设置
│   │   └── components/
│   │       ├── Layout.tsx        # 布局组件
│   │       └── ui/               # shadcn/ui 组件
│   └── ...
│
├── tests/                        # 测试
├── .env.example
├── docker-compose.yml
├── requirements.txt
└── server_key                    # SSH 密钥（部署用）
```

---

## 6. 数据模型

```python
# app/db/models.py - 当前完整模型

class User(Base):
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True)
    wxwork_userid = Column(String(64), unique=True)    # 兼容旧数据
    student_id    = Column(String(32))
    created_at    = Column(DateTime, default=func.now())
    # 关系
    data_sources  = relationship("DataSource", back_populates="user")
    courses       = relationship("Course", back_populates="user")
    assignments   = relationship("Assignment", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    todos         = relationship("Todo", back_populates="user")

class DataSource(Base):
    """数据源配置（Web UI 添加）"""
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
    location_schedule = Column(Text)       # JSON 多周次多地点
    day_of_week     = Column(Integer)      # 1=周一…7=周日
    start_week      = Column(Integer)
    end_week        = Column(Integer)
    week_mask       = Column(String(30))   # 二进制周次标记
    start_slot      = Column(Integer)
    end_slot        = Column(Integer)
    start_time      = Column(String(10))   # "08:30"
    end_time        = Column(String(10))   # "10:05"

class Assignment(Base):
    __tablename__ = "assignments"
    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, ForeignKey("users.id"))
    source_id     = Column(Integer, ForeignKey("data_sources.id"))
    remote_id     = Column(String(100))    # 平台原始 ID，去重用
    title         = Column(String(500))
    description   = Column(Text)
    course_name   = Column(String(200))
    due_time      = Column(DateTime)
    is_completed  = Column(Boolean, default=False)
    # 推送状态标记
    notified_new  = Column(Boolean, default=False)
    notified_24h  = Column(Boolean, default=False)
    notified_1h   = Column(Boolean, default=False)

class Todo(Base):
    """待办事项（支持飞书自然语言创建）"""
    __tablename__ = "todos"
    id           = Column(Integer, primary_key=True)
    user_id      = Column(Integer, ForeignKey("users.id"))
    title        = Column(String(500))
    description  = Column(Text)
    due_time     = Column(DateTime)
    priority     = Column(String(20), default="normal")  # low/normal/high
    is_completed = Column(Boolean, default=False)
    source       = Column(String(50), default="manual")  # manual/llm
    created_at   = Column(DateTime, default=func.now())
    updated_at   = Column(DateTime, default=func.now(), onupdate=func.now())

class Notification(Base):
    __tablename__ = "notifications"
    id       = Column(Integer, primary_key=True)
    user_id  = Column(Integer, ForeignKey("users.id"))
    type     = Column(String(50))     # "new_assignment"|"deadline_24h"|等
    content  = Column(Text)
    sent_at  = Column(DateTime, default=func.now())
    success  = Column(Boolean, default=True)

class SystemConfig(Base):
    """系统配置键值存储（替代 .env 中的业务配置）"""
    __tablename__ = "system_configs"
    id          = Column(Integer, primary_key=True)
    key         = Column(String(100), unique=True, index=True)
    value       = Column(Text)
    description = Column(String(200))
    updated_at  = Column(DateTime, default=func.now(), onupdate=func.now())
```

---

## 7. LLM 模块详解（核心变化）

### 7.1 架构演进

v2 → v3 最大的架构变化是 LLM 交互方式：

```
v2: 用户消息 → 固定意图分类 → 预定义工具函数 → 返回结果
    (intent.py)        (6种固定意图)   (get_today_courses 等)

v3: 用户消息 → 智能分流判断 → [查询] Text-to-SQL → 执行SQL → AI总结 → 回复
                              [普通] 直接 AI 聊天
                              [创建] 调用 create_todo 工具
```

### 7.2 智能分流（`_is_data_query` in `client.py`）

```python
def _is_data_query(question: str) -> str:
    # 返回: "query" / "create_todo" / "chat"
    # 基于关键词匹配判断用户意图
```

分流逻辑：
- 含"课表""课程""作业""待办""统计"等关键词 → `query`
- 含"添加待办""帮我记""提醒我"等关键词 → `create_todo`
- 其他（你好、谢谢、正常聊天） → `chat`

### 7.3 Text-to-SQL 引擎（`chat_text_to_sql`）

```
流程：
1. 用户问题 → 构造 SQL 生成提示（含完整数据库 Schema）
2. 调用 DeepSeek → 生成 SELECT SQL 语句
3. SQL 安全校验（只允许 SELECT，禁用 INSERT/UPDATE/DELETE）
4. 执行 SQL 查询 SQLite 数据库
5. 格式化查询结果
6. 调用 DeepSeek 用自然语言总结查询结果 → 返回用户
```

特点：
- **无需预定义工具**，任何数据查询需求自动生成 SQL
- **Schema 感知**：提示中包含完整的表结构、字段类型、关联关系
- **周数计算**：课程查询自动考虑当前周（`start_week`/`end_week`）
- **周几转换**：处理 SQLite `strftime('%w')` 与数据库 `day_of_week` 的映射

### 7.4 预定义工具（`tools.py`）

保留了常见的预定义工具用于快速查询（无需每次都调用 Text-to-SQL）：

| 工具 | 功能 | 参数 |
|------|------|------|
| `get_today_courses` | 今天的课表 | 无 |
| `get_tomorrow_courses` | 明天的课表 | 无 |
| `get_day_courses` | 指定日期的课表 | date (YYYY-MM-DD) |
| `get_this_week_courses` | 本周课表 | 无 |
| `get_pending_assignments` | 待完成作业 | days (可选) |
| `get_overdue_assignments` | 已过期作业 | 无 |
| `get_current_week_number` | 当前周数 | 无 |
| `get_todos` | 查看待办 | status, priority |
| `create_todo` | 创建待办 | title, description, due_time, priority |
| `flex_query` | 灵活查询（Text-to-SQL） | question |

### 7.5 DSML 格式兼容

DeepSeek V4 Flash 可能返回非标准 OpenAI 格式的工具调用（`<｜｜DSML｜｜tool_calls>` XML 格式），`client.py` 中实现了 `_parse_dsml_tool_calls()` 进行兼容处理。

---

## 8. 飞书事件回调流程

```
飞书服务器
    │ POST /api/feishu/app/event
    │ Body: {"schema":"2.0", "header":{...}, "event":{...}}
    ▼
FeishuAppService.parse_event_body(body)
    │
    ├── type == "url_verify"
    │   └── 返回 {challenge: "..."}（配置回调时验证）
    │
    └── type == "message"
        ├── 去重检查（30s TTL 内存缓存）
        ├── chat_or_reply()  // 智能分流
        │   ├── 查询类 → chat_text_to_sql(db)
        │   ├── 创建待办 → execute_tool("create_todo")
        │   └── 闲聊 → chat_completion()
        └── send_message(chat_id, reply)
```

---

## 9. SSH 隧道模块（`services/tunnel.py`）

用于本地开发时暴露服务至公网（替代 cpolar/frp）。

### 工作原理

- 本地启动时自动执行 `ssh -R` 反向隧道命令
- 将本地 `localhost:8000` 映射到公网服务器的指定端口
- 飞书回调配置指向公网服务器地址即可

### 配置（`.env`）

```env
TUNNEL_SERVER_HOST=47.76.188.165
TUNNEL_SERVER_USER=root
TUNNEL_REMOTE_PORT=9999
TUNNEL_LOCAL_PORT=8000
```

### 自动管理

- 在 `app/main.py` 的 `lifespan` 中自动启动
- 应用关闭时自动停止隧道

---

## 10. API 接口一览

### 飞书应用回调

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/feishu/app/event` | 事件回调（含消息去重）|
| GET | `/api/feishu/app/status` | 配置状态查询 |
| POST | `/api/feishu/app/test` | 测试连接 |

### 课程

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/courses` | 获取课表（支持 week 参数）|
| GET | `/api/courses/today` | 今日课程 |
| GET | `/api/courses/summary/overview` | 课程概览统计 |

### 作业

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/assignments` | 获取作业列表 |
| GET | `/api/assignments/summary/overview` | 作业统计 |

### 待办

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/todos` | 获取待办列表 |
| POST | `/api/todos` | 创建待办 |
| GET | `/api/todos/summary/dashboard` | 待办统计（仪表盘）|

### 数据源

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/data-sources` | 获取所有数据源 |
| POST | `/api/data-sources` | 新增数据源 |
| PUT | `/api/data-sources/{id}` | 更新数据源 |

### 通知

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/notification/recent` | 最近通知 |

---

## 11. 环境变量配置

```env
# ===== 基础 =====
STUDENT_ID=2025xxxxxx
DEPLOY_MODE=laptop

# ===== DeepSeek =====
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
DEEPSEEK_MODEL=deepseek-chat

# ===== 飞书应用 =====
FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxx

# ===== SSH 隧道（公网服务器）=====
TUNNEL_SERVER_HOST=47.76.188.165
TUNNEL_SERVER_USER=root
TUNNEL_REMOTE_PORT=9999

# ===== 校历 =====
TERM_START_DATE=2026-03-02

# ===== 加密密钥 =====
FERNET_KEY=xxxxxxxxxxxxxxxx

# ===== 学习通 =====
CHAOXING_USERNAME=手机号
CHAOXING_PASSWORD=密码

# ===== 数你最灵 =====
SMARTESTU_STUDENT_ID=学号
SMARTESTU_PASSWORD=密码
SMARTESTU_SCHOOL_ID=学校ID

# ===== 应用 =====
FRONTEND_URL=http://localhost:3000
```

---

## 12. 前端页面

| 页面 | 路由 | 功能 |
|------|------|------|
| 仪表盘 | `/` | 今日概览、课表、即将截止作业、数据源状态 |
| 课表 | `/courses` | 周视图课表网格，支持切换周次 |
| 作业 | `/assignments` | 作业列表，支持筛选、标记完成 |
| 待办 | `/todos` | 待办列表，支持创建、完成、筛选 |
| 通知 | `/notifications` | 推送历史记录 |
| 设置 | `/settings` | 数据源管理、通知设置 |

前端技术栈：React 18 + TypeScript + Vite + shadcn/ui + Tailwind CSS + Recharts

---

## 13. 定时任务

| 任务 | 频率 | 说明 |
|------|------|------|
| 教务课表爬虫 | 每天 06:00 | 从 jwzx.cqupt.edu.cn 抓取课表 |
| 学习通爬虫 | 每 1 小时 | 抓取学习通作业（需处理滑块验证码）|
| 数你最灵爬虫 | 每 30 分钟 | 抓取数你最灵作业（JWT 认证）|
| 每日日报 | 每天 08:00 | 推送今日课表和即将截止作业 |
| 截止提醒扫描 | 每小时 | 扫描即将截止作业并推送提醒 |

---

## 14. 爬虫模块

### 教务系统课表
- **URL**: `https://jwzx.cqupt.edu.cn/kebiao/kb_stu.php?xh={student_id}`
- **方式**: 直接 GET（无需登录，但需校园网/VPN）
- **解析**: BeautifulSoup4 解析 HTML 表格

### 学习通
- **登录**: 账号密码 + 滑块验证码（Playwright + ddddocr）
- **作业查询**: 遍历课程列表获取未完成作业
- **网络**: 公网可访问，不需要 VPN

### 数你最灵
- **认证**: JWT Bearer Token（登录获取，自动刷新）
- **作业查询**: POST 接口，支持按课程、按时间筛选
- **网络**: 公网可访问，不需要 VPN

---

## 15. 开发阶段划分

### Phase 1 ✅ — 项目骨架
- FastAPI 项目结构、数据模型、Alembic 迁移
- React + Vite + shadcn/ui 前端项目
- Docker Compose 配置

### Phase 2 ✅ — 教务课表爬虫 + 课表 UI
- jwxt_crawler.py + CourseService
- 课表 API 接口
- 前端课表页面（周视图）

### Phase 3 ✅ — 数你最灵爬虫 + 作业 UI
- smartestu_crawler.py + AssignmentService
- 作业 API 接口
- 前端作业页面

### Phase 4 ✅ — 学习通爬虫
- chaoxing_crawler.py（Playwright + ddddocr 滑块处理）

### Phase 5 ✅ — 飞书应用集成
- FeishuAppService 消息发送/接收
- 事件回调 + 消息去重
- SSH 隧道自动管理

### Phase 6 ✅ — LLM 智能查询
- Text-to-SQL 引擎（chat_text_to_sql）
- 智能分流（chat_or_reply）
- 待办创建（create_todo 工具）

### Phase 7 ✅ — Web UI 数据源配置
- 设置页面：数据源增删改查
- 仪表盘数据源状态卡片

### Phase 8 ✅ — 待办管理 + 仪表盘完善
- 待办页面（Web + 飞书）
- 仪表盘统计卡片

---

## 16. 技术栈总览

### 后端
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
| AI | DeepSeek V4 Flash (OpenAI 兼容接口) |
| 加密 | cryptography (Fernet) |

### 前端
| 模块 | 技术 |
|------|------|
| 框架 | React 18 + TypeScript |
| 构建 | Vite |
| 组件 | shadcn/ui (Radix UI) |
| 样式 | Tailwind CSS |
| 图表 | Recharts |
| 状态管理 | Zustand |

---

## 17. 安全注意事项

- 所有密码/Token 通过 `.env` 注入，严禁硬编码
- 数据库中的账号密码使用 `cryptography.Fernet` 加密存储
- `.env` 已加入 `.gitignore`
- 前端不直接存储任何凭据，所有敏感操作走后端 API
- 飞书消息去重防止重复处理
- Text-to-SQL 只允许 SELECT 查询，禁止写操作

---

## 18. 当前状态（2026-05-26）

| 模块 | 状态 | 备注 |
|------|------|------|
| 飞书回调 | ✅ 正常运行 | 通过 SSH 隧道暴露 |
| 消息去重 | ✅ 已实现 | 30s TTL 内存缓存 |
| LLM 聊天 | ✅ 正常运行 | 智能分流 + Text-to-SQL |
| 课表查询 | ✅ 正常 | 预定义工具 + Text-to-SQL |
| 作业查询 | ✅ 正常 | 同上 |
| 待办查询/创建 | ✅ 正常 | 飞书和 Web 双端 |
| 飞书通知推送 | ✅ 正常 | Bark 可选 |
| 教务课表爬虫 | ✅ 有数据 | 32 条课程记录 |
| 数你最灵爬虫 | ✅ 已实现 | JWT 自动刷新 |
| 学习通爬虫 | ✅ 已实现 | Playwright 滑块 |
| Web 前端 | ✅ 可用 | 6 个页面 |
| SSH 隧道 | ✅ 自动管理 | 随服务启停 |
| 创建待办（飞书） | ⬜ 优化中 | 通过 LLM 自然语言 |
