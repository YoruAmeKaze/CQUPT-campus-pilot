import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import User, Course
from app.db.session import get_db
from app.services.course_service import CourseService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/courses", tags=["课表"])


async def _get_active_user_id(db: AsyncSession) -> int:
    """获取当前活跃用户的 ID"""
    student_id = settings.student_id or "2025213306"
    user_result = await db.execute(select(User).where(User.student_id == student_id))
    user = user_result.scalar_one_or_none()
    if user:
        return user.id

    course_result = await db.execute(select(Course).limit(1))
    course_with_data = course_result.scalar_one_or_none()
    if course_with_data:
        return course_with_data.user_id

    return 1


@router.get("")
async def get_courses(
    week: Optional[int] = Query(None, description="周次，不传则返回当前周"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取课表列表

    - **week**: 可选，指定查询的周次（1-20）
    - 返回指定周的所有课程
    """
    service = CourseService(db)

    try:
        user_id = await _get_active_user_id(db)
        courses = await service.get_courses_by_week(user_id=user_id, week=week)

        return {
            "success": True,
            "week": week,
            "courses_count": len(courses),
            "courses": courses,
        }

    except Exception as e:
        logger.error(f"获取课表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取课表失败: {str(e)}")


@router.get("/today")
async def get_today_courses(db: AsyncSession = Depends(get_db)):
    """获取今天的课程"""
    service = CourseService(db)

    try:
        user_id = await _get_active_user_id(db)
        courses = await service.get_today_courses(user_id=user_id)

        today_weekday = datetime.now().weekday() + 1

        return {
            "success": True,
            "today": today_weekday,
            "courses_count": len(courses),
            "courses": courses,
        }

    except Exception as e:
        logger.error(f"获取今日课程失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync")
async def sync_courses(
    student_id: Optional[str] = Query(None, description="学号，可选"),
    db: AsyncSession = Depends(get_db),
):
    """
    手动触发课表同步

    从教务系统抓取最新课表并更新到数据库
    """
    service = CourseService(db)

    result = await service.sync_courses_from_jwxt(student_id)

    if result["success"]:
        return result
    else:
        raise HTTPException(status_code=400, detail=result["message"])


@router.get("/summary")
async def get_course_summary(db: AsyncSession = Depends(get_db)):
    """
    获取课表摘要信息

    返回今日课程数、本周课程总数等统计信息
    """
    service = CourseService(db)

    try:
        user_id = await _get_active_user_id(db)

        week_courses = await service.get_courses_by_week(user_id=user_id)

        today_courses = await service.get_today_courses(user_id=user_id)

        today_weekday = datetime.now().weekday() + 1

        return {
            "success": True,
            "today_courses_count": len(today_courses),
            "week_courses_count": len(week_courses),
            "today_weekday": today_weekday,
            "current_week": service._calculate_week_number(),
        }

    except Exception as e:
        logger.error(f"获取课表摘要失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
