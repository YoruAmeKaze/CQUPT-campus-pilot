# CampusPilot — 重庆邮电大学个人学业智能助理

## 项目技术要求与开发指令文档 v3.1

> 本文档面向 AI 编程助手（Trae/Cursor）直接使用，包含项目当前完整技术细节。
>
> 版本历史：v1（初版）→ v2（技术栈明细）→ v3（飞书 + Text-to-SQL）→ v3.1（空教室 + 自定义 AI + 行程规划）

---

## 1. 项目目标

构建一个运行在**个人笔记本**上的智能 Agent + Web 管理界面，帮助重庆邮电大学学生：

- 自动抓取**教务系统课表**、**学习通作业**、**数你最灵作业**
- 通过**飞书应用（App）**主动推送和双向对话
- 支持**Text-to-SQL 自然语言查询**：用自然语言查询课表、作业、待办
- 提供 **Web 管理仪表盘**，可视化查看课表、作业、待办、空教室
- 支持通过飞书自然语言**创建待办事项**
- 支持**空教室查询**、**自习行程规划**
- 支持**自定义 AI 提供商**（Ollama、其他 OpenAI 兼容 API）
- 支持**自定义定时提醒**（免打扰定时推送）

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
5. 在 Web 设置页面配置

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
│  │  │  │ (关键词匹)│  │ (SQL生成)    │  │ (12工具) │ │   │   │
│  │  │  │ 配+LLM)   │  │              │  │          │ │   │   │
│  │  │  └──────────┘  └──────────────┘  └──────────┘ │   │   │
│  │  └────────────────────────────────────────────────┘   │   │
│  │                                                        │   │
│  │  API 路由:                                              │   │
│  │  ├── /api/feishu/app/event  ← 飞书事件回调              │   │
│  │  ├── /api/courses             ← 课表 CRUD               │   │
│  │  ├── /api/assignments         ← 作业 CRUD               │   │
│  │  ├── /api/todos               ← 待办 CRUD               │   │
│  │  ├── /api/rooms               ← 空教室查询              │   │
│  │  ├── /api/config              ← 系统配置                │   │
│  │  ├── /api/data-sources        ← 数据源管理              │   │
│  │  ├── /api/notification        ← 通知记录                │   │
│  │  ├── /api/llm                 ← AI 对话                 │   │
│  │  ├── /api/ai/providers        ← 自定义 AI 配置          │   │
│  │  └── /api/custom-reminders    ← 自定义定时提醒          │   │
│  │                                                        │   │
│  │  APScheduler 定时任务:                                   │   │
│  │  ├── 教务课表爬虫  (每天06:00)                           │   │
│  │  ├── 每日日报      (每天07:50)                           │   │
│  │  ├── 截止提醒扫描  (每小时)                              │   │
│  │  ├── 作业同步      (每30分钟)                            │   │
│  │  ├── 作业清理      (每天03:00)                           │   │
│  │  ├── 教室数据刷新  (每天04:00)                           │   │
│  │  ├── 自定义提醒    (每分钟)                              │   │
│  │  └── 待办提醒      (每5分钟)                             │   │
│  │                                                        │   │
│  │  SQLite (data/campus.db)                               │   │
│  └──────────────────────────────────────────────────────┘   │
│                         ↕ SSH 反向隧道                       │
│                   公网服务器 (SERVER_IP:9997)            │
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
├── start.bat / start.sh          # 一键启动
├── docker-start.bat              # Docker 一键启动
│
├── app/
│   ├── main.py                   # FastAPI 入口 + 生命周期管理
│   ├── config.py                 # 从环境变量加载配置
│   │
│   ├── api/                      # API 路由层（11个模块）
│   │   ├── courses.py            # 课表 CRUD
│   │   ├── assignments.py        # 作业 CRUD + 同步 + 清理
│   │   ├── todos.py              # 待办 CRUD
│   │   ├── rooms.py              # 空教室查询 + 数据刷新
│   │   ├── config.py             # 系统配置（数据库优先）
│   │   ├── data_sources.py       # 数据源 CRUD
│   │   ├── feishu_app.py         # 飞书事件回调（含去重）
│   │   ├── notification.py       # 通知测试接口
│   │   ├── llm.py                # AI 对话 / 测试接口
│   │   ├── ai_providers.py       # 自定义 AI 提供商配置
│   │   └── custom_reminders.py   # 自定义定时提醒 CRUD
│   │
│   ├── crawlers/                 # 爬虫模块（4个）
│   │   ├── jwxt_crawler.py       # 教务系统课表（httpx/Playwright）
│   │   ├── chaoxing_crawler.py   # 学习通作业（AES-CBC 加密）
│   │   ├── smartestu_crawler.py  # 数你最灵作业（JWT 认证）
│   │   └── room_crawler.py       # 教室课表（并发抓取）
│   │
│   ├── db/                       # 数据库
│   │   ├── models.py             # 9 个数据模型
│   │   └── session.py            # 异步数据库连接 + 列迁移
│   │
│   ├── llm/                      # AI 模块
│   │   ├── client.py             # DeepSeek/自定义 API 客户端
│   │   ├── tools.py              # 12 个工具定义 + 执行器
│   │   └── text_to_sql.py        # Text-to-SQL 引擎（独立）
│   │
│   ├── notifications/            # 推送通知
│   │   ├── bark_notifier.py      # Bark iOS 推送
│   │   └── feishu_notifier.py    # 飞书群机器人推送
│   │
│   ├── scheduler/                # 定时任务
│   │   ├── jobs.py               # 8 个定时任务函数
│   │   └── task_scheduler.py     # APScheduler 封装
│   │
│   └── services/                 # 业务逻辑层（6个服务）
│       ├── course_service.py     # 课表服务
│       ├── assignment_service.py # 作业服务
│       ├── todo_service.py       # 待办服务
│       ├── room_service.py       # 空教室服务
│       ├── feishu_app_service.py # 飞书 App 服务
│       ├── config_store.py       # 数据库配置存储
│       └── tunnel.py             # SSH 隧道管理
│
├── frontend/                     # Web 前端
│   ├── src/
│   │   ├── App.tsx               # 路由配置（9个页面）
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx     # 仪表盘
│   │   │   ├── Courses.tsx       # 课表
│   │   │   ├── Assignments.tsx   # 作业
│   │   │   ├── Todos.tsx         # 待办
│   │   │   ├── Rooms.tsx         # 空教室
│   │   │   ├── Schedules.tsx     # 行程安排
│   │   │   ├── Tools.tsx         # 工具
│   │   │   ├── Notifications.tsx # 通知记录
│   │   │   └── Settings.tsx      # 设置
│   │   └── components/
│   │       ├── Layout.tsx        # 导航布局
│   │       └── ui/               # shadcn/ui 组件
│   └── ...
│
├── docs/
│   └── AI_开发指南.md            # AI 开发参考（本文件）
├── scripts/                      # 部署脚本
├── tests/                        # 测试
├── docker-compose.yml
├── requirements.txt
└── Dockerfile
```

---

## 6. 数据模型

```python
# app/db/models.py - 当前完整模型（9个）

