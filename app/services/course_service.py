import json
import logging
from datetime import datetime, date
from typing import List, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.crawlers.jwxt_crawler import JwxtCrawler
from app.db.models import Course, User, DataSource
from app.config import settings

logger = logging.getLogger(__name__)


class CourseService:
    """课表数据服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _get_location_for_week(self, course: Course, week: int) -> str:
        """
        根据周次获取课程的上课地点

        Args:
            course: 课程对象
            week: 周次

        Returns:
            str: 该周次的上课地点
        """
        # 如果有 location_schedule，按周次匹配
        if course.location_schedule:
            try:
                schedule = json.loads(course.location_schedule)
                for entry in schedule:
                    start = entry.get("start_week", 1)
                    end = entry.get("end_week", 20)
                    if start <= week <= end:
                        return entry.get("location", course.location or "")
                # 没有匹配的区间，返回默认地点
                return course.location or ""
            except (json.JSONDecodeError, TypeError):
                # 解析失败，返回默认地点
                return course.location or ""

        # 没有 schedule，返回默认地点
        return course.location or ""

    def _calculate_week_number(self, target_date: Optional[date] = None) -> int:
        """
        计算指定日期是第几周
        
        Args:
            target_date: 目标日期，不传则用今天
            
        Returns:
            int: 周数（从1开始）
        """
        if target_date is None:
            target_date = date.today()
        
        # 解析学期开始日期
        term_start = datetime.strptime(settings.term_start_date, "%Y-%m-%d").date()
        
        # 计算相差的天数
        delta_days = (target_date - term_start).days
        
        # 计算周数（从1开始）
        if delta_days < 0:
            return 1
        week_number = (delta_days // 7) + 1
        return week_number
    
    def _is_course_in_week(self, course: Course, week: int) -> bool:
        """
        检查课程在指定周是否有课
        
        Args:
            course: 课程对象
            week: 周次
            
        Returns:
            bool: 是否有课
        """
        # 如果有 week_mask，使用精确匹配
        if course.week_mask:
            mask = course.week_mask
            # week_mask 是二进制字符串，索引0对应第1周
            if week >= 1 and week <= len(mask):
                return mask[week - 1] == "1"
            return False
        
        # 没有 week_mask，使用范围判断（兼容旧数据）
        return course.start_week <= week <= course.end_week
    
    async def sync_courses_from_jwxt(self, student_id: Optional[str] = None) -> dict:
        """
        从教务系统同步课表到数据库
        
        Args:
            student_id: 学号，如果不传则使用配置中的学号
            
        Returns:
            dict: 同步结果 {
                "success": bool,
                "courses_count": int,
                "message": str
            }
        """
        crawler = JwxtCrawler(student_id)
        
        try:
            # 1. 抓取并解析课表
            courses_data = await crawler.crawl_and_parse()
            
            if not courses_data:
                return {
                    "success": False,
                    "courses_count": 0,
                    "message": "未获取到课程数据",
                }

            # 2. 确保用户存在
            user = await self._get_or_create_user(student_id or crawler.student_id)
            
            # 3. 清除该用户的旧课表数据
            await self.db.execute(
                delete(Course).where(Course.user_id == user.id)
            )
            
            # 4. 插入新数据
            inserted_count = 0
            for course_data in courses_data:
                location_schedule = course_data.get("location_schedule")
                course = Course(
                    user_id=user.id,
                    name=course_data["name"],
                    teacher=course_data.get("teacher", ""),
                    location=course_data.get("location", ""),
                    location_schedule=json.dumps(location_schedule) if location_schedule else None,
                    day_of_week=course_data["day_of_week"],
                    start_week=course_data.get("start_week", 1),
                    end_week=course_data.get("end_week", 18),
                    week_mask=course_data.get("week_mask", ""),
                    start_slot=course_data["start_slot"],
                    end_slot=course_data["end_slot"],
                    start_time=course_data.get("start_time", ""),
                    end_time=course_data.get("end_time", ""),
                )
                self.db.add(course)
                inserted_count += 1
            
            await self.db.commit()
            
            logger.info(f"成功同步 {inserted_count} 门课程")
            
            return {
                "success": True,
                "courses_count": inserted_count,
                "message": f"成功同步 {inserted_count} 门课程",
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"同步课表失败: {e}", exc_info=True)
            return {
                "success": False,
                "courses_count": 0,
                "message": f"同步失败: {str(e)}",
            }

    async def get_courses_by_week(
        self,
        user_id: int,
        week: Optional[int] = None,
    ) -> List[dict]:
        """
        获取指定周的课表
        
        Args:
            user_id: 用户 ID
            week: 周次（可选），不传则返回当前周
            
        Returns:
            List[dict]: 课程列表
        """
        if week is None:
            week = self._calculate_week_number()
        
        # 先获取时间范围内的课程，然后用 week_mask 精确过滤
        query = (
            select(Course)
            .where(
                Course.user_id == user_id,
                Course.start_week <= week,
                Course.end_week >= week,
            )
            .order_by(Course.day_of_week, Course.start_slot)
        )
        
        result = await self.db.execute(query)
        courses = result.scalars().all()
        
        # 使用 week_mask 精确过滤，并返回正确地点
        filtered_courses = [c for c in courses if self._is_course_in_week(c, week)]

        return [
            {
                "id": c.id,
                "name": c.name,
                "teacher": c.teacher,
                "location": self._get_location_for_week(c, week),
                "day_of_week": c.day_of_week,
                "start_week": c.start_week,
                "end_week": c.end_week,
                "week_mask": c.week_mask,
                "start_slot": c.start_slot,
                "end_slot": c.end_slot,
                "start_time": c.start_time,
                "end_time": c.end_time,
            }
            for c in filtered_courses
        ]

    async def get_today_courses(self, user_id: int) -> List[dict]:
        """
        获取今天的课程
        
        Args:
            user_id: 用户 ID
            
        Returns:
            List[dict]: 今天的课程列表
        """
        today = date.today()
        today_weekday = today.weekday() + 1  # 0=Monday → 1=Monday
        current_week = self._calculate_week_number(today)
        
        # 获取本周课程（已通过 week_mask 精确过滤）
        week_courses = await self.get_courses_by_week(user_id, current_week)
        
        # 只返回今天的课程
        today_courses = [
            course for course in week_courses 
            if course["day_of_week"] == today_weekday
        ]
        
        return today_courses
    
    async def get_tomorrow_courses(self, user_id: int) -> List[dict]:
        """
        获取明天的课程
        
        Args:
            user_id: 用户 ID
            
        Returns:
            List[dict]: 明天的课程列表
        """
        from datetime import timedelta
        
        tomorrow = date.today() + timedelta(days=1)
        tomorrow_weekday = tomorrow.weekday() + 1  # 0=Monday → 1=Monday
        
        # 如果明天是周日，下周一是下周
        if tomorrow_weekday == 7:
            tomorrow_weekday = 1
        
        tomorrow_week = self._calculate_week_number(tomorrow)
        
        # 获取明天所在周的课程
        week_courses = await self.get_courses_by_week(user_id, tomorrow_week)
        
        # 只返回明天的课程
        tomorrow_courses = [
            course for course in week_courses 
            if course["day_of_week"] == tomorrow_weekday
        ]
        
        return tomorrow_courses

    async def _get_or_create_user(self, student_id: str) -> User:
        """获取或创建用户"""
        query = select(User).where(User.student_id == student_id)
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(student_id=student_id)
            self.db.add(user)
            await self.db.flush()
        
        return user
