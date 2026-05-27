"""
定时任务定义
"""

import asyncio
import logging
from datetime import datetime

from app.config import settings
from app.db.session import async_session
from app.db.models import Todo, CustomReminder, User, RoomSchedule
from app.services.course_service import CourseService
from app.services.assignment_service import AssignmentService
from app.notifications.bark_notifier import BarkNotifier
from app.notifications.feishu_notifier import FeishuNotifier

logger = logging.getLogger(__name__)


async def _get_feishu_notifier(db) -> FeishuNotifier:
    """从数据库加载飞书 Webhook URL 创建通知器"""
    from app.services.config_store import ConfigStoreService
    store = ConfigStoreService(db, settings.fernet_key)
    url = await store.get("feishu_webhook_url", "")
    return FeishuNotifier(webhook_url=url or settings.feishu_webhook_url)


async def notify_all(title: str, message: str, assignment_data: dict = None):
    """同时推送到 Bark 和飞书"""
    # Bark 推送
    bark = BarkNotifier()
    await bark.send(message=message, title=title)

    # 飞书推送（从 settings 获取 URL）
    feishu = FeishuNotifier()
    await feishu.send_text(f"{title}\n{message}")


async def send_daily_schedule():
    """
    每日课表推送任务
    每天早上 7:50 发送今日课表到 Bark 和飞书
    """
    logger.info("📅 开始执行每日课表推送任务")

    try:
        async with async_session() as db:
            course_service = CourseService(db)
            bark_notifier = BarkNotifier()
            feishu_notifier = await _get_feishu_notifier(db)

            # 获取用户
            from app.db.models import User
            from sqlalchemy import select
            result = await db.execute(select(User).where(User.student_id == settings.student_id).limit(1))
            user = result.scalar_one_or_none()

            if not user:
                logger.warning("⚠️ 没有找到用户，跳过推送")
                return

            # 获取今日课程
            today_courses = await course_service.get_today_courses(user.id)

            if not today_courses:
                logger.info("📭 今日无课，跳过推送")
                return

            # 推送课表到 Bark
            bark_success = await bark_notifier.send_schedule_reminder(today_courses)

            # 推送课表到飞书（富文本格式）
            feishu_success = await feishu_notifier.send_schedule_reminder(today_courses)

            if bark_success or feishu_success:
                logger.info(f"✅ 每日课表推送成功 (Bark: {bark_success}, 飞书: {feishu_success})")
            else:
                logger.error("❌ 每日课表推送失败")

    except Exception as e:
        logger.error(f"❌ 每日课表推送任务异常: {e}", exc_info=True)


async def check_assignment_deadlines():
    """
    作业截止检查任务
    每小时检查一次即将截止的作业，同时推送到 Bark 和飞书
    """
    logger.info("⏰ 开始执行作业截止检查任务")

    try:
        async with async_session() as db:
            assignment_service = AssignmentService(db)
            bark_notifier = BarkNotifier()
            feishu_notifier = await _get_feishu_notifier(db)

            # 获取用户
            from app.db.models import User
            from sqlalchemy import select
            result = await db.execute(select(User).where(User.student_id == settings.student_id).limit(1))
            user = result.scalar_one_or_none()

            if not user:
                logger.warning("⚠️ 没有找到用户，跳过检查")
                return

            # 获取即将截止的作业（1天内）
            upcoming_assignments = await assignment_service.get_upcoming_assignments(
                user.id, days=1
            )

            if not upcoming_assignments:
                logger.info("📭 没有即将截止的作业")
                return

            # 推送提醒
            for assignment in upcoming_assignments:
                # 计算剩余时间
                due_time = assignment.due_time
                if due_time:
                    now = datetime.now()
                    hours_left = (due_time - now).total_seconds() / 3600

                    # 只在关键时间点推送
                    if hours_left <= 1 or (12 <= hours_left <= 13) or (23 <= hours_left <= 25):
                        # Bark 推送
                        bark_success = await bark_notifier.send_assignment_reminder(
                            course_name=assignment.course_name or "未知课程",
                            title=assignment.title,
                            due_time=due_time.isoformat(),
                            hours_left=int(hours_left)
                        )

                        # 飞书推送
                        feishu_success = await feishu_notifier.send_assignment_reminder(
                            course_name=assignment.course_name or "未知课程",
                            title=assignment.title,
                            due_time=due_time.isoformat(),
                            hours_left=int(hours_left)
                        )

                        if bark_success or feishu_success:
                            logger.info(f"✅ 作业提醒推送成功: {assignment.title} (Bark: {bark_success}, 飞书: {feishu_success})")
                        else:
                            logger.error(f"❌ 作业提醒推送失败: {assignment.title}")

    except Exception as e:
        logger.error(f"❌ 作业截止检查任务异常: {e}", exc_info=True)