class User(Base):
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True, index=True)
    student_id    = Column(String(32), nullable=True)
    created_at    = Column(DateTime, default=func.now())
    # 关系
    data_sources  = relationship("DataSource", back_populates="user", lazy="dynamic")
    courses       = relationship("Course", back_populates="user", lazy="dynamic")
    assignments   = relationship("Assignment", back_populates="user", lazy="dynamic")
    notifications = relationship("Notification", back_populates="user", lazy="dynamic")
    todos         = relationship("Todo", back_populates="user", lazy="dynamic")

class DataSource(Base):
    """用户在 Web UI 中添加的数据源配置"""
    __tablename__ = "data_sources"
    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=False)
    type          = Column(String(20), nullable=False)    # "jwxt"|"chaoxing"|"smartestu"
    name          = Column(String(100))
    enabled       = Column(Boolean, default=True)
    credentials   = Column(Text)                          # Fernet 加密后的 JSON
    last_sync     = Column(DateTime, nullable=True)
    sync_status   = Column(String(20), default="pending")
    error_message = Column(Text, nullable=True)
    created_at    = Column(DateTime, default=func.now())
    # 关系
    user          = relationship("User", back_populates="data_sources")
    courses       = relationship("Course", back_populates="source")
    assignments   = relationship("Assignment", back_populates="source")

