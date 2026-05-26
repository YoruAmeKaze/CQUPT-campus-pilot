import json
import logging
from datetime import datetime, date
from typing import List, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Assignment, User, DataSource

logger = logging.getLogger(__name__)


class AssignmentService:
    """作业数据服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_assignments(
        self,
        user_id: int,
        status: Optional[str] = None,
        limit: int = 100,
        term_start: Optional[str] = None,
    ) -> List[Assignment]:
        """
        获取用户的作业列表

        Args:
            user_id: 用户ID
            status: 筛选状态（pending=未完成, completed=已完成, all=全部）
            limit: 限制数量
            term_start: 学期开始日期（用于过滤上学期已完成的作业）

        Returns:
            List[Assignment]: 作业列表
        """
        query = select(Assignment).where(Assignment.user_id == user_id)

        if status == "pending":
            query = query.where(Assignment.is_completed == False)
        elif status == "completed":
            query = query.where(Assignment.is_completed == True)

        # 过滤上学期已完成作业（due_time < term_start 且已完成的归为"历史"）
        if term_start:
            try:
                cutoff = datetime.strptime(term_start[:10], "%Y-%m-%d")
                query = query.where(
                    (Assignment.due_time >= cutoff)
                    | (Assignment.due_time == None)
                    | (Assignment.is_completed == False)
                )
            except (ValueError, AttributeError):
                pass

        query = query.order_by(Assignment.due_time).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_today_assignments(self, user_id: int) -> List[Assignment]:
        """
        获取今日截止的作业
        
        Args:
            user_id: 用户ID
            
        Returns:
            List[Assignment]: 今日截止作业列表
        """
        today = date.today()
        start = datetime.combine(today, datetime.min.time())
        end = datetime.combine(today, datetime.max.time())
        
        query = (
            select(Assignment)
            .where(Assignment.user_id == user_id)
            .where(Assignment.due_time >= start)
            .where(Assignment.due_time <= end)
            .where(Assignment.is_completed == False)
            .order_by(Assignment.due_time)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_upcoming_assignments(
        self,
        user_id: int,
        days: int = 3,
    ) -> List[Assignment]:
        """
        获取未来 N 天截止的作业
        
        Args:
            user_id: 用户ID
            days: 天数
            
        Returns:
            List[Assignment]: 作业列表
        """
        today = date.today()
        end_date = datetime.combine(today, datetime.max.time())
        end_date = end_date.replace(day=end_date.day + days)
        
        query = (
            select(Assignment)
            .where(Assignment.user_id == user_id)
            .where(Assignment.due_time <= end_date)
            .where(Assignment.is_completed == False)
            .order_by(Assignment.due_time)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def save_assignments(
        self,
        user_id: int,
        assignments_data: List[dict],
        source_id: Optional[int] = None,
    ) -> int:
        """
        保存作业列表（去重处理）
        
        Args:
            user_id: 用户ID
            assignments_data: 作业数据列表
            source_id: 数据源ID
            
        Returns:
            int: 新增作业数量
        """
        if not assignments_data:
            return 0
            
        # 先获取现有作业 remote_id 列表
        existing_query = (
            select(Assignment)
            .where(Assignment.user_id == user_id)
            .where(Assignment.remote_id != None)
        )
        existing_result = await self.db.execute(existing_query)
        existing_map = {a.remote_id: a for a in existing_result.scalars().all() if a.remote_id}

        # 逐个处理作业
        new_count = 0
        updated_count = 0
        for data in assignments_data:
            remote_id = data.get("remote_id")

            if remote_id and remote_id in existing_map:
                existing = existing_map[remote_id]
                new_completed = data.get("is_completed", False)
                if existing.is_completed != new_completed:
                    existing.is_completed = new_completed
                    updated_count += 1
                continue

            # 创建新作业
            assignment = Assignment(
                user_id=user_id,
                source_id=source_id,
                remote_id=remote_id,
                title=data.get("title", ""),
                description=data.get("description"),
                course_name=data.get("course_name"),
                due_time=data.get("due_time"),
                is_completed=data.get("is_completed", False),
            )
            self.db.add(assignment)
            new_count += 1

        if new_count > 0 or updated_count > 0:
            await self.db.commit()

        logger.info(f"📝 保存作业: 新增 {new_count} 条，更新状态 {updated_count} 条")
        return new_count

    async def mark_completed(
        self,
        assignment_id: int,
        user_id: int,
    ) -> bool:
        """
        标记作业为已完成
        
        Args:
            assignment_id: 作业ID
            user_id: 用户ID
            
        Returns:
            bool: 是否成功
        """
        query = (
            select(Assignment)
            .where(Assignment.id == assignment_id)
            .where(Assignment.user_id == user_id)
        )
        result = await self.db.execute(query)
        assignment = result.scalar_one_or_none()
        
        if not assignment:
            return False
            
        assignment.is_completed = True
        await self.db.commit()
        return True

    async def delete_assignment(
        self,
        assignment_id: int,
        user_id: int,
    ) -> bool:
        """
        删除指定作业
        
        Args:
            assignment_id: 作业ID
            user_id: 用户ID
            
        Returns:
            bool: 是否成功
        """
        query = (
            select(Assignment)
            .where(Assignment.id == assignment_id)
            .where(Assignment.user_id == user_id)
        )
        result = await self.db.execute(query)
        assignment = result.scalar_one_or_none()

        if not assignment:
            return False

        await self.db.delete(assignment)
        await self.db.commit()
        return True

    async def delete_old_completed_assignments(self, user_id: int, days: int = 30) -> int:
        """
        删除已完成且超过指定天数的作业
        
        Args:
            user_id: 用户ID
            days: 保留天数
            
        Returns:
            int: 删除数量
        """
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        
        query = (
            delete(Assignment)
            .where(Assignment.user_id == user_id)
            .where(Assignment.is_completed == True)
            .where(Assignment.created_at < cutoff)
        )
        result = await self.db.execute(query)
        await self.db.commit()
        return result.rowcount