async def sync_courses_daily():
    """
    每日课程同步任务
    每天早上 6:00 同步课表
    """
    logger.info("📚 开始执行每日课程同步任务")

    try:
        async with async_session() as db:
            course_service = CourseService(db)

            # 获取用户
            from app.db.models import User
            from sqlalchemy import select
            result = await db.execute(select(User).where(User.student_id == settings.student_id).limit(1))
            user = result.scalar_one_or_none()

            if not user:
                logger.warning("⚠️ 没有找到用户，跳过同步")
                return

            # 同步课表
            result = await course_service.sync_courses_from_jwxt(user.student_id)

            if result.get("success"):
                logger.info(f"✅ 课程同步成功，共 {result.get('courses_count')} 门课程")
            else:
                logger.error(f"❌ 课程同步失败: {result.get('message')}")

    except Exception as e:
        logger.error(f"❌ 每日课程同步任务异常: {e}", exc_info=True)


async def sync_assignments_periodically():
    """
    定期作业同步任务
    每 30 分钟同步一次作业（数你最灵 + 学习通）
    """
    logger.info("📝 开始执行定期作业同步任务")

    try:
        async with async_session() as db:
            assignment_service = AssignmentService(db)

            # 获取用户
            from app.db.models import User
            from sqlalchemy import select
            result = await db.execute(select(User).where(User.student_id == settings.student_id).limit(1))
            user = result.scalar_one_or_none()

            if not user:
                logger.warning("⚠️ 没有找到用户，跳过同步")
                return

            # 同步学习通作业
            from app.crawlers.chaoxing_crawler import ChaoxingCrawler
            crawler = ChaoxingCrawler()
            assignments = await crawler.crawl_and_parse()
            
            if assignments:
                new_count = await assignment_service.save_assignments(user.id, assignments)
                logger.info(f"✅ 学习通作业同步完成，新增 {new_count} 条")
            else:
                logger.info("⏳ 学习通未抓取到新作业")

            # 同步数你最灵作业
            from app.crawlers.smartestu_crawler import SmartestuCrawler
            from app.services.config_store import ConfigStoreService
            store = ConfigStoreService(db, settings.fernet_key)
            sm_config = await store.get_data_source(user.id, "smartestu")
            sm_student_id = (sm_config or {}).get("student_id", "") or settings.smartestu_student_id
            sm_password = (sm_config or {}).get("password", "") or settings.smartestu_password

            if sm_student_id and sm_password:
                smartestu = SmartestuCrawler(student_id=sm_student_id, password=sm_password)
                sm_assignments = await smartestu.crawl_and_parse()
                if sm_assignments:
                    sm_new = await assignment_service.save_assignments(user.id, sm_assignments)
                    logger.info(f"✅ 数你最灵作业同步完成，新增 {sm_new} 条")

    except Exception as e:
        logger.error(f"❌ 定期作业同步任务异常: {e}", exc_info=True)