class Course(Base):
    __tablename__ = "courses"
    id              = Column(Integer, primary_key=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    source_id       = Column(Integer, ForeignKey("data_sources.id"), nullable=True)
    name            = Column(String(200), nullable=False)
    teacher         = Column(String(100), nullable=True)
    location        = Column(String(200), nullable=True)       # 默认地点
    location_schedule = Column(Text, nullable=True)            # JSON多周次地点
    day_of_week     = Column(Integer)                          # 1=周一…7=周日
    start_week      = Column(Integer)
    end_week        = Column(Integer)
    week_mask       = Column(String(30))                       # 二进制周次标记
    start_slot      = Column(Integer)
    end_slot        = Column(Integer)
    start_time      = Column(String(10))
    end_time        = Column(String(10))
    created_at      = Column(DateTime, default=func.now())
    updated_at      = Column(DateTime, default=func.now(), onupdate=func.now())

class Assignment(Base):
    __tablename__ = "assignments"
    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=False)
    source_id     = Column(Integer, ForeignKey("data_sources.id"), nullable=True)
    remote_id     = Column(String(100), nullable=True)         # 平台原始ID（去重）
    title         = Column(String(500), nullable=False)
    description   = Column(Text, nullable=True)
    course_name   = Column(String(200), nullable=True)
    due_time      = Column(DateTime, nullable=True)
    is_completed  = Column(Boolean, default=False)
    created_at    = Column(DateTime, default=func.now())
    updated_at    = Column(DateTime, default=func.now(), onupdate=func.now())
    # 推送状态
    notified_new  = Column(Boolean, default=False)
    notified_24h  = Column(Boolean, default=False)
    notified_1h   = Column(Boolean, default=False)

class Todo(Base):
    """待办事项"""
    __tablename__ = "todos"
    id           = Column(Integer, primary_key=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    title        = Column(String(500), nullable=False)
    description  = Column(Text, nullable=True)
    due_time     = Column(DateTime, nullable=True)
    priority     = Column(String(20), default="normal")        # low/normal/high
    is_completed = Column(Boolean, default=False)
    source       = Column(String(50), default="manual")        # manual/llm
    reminder_enabled = Column(Boolean, default=False)          # 是否开启提醒
    reminder_sent    = Column(Boolean, default=False)          # 提醒是否已发送
    created_at   = Column(DateTime, default=func.now())
    updated_at   = Column(DateTime, default=func.now(), onupdate=func.now())

class Notification(Base):
    __tablename__ = "notifications"
    id       = Column(Integer, primary_key=True)
    user_id  = Column(Integer, ForeignKey("users.id"), nullable=False)
    type     = Column(String(50), nullable=False)              # new_assignment|deadline_24h等
    content  = Column(Text, nullable=False)
    sent_at  = Column(DateTime, default=func.now())
    success  = Column(Boolean, default=True)

class SystemConfig(Base):
    """系统配置键值存储"""
    __tablename__ = "system_configs"
    id          = Column(Integer, primary_key=True)
    key         = Column(String(100), unique=True, nullable=False, index=True)
    value       = Column(Text, nullable=True)
    description = Column(String(200), nullable=True)
    updated_at  = Column(DateTime, default=func.now(), onupdate=func.now())

class RoomSchedule(Base):
    """教室课表/空教室数据"""
    __tablename__ = "room_schedules"
    id          = Column(Integer, primary_key=True)
    room_name   = Column(String(100), nullable=False, index=True)
    room_type   = Column(String(50), default="教室")
    capacity    = Column(Integer, nullable=True)
    building    = Column(String(100), nullable=True)
    day_of_week = Column(Integer, nullable=False)
    start_slot  = Column(Integer, nullable=False)
    end_slot    = Column(Integer, nullable=False)
    start_week  = Column(Integer, nullable=False)
    end_week    = Column(Integer, nullable=False)
    week_mask   = Column(String(30), nullable=True)
    course_name = Column(String(200), nullable=True)           # 占用课程名
    created_at  = Column(DateTime, default=func.now())
    updated_at  = Column(DateTime, default=func.now(), onupdate=func.now())

class CustomReminder(Base):
    """自定义定时提醒"""
    __tablename__ = "custom_reminders"
    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=False)
    name          = Column(String(200), nullable=False)
    title         = Column(String(200), nullable=False)
    content       = Column(Text, nullable=True)
    repeat_type   = Column(String(20), nullable=False, default="daily")  # daily/weekly/monthly
    repeat_day    = Column(Integer, nullable=True)              # weekly=0-6, monthly=1-31
    reminder_time = Column(String(5), nullable=False)           # HH:MM
    enabled       = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=func.now())
    updated_at    = Column(DateTime, default=func.now(), onupdate=func.now())

