# CampusPilot — AI 待同步技能文档

> 本文档记录项目中**新近开发完成的功能**，供 AI 编程助手（Trae/Cursor）在后续开发时同步参考。包含完整的数据模型、API 接口、前端页面、定时任务等细节。

---

## 1. 自定义定时提醒系统

### 1.1 数据模型

```python
# app/db/models.py — CustomReminder
class CustomReminder(Base):
    """自定义定时提醒"""
    __tablename__ = "custom_reminders"

    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, ForeignKey("users.id"))
    name          = Column(String(200))     # 提醒名称（如"喝水提醒"）
    title         = Column(String(200))     # 推送标题（如"💧 喝水时间"）
    content       = Column(Text)            # 推送内容（可选）
    repeat_type   = Column(String(20))      # "daily" / "weekly" / "monthly"
    repeat_day    = Column(Integer)         # weekly=0-6(周一到周日), monthly=1-31
    reminder_time = Column(String(5))       # HH:MM 格式
    enabled       = Column(Boolean, default=True)
    created_at    = Column(DateTime)
    updated_at    = Column(DateTime)
```

### 1.2 API 接口

路径前缀：`/api/custom-reminders`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/custom-reminders` | 获取所有自定义提醒列表 |
| POST | `/api/custom-reminders` | 创建自定义提醒 |
| PUT | `/api/custom-reminders/{reminder_id}` | 更新提醒（启/停、修改时间等） |
| DELETE | `/api/custom-reminders/{reminder_id}` | 删除提醒 |

**POST 请求体**：
```json
{
  "name": "喝水提醒",
  "title": "💧 喝水时间",
  "content": "该喝水了！每天8杯水保持健康",
  "repeat_type": "daily",
  "repeat_day": null,
  "reminder_time": "10:00"
}
```

**repeat_type 规则**：
- `daily` — 每天推送，repeat_day 传 null
- `weekly` — 每周某天，repeat_day=0(周一)~6(周日)
- `monthly` — 每月某日，repeat_day=1~31

### 1.3 文件路径

| 层级 | 文件 |
|------|------|
| 数据模型 | `app/db/models.py:154` |
| API 路由 | `app/api/custom_reminders.py` |
| 注册路由 | `app/main.py:157` `app.include_router(custom_reminders_router)` |

### 1.4 定时任务

**任务函数**：`check_custom_reminders` 在 `app/scheduler/jobs.py`
**触发器**：`interval` 每 1 分钟
**逻辑**：
1. 查询所有 `enabled=True` 且 `reminder_time == 当前HH:MM` 的记录
2. 根据 `repeat_type` 过滤：daily 全部通过，weekly 检查今天星期几，monthly 检查今天几号
3. 同时推送 Bark + 飞书，使用 `BarkNotifier.send_custom()` 和 `FeishuNotifier.send_text()`

**注册代码**（在 `register_tasks()` 末尾）：
```python
scheduler.scheduler.add_job(
    check_custom_reminders,
    "interval", minutes=1,
    id="check_custom_reminders",
    replace_existing=True,
)
```

### 1.5 前端页面

**位置**：`frontend/src/pages/Settings.tsx`
**组件**：设置页中的"自定义定时提醒"Card，在 VPN 配置卡片下方、定时任务状态卡片上方
**功能**：
- 列表展示所有提醒：名称 + 循环描述（"每天" / "周一" / "每月5日"）+ 时间 + 开关按钮 + 删除按钮
- "添加提醒"按钮弹出模态框表单
- 表单包含：提醒名称、推送标题、推送内容、重复类型(每天/每周/每月)、重复日、推送时间

---

## 2. 待办事项提醒功能

### 2.1 数据模型变更

```python
# app/db/models.py — Todo 新增字段
class Todo(Base):
    reminder_enabled = Column(Boolean, default=False)  # 是否开启提醒
    reminder_sent    = Column(Boolean, default=False)  # 提醒是否已发送（防重复）
