"""
DeepSeek API 调用客户端

使用 OpenAI 兼容接口直接调用 DeepSeek API
模型：deepseek-chat（v4 flash）
支持 Function Calling 获取课表、作业等真实数据
"""

import json
import logging
import re
from typing import List, Dict, Optional

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import settings
from app.llm.tools import TOOLS, execute_tool

logger = logging.getLogger(__name__)

def _match_tool(question: str) -> Optional[str]:
    """
    尝试将用户问题匹配到预定义工具。
    对于有自习/安排意图的查询，优先走 plan_schedule（综合处理课程+教室）。
    纯课程/作业/待办查询由 LLM 的 Function Calling 自动路由。

    返回工具名称，或 None 表示无法匹配（走 LLM 工具调用或聊天）
    """
    q = question.lower().strip()

    # ─── 创建待办 ───
    create_keywords = ["添加待办", "创建待办", "新增待办", "添加代办", "创建代办",
                       "帮我记", "提醒我", "别忘了"]
    if any(kw in q for kw in create_keywords):
        return "create_todo"

    # ─── 行程规划/自习安排（优先匹配，综合处理课程+教室）───
    plan_keywords = ["自习", "学习", "复习", "安排", "行程", "计划", "去哪",
                     "哪里可以", "哪个教室", "图书馆", "无课", "有空"]
    if any(kw in q for kw in plan_keywords):
        return "plan_schedule"

    # ─── 待完成作业（广泛匹配，避免掉入LLM Function Calling产生DSML）───
    pending_asmt = ["待完成作业", "没完成作业", "未完成作业", "有哪些作业",
                    "作业有哪些", "查看作业", "作业列表", "剩余作业",
                    "即将截止作业", "快要截止作业", "要交的作业",
                    "作业要交", "作业截止", "作业快截止",
                    "几天内要交", "天内要交", "天内的作业",
                    "最近作业", "当前作业", "本周作业"]
    if any(kw in q for kw in pending_asmt):
        return "get_pending_assignments"
    if "作业" in q and any(kw in q for kw in ["未完成", "要交", "截止", "到期",
                                                "快交", "还有", "几天", "天内",
                                                "未做", "没做", "没写", "提交"]):
        return "get_pending_assignments"

    # ─── 过期作业 ───
    if "过期" in q and "作业" in q:
        return "get_overdue_assignments"

    # ─── 查看待办 ───
    view_todo = ["查看待办", "查看todo", "我的待办", "我的todo",
                 "待办列表", "有哪些待办", "待办事项", "任务列表"]
    if any(kw in q for kw in view_todo):
        return "get_todos"

    # 未匹配 → 走 LLM Function Calling 或聊天
    return None

DEEPSEEK_BASE_URL = settings.llm_base_url

def _build_system_prompt() -> str:
    from datetime import date
    today_str = date.today().isoformat()

    # 从 term_start_date 动态推算学期
    term_start = date.fromisoformat(settings.term_start_date)
    term_year = term_start.year
    term_month = term_start.month
    if 2 <= term_month <= 7:
        # 春季学期（第二学期），学年是前一年-当年
        school_year = f"{term_year - 1}-{term_year}"
        semester_label = "第二学期"
    else:
        # 秋季学期（第一学期），学年是当年-下一年
        school_year = f"{term_year}-{term_year + 1}"
        semester_label = "第一学期"

    return f"""你是 CampusPilot 校园助手，运行在重庆邮电大学学生的个人学业管理系统中。

你可以帮助用户管理以下内容：
1. **课表查询** - 今日课表、本周课表、指定日期课程等
2. **作业管理** - 待完成作业、即将截止的作业
3. **待办管理** - 查看待办、创建新的待办事项
4. **空教室查询** - 查找空闲的自习教室
5. **行程规划** - 帮用户规划自习、学习时间，推荐空教室

**回答规则：**
- 对于「想去自习」「帮我安排」「去哪学习」等请求，请调用 plan_schedule 工具，帮用户查找空教室并给出具体推荐
- 对于简单的问候、闲聊，直接用自然语言回复即可
- 对于需要查询数据的问题（课表、作业、待办等），你会收到系统执行 SQL 后的结果，用友好的方式总结给用户
- 涉及时间时注意当前日期（今天是 {today_str}）

你的回答风格：
- 简洁清晰，直接给出有用信息
- 使用合适的 emoji 让消息更友好
- 如果用户问的问题超出能力范围，诚实告知
- 涉及时间时注意当前日期和时间

当前用户：重庆邮电大学学生
当前学期：{school_year} 学年{semester_label}

**关键节次时间参考（重邮作息）：**
- 第1-2节：08:00-09:40
- 第3-4节：10:05-11:40
- 第5-6节：14:00-15:35
- 第7-8节：16:00-17:35
- 第9-10节：19:00-20:35
- 第11-12节：20:50-22:30
"""

