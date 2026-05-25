"""
发送今日课表到 Bark
"""

import asyncio
from app.config import settings
from app.db.session import async_session
from app.services.course_service import CourseService
from app.notifications.bark_notifier import BarkNotifier


async def send_today_schedule():
    """获取今日课程并通过 Bark 推送"""

    print(f"📅 今天是：{settings.term_start_date} 后的第 13 周\n")

    async with async_session() as db:
        service = CourseService(db)

        # 获取用户
        from app.db.models import User
        from sqlalchemy import select
        result = await db.execute(select(User))
        user = result.scalar_one_or_none()

        if not user:
            print("❌ 没有找到用户！")
            return

        # 获取今日课程
        today_courses = await service.get_today_courses(user.id)

        print(f"📚 今日共有 {len(today_courses)} 门课程：\n")
        for course in today_courses:
            print(f"  - {course['name']} {course['start_time']} @ {course['location']}")

        # 通过 Bark 推送
        print("\n📱 正在通过 Bark 推送...")
        notifier = BarkNotifier()

        success = await notifier.send_schedule_reminder(today_courses)

        if success:
            print("✅ 推送成功！请检查您的 iPhone Bark 通知。")
        else:
            print("❌ 推送失败")


if __name__ == "__main__":
    asyncio.run(send_today_schedule())
