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

def _is_data_query(question: str) -> str:
    """
    判断用户消息类型：
    - "query" → 需要查询数据库
    - "create_todo" → 需要创建待办
    - "chat" → 普通聊天
    """
    q = question.lower().strip()
    
    # 创建待办
    create_keywords = ["添加待办", "创建待办", "新增待办", "添加代办", "创建代办",
                       "帮我记", "提醒我", "别忘了"]
    if any(kw in q for kw in create_keywords):
        return "create_todo"
    
    # 数据查询
    query_keywords = [
        "课表", "课程", "上课", "几点", "教室",
        "作业", "截止", "提交",
        "待办", "todo", "任务", "事项",
        "统计", "多少", "有几个", "有哪些", "查询", "看看", "查看",
        "星期", "周几", "哪天",
    ]
    if any(kw in q for kw in query_keywords):
        return "query"
    
    return "chat"

DEEPSEEK_BASE_URL = "https://api.deepseek.com"

SYSTEM_PROMPT = """你是 CampusPilot 校园助手，运行在重庆邮电大学学生的个人学业管理系统中。

你可以帮助用户管理以下内容：
1. **课表查询** - 今日课表、本周课表等
2. **作业管理** - 待完成作业、即将截止的作业
3. **待办管理** - 查看待办、创建新的待办事项

**回答规则：**
- 对于简单的问候、闲聊，直接用自然语言回复即可
- 对于需要查询数据的问题（课表、作业、待办等），你会收到系统执行 SQL 后的结果，用友好的方式总结给用户

你的回答风格：
- 简洁清晰，直接给出有用信息
- 使用合适的 emoji 让消息更友好
- 如果用户问的问题超出能力范围，诚实告知
- 涉及时间时注意当前日期和时间

当前用户：重庆邮电大学学生
当前学期：2025-2026 学年第二学期
"""


TEXT_TO_SQL_PROMPT = """你是一个 SQL 查询专家。根据用户的问题，生成可以在 SQLite 数据库中执行的 SQL 查询语句。

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
2. **只查询 user_id = 2 的数据**（当前用户）
3. 查询课程时，需要确保当前周在 start_week 和 end_week 之间：current_week BETWEEN start_week AND end_week
4. 使用 LIMIT 限制返回行数，最多 20 行
5. 日期比较使用 date('now') 获取当前日期
6. 只输出 SQL 语句，不要包含其他解释性文字

## 关于周数计算：
- 学期开始日期：2026-03-02（这是第 1 周周一）
- 当前日期是 2026-05-26
- 当前是第 13 周
- 查询课程时，需要添加条件：13 BETWEEN start_week AND end_week

## 关于周几计算：
- SQLite 中 strftime('%w', date) 返回：0=周日，1=周一... 6=周六
- 我们的数据库中 day_of_week 是：1=周一，7=周日
- 转换公式：our_day_of_week = CASE WHEN strftime('%w', date) = '0' THEN 7 ELSE CAST(strftime('%w', date) AS INTEGER) END

## 示例：
用户问："今天有什么课？"
SQL: SELECT name, start_time, end_time, location FROM courses WHERE user_id = 2 AND day_of_week = CASE WHEN strftime('%w', date('now')) = '0' THEN 7 ELSE CAST(strftime('%w', date('now')) AS INTEGER) END AND 13 BETWEEN start_week AND end_week ORDER BY start_time

用户问："明天有什么课？"
SQL: SELECT name, start_time, end_time, location FROM courses WHERE user_id = 2 AND day_of_week = CASE WHEN strftime('%w', date('now', '+1 day')) = '0' THEN 7 ELSE CAST(strftime('%w', date('now', '+1 day')) AS INTEGER) END AND 13 BETWEEN start_week AND end_week ORDER BY start_time

用户问："有多少作业没完成？"
SQL: SELECT COUNT(*) FROM assignments WHERE user_id = 2 AND is_completed = 0
"""


