"""
Text-to-SQL 工具模块

让 LLM 能够根据数据库 Schema 动态生成 SQL 查询，
实现灵活的数据库查询能力（Text-to-SQL）。

安全措施：
1. 只允许 SELECT 查询
2. 限制返回行数
3. 结果格式化
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

MAX_ROWS = 20

TABLES_TO_QUERY = [
    "courses",
    "assignments",
    "todos",
    "notifications",
]

ALLOWED_TABLES = set(TABLES_TO_QUERY)


def get_database_schema(db: AsyncSession) -> str:
    """
    获取数据库 Schema 描述，用于传给 LLM

    返回格式化的数据库结构说明，包括：
    - 表名和用途
    - 字段名、类型、可空性
    - 表之间的关系
    """
    from app.db.models import Base

    schema_parts = []

    for table_name, table in Base.metadata.tables.items():
        if table_name.startswith("sqlite_"):
            continue

        col_lines = []
        for col in table.columns:
            nullable = "NULL" if col.nullable else "NOT NULL"
            col_type = str(col.type)
            col_lines.append(f"    {col.name}: {col_type} ({nullable})")

        if col_lines:
            schema_parts.append(f"表名: {table_name}")
            schema_parts.append("字段:")
            schema_parts.append(", ".join(col_lines))

    if not schema_parts:
        schema_parts.append("（数据库为空）")

    return "\n".join(schema_parts)


def _sanitize_sql(sql: str) -> tuple[bool, str]:
    """
    检查并清理 SQL 语句

    返回: (is_safe, sanitized_sql)
    """
    sql_upper = sql.upper().strip()

    if not sql_upper.startswith("SELECT"):
        return False, "只允许 SELECT 查询"

    forbidden_keywords = [
        "INSERT", "UPDATE", "DELETE", "DROP", "CREATE",
        "ALTER", "TRUNCATE", "EXEC", "EXECUTE", "GRANT",
        "REVOKE", "UNION", "--", "/*", "*/"
    ]

    for keyword in forbidden_keywords:
        if keyword in sql_upper:
            match = re.search(rf'\b{keyword}\b', sql_upper)
            if match:
                return False, f"禁止使用关键字: {keyword}"

    return True, sql


async def execute_text_sql(
    db: AsyncSession,
    user_question: str,
) -> str:
    """
    根据用户问题执行 Text-to-SQL 查询

    流程：
    1. 获取数据库 Schema
    2. 构建提示让 LLM 生成 SQL
    3. 验证 SQL 安全性
    4. 执行查询并格式化结果
    """
    from openai import AsyncOpenAI
    from app.config import settings

    schema = get_database_schema(db)

    system_prompt = f"""你是一个 SQL 查询生成器。根据用户问题，从以下数据库 Schema 生成 SQL 查询。

数据库 Schema:
{schema}

重要规则：
1. 只生成 SELECT 查询，禁止 INSERT/UPDATE/DELETE
2. 使用 LIMIT 限制返回行数（最多 {MAX_ROWS} 行）
3. 表名和字段名使用实际名称，不要用别名
4. 如果涉及时间比较，使用 datetime('now') 或 datetime('localtime')
5. 只查询当前用户的数据（user_id = 1）

输出格式：只输出 SQL 语句，不要其他内容
"""

    try:
        client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
        )

        response = await client.chat.completions.create(
            model=settings.deepseek_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_question},
            ],
            temperature=0,
            max_tokens=500,
        )

        sql = response.choices[0].message.content.strip()

        sql_clean = sql.replace("```sql", "").replace("```", "").strip()

        is_safe, message = _sanitize_sql(sql_clean)
        if not is_safe:
            return f"⚠️ {message}"

        logger.info(f"📝 生成的 SQL: {sql_clean}")

        result = await db.execute(text(sql_clean))
        rows = result.fetchall()

        if not rows:
            return "📭 查询结果为空"

        columns = result.keys()
        rows_data = [dict(zip(columns, row)) for row in rows[:MAX_ROWS]]

        formatted = _format_results(rows_data, user_question)
        return formatted

    except Exception as e:
        logger.error(f"Text-to-SQL 执行失败: {e}", exc_info=True)
        return f"❌ 查询失败: {str(e)}"


def _format_results(rows: List[Dict[str, Any]], question: str) -> str:
    """格式化查询结果为自然语言"""
    if not rows:
        return "📭 没有找到相关数据"

    if len(rows) == 1:
        row = rows[0]
        parts = []
        for key, value in row.items():
            if value is not None:
                parts.append(f"{key}={value}")
        return "🔍 查询结果: " + ", ".join(parts)

    lines = [f"📊 查询结果（共 {len(rows)} 条）："]

    for i, row in enumerate(rows, 1):
        line_parts = []
        for key, value in row.items():
            if value is not None and key != "id":
                if isinstance(value, str) and len(value) > 50:
                    value = value[:50] + "..."
                line_parts.append(f"{key}: {value}")
        if line_parts:
            lines.append(f"{i}. " + ", ".join(line_parts))

    return "\n".join(lines)
