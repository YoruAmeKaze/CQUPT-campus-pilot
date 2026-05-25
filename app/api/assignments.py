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
    """同步作业（从数据库读配置）"""
    user_id = await get_or_create_default_user(db)
    service = AssignmentService(db)

    logger.info("🔄 开始同步作业...")

    from app.services.config_store import ConfigStoreService
    from app.config import settings
    from app.db.models import DataSource
    from sqlalchemy import select
    from datetime import datetime

    store = ConfigStoreService(db, settings.fernet_key)
    total_new = 0
    results = []

    async def _sync_source(source_type: str, label: str):
        nonlocal total_new
        result_query = await db.execute(
            select(DataSource).where(
                DataSource.user_id == user_id,
                DataSource.type == source_type,
            )
        )
        ds = result_query.scalar_one_or_none()
        if not ds:
            logger.info(f"  ⏭️ {label} 未配置")
            return

        try:
            import json
            creds = json.loads(ds.credentials) if ds.credentials else {}
            assignments = []

            if source_type == "chaoxing":
                username = creds.get("username", "") or settings.chaoxing_username
                password = creds.get("password", "") or settings.chaoxing_password
                if not username or not password:
                    raise Exception("未配置学习通账号密码")
                from app.crawlers.chaoxing_crawler import ChaoxingCrawler
                async with ChaoxingCrawler(username=username, password=password) as crawler:
                    assignments = await crawler.crawl_and_parse()
            elif source_type == "smartestu":
                student_id = creds.get("student_id", "") or settings.smartestu_student_id
                password = creds.get("password", "") or settings.smartestu_password
                if not student_id or not password:
                    raise Exception("未配置数你最灵账号密码")
                from app.crawlers.smartestu_crawler import SmartestuCrawler
                async with SmartestuCrawler(student_id=student_id, password=password) as crawler:
                    assignments = await crawler.crawl_and_parse()
            else:
                return

            new_count = 0
            if assignments:
                new_count = await service.save_assignments(user_id, assignments, source_id=ds.id)
                total_new += new_count

            ds.last_sync = datetime.now()
            ds.sync_status = "ok"
            ds.error_message = None
            results.append({"source": label, "status": "ok", "new": new_count})
            logger.info(f"  ✅ {label} 同步完成，新增 {new_count} 条")

        except Exception as e:
            ds.sync_status = "error"
            ds.error_message = str(e)[:500]
            results.append({"source": label, "status": "error", "error": str(e)})
            logger.error(f"  ❌ {label} 同步失败: {e}")

        await db.commit()

    await _sync_source("chaoxing", "学习通")
    await _sync_source("smartestu", "数你最灵")

    return {
        "success": True,
        "message": "同步完成",
        "new_count": total_new,
        "results": results,
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


@router.delete("/{assignment_id}")
async def delete_assignment(
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除作业"""
    user_id = await get_or_create_default_user(db)
    service = AssignmentService(db)
    success = await service.delete_assignment(assignment_id, user_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="作业不存在")
    
    return {
        "success": True,
        "message": "已删除",
    }