def _parse_dsml_tool_calls(content: str) -> List[Dict]:
    """
    解析 DeepSeek 返回的 DSML 格式工具调用
    示例：
    <｜｜DSML｜｜tool_calls>
    <｜｜DSML｜｜invoke name="get_day_courses">
    <｜｜DSML｜｜parameter name="date" string="true">2026-05-21</｜｜DSML｜｜parameter>
    </｜｜DSML｜｜invoke>
    </｜｜DSML｜｜tool_calls>
    """
    tool_calls = []
    
    # 提取 invoke 块
    invoke_pattern = r'<｜｜DSML｜｜invoke name="([^"]+)">([\s\S]*?)</｜｜DSML｜｜invoke>'
    invoke_matches = re.findall(invoke_pattern, content)
    
    for func_name, params_content in invoke_matches:
        # 提取参数
        param_pattern = r'<｜｜DSML｜｜parameter name="([^"]+)"(?: [^>]+)?>([^<]*)</｜｜DSML｜｜parameter>'
        param_matches = re.findall(param_pattern, params_content)
        
        func_args = {}
        for param_name, param_value in param_matches:
            # 尝试解析参数值（处理 string="true" 等属性）
            func_args[param_name] = param_value
        
        tool_calls.append({
            "name": func_name,
            "arguments": func_args
        })
    
    return tool_calls


def _get_client() -> AsyncOpenAI:
    """创建 DeepSeek API 客户端"""
    return AsyncOpenAI(
        api_key=settings.deepseek_api_key,
        base_url=DEEPSEEK_BASE_URL,
    )


