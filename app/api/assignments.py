import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.assignment_service import AssignmentService
from app.crawlers.chaoxing_crawler import ChaoxingCrawler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assignments", tags=["作业"])


async def get_or_create_default_user(db: AsyncSession) -> int:
    """获取用户（获取有数据的用户）"""
    from sqlalchemy import select
    from app.db.models import User, Course
    
    # 先尝试用配置的学号找用户
    from app.config import settings
    student_id = settings.student_id or "2025213306"
    
    # 查询该学号的用户
    result = await db.execute(select(User).where(User.student_id == student_id))
    user = result.scalar_one_or_none()
    
    if user:
        return user.id
    
    # 如果没找到，尝试找第一个有课程的用户
    course_result = await db.execute(select(Course).limit(1))
    course = course_result.scalar_one_or_none()
    if course:
        return course.user_id
        
    # 降级到 1
    return 1


@router.get("")
async def get_assignments(
    status: Optional[str] = Query(None, description="筛选状态：pending|completed|all"),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """获取作业列表"""
    user_id = await get_or_create_default_user(db)
    service = AssignmentService(db)
    assignments = await service.get_assignments(user_id, status=status, limit=limit)
    
    return {
        "success": True,
        "assignments": [
            {
                "id": a.id,
                "title": a.title,
                "description": a.description,
                "course_name": a.course_name,
                "due_time": a.due_time.isoformat() if a.due_time else None,
                "is_completed": a.is_completed,
                "created_at": a.created_at.isoformat(),
            }
            for a in assignments
        ],
    }


@router.get("/today")
async def get_today_assignments(db: AsyncSession = Depends(get_db)):
    """获取今日截止的作业"""
    user_id = await get_or_create_default_user(db)
    service = AssignmentService(db)
    assignments = await service.get_today_assignments(user_id)
    
    return {
        "success": True,
        "assignments": [
            {
                "id": a.id,
                "title": a.title,
                "course_name": a.course_name,
                "due_time": a.due_time.isoformat() if a.due_time else None,
            }
            for a in assignments
        ],
    }


@router.get("/upcoming")
async def get_upcoming_assignments(
    days: int = Query(3, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """获取未来 N 天截止的作业"""
    user_id = await get_or_create_default_user(db)
    service = AssignmentService(db)
    assignments = await service.get_upcoming_assignments(user_id, days=days)
    
    return {
        "success": True,
        "days": days,
        "assignments": [
            {
                "id": a.id,
                "title": a.title,
                "course_name": a.course_name,
                "due_time": a.due_time.isoformat() if a.due_time else None,
            }
            for a in assignments
        ],
    }


@router.post("/sync")
async def sync_assignments(db: AsyncSession = Depends(get_db)):
    """同步作业（先同步学习通，后续支持多数据源）"""
    user_id = await get_or_create_default_user(db)
    service = AssignmentService(db)
    
    logger.info("🔄 开始同步作业...")
    
    # 1. 同步学习通
    chaoxing = ChaoxingCrawler()
    assignments = await chaoxing.crawl_and_parse()
    
    new_count = 0
    if assignments:
        new_count = await service.save_assignments(user_id, assignments)
    
    # TODO: 同步数你最灵等其他数据源
    
    return {
        "success": True,
        "message": "同步完成",
        "new_count": new_count,
    }


@router.post("/{assignment_id}/complete")
async def mark_completed(
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
):
    """标记作业为已完成"""
    user_id = await get_or_create_default_user(db)
    service = AssignmentService(db)
    success = await service.mark_completed(assignment_id, user_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="作业不存在")
    
    return {
        "success": True,
        "message": "已标记为完成",
    }