async def send_test_notification():
    """
    测试通知任务（仅用于调试）
    同时推送到 Bark 和飞书
    """
    logger.info("🔔 发送测试通知")

    bark_notifier = BarkNotifier()
    feishu_notifier = FeishuNotifier()

    # Bark 推送
    await bark_notifier.send_custom(
        message="定时任务测试成功！",
        title="🔔 测试通知"
    )

    # 飞书推送
    await feishu_notifier.send_text("🔔 测试通知\n定时任务测试成功！")

    logger.info("✅ 测试通知发送成功（Bark + 飞书）")


async def cleanup_old_assignments_periodically():
    """
    定期清理过时作业任务
    每天凌晨 3:00 检查配置并清理
    """
    logger.info("🧹 开始执行定期作业清理任务")

    try:
        async with async_session() as db:
            from app.services.config_store import ConfigStoreService
            from app.config import settings
            store = ConfigStoreService(db, settings.fernet_key)

            enabled = await store.get("auto_cleanup_enabled", "false")
            if enabled != "true":
                logger.info("  ⏭️ 自动清理未开启，跳过")
                return

            days = int(await store.get("auto_cleanup_days", "30"))
            assignment_service = AssignmentService(db)

            from app.db.models import User
            from sqlalchemy import select
            result = await db.execute(select(User).where(User.student_id == settings.student_id).limit(1))
            user = result.scalar_one_or_none()
            if not user:
                logger.warning("⚠️ 没有找到用户，跳过清理")
                return

            deleted = await assignment_service.delete_old_completed_assignments(user.id, days)
            logger.info(f"✅ 定期清理完成，删除 {deleted} 条过时作业")

    except Exception as e:
        logger.error(f"❌ 定期清理任务异常: {e}", exc_info=True)


async def check_custom_reminders():
    """
    检查自定义定时提醒
    每分钟检查一次，发送到期的提醒到 Bark 和飞书
    """
    logger.debug("⏰ 开始检查自定义定时提醒")

    try:
        from datetime import datetime, date
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        today_weekday = now.weekday()  # 0=周一
        today_day = now.day

        async with async_session() as db:
            from sqlalchemy import select
            result = await db.execute(
                select(CustomReminder).where(
                    CustomReminder.enabled == True,
                    CustomReminder.reminder_time == current_time,
                )
            )
            reminders = result.scalars().all()

            if not reminders:
                return

            bark = BarkNotifier()
            feishu = FeishuNotifier()

            for r in reminders:
                # 检查是否匹配重复规则
                if r.repeat_type == "weekly" and r.repeat_day is not None and r.repeat_day != today_weekday:
                    continue
                if r.repeat_type == "monthly" and r.repeat_day is not None and r.repeat_day != today_day:
                    continue

                title = r.title or r.name
                message = r.content or r.name

                bark_success = await bark.send_custom(message=message, title=title)
                feishu_success = await feishu.send_text(f"{title}\n{message}")

                if bark_success or feishu_success:
                    logger.info(f"✅ 自定义提醒推送成功: {r.name}")
                else:
                    logger.warning(f"⚠️ 自定义提醒推送未送达（未配置推送渠道）: {r.name}")

    except Exception as e:
        logger.error(f"❌ 自定义提醒检查异常: {e}", exc_info=True)


