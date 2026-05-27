"""
LLM 工具函数定义

定义 AI 可以调用的工具（函数），用于查询课表、作业等实际数据
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.db.models import User
from app.services.course_service import CourseService
from app.services.assignment_service import AssignmentService
from app.services.todo_service import TodoService
from app.services.room_service import RoomService
from app.llm.text_to_sql import execute_text_sql

logger = logging.getLogger(__name__)

# ============================================================
# 工具 Schema（OpenAI / DeepSeek 兼容格式）
# ============================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_today_courses",
            "description": "获取今天的课程表，返回课程名称、时间、地点",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_day_courses",
            "description": "获取指定日期的课程表，返回课程名称、时间、地点",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "日期，格式为 YYYY-MM-DD（例如 2026-05-26）",
                    }
                },
                "required": ["date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tomorrow_courses",
            "description": "获取明天的课程表，返回课程名称、时间、地点",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_this_week_courses",
            "description": "获取本周全部课程表，按星期排列",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pending_assignments",
            "description": "获取未完成的作业列表，按截止时间排序",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "只查未来几天内的作业，不传则查所有未完成",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_overdue_assignments",
            "description": "获取已过期的未完成作业",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_week_number",
            "description": "获取当前是第几周",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_todos",
            "description": "获取待办事项列表，可筛选状态和优先级",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "筛选状态：pending（未完成）/ completed（已完成）/ all（全部），默认 pending",
                        "enum": ["pending", "completed", "all"],
                    },
                    "priority": {
                        "type": "string",
                        "description": "筛选优先级：low / normal / high",
                        "enum": ["low", "normal", "high"],
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_todo",
            "description": "创建一条新的待办事项",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "待办标题（必填）",
                    },
                    "description": {
                        "type": "string",
                        "description": "待办描述（可选）",
                    },
                    "due_time": {
                        "type": "string",
                        "description": "截止时间，格式如 2026-05-28 23:59（可选）",
                    },
                    "priority": {
                        "type": "string",
                        "description": "优先级：low / normal / high，默认 normal",
                        "enum": ["low", "normal", "high"],
                    },
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "flex_query",
            "description": "灵活的数据库查询工具，用于回答需要查询数据库的复杂问题，如统计、筛选特定条件的记录等",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "用户想要查询的问题，用自然语言描述",
                    },
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_empty_rooms",
            "description": "查询指定时间段哪些教室是空闲的，支持按教学楼、教室类型、最少座位数筛选",
            "parameters": {
                "type": "object",
                "properties": {
                    "day_of_week": {
                        "type": "integer",
                        "description": "星期几，1=周一，2=周二...7=周日，不传则查今天",
                    },
                    "start_slot": {
                        "type": "integer",
                        "description": "开始节次，如 1（1-2节）、3（3-4节）、5（5-6节）、7（7-8节）、9（9-10节）、11（11-12节），不传查全天",
                    },
                    "building": {
                        "type": "string",
                        "description": "教学楼名称筛选，如'3100'、'2100'，不传查全部",
                    },
                    "min_capacity": {
                        "type": "integer",
                        "description": "最少座位数，不传不限",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plan_schedule",
            "description": "智能行程规划助手。当用户说「想去自习」「安排行程」「帮我计划」「哪天有空」等模糊请求时调用此工具。它会解析时间、查询课表和空教室，并给出具体的行程建议，包括推荐的自习地点。",
            "parameters": {
                "type": "object",
                "properties": {
                    "request": {
                        "type": "string",
                        "description": "用户的原始请求，如「后天上午想去自习」「这周哪天上午有空」「帮我安排明天的学习计划」等",
                    },
                },
                "required": ["request"],
            },
        },
    },
]


weekday_names = {1: "周一", 2: "周二", 3: "周三", 4: "周四", 5: "周五", 6: "周六", 7: "周日"}


async def _get_user_id(db: AsyncSession) -> Optional[int]:
    """获取当前用户的 user_id"""
    from app.db.session import async_session
    result = await db.execute(
        select(User).where(User.student_id == settings.student_id).limit(1)
    )
    user = result.scalar_one_or_none()
    if not user:
        # 兜底：取第一个用户
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
    return user.id if user else None


# ============================================================
# 工具函数实现
# ============================================================

async def _format_course_list(courses: List[dict]) -> str:
    """将课程列表格式化为可读文本"""
    if not courses:
        return "暂无课程安排 🎉"

    lines = []
    for i, c in enumerate(courses, 1):
        name = c.get("name", "未知课程")
        time = f"{c.get('start_time', '')}-{c.get('end_time', '')}"
        loc = c.get("location", "")
        lines.append(f"{i}. {name}  {time}  📍{loc}")
    return "\n".join(lines)


async def handle_get_today_courses(db: AsyncSession) -> str:
    """工具：获取今日课程"""
    user_id = await _get_user_id(db)
    if not user_id:
        return "⚠️ 未找到用户信息"

    svc = CourseService(db)
    courses = await svc.get_today_courses(user_id)

    today = date.today()
    weekday = weekday_names.get(today.weekday() + 1, f"周{today.weekday() + 1}")

    course_text = await _format_course_list(courses)
    week = svc._calculate_week_number(today)

    return f"📅 今日（{weekday} 第{week}周）课程：\n{course_text}"


async def handle_get_day_courses(db: AsyncSession, date_str: str) -> str:
    """工具：获取指定日期课程"""
    user_id = await _get_user_id(db)
    if not user_id:
        return "⚠️ 未找到用户信息"

    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        return f"⚠️ 日期格式不正确：{date_str}，请使用 YYYY-MM-DD 格式"

    svc = CourseService(db)
    # 使用 get_day_courses 或类似方法查询指定日期的课程
    # 如果 service 没有这个方法，我们可以用 get_courses_by_week 来处理
    try:
        # 先尝试直接调用 get_day_courses
        courses = await svc.get_day_courses(user_id, target_date)
    except AttributeError:
        # 如果没有这个方法，我们可以自己实现简单版
        # 获取指定日期是周几，然后查找该周那天的课程
        week_number = svc._calculate_week_number(target_date)
        all_week_courses = await svc.get_courses_by_week(user_id, week_number)
        target_weekday = target_date.weekday() + 1  # 1-7
        courses = [c for c in all_week_courses if c.get("day_of_week") == target_weekday]

    weekday = weekday_names.get(target_date.weekday() + 1, f"周{target_date.weekday() + 1}")
    week = svc._calculate_week_number(target_date)

    course_text = await _format_course_list(courses)
    return f"📅 {target_date}（{weekday} 第{week}周）课程：\n{course_text}"


async def handle_get_tomorrow_courses(db: AsyncSession) -> str:
    """工具：获取明日课程"""
    user_id = await _get_user_id(db)
    if not user_id:
        return "⚠️ 未找到用户信息"

    svc = CourseService(db)
    courses = await svc.get_tomorrow_courses(user_id)

    tomorrow = date.today() + timedelta(days=1)
    weekday = weekday_names.get(tomorrow.weekday() + 1, f"周{tomorrow.weekday() + 1}")
    week = svc._calculate_week_number(tomorrow)

    course_text = await _format_course_list(courses)
    return f"📅 明日（{weekday} 第{week}周）课程：\n{course_text}"


async def handle_get_this_week_courses(db: AsyncSession) -> str:
    """工具：获取本周课程"""
    user_id = await _get_user_id(db)
    if not user_id:
        return "⚠️ 未找到用户信息"

    svc = CourseService(db)
    today = date.today()
    week = svc._calculate_week_number(today)
    courses = await svc.get_courses_by_week(user_id, week)

    if not courses:
        return f"📅 第{week}周没有课程安排 🎉"

    # 按星期分组
    by_day: Dict[str, list] = {}
    for c in courses:
        day = weekday_names.get(c["day_of_week"], f"周{c['day_of_week']}")
        if day not in by_day:
            by_day[day] = []
        by_day[day].append(c)

    parts = [f"📅 第{week}周课表"]
    for day in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]:
        if day in by_day:
            parts.append(f"\n【{day}】")
            for c in by_day[day]:
                parts.append(f"  {c['name']}  {c['start_time']}-{c['end_time']}  📍{c['location']}")

    return "\n".join(parts)


async def handle_get_pending_assignments(db: AsyncSession, days: Optional[int] = None) -> str:
    """工具：获取待完成作业"""
    user_id = await _get_user_id(db)
    if not user_id:
        return "⚠️ 未找到用户信息"

    svc = AssignmentService(db)
    if days:
        assignments = await svc.get_upcoming_assignments(user_id, days=days)
    else:
        assignments = await svc.get_assignments(user_id, status="pending")

    if not assignments:
        return "📝 暂时没有待完成的作业 🎉"

    lines = [f"📝 待完成作业（共 {len(assignments)} 个）："]
    for a in assignments:
        due = a.due_time.strftime("%m-%d %H:%M") if a.due_time else "无截止时间"
        status = "⏰" if a.due_time and a.due_time > datetime.now() else "🚨"
        lines.append(f"  {status} 【{a.course_name}】{a.title}（截止 {due}）")

    return "\n".join(lines)


async def handle_get_overdue_assignments(db: AsyncSession) -> str:
    """工具：获取过期未完成作业"""
    user_id = await _get_user_id(db)
    if not user_id:
        return "⚠️ 未找到用户信息"

    svc = AssignmentService(db)
    now = datetime.now()
    assignments = await svc.get_assignments(user_id, status="pending")

    overdue = [a for a in assignments if a.due_time and a.due_time < now]

    if not overdue:
        return "✅ 没有过期未完成的作业，继续保持！"

    lines = [f"🚨 过期作业（共 {len(overdue)} 个）："]
    for a in overdue:
        due = a.due_time.strftime("%m-%d %H:%M")
        lines.append(f"  【{a.course_name}】{a.title}（已过截止 {due}）")

    return "\n".join(lines)


async def handle_get_current_week(db: AsyncSession) -> str:
    """工具：获取当前周次"""
    today = date.today()
    term_start = date.fromisoformat(settings.term_start_date)
    week = (today - term_start).days // 7 + 1
    return f"📆 当前是第 {week} 周（{today}）"


async def handle_get_todos(db: AsyncSession,
                           status: Optional[str] = None,
                           priority: Optional[str] = None) -> str:
    """工具：获取待办事项"""
    user_id = await _get_user_id(db)
    if not user_id:
        return "⚠️ 未找到用户信息"

    svc = TodoService(db)
    todos = await svc.get_todos(user_id=user_id, status=status or "pending", priority=priority)

    if not todos:
        if status == "completed":
            return "✅ 没有已完成的待办事项"
        return "📋 暂时没有待办事项 🎉"

    status_label = {"pending": "未完成", "completed": "已完成", "all": "全部"}
    label = status_label.get(status or "pending", "待办")

    lines = [f"📋 {label}待办（共 {len(todos)} 项）："]
    for t in todos:
        prefix = "✅" if t.get("is_completed") else "📌"
        p_icon = {"high": "🔴", "normal": "🟡", "low": "🟢"}.get(t.get("priority", "normal"), "")
        due = f" 截止 {t.get('due_time')}" if t.get("due_time") else ""
        lines.append(f"  {prefix}{p_icon} {t['title']}{due}")

    return "\n".join(lines)


async def handle_create_todo(db: AsyncSession,
                              title: str,
                              description: Optional[str] = None,
                              due_time: Optional[str] = None,
                              priority: str = "normal") -> str:
    """工具：创建待办事项"""
    if not title or not title.strip():
        return "❌ 待办标题不能为空"

    user_id = await _get_user_id(db)
    if not user_id:
        return "⚠️ 未找到用户信息"

    due_dt = None
    if due_time:
        try:
            due_dt = datetime.fromisoformat(due_time)
        except ValueError:
            try:
                due_dt = datetime.strptime(due_time, "%Y-%m-%d %H:%M")
            except ValueError:
                try:
                    due_dt = datetime.strptime(due_time, "%Y-%m-%d")
                except ValueError:
                    pass

    svc = TodoService(db)
    todo = await svc.create_todo(
        title=title.strip(),
        user_id=user_id,
        description=description.strip() if description else None,
        due_time=due_dt,
        priority=priority,
        source="llm",
    )

    p_icon = {"high": "🔴", "normal": "🟡", "low": "🟢"}.get(priority, "")
    due_str = f"，截止 {due_time}" if due_time else ""
    return f"✅ 已创建待办：{p_icon} {title}{due_str}"


async def handle_flex_query(db: AsyncSession, question: str) -> str:
    """工具：灵活的数据库查询"""
    if not question or not question.strip():
        return "❌ 查询问题不能为空"

    logger.info(f"🔍 灵活查询: {question}")
    return await execute_text_sql(db, question)


async def handle_query_empty_rooms(db: AsyncSession,
                                   day_of_week: Optional[int] = None,
                                   start_slot: Optional[int] = None,
                                   building: Optional[str] = None,
                                   min_capacity: Optional[int] = None) -> str:
    """工具：查询空教室"""
    from datetime import date

    svc = RoomService(db)
    rooms = await svc.query_empty_rooms(
        day_of_week=day_of_week,
        start_slot=start_slot,
        end_slot=start_slot + 1 if start_slot else None,
        building=building,
        min_capacity=min_capacity,
    )

    if not rooms:
        return "🏫 该时间段没有空教室，试试调整查询条件"

    weekday_names = {1: "周一", 2: "周二", 3: "周三", 4: "周四", 5: "周五", 6: "周六", 7: "周日"}
    today = date.today()
    dow = day_of_week or today.weekday() + 1
    slot_str = f"第{start_slot}节" if start_slot else "全天"

    lines = [f"🏫 {weekday_names.get(dow, '')} {slot_str} 空教室（共 {len(rooms)} 间）："]
    current_building = None
    for r in rooms:
        bld = r.get("building") or ""
        if bld and bld != current_building:
            current_building = bld
            lines.append(f"\n📍 {bld}")
        cap = f"（{r.get('capacity', '-')}座）" if r.get("capacity") else ""
        lines.append(f"  {r['room_name']}  {r.get('room_type', '')}{cap}")

    return "\n".join(lines)


_slot_labels = {
    1: "1-2节（08:00-09:40）",
    3: "3-4节（10:05-11:40）",
    5: "5-6节（14:00-15:35）",
    7: "7-8节（16:00-17:35）",
    9: "9-10节（19:00-20:35）",
    11: "11-12节（21:00-22:00）",
}

_slot_to_time = {
    1: ("08:00", "09:40"),
    3: ("10:05", "11:40"),
    5: ("14:00", "15:35"),
    7: ("16:00", "17:35"),
    9: ("19:00", "20:35"),
    11: ("21:00", "22:00"),
}


async def handle_plan_schedule(db: AsyncSession, request: str) -> str:
    """工具：智能行程规划"""
    import re
    from datetime import date, timedelta

    today = date.today()
    weekday_names_str = {1: "周一", 2: "周二", 3: "周三", 4: "周四", 5: "周五", 6: "周六", 7: "周日"}

    day_of_week = None
    date_label = None
    target_date = None

    if "今天" in request or "今日" in request:
        target_date = today
        day_of_week = today.weekday() + 1
        date_label = f"今天（{weekday_names_str.get(day_of_week)}）"
    elif "明天" in request or "明日" in request:
        target_date = today + timedelta(days=1)
        day_of_week = target_date.weekday() + 1
        date_label = f"明天（{weekday_names_str.get(day_of_week)}）"
    elif "后天" in request:
        target_date = today + timedelta(days=2)
        day_of_week = target_date.weekday() + 1
        date_label = f"后天（{weekday_names_str.get(day_of_week)}）"
    elif "大后天" in request:
        target_date = today + timedelta(days=3)
        day_of_week = target_date.weekday() + 1
        date_label = f"大后天（{weekday_names_str.get(day_of_week)}）"

    slot = None
    if "上午" in request or "早上" in request:
        slot = 1
    elif "中午" in request or "午休" in request:
        slot = 5
    elif "下午" in request:
        slot = 7
    elif "晚上" in request or "夜间" in request:
        slot = 9

    if day_of_week and day_of_week > 7:
        day_of_week = day_of_week % 7 or 7

    course_svc = CourseService(db)
    room_svc = RoomService(db)
    user_id = await _get_user_id(db)

    week_num = course_svc._calculate_week_number(target_date) if target_date else course_svc._calculate_week_number(today)

    all_rooms = await room_svc.get_buildings()
    if not all_rooms:
        return "⚠️ 空教室数据尚未同步，请联系管理员先执行教室数据刷新"

    if target_date:
        courses = []
        if user_id:
            week_courses = await course_svc.get_courses_by_week(user_id, week_num)
            courses = [c for c in week_courses if c.get("day_of_week") == day_of_week]

        morning_rooms = await room_svc.query_empty_rooms(day_of_week=day_of_week, start_slot=1, end_slot=4, min_capacity=30)
        afternoon_rooms = await room_svc.query_empty_rooms(day_of_week=day_of_week, start_slot=5, end_slot=8, min_capacity=30)
        evening_rooms = await room_svc.query_empty_rooms(day_of_week=day_of_week, start_slot=9, end_slot=12, min_capacity=30)

        result_lines = [f"📅 {date_label}（第{week_num}周）行程建议："]

        if courses:
            # 如果指定了时段（上午/下午/晚上），只显示该时段的课程
            if slot:
                if slot == 1:
                    slot_start, slot_end = 1, 4
                elif slot == 5 or slot == 7:
                    slot_start, slot_end = 5, 8
                elif slot == 9:
                    slot_start, slot_end = 9, 12
                else:
                    slot_start, slot_end = slot, slot + 1
                slot_courses = [c for c in courses if c.get("start_slot", 0) <= slot_end and c.get("end_slot", 99) >= slot_start]
            else:
                slot_courses = courses

            if slot_courses:
                result_lines.append(f"\n📚 该时段有 {len(slot_courses)} 节课：")
                for c in slot_courses:
                    loc = c.get("location", "未知地点")
                    time_range = f"{c.get('start_time', '')}-{c.get('end_time', '')}"
                    result_lines.append(f"  • {c['name']} {time_range} 📍{loc}")
            else:
                result_lines.append(f"\n✅ 该时段没有课，可以放心去自习！")

        has_study = "自习" in request or "学习" in request or "复习" in request or "图书馆" in request

        if has_study and slot:
            if slot == 1:
                empty = morning_rooms
                slot_label = "上午（1-4节 08:00-11:40）"
            elif slot == 5:
                empty = afternoon_rooms
                slot_label = "中午/下午（5-8节 14:00-17:35）"
            elif slot == 7:
                empty = afternoon_rooms
                slot_label = "下午（7-8节 16:00-17:35）"
            elif slot == 9:
                empty = evening_rooms
                slot_label = "晚上（9-12节 19:00-22:00）"
            else:
                empty = morning_rooms if slot <= 4 else (afternoon_rooms if slot <= 8 else evening_rooms)
                slot_label = f"第{slot}节"

            if empty:
                top3 = empty[:3]
                result_lines.append(f"\n🏫 该时段空教室 Top{len(top3)}：")
                for r in top3:
                    cap = f"{r.get('capacity', '-')}座" if r.get("capacity") else ""
                    bld = r.get("building", "")
                    result_lines.append(f"  • {r['room_name']} 📍{bld} {r.get('room_type', '')} {cap}")
                if len(empty) > 3:
                    result_lines.append(f"  ...还有 {len(empty) - 3} 间可用")
            else:
                result_lines.append(f"\n😅 {slot_label}暂时没有可用空教室")
            result_lines.append(f"\n💡 提示：数据来源于教务系统教室课表，建议去之前确认一下～")
        elif has_study:
            if morning_rooms:
                result_lines.append(f"\n🏫 上午推荐自习：{morning_rooms[0]['room_name']} 📍{morning_rooms[0].get('building', '')}")
            if afternoon_rooms:
                result_lines.append(f"🏫 下午推荐自习：{afternoon_rooms[0]['room_name']} 📍{afternoon_rooms[0].get('building', '')}")
            result_lines.append(f"\n💡 提示：数据来源于教务系统教室课表，建议去之前确认一下～")

        return "\n".join(result_lines)

    # 无具体日期 → 未来7天概览（优化：标注空闲时段和推荐教室）
    week_plan = []
    for i in range(7):
        check_date = today + timedelta(days=i)
        check_dow = check_date.weekday() + 1
        check_week = course_svc._calculate_week_number(check_date)
        day_courses = []
        if user_id:
            week_courses = await course_svc.get_courses_by_week(user_id, check_week)
            day_courses = [c for c in week_courses if c.get("day_of_week") == check_dow]
        has_class = bool(day_courses)
        day_label = "今天" if i == 0 else ("明天" if i == 1 else weekday_names_str.get(check_dow, ""))
        morning_empty = await room_svc.query_empty_rooms(day_of_week=check_dow, start_slot=1, end_slot=4, min_capacity=30) if not has_class else []
        free_msg = f"（推荐自习{morning_empty[0]['room_name'] if morning_empty else ''}）" if morning_empty else ""
        week_plan.append(f"{day_label}（{weekday_names_str.get(check_dow)}）{'📚 有课' if has_class else '🆓 无课' + free_msg}")

    result_lines = ["📅 本周课程安排概览："]
    result_lines.extend(week_plan)
    result_lines.append("\n💡 发送格式如「今天上午想去自习」可获取具体自习地点推荐！")
    return "\n".join(result_lines)


# ============================================================
# 工具调度器
# ============================================================

TOOL_HANDLERS = {
    "get_today_courses": handle_get_today_courses,
    "get_tomorrow_courses": handle_get_tomorrow_courses,
    "get_day_courses": handle_get_day_courses,
    "get_this_week_courses": handle_get_this_week_courses,
    "get_pending_assignments": handle_get_pending_assignments,
    "get_overdue_assignments": handle_get_overdue_assignments,
    "get_current_week_number": handle_get_current_week,
    "get_todos": handle_get_todos,
    "create_todo": handle_create_todo,
    "flex_query": handle_flex_query,
    "query_empty_rooms": handle_query_empty_rooms,
    "plan_schedule": handle_plan_schedule,
}


async def execute_tool(name: str, arguments: dict, db: AsyncSession) -> str:
    """执行工具函数"""
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        logger.warning(f"未知工具: {name}")
        return f"未知工具: {name}"

    logger.info(f"🔧 执行工具: {name}({arguments})")

    try:
        if name == "get_pending_assignments":
            days = arguments.get("days")
            return await handler(db, days=days)
        elif name == "get_todos":
            return await handler(db,
                                 status=arguments.get("status"),
                                 priority=arguments.get("priority"))
        elif name == "create_todo":
            return await handler(db,
                                 title=arguments.get("title", ""),
                                 description=arguments.get("description"),
                                 due_time=arguments.get("due_time"),
                                 priority=arguments.get("priority", "normal"))
        elif name == "get_day_courses":
            return await handler(db, date_str=arguments.get("date", ""))
        elif name == "flex_query":
            return await handler(db, question=arguments.get("question", ""))
        elif name == "query_empty_rooms":
            return await handler(db,
                                 day_of_week=arguments.get("day_of_week"),
                                 start_slot=arguments.get("start_slot"),
                                 building=arguments.get("building"),
                                 min_capacity=arguments.get("min_capacity"))
        elif name == "plan_schedule":
            return await handler(db, request=arguments.get("request", ""))
        return await handler(db)
    except Exception as e:
        logger.error(f"工具执行失败 {name}: {e}", exc_info=True)
        return f"查询失败: {str(e)}"