class AiProvider(Base):
    """用户自定义 AI 提供商配置"""
    __tablename__ = "ai_providers"
    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    name        = Column(String(100), nullable=False)           # 用户自定义名称
    api_key     = Column(String(500), nullable=False)
    base_url    = Column(String(500), nullable=False)
    model       = Column(String(100), nullable=False)
    is_active   = Column(Boolean, default=False)               # 是否当前使用
    created_at  = Column(DateTime, default=func.now())
    updated_at  = Column(DateTime, default=func.now(), onupdate=func.now())
```

---

## 7. LLM 模块详解

### 7.1 智能分流架构（v3.1）

```
用户消息 → _match_tool() 关键词匹配
    ├── 匹配到预定义工具 → 直接执行工具 → 返回结果（快、稳、省）
    └── 未匹配 → chat_with_tools()
              ├── LLM 判断调用工具 → 执行 → LLM 总结 → 返回
              ├── LLM 判断是查询 → Text-to-SQL → 执行SQL → LLM总结
              └── LLM 判断是闲聊 → 直接回复
```

### 7.2 关键词匹配（`_match_tool` in `client.py`）

优先使用预定义工具（快速响应），未匹配则降级到 LLM 工具调用：

| 优先级 | 关键词示例 | 匹配工具 |
|--------|-----------|---------|
| 1 | "添加待办""帮我记""提醒我" | `create_todo` |
| 2 | "自习""学习""安排""去哪" | `plan_schedule` |
| 3 | "今天有什么课""今日课表" | `get_today_courses` |
| 4 | "明天课表""明天上课" | `get_tomorrow_courses` |
| 5 | "本周课表""这周课程" | `get_this_week_courses` |
| 6 | "第几周""几周了" | `get_current_week_number` |
| 7 | "未完成作业""作业列表" | `get_pending_assignments` |
| 8 | "过期作业" | `get_overdue_assignments` |
| 9 | "查看待办""我的待办" | `get_todos` |
| 10 | "空教室""找教室" | `query_empty_rooms` |
| - | 其他 | 降级 LLM 处理 |

### 7.3 Text-to-SQL 引擎（`text_to_sql.py`）

独立模块，不依赖 LLM Function Calling：

```
流程：
1. 用户问题 → get_database_schema() 获取 Schema
2. 构造提示词（含完整表结构 + 动态周数 + 用户ID）
3. 调用 DeepSeek → 生成 SELECT SQL
4. SQL 安全校验（禁止 INSERT/UPDATE/DELETE/DROP 等）
5. 执行 SQL 查询 SQLite
6. 格式化查询结果为自然语言
```

特点：
- 动态生成提示词（周数、用户ID、学期日期均运行时计算）
- 只允许 SELECT，禁止所有写操作
- 限制返回行数 MAX_ROWS=20

### 7.4 预定义工具（tools.py - 12个）

| 工具 | 功能 | 参数 |
|------|------|------|
| `get_today_courses` | 今天的课表 | 无 |
| `get_day_courses` | 指定日期的课表 | date (YYYY-MM-DD) |
| `get_tomorrow_courses` | 明天的课表 | 无 |
| `get_this_week_courses` | 本周课表 | 无 |
| `get_pending_assignments` | 待完成作业 | days (可选) |
| `get_overdue_assignments` | 已过期作业 | 无 |
| `get_current_week_number` | 当前周数 | 无 |
| `get_todos` | 查看待办 | status, priority |
| `create_todo` | 创建待办 | title, description, due_time, priority |
| `flex_query` | 灵活查询（Text-to-SQL）| question |
| `query_empty_rooms` | 查询空教室 | day_of_week, start_slot, building, min_capacity |
| `plan_schedule` | 智能行程规划 | request (自然语言描述) |

### 7.5 行程规划工具（`plan_schedule`）

当用户说"今天上午想去自习"时：

1. 解析时间关键词（今天/明天/后天、上午/下午/晚上）
2. 查询该时段的课程表
3. 查询该时段的空教室（含教室类型、容量、教学楼）
4. 综合输出：有课则列课表，无课则推荐 Top3 空教室
5. 无具体日期时输出未来 7 天概览

### 7.6 自定义 AI 提供商

用户可在 Web 设置中配置任意 OpenAI 兼容 API：

- 支持 DeepSeek（默认）、Ollama 本地模型、其他兼容 API
- 每个提供商配：name、api_key、base_url、model
- 支持多提供商切换（`is_active` 标记当前使用的）
- 运行时从数据库动态读取激活配置（`_get_active_model`）

### 7.7 DSML 格式兼容

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
        ├── send_text_reply(chat_id, text, db)
        │   └── chat_or_reply()
        │       ├── _match_tool() 关键词匹配 → 直接执行工具
        │       └── chat_with_tools() → LLM Function Calling
        └── send_message(chat_id, reply)
```