SYSTEM_PROMPT = _build_system_prompt()


def _build_text_to_sql_prompt(db=None) -> str:
    from datetime import date
    today = date.today()
    today_str = today.isoformat()
    term_start = date.fromisoformat(settings.term_start_date)
    current_week = (today - term_start).days // 7 + 1
    user_id = 1
    if db:
        try:
            from sqlalchemy import select
            from app.db.models import User
            result = db.execute(select(User).limit(1))
            user = result.scalar_one_or_none()
            if user:
                user_id = user.id
        except Exception:
            pass
    return f"""你是一个 SQL 查询专家。根据用户的问题，生成可以在 SQLite 数据库中执行的 SQL 查询语句。

## 数据库表结构：

### users 表（用户表）
- id: INTEGER (主键)
- student_id: VARCHAR
- created_at: DATETIME

### courses 表（课程表）
- id: INTEGER (主键)
- user_id: INTEGER (外键)
- name: VARCHAR (课程名称)
- teacher: VARCHAR (教师)
- location: VARCHAR (教室)
- day_of_week: INTEGER (周几，1=周一，7=周日)
- start_week: INTEGER (开始周)
- end_week: INTEGER (结束周)
- start_time: VARCHAR (开始时间，如 "08:30")
- end_time: VARCHAR (结束时间，如 "10:05")

### assignments 表（作业表）
- id: INTEGER (主键)
- user_id: INTEGER (外键)
- title: VARCHAR (作业标题)
- description: TEXT (作业描述)
- course_name: VARCHAR (课程名称)
- due_time: DATETIME (截止时间)
- is_completed: BOOLEAN (是否完成)
- created_at: DATETIME

### todos 表（待办表）
- id: INTEGER (主键)
- user_id: INTEGER (外键)
- title: VARCHAR (待办标题)
- description: TEXT (待办描述)
- due_time: DATETIME (截止时间)
- priority: VARCHAR (优先级：low/normal/high)
- is_completed: BOOLEAN (是否完成)
- created_at: DATETIME

## 重要规则：
1. **只允许 SELECT 查询**，禁止 INSERT/UPDATE/DELETE/DROP/CREATE
2. **只查询 user_id = {user_id} 的数据**（当前用户）
3. 查询课程时，需要确保当前周在 start_week 和 end_week 之间：current_week BETWEEN start_week AND end_week
4. 使用 LIMIT 限制返回行数，最多 20 行
5. 日期比较使用 date('now') 获取当前日期
6. 只输出 SQL 语句，不要包含其他解释性文字

## 关于周数计算：
- 学期开始日期：{settings.term_start_date}（这是第 1 周周一）
- 当前日期是 {today_str}
- 当前是第 {current_week} 周
- 查询课程时，需要添加条件：{current_week} BETWEEN start_week AND end_week

## 关于周几计算：
- SQLite 中 strftime('%w', date) 返回：0=周日，1=周一... 6=周六
- 我们的数据库中 day_of_week 是：1=周一，7=周日
- 转换公式：our_day_of_week = CASE WHEN strftime('%w', date) = '0' THEN 7 ELSE CAST(strftime('%w', date) AS INTEGER) END

## 示例：
用户问："今天有什么课？"
SQL: SELECT name, start_time, end_time, location FROM courses WHERE user_id = {user_id} AND day_of_week = CASE WHEN strftime('%w', date('now')) = '0' THEN 7 ELSE CAST(strftime('%w', date('now')) AS INTEGER) END AND {current_week} BETWEEN start_week AND end_week ORDER BY start_time

用户问："明天有什么课？"
SQL: SELECT name, start_time, end_time, location FROM courses WHERE user_id = {user_id} AND day_of_week = CASE WHEN strftime('%w', date('now', '+1 day')) = '0' THEN 7 ELSE CAST(strftime('%w', date('now', '+1 day')) AS INTEGER) END AND {current_week} BETWEEN start_week AND end_week ORDER BY start_time

用户问："有多少作业没完成？"
SQL: SELECT COUNT(*) FROM assignments WHERE user_id = {user_id} AND is_completed = 0
"""