```

### 2.2 API 变更

`POST /api/todos` 新增请求字段：
```json
{
  "title": "交作业",
  "due_time": "2026-06-01T23:59",
  "reminder_enabled": true
}
```

`PUT /api/todos/{todo_id}` 新增可更新字段：`reminder_enabled`

`GET /api/todos` 响应新增字段：
```json
{
  "reminder_enabled": true,
  "reminder_sent": false
}
```

### 2.3 修改的文件

| 文件 | 改动 |
|------|------|
| `app/db/models.py` | Todo 表新增 `reminder_enabled`、`reminder_sent` |
| `app/services/todo_service.py` | `create_todo()` 接受 `reminder_enabled` 参数；`_todo_to_dict()` 输出两个新字段 |
| `app/api/todos.py` | `TodoCreateRequest`/`TodoUpdateRequest` 增加 `reminder_enabled` |

### 2.4 定时任务

**任务函数**：`check_todo_reminders` 在 `app/scheduler/jobs.py`
**触发器**：`interval` 每 5 分钟
**逻辑**：
1. 查询 `reminder_enabled=True AND is_completed=False AND reminder_sent=False AND due_time IS NOT NULL`
2. 计算距到期的小时数 `hours_left`
3. 只处理 `hours_left <= 1` 的待办（即将到期或已过期）
4. 同时推送 Bark + 飞书
5. 标记 `reminder_sent = True`，防止重复推送

```python
scheduler.scheduler.add_job(
    check_todo_reminders,
    "interval", minutes=5,
    id="check_todo_reminders",
    replace_existing=True,
)
```

### 2.5 前端变更

**文件**：`frontend/src/pages/Todos.tsx`

**创建表单**新增勾选框：
```
[✓] 到期前 1 小时推送提醒（需配置 Bark 或飞书）
```

**待办卡片**新增状态标签：
- `🔕 提醒中` — 已开启提醒，尚未到期
- `🔔 已提醒` — 提醒已发送

### 2.6 TodoService 关键方法签名

```python
async def create_todo(
    self, title: str, user_id=None,
    description=None, due_time=None,
    priority="normal", source="manual",
    reminder_enabled=False,  # ← 新增
) -> dict

def _todo_to_dict(self, todo: Todo) -> dict:
    return {
        ...
        "reminder_enabled": todo.reminder_enabled,   # ← 新增
        "reminder_sent": todo.reminder_sent,          # ← 新增
    }
```

---

## 3. 配置迁移：从 .env 到数据库

### 3.1 概述

以下配置项已从 `.env` 文件**迁移到数据库** `system_configs` 表。通过 Web 设置页面修改后即时生效，重启不丢失。

### 3.2 迁移的配置项

| 配置键 | 说明 | 前端设置页面位置 |
|--------|------|-----------------|
| `student_id` | 学号 | 用户信息卡片 |
| `chaoxing_username` | 学习通手机号 | 学习通配置卡片 |
| `chaoxing_password` | 学习通密码 | 学习通配置卡片（password 输入框） |
| `smartestu_student_id` | 数你最灵学号 | 数你最灵配置卡片 |
| `smartestu_password` | 数你最灵密码 | 数你最灵配置卡片（password 输入框） |
| `deepseek_api_key` | DeepSeek API Key | DeepSeek AI 配置卡片（password 输入框） |
| `deepseek_model` | 模型选择(flash/pro) | DeepSeek AI 配置卡片（Select 下拉） |
| `feishu_app_id` | 飞书应用 App ID | 飞书应用配置卡片 |
| `feishu_app_secret` | 飞书应用 App Secret | 飞书应用配置卡片（password 输入框） |
| `tunnel_server_host` | 公网服务器 IP | 公网服务器配置卡片 |
| `tunnel_server_user` | 公网服务器用户名 | 公网服务器配置卡片 |
| `tunnel_remote_port` | 远程监听端口 | 公网服务器配置卡片 |
| `tunnel_local_port` | 本地服务端口 | 公网服务器配置卡片 |
| `tunnel_key_path` | SSH 密钥路径 | 公网服务器配置卡片 |
| `vpn_host` | VPN 地址 | VPN 配置卡片 |
| `vpn_username` | VPN 用户名 | VPN 配置卡片 |
| `vpn_password` | VPN 密码 | VPN 配置卡片（password 输入框） |

### 3.3 数据库优先读取策略

**核心方法**：`ConfigStoreService.load_all_into_settings(settings_obj)` 在 `app/services/config_store.py`

**启动流程**（见 `app/main.py` lifespan）：
1. `store.migrate_from_env()` — 首次运行时将 .env 值写入数据库
2. `store.load_all_into_settings()` — 用数据库值覆盖 settings 对象（**数据库优先**）

**API 读取**：`GET /api/config` 使用 `store.get(key, settings.key)` 逻辑：数据库有值则用数据库，否则用 .env 兜底

**API 写入**：`PUT /api/config` 同时写入数据库 + 更新运行时 `settings` 对象

### 3.4 当前 .env 中保留的配置

```ini
FERNET_KEY=          # 自动生成，加密密钥
TZ=Asia/Shanghai
DATABASE_URL=sqlite+aiosqlite:///data/campus.db
FRONTEND_URL=http://localhost:3000
```

### 3.5 SYSTEM_KEYS 定义

```python
# app/services/config_store.py
SYSTEM_KEYS = {
    "term_start_date": "学期开始日期，格式 YYYY-MM-DD",
    "bark_key": "Bark iOS 推送 Key",
    "deploy_mode": "部署模式: laptop / server",
    "feishu_webhook_url": "飞书群机器人 Webhook URL",
    "auto_cleanup_enabled": "自动清理过时数据开关",
    "auto_cleanup_days": "数据保留天数",
    # 以下为从 .env 迁移来的:
    "student_id": "学号",
    "chaoxing_username": "学习通账号（手机号）",
    "chaoxing_password": "学习通密码",
    "smartestu_student_id": "数你最灵学号",
    "smartestu_password": "数你最灵密码",
    "deepseek_api_key": "DeepSeek API Key",
    "deepseek_model": "DeepSeek 模型 (deepseek-chat / deepseek-reasoner)",
    "feishu_app_id": "飞书应用 App ID",
    "feishu_app_secret": "飞书应用 App Secret",
    "tunnel_server_host": "公网服务器 IP",
    "tunnel_server_user": "公网服务器用户名",
    "tunnel_remote_port": "公网服务器监听端口",
    "tunnel_local_port": "本地服务端口",
    "tunnel_key_path": "SSH 密钥路径",
    "vpn_host": "VPN 地址",
    "vpn_username": "VPN 用户名",
    "vpn_password": "VPN 密码",
}
```

---

## 4. 移除企业微信 & iCloud

### 4.1 已删除的内容

| 项目 | 详情 |
|------|------|
| `config.py` | 删除 `wxwork_corp_id/agent_id/agent_secret/token/encoding_aes_key` 5个字段及 `is_wxwork_configured` 属性 |
| `db/models.py` | 删除 User 表 `wxwork_userid` 字段 |
| `llm/client.py` | 删除 SQL Schema 注释中的 `wxwork_userid` |
| `requirements.txt` | 移除 `wechatpy[crypto]==1.8.18` 依赖 |
| 前端 Dashboard | 删除"企业微信"文字引用，改为"多语言支持" |
| 前端 Todos | 文字改为"支持通过飞书自然语言创建" |
| `api/todos.py` | 注释改为"飞书/LLM" |
| `config.py` | 删除 `caldav_url/username/password` 3个字段（iCloud 日历） |
| `.env.example` | 仅保留 `FERNET_KEY`, `TZ`, `DATABASE_URL`, `FRONTEND_URL` |
| `requirements.txt` | 移除 `caldav` 注释 |

### 4.2 测试文件更新

| 文件 | 改动 |
|------|------|
| `tests/conftest.py` | sample_user_data 移除 `wxwork_userid` |
| `tests/test_main.py` | 验证逻辑移除 wxwork_userid 断言 |
| `tests/test_config.py` | 企业微信测试用例替换为 DeepSeek 等新配置测试 |

---

## 5. 前端的 Settings 页面重构

### 5.1 页面结构

`frontend/src/pages/Settings.tsx` 现已包含以下配置卡片（按显示顺序）：

1. **用户信息** — 学号（可编辑）、部署模式（只读 Badge）
2. **DeepSeek AI 配置** — API Key（password）、模型选择（Select 下拉：flash/pro）
3. **学习通配置** — 手机号、密码
4. **数你最灵配置** — 学号、密码（学校 ID 固定为 cqupt）
5. **飞书应用配置** — App ID、App Secret
6. **飞书机器人 Webhook** — Webhook URL + 测试推送按钮
7. **学期配置** — 开始日期 + 自动计算当前周次
8. **Bark 推送配置** — Bark Key + 测试推送按钮
9. **公网服务器配置** — IP、用户名、远程/本地端口、SSH 密钥路径
10. **VPN 配置** — 地址、用户名、密码
11. **自定义定时提醒** — 提醒列表（名称、时间、开关、删除）+ 添加按钮
12. **定时任务状态** — 只读表格（任务名、触发器、下次执行、运行状态）
13. **数据管理** — 自动清理开关、保留天数、导出/清空

### 5.2 子组件

```tsx
function InputField({ label, field, config, updateField, type?, placeholder?, className? })
// 通用文本输入框

