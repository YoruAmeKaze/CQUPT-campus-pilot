import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Todo, User

logger = logging.getLogger(__name__)


class TodoService:
    """待办事项数据服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_or_create_user(self, student_id: Optional[str] = None) -> User:
        """获取或创建用户"""
        if student_id is None:
            from app.config import settings
            student_id = settings.student_id or ""
        query = select(User).where(User.student_id == student_id)
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            user = User(student_id=student_id)
            self.db.add(user)
            await self.db.flush()

        return user

    async def create_todo(
        self,
        title: str,
        user_id: Optional[int] = None,
        description: Optional[str] = None,
        due_time: Optional[datetime] = None,
        priority: str = "normal",
        source: str = "manual",
        reminder_enabled: bool = False,
    ) -> dict:
        """
        创建待办事项

        Args:
            title: 待办标题
            user_id: 用户 ID，不传则自动创建/获取默认用户
            description: 描述
            due_time: 截止时间
            priority: 优先级 (low/normal/high)
            source: 来源 (manual/llm)
            reminder_enabled: 是否开启提醒

        Returns:
            待办事项数据
        """
        if user_id is None:
            user = await self._get_or_create_user()
            user_id = user.id

        try:
            todo = Todo(
                user_id=user_id,
                title=title,
                description=description,
                due_time=due_time,
                priority=priority,
                is_completed=False,
                source=source,
                reminder_enabled=reminder_enabled,
            )
            self.db.add(todo)
            await self.db.commit()
            await self.db.refresh(todo)

            logger.info(f"创建待办事项成功: {title}")

            return {
                "success": True,
                "todo": self._todo_to_dict(todo),
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"创建待办事项失败: {e}", exc_info=True)
            raise

    async def get_todos(
        self,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> List[dict]:
        """
        获取待办事项列表

        Args:
            user_id: 用户 ID，不传则使用默认用户
            status: 状态过滤 (all/pending/completed)
            priority: 优先级过滤

        Returns:
            待办事项列表
        """
        if user_id is None:
            user = await self._get_or_create_user()
            user_id = user.id

        query = select(Todo).where(Todo.user_id == user_id)

        if status == "pending":
            query = query.where(Todo.is_completed == False)
        elif status == "completed":
            query = query.where(Todo.is_completed == True)

        if priority:
            query = query.where(Todo.priority == priority)

        query = query.order_by(desc(Todo.created_at))

        result = await self.db.execute(query)
        todos = result.scalars().all()

        return [self._todo_to_dict(t) for t in todos]

    async def get_todo_by_id(
        self,
        todo_id: int,
        user_id: Optional[int] = None,
    ) -> Optional[dict]:
        """
        获取单个待办事项

        Args:
            todo_id: 待办 ID
            user_id: 用户 ID

        Returns:
            待办事项数据
        """
        if user_id is None:
            user = await self._get_or_create_user()
            user_id = user.id

        query = select(Todo).where(Todo.id == todo_id, Todo.user_id == user_id)
        result = await self.db.execute(query)
        todo = result.scalar_one_or_none()

        if todo:
            return self._todo_to_dict(todo)
        return None

    async def update_todo(
        self,
        todo_id: int,
        user_id: Optional[int] = None,
        **kwargs,
    ) -> Optional[dict]:
        """
        更新待办事项

        Args:
            todo_id: 待办 ID
            user_id: 用户 ID
            **kwargs: 要更新的字段

        Returns:
            更新后的待办事项数据
        """
        if user_id is None:
            user = await self._get_or_create_user()
            user_id = user.id

        query = select(Todo).where(Todo.id == todo_id, Todo.user_id == user_id)
        result = await self.db.execute(query)
        todo = result.scalar_one_or_none()

        if not todo:
            return None

        for key, value in kwargs.items():
            if hasattr(todo, key):
                setattr(todo, key, value)

        await self.db.commit()
        await self.db.refresh(todo)

        logger.info(f"更新待办事项成功: {todo_id}")

        return self._todo_to_dict(todo)

    async def delete_todo(
        self,
        todo_id: int,
        user_id: Optional[int] = None,
    ) -> bool:
        """
        删除待办事项

        Args:
            todo_id: 待办 ID
            user_id: 用户 ID

        Returns:
            是否删除成功
        """
        if user_id is None:
            user = await self._get_or_create_user()
            user_id = user.id

        query = delete(Todo).where(Todo.id == todo_id, Todo.user_id == user_id)
        result = await self.db.execute(query)
        await self.db.commit()

        if result.rowcount > 0:
            logger.info(f"删除待办事项成功: {todo_id}")
            return True
        return False

    async def complete_todo(
        self,
        todo_id: int,
        user_id: Optional[int] = None,
    ) -> Optional[dict]:
        """
        标记待办事项为完成

        Args:
            todo_id: 待办 ID
            user_id: 用户 ID

        Returns:
            更新后的待办事项数据
        """
        return await self.update_todo(
            todo_id=todo_id,
            user_id=user_id,
            is_completed=True,
        )

    def _todo_to_dict(self, todo: Todo) -> dict:
        """将 Todo 对象转换为字典"""
        return {
            "id": todo.id,
            "user_id": todo.user_id,
            "title": todo.title,
            "description": todo.description,
            "due_time": todo.due_time.isoformat() if todo.due_time else None,
            "priority": todo.priority,
            "is_completed": todo.is_completed,
            "source": todo.source,
            "reminder_enabled": todo.reminder_enabled,
            "reminder_sent": todo.reminder_sent,
            "created_at": todo.created_at.isoformat(),
            "updated_at": todo.updated_at.isoformat(),
        }