---

## 9. API 接口一览

### 飞书应用回调

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/feishu/app/event` | 事件回调（含消息去重）|
| GET  | `/api/feishu/app/status` | 配置状态 |
| POST | `/api/feishu/app/test` | 测试 token 获取 |

### 课程

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/courses` | 课表列表（支持 week 参数）|
| GET  | `/api/courses/today` | 今日课程 |
| GET  | `/api/courses/summary` | 课表摘要统计 |
| POST | `/api/courses/sync` | 手动触发课表同步 |

### 作业

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/assignments` | 作业列表（支持 status 筛选）|
| GET  | `/api/assignments/today` | 今日截止作业 |
| GET  | `/api/assignments/upcoming` | 未来 N 天截止作业 |
| POST | `/api/assignments/sync` | 手动触发作业同步 |
| POST | `/api/assignments/{id}/complete` | 标记完成 |
| DELETE | `/api/assignments/{id}` | 删除作业 |
| POST | `/api/assignments/cleanup` | 清理过期已完成作业 |

### 待办

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/todos` | 待办列表（status/priority 筛选）|
| GET  | `/api/todos/{id}` | 单个待办 |
| POST | `/api/todos` | 创建待办 |
| PUT  | `/api/todos/{id}` | 更新待办 |
| DELETE | `/api/todos/{id}` | 删除待办 |
| POST | `/api/todos/{id}/complete` | 标记完成 |
| POST | `/api/todos/llm/create` | LLM 创建待办 |
| GET  | `/api/todos/summary/dashboard` | 待办统计 |

### 空教室

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/rooms/empty` | 查询空教室（多参数筛选）|
| POST | `/api/rooms/refresh` | 刷新教室数据 |
| GET  | `/api/rooms/stats` | 教室数据统计 |
| GET  | `/api/rooms/buildings` | 教学楼列表 |

### 数据源

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/data-sources` | 获取所有数据源 |
| POST | `/api/data-sources` | 新增数据源 |
| DELETE | `/api/data-sources/{id}` | 删除数据源 |

### AI 对话

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/llm/chat` | 简单对话 |
| POST | `/api/llm/test` | 完整机器人回复测试 |
| GET  | `/api/llm/status` | LLM 服务状态 |

### 自定义 AI 提供商

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/ai/providers` | 所有 AI 配置 |
| POST | `/api/ai/providers` | 添加 AI 配置 |
| PUT  | `/api/ai/providers/{id}` | 更新配置 |
| DELETE | `/api/ai/providers/{id}` | 删除配置 |
| POST | `/api/ai/providers/{id}/activate` | 切换使用 |

### 自定义提醒

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/custom-reminders` | 所有提醒 |
| POST | `/api/custom-reminders` | 创建提醒 |
| PUT  | `/api/custom-reminders/{id}` | 更新提醒 |
| DELETE | `/api/custom-reminders/{id}` | 删除提醒 |

### 通知

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/notification/test` | 测试 Bark 推送 |
| POST | `/api/notification/feishu/test` | 测试飞书推送 |
| GET  | `/api/notification/status` | 推送服务状态 |

### 系统配置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/config` | 获取所有配置 |
| PUT  | `/api/config` | 更新配置 |
| GET  | `/api/config/scheduler` | 定时任务状态 |