function SecretField({ label, field, config, updateField, placeholder? })
// 密码输入框（type="password"）
```

两个子组件接收 `config: SystemConfig` 和 `updateField` 回调，通过 `field: keyof SystemConfig` 泛型约束保证类型安全。

---

## 6. 定时任务完整清单

当前注册的所有任务（`app/scheduler/jobs.py` 中的 `register_tasks()`）：

| 任务名 | 触发方式 | 说明 |
|--------|---------|------|
| `sync_courses_daily` | daily 06:00 | 同步教务系统课表 |
| `send_daily_schedule` | daily 07:50 | 推送今日课表到 Bark+飞书 |
| `check_assignment_deadlines` | hourly :00 | 检查即将截止作业并推送 |
| `sync_assignments_periodically` | interval 30min | 同步学习通+数你最灵作业 |
| `cleanup_old_assignments` | daily 03:00 | 删除过时已完成作业 |
| `check_custom_reminders` | interval 1min | 检查并推送自定义提醒 |
| `check_todo_reminders` | interval 5min | 检查并推送待办到期提醒 |

### 6.1 TaskScheduler 类方法

```python
# app/scheduler/task_scheduler.py
scheduler.add_daily_task(func, hour, minute, name)     # 每日固定时间
scheduler.add_hourly_task(func, minute, name)           # 每小时固定分钟
scheduler.add_interval_task(func, minutes, name)        # 固定间隔
scheduler.add_custom_cron_task(func, cron_expr, name)   # 自定义 Cron
# 直接使用 scheduler.scheduler.add_job(...) 可注册任意 APScheduler job
```
