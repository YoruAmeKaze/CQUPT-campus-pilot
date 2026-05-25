"""
定时任务定义
"""

import asyncio
import logging
from datetime import datetime

from app.config import settings
from app.db.session import async_session
from app.services.course_service import CourseService
from app.services.assignment_service import AssignmentService
from app.notifications.bark_notifier import BarkNotifier

logger = logging.getLogger(__name__)


async def send_daily_schedule():
    """
    每日课表推送任务
    每天早上 7:50 发送今日课表到 Bark
    """
    logger.info("📅 开始执行每日课表推送任务")

    try:
        async with async_session() as db:
            course_service = CourseService(db)
            notifier = BarkNotifier()

            # 获取用户
            from app.db.models import User
            from sqlalchemy import select
            result = await db.execute(select(User))
            user = result.scalar_one_or_none()

            if not user:
                logger.warning("⚠️ 没有找到用户，跳过推送")
                return

            # 获取今日课程
            today_courses = await course_service.get_today_courses(user.id)

            if not today_courses:
                logger.info("📭 今日无课，跳过推送")
                return

            # 推送课表
            success = await notifier.send_schedule_reminder(today_courses)

            if success:
                logger.info("✅ 每日课表推送成功")
            else:
                logger.error("❌ 每日课表推送失败")

    except Exception as e:
        logger.error(f"❌ 每日课表推送任务异常: {e}", exc_info=True)


async def check_assignment_deadlines():
    """
    作业截止检查任务
    每小时检查一次即将截止的作业
    """
    logger.info("⏰ 开始执行作业截止检查任务")

    try:
        async with async_session() as db:
            assignment_service = AssignmentService(db)
            notifier = BarkNotifier()

            # 获取用户
            from app.db.models import User
            from sqlalchemy import select
            result = await db.execute(select(User))
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
                        success = await notifier.send_assignment_reminder(
                            course_name=assignment.course_name or "未知课程",
                            title=assignment.title,
                            due_time=due_time.isoformat(),
                            hours_left=int(hours_left)
                        )

                        if success:
                            logger.info(f"✅ 作业提醒推送成功: {assignment.title}")
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
            result = await db.execute(select(User))
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
            result = await db.execute(select(User))
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
    """
    logger.info("🔔 发送测试通知")
    
    notifier = BarkNotifier()
    await notifier.send_custom(
        message="定时任务测试成功！",
        title="🔔 测试通知"
    )
    logger.info("✅ 测试通知发送成功")


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

    logger.info("✅ 所有定时任务注册完成")


if __name__ == "__main__":
    """测试定时任务"""
    print("🧪 测试定时任务...")
    
    # 测试发送今日课表
    asyncio.run(send_daily_schedule())