### 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/health` | 基础健康检查 |
| GET  | `/api/health/detailed` | 详细服务状态（含所有组件）|

---

## 10. 前端页面

| 页面 | 路由 | 功能 |
|------|------|------|
| 仪表盘 | `/` | 今日概览、课表、作业统计、数据源状态 |
| 课表 | `/courses` | 周视图课表网格，支持切换周次 |
| 作业 | `/assignments` | 作业列表，筛选、标记完成、删除 |
| 待办 | `/todos` | 待办列表，创建、完成、筛选、提醒开关 |
| 空教室 | `/rooms` | 教学楼/时段筛选，查看空闲教室 |
| 行程安排 | `/schedules` | 每日/每周行程规划 |
| 工具 | `/tools` | 功能入口集合页 |
| 通知 | `/notifications` | 推送历史记录 |
| 设置 | `/settings` | 数据源管理、AI 配置、提醒设置、系统配置 |

---

## 11. 定时任务

| 任务 | 频率 | 说明 |
|------|------|------|
| 教务课表爬虫 | 每天 06:00 | 从 jwzx.cqupt.edu.cn 抓取课表 |
| 每日课表推送 | 每天 07:50 | 推送今日课表（Bark + 飞书）|
| 作业截止检查 | 每小时 | 扫描即将截止作业，推送提醒 |
| 作业同步 | 每 30 分钟 | 同步学习通 + 数你最灵作业 |
| 作业清理 | 每天 03:00 | 清理超过保留天数的已完成作业 |
| 教室数据刷新 | 每天 04:00 | 全量刷新教室课表数据 |
| 自定义提醒检查 | 每 1 分钟 | 检查到期的自定义提醒并推送 |
| 待办提醒检查 | 每 5 分钟 | 检查启用了提醒的待办，到期推送 |

---

## 12. 爬虫模块

### 教务系统课表（`jwxt_crawler.py`）
- **URL**: `http://jwzx.cqupt.edu.cn/kebiao/kb_stu.php?xh={student_id}`
- **方式**: 优先 httpx（轻量），备选 Playwright（反检测）
- **解析**: BeautifulSoup4 解析 kbTd div，支持 week_mask 和 location_schedule
- **网络**: 需校园网/VPN

### 学习通（`chaoxing_crawler.py`）
- **认证**: 账号密码 + AES-CBC 加密 + 滑块验证码
- **作业查询**: 遍历课程列表获取未完成作业
- **网络**: 公网可访问

### 数你最灵（`smartestu_crawler.py`）
- **认证**: JWT Bearer Token（自动获取 + 刷新）
- **作业查询**: POST 接口 `queryHomeworks`
- **网络**: 公网可访问

### 教室课表（`room_crawler.py`）
- **URL**: `http://jwzx.cqupt.edu.cn/kebiao/kb_room.php?room={room_name}`
- **方式**: 并发抓取（Semaphore 限流），解析教室 kbTd
- **教室信息**: 类型（教室/实验室/室外）、容量、教学楼
- **网络**: 需校园网/VPN

---

## 13. SSH 隧道模块

用于本地开发时暴露服务至公网（替代 cpolar/frp）。

### 工作原理
- 启动时执行 `ssh -R` 反向隧道
- 固定端口映射：远程 `9997` → 本地 `8000`
- 应用关闭时自动停止隧道

### 配置
```env
TUNNEL_SERVER_HOST=SERVER_IP
TUNNEL_SERVER_USER=root
TUNNEL_KEY_PATH=/path/to/private_key
```

---

## 14. 通知通道

项目支持三种通知通道：

| 通道 | 实现 | 用途 |
|------|------|------|
| 飞书 App（双向） | `feishu_app_service.py` | 双向对话、查询课表/作业/待办 |
| 飞书群机器人 | `feishu_notifier.py` | 定时推送、作业提醒、课表通知 |
| Bark iOS | `bark_notifier.py` | iPhone 推送通知 |

---

## 15. 技术栈

### 后端

| 模块 | 技术 |
|------|------|
| 语言 | Python 3.11+ |
| Web 框架 | FastAPI + uvicorn |
| 任务调度 | APScheduler 3.x (AsyncIO) |
| 数据库 | SQLite + SQLAlchemy 2.0 (asyncio) |
| HTTP 客户端 | httpx |
| 浏览器自动化 | Playwright |
| 滑块识别 | ddddocr |
| HTML 解析 | BeautifulSoup4 (lxml) |
| AI | DeepSeek / 自定义 OpenAI 兼容 API |
| 加密 | cryptography (Fernet + AES-CBC) |

