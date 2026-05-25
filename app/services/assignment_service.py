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
        limit: int = 50,
    ) -> List[Assignment]:
        """
        获取用户的作业列表
        
        Args:
            user_id: 用户ID
            status: 筛选状态（pending=未完成, completed=已完成, all=全部）
            limit: 限制数量
            
        Returns:
            List[Assignment]: 作业列表
        """
        query = select(Assignment).where(Assignment.user_id == user_id)
        
        if status == "pending":
            query = query.where(Assignment.is_completed == False)
        elif status == "completed":
            query = query.where(Assignment.is_completed == True)
        
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
            select(Assignment.remote_id)
            .where(Assignment.user_id == user_id)
            .where(Assignment.remote_id != None)
        )
        existing_result = await self.db.execute(existing_query)
        existing_ids = {id[0] for id in existing_result.all() if id[0]}
        
        # 逐个处理作业
        new_count = 0
        for data in assignments_data:
            remote_id = data.get("remote_id")
            
            # 如果有 remote_id 且已存在，则跳过
            if remote_id and remote_id in existing_ids:
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
            
        if new_count > 0:
            await self.db.commit()
            
        logger.info(f"📝 保存作业: 新增 {new_count} 条")
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

    async def delete_old_completed_assignments(self, user_id: int, days: int = 30) -> int:
        """
        删除已完成且超过指定天数的作业
        
        Args:
            user_id: 用户ID
            days: 保留天数
            
        Returns:
            int: 删除数量
        """
        cutoff = datetime.now()
        cutoff = cutoff.replace(day=cutoff.day - days)
        
        query = (
            delete(Assignment)
            .where(Assignment.user_id == user_id)
            .where(Assignment.is_completed == True)
            .where(Assignment.created_at < cutoff)
        )
        result = await self.db.execute(query)
        await self.db.commit()
        return result.rowcount
