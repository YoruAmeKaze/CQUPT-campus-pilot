import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.db.session import get_db
from app.db.models import CustomReminder, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/custom-reminders", tags=["自定义提醒"])


class ReminderCreate(BaseModel):
    name: str = Field(..., description="提醒名称")
    title: str = Field(..., description="推送标题")
    content: Optional[str] = Field(None, description="推送内容")
    repeat_type: str = Field("daily", description="daily / weekly / monthly")
    repeat_day: Optional[int] = Field(None, description="weekly=0-6(周一到周日), monthly=1-31")
    reminder_time: str = Field(..., description="HH:MM 格式")


class ReminderUpdate(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    repeat_type: Optional[str] = None
    repeat_day: Optional[int] = None
    reminder_time: Optional[str] = None
    enabled: Optional[bool] = None


class ReminderResponse(BaseModel):
    id: int
    name: str
    title: str
    content: Optional[str] = None
    repeat_type: str
    repeat_day: Optional[int] = None
    reminder_time: str
    enabled: bool
    created_at: str
    updated_at: str


async def _get_user_id(db: AsyncSession) -> int:
    from app.config import settings
    result = await db.execute(select(User).where(User.student_id == settings.student_id))
    user = result.scalar_one_or_none()
    return user.id if user else 1


def _reminder_to_dict(r: CustomReminder) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "title": r.title,
        "content": r.content,
        "repeat_type": r.repeat_type,
        "repeat_day": r.repeat_day,
        "reminder_time": r.reminder_time,
        "enabled": r.enabled,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }


@router.get("", response_model=List[ReminderResponse])
async def list_reminders(db: AsyncSession = Depends(get_db)):
    """获取所有自定义提醒"""
    user_id = await _get_user_id(db)
    result = await db.execute(
        select(CustomReminder).where(CustomReminder.user_id == user_id).order_by(CustomReminder.created_at.desc())
    )
    return [_reminder_to_dict(r) for r in result.scalars().all()]


@router.post("")
async def create_reminder(reminder: ReminderCreate, db: AsyncSession = Depends(get_db)):
    """创建自定义提醒"""
    if reminder.repeat_type not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="repeat_type 必须是 daily/weekly/monthly")
    if reminder.repeat_type == "weekly" and (reminder.repeat_day is None or not (0 <= reminder.repeat_day <= 6)):
        raise HTTPException(status_code=400, detail="weekly 模式需要 repeat_day 在 0-6 之间")
    if reminder.repeat_type == "monthly" and (reminder.repeat_day is None or not (1 <= reminder.repeat_day <= 31)):
        raise HTTPException(status_code=400, detail="monthly 模式需要 repeat_day 在 1-31 之间")

    user_id = await _get_user_id(db)
    obj = CustomReminder(
        user_id=user_id,
        name=reminder.name,
        title=reminder.title,
        content=reminder.content,
        repeat_type=reminder.repeat_type,
        repeat_day=reminder.repeat_day,
        reminder_time=reminder.reminder_time,
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return {"success": True, "reminder": _reminder_to_dict(obj)}


@router.put("/{reminder_id}")
async def update_reminder(reminder_id: int, reminder: ReminderUpdate, db: AsyncSession = Depends(get_db)):
    """更新自定义提醒"""
    user_id = await _get_user_id(db)
    result = await db.execute(
        select(CustomReminder).where(CustomReminder.id == reminder_id, CustomReminder.user_id == user_id)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="提醒不存在")

    update_data = reminder.model_dump(exclude_none=True)
    for key, value in update_data.items():
        if hasattr(obj, key):
            setattr(obj, key, value)

    await db.commit()
    await db.refresh(obj)
    return {"success": True, "reminder": _reminder_to_dict(obj)}


@router.delete("/{reminder_id}")
async def delete_reminder(reminder_id: int, db: AsyncSession = Depends(get_db)):
    """删除自定义提醒"""
    user_id = await _get_user_id(db)
    result = await db.execute(
        delete(CustomReminder).where(CustomReminder.id == reminder_id, CustomReminder.user_id == user_id)
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="提醒不存在")
    return {"success": True, "message": "删除成功"}
