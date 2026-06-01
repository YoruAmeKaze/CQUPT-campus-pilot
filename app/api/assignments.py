import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.assignment_service import AssignmentService
from app.crawlers.chaoxing_crawler import ChaoxingCrawler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assignments", tags=["作业"])


PLATFORM_LABELS = {
    "chaoxing": "学习通",
    "smartestu": "数你最灵",
    "jwxt": "教务系统",
}

PLATFORM_COLORS = {
    "chaoxing": "blue",
    "smartestu": "green",
    "jwxt": "orange",
}


def _format_assignment(a) -> dict:
    """格式化作业对象为字典"""
    source_type = a.source.type if a.source else None
    source_name = a.source.name if a.source else None
    return {
        "id": a.id,
        "title": a.title,
        "description": a.description,
        "course_name": a.course_name,
        "due_time": a.due_time.isoformat() if a.due_time else None,
        "is_completed": a.is_completed,
        "created_at": a.created_at.isoformat(),
        "source": {
            "type": source_type,
            "name": source_name or PLATFORM_LABELS.get(source_type, "未知"),
            "label": PLATFORM_LABELS.get(source_type, "未知"),
            "color": PLATFORM_COLORS.get(source_type, "gray"),
        } if source_type else None,
    }


async def get_or_create_default_user(db: AsyncSession) -> int:
    """获取用户（获取有数据的用户）"""
    from sqlalchemy import select
    from app.db.models import User, Course
    
    # 先尝试用配置的学号找用户
    from app.config import settings
    student_id = settings.student_id or "STUDENT_ID"
    
    result = await db.execute(select(User).where(User.student_id == student_id))
    user = result.scalar_one_or_none()
    
    if user:
        return user.id
    
    course_result = await db.execute(select(Course).limit(1))
    course = course_result.scalar_one_or_none()
    if course:
        return course.user_id
        
    return 1


@router.get("")
async def get_assignments(
    status: Optional[str] = Query(None, description="筛选状态：pending|completed|expired|all"),
    limit: int = Query(100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """
    获取作业列表
    
    不传 status 时返回分类数据：{ pending, expired, completed }
    传 status 时返回对应分类的列表
    """
    user_id = await get_or_create_default_user(db)
    service = AssignmentService(db)

    if not status:
        # 返回分类数据
        categorized = await service.get_assignments_with_expired(user_id, limit=limit)
        return {
            "success": True,
            "pending": [_format_assignment(a) for a in categorized["pending"]],
            "expired": [_format_assignment(a) for a in categorized["expired"]],
            "completed": [_format_assignment(a) for a in categorized["completed"]],
            "summary": {
                "pending_count": len(categorized["pending"]),
                "expired_count": len(categorized["expired"]),
                "completed_count": len(categorized["completed"]),
            },
        }

    from app.services.config_store import ConfigStoreService
    from app.config import settings
    store = ConfigStoreService(db, settings.fernet_key)
    term_start_str = await store.get("term_start_date", settings.term_start_date)

    assignments = await service.get_assignments(
        user_id,
        status=status,
        limit=limit,
        term_start=term_start_str,
    )
    
    return {
        "success": True,
        "assignments": [_format_assignment(a) for a in assignments],
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

            save_result = {"new": 0, "updated": 0, "skipped_expired": 0}
            if assignments:
                save_result = await service.save_assignments(user_id, assignments, source_id=ds.id)
                total_new += save_result.get("new", 0)

            ds.last_sync = datetime.now()
            ds.sync_status = "ok"
            ds.error_message = None
            results.append({
                "source": label,
                "status": "ok",
                **save_result,
            })
            logger.info(f"  ✅ {label} 同步完成，新增 {save_result['new']} 条，跳过过期 {save_result.get('skipped_expired', 0)} 条，跳过重复 {save_result.get('skipped_duplicate', 0)} 条")

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
    
    return {"success": True, "message": "已标记为完成"}


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
    
    return {"success": True, "message": "已删除"}


@router.post("/cleanup")
async def cleanup_old_assignments(db: AsyncSession = Depends(get_db)):
    """清理过时已完成作业"""
    user_id = await get_or_create_default_user(db)
    service = AssignmentService(db)

    from app.services.config_store import ConfigStoreService
    from app.config import settings
    store = ConfigStoreService(db, settings.fernet_key)

    enabled = await store.get("auto_cleanup_enabled", "false")
    days = int(await store.get("auto_cleanup_days", "30"))

    if enabled != "true":
        return {"success": True, "message": "自动清理未开启，跳过", "deleted": 0}

    deleted = await service.delete_old_completed_assignments(user_id, days)
    return {"success": True, "message": f"已清理 {deleted} 条过时作业", "deleted": deleted}


@router.post("/cleanup-expired")
async def cleanup_expired_assignments(db: AsyncSession = Depends(get_db)):
    """
    清理已过期未完成的作业（手动触发）
    
    删除截止时间超过 120 天前且仍未完成的作业
    """
    user_id = await get_or_create_default_user(db)
    service = AssignmentService(db)
    deleted = await service.cleanup_expired_assignments(user_id)
    return {"success": True, "message": f"已清理 {deleted} 条过期作业", "deleted": deleted}