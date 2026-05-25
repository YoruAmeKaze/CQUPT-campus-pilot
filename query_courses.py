import asyncio
from sqlalchemy import select
from app.db.models import Course, User
from app.db.session import async_session

async def query_courses():
    """查询数据库中的课程"""
    
    async with async_session() as db:
        # 先找用户
        user_result = await db.execute(select(User))
        user = user_result.scalar_one_or_none()
        
        if not user:
            print("❌ 数据库中没有用户数据")
            return
        
        print(f"👤 用户: {user.student_id}")
        
        # 查询所有课程
        courses_result = await db.execute(
            select(Course)
            .where(Course.user_id == user.id)
            .order_by(Course.day_of_week, Course.start_slot)
        )
        courses = courses_result.scalars().all()
        
        print(f"\n📚 数据库中共有 {len(courses)} 门课程：\n")
        
        # 按周几分组显示
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        for day in range(1, 8):
            day_courses = [c for c in courses if c.day_of_week == day]
            if day_courses:
                print(f"--- {weekdays[day-1]} ---")
                for course in day_courses:
                    print(f"  {course.start_slot}-{course.end_slot}节 | {course.start_time}-{course.end_time}")
                    print(f"    📖 {course.name}")
                    print(f"    👨‍🏫 {course.teacher}")
                    print(f"    📍 {course.location}")
                    print(f"    📅 第{course.start_week}-{course.end_week}周")
                    print()

if __name__ == "__main__":
    asyncio.run(query_courses())