### 前端

| 模块 | 技术 |
|------|------|
| 框架 | React 18 + TypeScript |
| 构建 | Vite |
| 组件 | shadcn/ui (Radix UI) |
| 样式 | Tailwind CSS |
| 图表 | Recharts |
| 状态管理 | Zustand |
| 路由 | React Router v6 |

---

## 16. 安全注意事项

- 所有密码/Token 通过 `.env` 或 Web 设置页面配置，自动 Fernet 加密存储
- `.env` 已加入 `.gitignore`
- 前端不存储凭据，所有敏感操作走后端 API
- 飞书消息去重（30s TTL 内存缓存）
- Text-to-SQL 只允许 SELECT，禁止所有写操作
- 配置更新时同时同步到运行时 settings 对象
- 数据库列自动迁移（`_migrate_missing_columns`）兼容旧版本

---

## 17. 环境变量

```env
# ===== 基础 =====
STUDENT_ID=2025xxxxxx
DEPLOY_MODE=laptop
TZ=Asia/Shanghai
DATABASE_URL=sqlite+aiosqlite:///data/campus.db
FRONTEND_URL=http://localhost:3000

# ===== DeepSeek / LLM =====
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
DEEPSEEK_MODEL=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com

# ===== 飞书应用 =====
FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxx
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx

# ===== SSH 隧道 =====
TUNNEL_SERVER_HOST=SERVER_IP
TUNNEL_SERVER_USER=root
TUNNEL_KEY_PATH=

# ===== 校历 =====
TERM_START_DATE=2026-03-02

# ===== 加密 =====
FERNET_KEY=xxxxxxxxxxxxxxxx

# ===== 学习通 =====
CHAOXING_USERNAME=手机号
CHAOXING_PASSWORD=密码

# ===== 数你最灵 =====
SMARTESTU_STUDENT_ID=学号
SMARTESTU_PASSWORD=密码
SMARTESTU_SCHOOL_ID=cqupt

# ===== Bark =====
BARK_KEY=xxxxxxxxxxxxxxxx

# ===== 教室查询 =====
CAMPUS=main
ENABLE_LAB_QUERY=false

# ===== VPN（仅 server 模式）=====
VPN_HOST=vpn.cqupt.edu.cn
VPN_USERNAME=
VPN_PASSWORD=
```

---

## 18. 当前状态（2026-05-28）

| 模块 | 状态 | 备注 |
|------|------|------|
| 飞书回调 | ✅ 正常运行 | 通过 SSH 隧道暴露 |
| 消息去重 | ✅ 已实现 | 30s TTL 内存缓存 |
| LLM 聊天 | ✅ 正常运行 | 关键词匹配 + LLM Function Calling |
| Text-to-SQL | ✅ 已实现 | 独立引擎 + 安全检查 |
| 课表查询 | ✅ 正常 | 预定义工具 + Text-to-SQL |
| 作业查询 | ✅ 正常 | 预定义工具 + Text-to-SQL |
| 待办管理 | ✅ 正常 | 飞书 + Web 双端 |
| 空教室查询 | ✅ 已实现 | 支持教学楼/时段筛选 |
| 行程规划 | ✅ 已实现 | 自然语言 → 查课表 + 推荐空教室 |
| 自定义 AI | ✅ 已实现 | Web 配置，运行时切换 |
| 自定义提醒 | ✅ 已实现 | 每天/每周/每月定时推送 |
| 待办提醒 | ✅ 已实现 | 到期前自动推送 |
| 飞书推送 | ✅ 正常 | Bark + 飞书双通道 |
| 教务课表爬虫 | ✅ 有数据 | httpx + Playwright 双方案 |
| 数你最灵爬虫 | ✅ 已实现 | JWT 自动刷新 |
| 学习通爬虫 | ✅ 已实现 | AES-CBC 加密登录 |
| 教室爬虫 | ✅ 已实现 | 并发抓取 |
| SSH 隧道 | ✅ 自动管理 | 随服务启停 |
| Web 前端 | ✅ 可用 | 9 个页面 |