async def chat_completion(
    messages: List[Dict[str, str]],
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    """调用 DeepSeek 对话补全 API（无工具调用）"""
    if not settings.deepseek_api_key:
        logger.warning("DeepSeek API Key 未配置")
        return "⚠️ DeepSeek API Key 未配置，请在 .env 中设置 DEEPSEEK_API_KEY"

    full_messages = [{"role": "system", "content": system_prompt or SYSTEM_PROMPT}]
    full_messages.extend(messages)

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=settings.deepseek_model,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        return content or "（AI 未返回内容）"
    except Exception as e:
        logger.error(f"DeepSeek API 调用失败: {e}", exc_info=True)
        return f"❌ AI 响应失败: {str(e)}"


async def chat_with_tools(
    messages: List[Dict[str, str]],
    db: AsyncSession,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """
    调用 DeepSeek 对话补全 API（支持 Function Calling）

    流程：
    1. 发送用户消息 + 工具定义给 DeepSeek
    2. 如果 DeepSeek 决定调用工具，执行工具函数
    3. 将工具结果返回给 DeepSeek，生成最终回复
    """
    if not settings.deepseek_api_key:
        logger.warning("DeepSeek API Key 未配置")
        return "⚠️ DeepSeek API Key 未配置"

    full_messages = [{"role": "system", "content": system_prompt or SYSTEM_PROMPT}]
    full_messages.extend(messages)

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=settings.deepseek_model,
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
        elif message.content and "<｜｜DSML｜｜tool_calls>" in message.content:
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

            logger.info(f"🔧 LLM 调用工具: {func_name}({func_args})")

            # 执行工具函数
            tool_result = await execute_tool(func_name, func_args, db)
            logger.info(f"✅ 工具结果: {tool_result[:100]}...")

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

        # 让 DeepSeek 根据工具结果生成最终回复
        final_response = await client.chat.completions.create(
            model=settings.deepseek_model,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return final_response.choices[0].message.content or "（查询完成）"

    except Exception as e:
        logger.error(f"DeepSeek 工具调用失败: {e}", exc_info=True)
        return f"❌ 查询失败: {str(e)}"


async def simple_chat(user_message: str) -> str:
    """简单对话 - 单轮对话"""
    return await chat_completion(
        messages=[{"role": "user", "content": user_message}],
    )


async def chat_or_reply(
    user_message: str,
    db: AsyncSession,
) -> str:
    """
    智能判断：如果是查询就走 Text-to-SQL，否则正常聊天

    同时支持创建待办（使用 execute_tool）
    """
    msg_type = _is_data_query(user_message)

    if msg_type == "create_todo":
        from app.llm.tools import execute_tool
        result = await execute_tool("create_todo", {"title": user_message}, db)
        return result

    if msg_type == "query":
        return await chat_text_to_sql(user_message, db)

    return await chat_completion(
        messages=[{"role": "user", "content": user_message}],
    )


def _sanitize_sql(sql_text: str) -> str:
    """清理并提取 SQL 语句"""
    original = sql_text
    
    # 移除 markdown 代码块标记
    sql_text = sql_text.replace("```sql", "").replace("```", "").replace("`", "").strip()
    
    # 如果整段话以 SELECT 开头，直接使用
    if sql_text.upper().startswith("SELECT"):
        return sql_text
    
    # 尝试在文本中查找 SELECT 语句
    idx = sql_text.upper().find("SELECT")
    if idx >= 0:
        sql_text = sql_text[idx:].strip()
        # 移除末尾的句号或多余内容
        for end_marker in ["\n\n", ";--", "；"]:
            if end_marker in sql_text:
                sql_text = sql_text[:sql_text.index(end_marker)].strip()
        return sql_text
    
    return original


async def chat_text_to_sql(
    user_message: str,
    db: AsyncSession,
) -> str:
    """
    直接使用 Text-to-SQL 查询数据库（跳过工具调用）
    
    流程：
    1. 根据用户问题生成 SQL 查询
    2. 验证 SQL 安全性
    3. 执行 SQL
    4. 将结果用自然语言总结给用户
    """
    if not settings.deepseek_api_key:
        return "⚠️ DeepSeek API Key 未配置"

    try:
        client = _get_client()

        # 第一步：生成 SQL
        sql_response = await client.chat.completions.create(
            model=settings.deepseek_model,
            messages=[
                {"role": "system", "content": TEXT_TO_SQL_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0,
            max_tokens=500,
        )

        sql_text = sql_response.choices[0].message.content.strip()
        logger.info(f"📝 DeepSeek 原始返回: {sql_text[:200]}")

        # 清理 SQL
        sql_text = _sanitize_sql(sql_text)
        logger.info(f"📝 清理后 SQL: {sql_text}")

        # 安全检查
        if not sql_text.upper().startswith("SELECT"):
            logger.warning(f"❌ 仍然是无效 SQL: {sql_text}")
            return await chat_completion(
                messages=[{"role": "user", "content": user_message}],
            )

        # 执行 SQL
        result = await db.execute(text(sql_text))
        rows = result.fetchall()

        if not rows:
            return "📭 查询结果为空"

        columns = result.keys()
        rows_data = [dict(zip(columns, row)) for row in rows[:20]]

        # 格式化结果为自然语言
        result_text = _format_sql_results(rows_data, user_message)

        # 第二步：让 AI 总结结果
        summary_response = await client.chat.completions.create(
            model=settings.deepseek_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": f"查询结果：\n{result_text}"},
            ],
            temperature=0.7,
            max_tokens=1024,
        )

        return summary_response.choices[0].message.content or result_text

    except Exception as e:
        logger.error(f"Text-to-SQL 执行失败: {e}", exc_info=True)
        return f"❌ 查询失败: {str(e)}"


def _format_sql_results(rows: list, question: str) -> str:
    """格式化 SQL 查询结果"""
    if not rows:
        return "没有找到数据"

    lines = [f"查询结果（共 {len(rows)} 条）："]
    for i, row in enumerate(rows, 1):
        parts = []
        for key, value in row.items():
            if value is not None:
                if isinstance(value, str) and len(value) > 30:
                    value = value[:30] + "..."
                parts.append(f"{key}={value}")
        if parts:
            lines.append(f"{i}. " + ", ".join(parts))

    return "\n".join(lines)


async def check_api_key() -> bool:
    """检查 DeepSeek API Key 是否有效"""
    if not settings.deepseek_api_key:
        return False
    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=settings.deepseek_model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        return bool(response.choices)
    except Exception as e:
        logger.warning(f"DeepSeek API Key 验证失败: {e}")
        return False