async def check_todo_reminders():
    """
    检查待办事项提醒
    每 5 分钟检查一次，发送启用了提醒的即将到期待办到 Bark 和飞书
    """
    logger.debug("⏰ 开始检查待办事项提醒")

    try:
        from datetime import datetime, timedelta
        now = datetime.now()

        async with async_session() as db:
            from sqlalchemy import select
            # 查找已启用提醒、未完成、未发送提醒、有截止时间的待办
            result = await db.execute(
                select(Todo).where(
                    Todo.reminder_enabled == True,
                    Todo.is_completed == False,
                    Todo.reminder_sent == False,
                    Todo.due_time.isnot(None),
                )
            )
            todos = result.scalars().all()

            if not todos:
                return

            bark = BarkNotifier()
            feishu = FeishuNotifier()

            for todo in todos:
                # 只提醒即将在 1 小时内到期的
                hours_left = (todo.due_time - now).total_seconds() / 3600
                if hours_left > 1:
                    continue

                due_str = todo.due_time.strftime("%m-%d %H:%M") if todo.due_time else ""
                title = "📌 待办提醒"
                message = f"{todo.title}"
                if due_str:
                    message += f"\n截止时间：{due_str}"
                if hours_left <= 0:
                    message += "\n⚠️ 已过期！"
                else:
                    message += f"\n还剩 {int(hours_left)} 小时"

                bark_success = await bark.send_todo_reminder(title=todo.title, due_time=due_str)
                feishu_success = await feishu.send_text(f"{title}\n{message}")

                # 标记已发送
                todo.reminder_sent = True

                if bark_success or feishu_success:
                    logger.info(f"✅ 待办提醒推送成功: {todo.title}")
                else:
                    logger.warning(f"⚠️ 待办提醒推送未送达: {todo.title}")

            await db.commit()

    except Exception as e:
        logger.error(f"❌ 待办提醒检查异常: {e}", exc_info=True)


def register_tasks(scheduler):
    """
    注册所有定时任务

    Args:
        scheduler: TaskScheduler 实例
    """
    logger.info("📋 正在注册定时任务...")

    # 每日课程同步（6:00）
    scheduler.add_daily_task(
        sync_courses_daily,
        hour=6,
        minute=0,
        name="sync_courses_daily"
    )

    # 每日课表推送（7:50）
    scheduler.add_daily_task(
        send_daily_schedule,
        hour=7,
        minute=50,
        name="send_daily_schedule"
    )

    # 作业截止检查（每小时）
    scheduler.add_hourly_task(
        check_assignment_deadlines,
        minute=0,
        name="check_assignment_deadlines"
    )

    # 作业同步（每30分钟）
    scheduler.add_interval_task(
        sync_assignments_periodically,
        minutes=30,
        name="sync_assignments_periodically"
    )

    # 作业清理（每日 3:00）
    scheduler.add_daily_task(
        cleanup_old_assignments_periodically,
        hour=3,
        minute=0,
        name="cleanup_old_assignments"
    )

    # 自定义定时提醒（每分钟检查）
    scheduler.scheduler.add_job(
        check_custom_reminders,
        "interval",
        minutes=1,
        id="check_custom_reminders",
        name="check_custom_reminders",
        replace_existing=True,
    )

    # 待办事项提醒（每 5 分钟检查）
    scheduler.scheduler.add_job(
        check_todo_reminders,
        "interval",
        minutes=5,
        id="check_todo_reminders",
        name="check_todo_reminders",
        replace_existing=True,
    )

    # 教室课表数据刷新（每日 4:00）
    scheduler.add_daily_task(
        refresh_room_data_daily,
        hour=4,
        minute=0,
        name="refresh_room_data_daily"
    )

    logger.info("✅ 所有定时任务注册完成")


async def refresh_room_data_daily():
    """
    每日教室课表数据刷新任务
    每天凌晨 4:00 刷新一次（数据量小、早起用的人少）
    """
    logger.info("🏢 开始执行每日教室数据刷新任务")

    try:
        async with async_session() as db:
            from app.services.room_service import RoomService
            service = RoomService(db)
            result = await service.refresh_room_data()
            if result.get("success"):
                logger.info(f"✅ 教室数据刷新成功: {result['rooms_count']} 个教室, {result['schedules_count']} 条记录")
            else:
                logger.error(f"❌ 教室数据刷新失败: {result.get('message')}")
    except Exception as e:
        logger.error(f"❌ 教室数据刷新异常: {e}", exc_info=True)


if __name__ == "__main__":
    """测试定时任务"""
    print("🧪 测试定时任务...")
    
    # 测试发送今日课表
    asyncio.run(send_daily_schedule())