TEXT_TO_SQL_PROMPT = _build_text_to_sql_prompt()


def _parse_dsml_tool_calls(content: str) -> List[Dict]:
    """
    解析 DeepSeek 返回的 DSML 格式工具调用
    示例：
    <tool_calls>
    <invoke name="get_day_courses">
    <parameter name="date" string="true">2026-05-21</parameter>
    </invoke>
    </tool_calls>
    """
    tool_calls = []

    # 提取 invoke 块
    invoke_pattern = r'<invoke name="([^"]+)">([\s\S]*?)</invoke>'
    invoke_matches = re.findall(invoke_pattern, content)

    for func_name, params_content in invoke_matches:
        # 提取参数
        param_pattern = r'<parameter name="([^"]+)"(?: [^>]+)?>([^<]*)</parameter>'
        param_matches = re.findall(param_pattern, params_content)

        func_args = {}
        for param_name, param_value in param_matches:
            func_args[param_name] = param_value

        tool_calls.append({
            "name": func_name,
            "arguments": func_args
        })

    return tool_calls


def _get_client(api_key: Optional[str] = None, base_url: Optional[str] = None) -> AsyncOpenAI:
    """创建 LLM API 客户端，优先使用传入参数，其次使用配置"""
    return AsyncOpenAI(
        api_key=api_key or settings.deepseek_api_key,
        base_url=base_url or DEEPSEEK_BASE_URL,
    )


async def _get_active_model(db: Optional[AsyncSession] = None) -> tuple:
    """
    获取当前激活的 AI 配置。
    如果数据库中有激活的 provider 则使用，否则回退到 settings 中的默认配置。
    返回 (api_key, base_url, model)
    """
    if db is not None:
        try:
            from sqlalchemy import select
            from app.db.models import AiProvider
            result = await db.execute(
                select(AiProvider).where(AiProvider.is_active == True).limit(1)
            )
            provider = result.scalar_one_or_none()
            if provider:
                return provider.api_key, provider.base_url, provider.model
        except Exception:
            pass
    return settings.deepseek_api_key, DEEPSEEK_BASE_URL, settings.deepseek_model


