import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.todo_service import TodoService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/todos", tags=["待办事项"])


class TodoCreateRequest(BaseModel):
    """创建待办事项请求"""
    title: str = Field(..., description="待办标题")
    description: Optional[str] = Field(None, description="描述")
    due_time: Optional[datetime] = Field(None, description="截止时间")
    priority: str = Field("normal", description="优先级 (low/normal/high)")
    source: str = Field("manual", description="来源 (manual/llm)")
    reminder_enabled: bool = Field(False, description="是否开启提醒")


class TodoUpdateRequest(BaseModel):
    """更新待办事项请求"""
    title: Optional[str] = None
    description: Optional[str] = None
    due_time: Optional[datetime] = None
    priority: Optional[str] = None
    is_completed: Optional[bool] = None
    reminder_enabled: Optional[bool] = None


@router.get("")
async def get_todos(
    status: Optional[str] = Query(None, description="状态 (all/pending/completed)"),
    priority: Optional[str] = Query(None, description="优先级过滤"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取待办事项列表

    - **status**: 可选，状态过滤
    - **priority**: 可选，优先级过滤
    """
    service = TodoService(db)

    try:
        todos = await service.get_todos(status=status, priority=priority)

        return {
            "success": True,
            "todos_count": len(todos),
            "todos": todos,
        }

    except Exception as e:
        logger.error(f"获取待办事项失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取待办事项失败: {str(e)}")


@router.get("/{todo_id}")
async def get_todo(
    todo_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取单个待办事项"""
    service = TodoService(db)

    todo = await service.get_todo_by_id(todo_id)

    if not todo:
        raise HTTPException(status_code=404, detail="待办事项不存在")

    return {
        "success": True,
        "todo": todo,
    }


@router.post("")
async def create_todo(
    request: TodoCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    创建待办事项

    支持通过自然语言或手动输入创建待办事项
    """
    service = TodoService(db)

    try:
        result = await service.create_todo(
            title=request.title,
            description=request.description,
            due_time=request.due_time,
            priority=request.priority,
            source=request.source,
            reminder_enabled=request.reminder_enabled,
        )

        return result

    except Exception as e:
        logger.error(f"创建待办事项失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建待办事项失败: {str(e)}")


@router.put("/{todo_id}")
async def update_todo(
    todo_id: int,
    request: TodoUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新待办事项"""
    service = TodoService(db)

    todo = await service.update_todo(
        todo_id=todo_id,
        **request.model_dump(exclude_none=True),
    )

    if not todo:
        raise HTTPException(status_code=404, detail="待办事项不存在")

    return {
        "success": True,
        "todo": todo,
    }


@router.delete("/{todo_id}")
async def delete_todo(
    todo_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除待办事项"""
    service = TodoService(db)

    success = await service.delete_todo(todo_id)

    if not success:
        raise HTTPException(status_code=404, detail="待办事项不存在")

    return {
        "success": True,
        "message": "删除成功",
    }


@router.post("/{todo_id}/complete")
async def complete_todo(
    todo_id: int,
    db: AsyncSession = Depends(get_db),
):
    """标记待办事项为完成"""
    service = TodoService(db)

    todo = await service.complete_todo(todo_id)

    if not todo:
        raise HTTPException(status_code=404, detail="待办事项不存在")

    return {
        "success": True,
        "todo": todo,
    }


@router.post("/llm/create")
async def create_todo_by_llm(
    request: TodoCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    通过大语言模型创建待办事项

    此接口专门用于飞书/LLM 意图识别后创建待办事项
    """
    service = TodoService(db)

    try:
        result = await service.create_todo(
            title=request.title,
            description=request.description,
            due_time=request.due_time,
            priority=request.priority,
            source="llm",
        )

        return result

    except Exception as e:
        logger.error(f"LLM 创建待办事项失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建待办事项失败: {str(e)}")


@router.get("/summary/dashboard")
async def get_todo_summary(
    db: AsyncSession = Depends(get_db),
):
    """
    获取待办事项统计摘要（用于仪表盘）

    返回待办总数、待完成数、已完成数、今日截止数等
    """
    service = TodoService(db)

    try:
        all_todos = await service.get_todos()
        pending_todos = [t for t in all_todos if not t["is_completed"]]
        completed_todos = [t for t in all_todos if t["is_completed"]]

        today = datetime.now().date()
        today_due = [
            t for t in pending_todos
            if t["due_time"] and datetime.fromisoformat(t["due_time"]).date() == today
        ]

        high_priority = [t for t in pending_todos if t["priority"] == "high"]

        return {
            "success": True,
            "total": len(all_todos),
            "pending": len(pending_todos),
            "completed": len(completed_todos),
            "today_due": len(today_due),
            "high_priority": len(high_priority),
        }

    except Exception as e:
        logger.error(f"获取待办摘要失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取摘要失败: {str(e)}")