async def chat_completion(
    messages: List[Dict[str, str]],
    db: Optional[AsyncSession] = None,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    """调用 LLM 对话补全 API（无工具调用）"""
    api_key, base_url, model = await _get_active_model(db)
    if not api_key:
        return "API Key 未配置，请在设置中添加 AI 配置"

    full_messages = [{"role": "system", "content": system_prompt or SYSTEM_PROMPT}]
    full_messages.extend(messages)

    try:
        client = _get_client(api_key, base_url)
        response = await client.chat.completions.create(
            model=model,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        return content or "（AI 未返回内容）"
    except Exception as e:
        logger.error(f"LLM API 调用失败: {e}", exc_info=True)
        return f"AI 响应失败: {str(e)}"


async def chat_with_tools(
    messages: List[Dict[str, str]],
    db: AsyncSession,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    调用 LLM 对话补全 API（支持 Function Calling）

    流程：
    1. 获取当前激活的 AI 配置
    2. 如果提供了 history，注入到 system prompt 之后、本轮消息之前
    3. 发送用户消息 + 工具定义给 LLM
    4. 如果 LLM 决定调用工具，执行工具函数
    5. 将工具结果返回给 LLM，生成最终回复
    """
    api_key, base_url, model = await _get_active_model(db)
    if not api_key:
        return "API Key 未配置，请在设置中添加 AI 配置"

    full_messages = [{"role": "system", "content": system_prompt or SYSTEM_PROMPT}]
    if history:
        full_messages.extend(history)
    full_messages.extend(messages)

    try:
        client = _get_client(api_key, base_url)
        response = await client.chat.completions.create(
            model=model,
            messages=full_messages,
            tools=TOOLS,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        message = response.choices[0].message
        tool_calls_data = []

        # 检查是否是标准 OpenAI 工具调用格式
        if message.tool_calls:
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                tool_calls_data.append({
                    "id": tool_call.id,
                    "name": func_name,
                    "arguments": func_args,
                    "raw_arguments": tool_call.function.arguments
                })
        # 检查是否是 DSML 格式工具调用
        elif message.content and "<tool_calls>" in message.content:
            dsml_tool_calls = _parse_dsml_tool_calls(message.content)
            for i, tc in enumerate(dsml_tool_calls):
                tool_calls_data.append({
                    "id": f"dsml_call_{i}",
                    "name": tc["name"],
                    "arguments": tc["arguments"],
                    "raw_arguments": json.dumps(tc["arguments"])
                })

        # 如果没有工具调用，直接返回文本
        if not tool_calls_data:
            return message.content or "（AI 未返回内容）"

        # 处理工具调用
        for tc in tool_calls_data:
            func_name = tc["name"]
            func_args = tc["arguments"]

            logger.info(f"LLM 调用工具: {func_name}({func_args})")

            # 执行工具函数
            tool_result = await execute_tool(func_name, func_args, db)
            logger.info(f"工具结果: {tool_result[:100]}...")

            # 将工具调用和结果加入对话
            full_messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": func_name,
                            "arguments": tc["raw_arguments"],
                        },
                    }
                ],
            })
            full_messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": tool_result,
            })

        # 让 LLM 根据工具结果生成最终回复
        final_response = await client.chat.completions.create(
            model=model,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        final_content = final_response.choices[0].message.content or "（查询完成）"

        # 如果 LLM 最终回复仍包含 DSML 标签，剥离后返回自然语言部分
        if "<tool_calls>" in final_content:
            import re
            clean = re.sub(r'<tool_calls>[\s\S]*?</tool_calls>', '', final_content).strip()
            if clean:
                return clean
            return tool_result

        return final_content

    except Exception as e:
        logger.error(f"LLM 工具调用失败: {e}", exc_info=True)
        return f"查询失败: {str(e)}"


async def simple_chat(user_message: str) -> str:
    """简单对话 - 单轮对话"""
    return await chat_completion(
        messages=[{"role": "user", "content": user_message}],
    )


async def chat_or_reply(
    user_message: str,
    db: AsyncSession,
    session_id: Optional[str] = None,
) -> str:
    """
    智能对话：自动判断是否需要调用工具
    1. 先尝试关键词匹配预定义工具
    2. 匹配到工具 -> 直接执行（快、稳、省）
    3. 未匹配 -> 交由 LLM 判断（走 Function Calling 或聊天）

    如果提供了 session_id，自动注入最近 3 轮对话历史。
    """
    history = None
    if session_id:
        from app.llm.memory import memory
        history = memory.get_history(session_id)

    # 第一步：尝试关键词匹配
    matched_tool = _match_tool(user_message)

    if matched_tool:
        logger.info(f"关键词匹配到工具: {matched_tool}")

        if matched_tool == "plan_schedule":
            tool_result = await execute_tool("plan_schedule", {"request": user_message}, db)
        else:
            tool_result = await execute_tool(matched_tool, {}, db)

        # 记录记忆
        if session_id:
            from app.llm.memory import memory
            memory.add(session_id, user_message, str(tool_result))

        return str(tool_result)

    # 第二步：走 LLM 工具调用（Function Calling）
    reply = await chat_with_tools(
        messages=[{"role": "user", "content": user_message}],
        db=db,
        history=history,
    )

    # 兜底：如果回复中还包含未解析的 DSML 调用标签，手动解析执行
    if "<tool_calls>" in reply:
        import re
        clean_parts = re.split(r'<tool_calls>[\s\S]*?</tool_calls>', reply)
        clean_text = ''.join(clean_parts).strip()

        dsml_calls = _parse_dsml_tool_calls(reply)
        if dsml_calls:
            results = []
            for tc in dsml_calls:
                result = await execute_tool(tc["name"], tc["arguments"], db)
                results.append(str(result))
            tool_output = "\n\n".join(results)
            reply = f"{clean_text}\n\n{tool_output}" if clean_text else tool_output

    # 记录记忆
    if session_id:
        from app.llm.memory import memory
        memory.add(session_id, user_message, reply)

    return reply


async def check_api_key(db: Optional[AsyncSession] = None) -> bool:
    """检查 API Key 是否有效"""
    api_key, base_url, _ = await _get_active_model(db)
    if not api_key:
        return False
    try:
        client = _get_client(api_key, base_url)
        response = await client.models.list()
        return len(response.data) > 0
    except Exception:
        return False


async def get_db_schema(db: Optional[AsyncSession] = None) -> str:
    """获取数据库表结构（给 Text-to-SQL 使用）"""
    return _build_text_to_sql_prompt(db)
