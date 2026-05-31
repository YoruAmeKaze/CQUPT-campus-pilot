import json
import logging
from datetime import datetime, date, timedelta
from typing import List, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Assignment, User, DataSource

logger = logging.getLogger(__name__)

# 截止时间超过此天数的未完成作业视为"过期"，同步时不存入
EXPIRE_DAYS = 60


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
            status: 筛选状态（pending=未完成, completed=已完成, expired=已过期, all=全部）
            limit: 限制数量
            term_start: 学期开始日期（用于过滤上学期已完成的作业）

        Returns:
            List[Assignment]: 作业列表
        """
        query = select(Assignment).where(Assignment.user_id == user_id)

        if status == "pending":
            cutoff = datetime.now() - timedelta(days=EXPIRE_DAYS)
            query = query.where(Assignment.is_completed == False)
            query = query.where((Assignment.due_time >= cutoff) | (Assignment.due_time == None))
        elif status == "completed":
            query = query.where(Assignment.is_completed == True)
        elif status == "expired":
            cutoff = datetime.now() - timedelta(days=EXPIRE_DAYS)
            query = query.where(Assignment.is_completed == False)
            query = query.where(Assignment.due_time < cutoff)

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

    async def get_assignments_with_expired(
        self,
        user_id: int,
        limit: int = 100,
    ) -> dict:
        """
        获取作业列表，同时返回待完成和已过期的作业

        Returns:
            dict: { pending: [...], expired: [...], completed: [...] }
        """
        now = datetime.now()
        expire_cutoff = now - timedelta(days=EXPIRE_DAYS)

        # 待完成（未过期）
        pending_query = (
            select(Assignment)
            .where(Assignment.user_id == user_id)
            .where(Assignment.is_completed == False)
            .where((Assignment.due_time >= expire_cutoff) | (Assignment.due_time == None))
            .order_by(Assignment.due_time)
            .limit(limit)
        )
        pending_result = await self.db.execute(pending_query)
        pending = list(pending_result.scalars().all())

        # 已过期（未完成但截止时间过早）
        expired_query = (
            select(Assignment)
            .where(Assignment.user_id == user_id)
            .where(Assignment.is_completed == False)
            .where(Assignment.due_time < expire_cutoff)
            .order_by(Assignment.due_time.desc())
            .limit(limit)
        )
        expired_result = await self.db.execute(expired_query)
        expired = list(expired_result.scalars().all())

        # 已完成
        completed_query = (
            select(Assignment)
            .where(Assignment.user_id == user_id)
            .where(Assignment.is_completed == True)
            .order_by(Assignment.due_time.desc())
            .limit(limit)
        )
        completed_result = await self.db.execute(completed_query)
        completed = list(completed_result.scalars().all())

        return {
            "pending": pending,
            "expired": expired,
            "completed": completed,
        }

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
        获取未来 N 天截止的作业（自动过滤已过期的）
        
        Args:
            user_id: 用户ID
            days: 天数
            
        Returns:
            List[Assignment]: 作业列表（不含已过期超过 EXPIRE_DAYS 的）
        """
        today = date.today()
        end_date = datetime.combine(today, datetime.max.time())
        end_date = end_date.replace(day=end_date.day + days)
        
        expire_cutoff = datetime.now() - timedelta(days=EXPIRE_DAYS)
        
        query = (
            select(Assignment)
            .where(Assignment.user_id == user_id)
            .where(Assignment.due_time <= end_date)
            .where(Assignment.is_completed == False)
            # 过滤已过期的：截止时间不能太早
            .where((Assignment.due_time >= expire_cutoff) | (Assignment.due_time == None))
            .order_by(Assignment.due_time)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def save_assignments(
        self,
        user_id: int,
        assignments_data: List[dict],
        source_id: Optional[int] = None,
    ) -> dict:
        """
        保存作业列表（双重去重 + 过期过滤）

        去重策略（两层）：
          1. remote_id 精确匹配：同一平台ID不重复创建
          2. 内容级去重：(title + course_name + source_id) 相同则视为同一条作业，
             保留数据库中已有的那条，跳过新数据

        过期规则：截止时间超过 EXPIRE_DAYS 天前且未完成的作业不再存入新记录。

        Args:
            user_id: 用户ID
            assignments_data: 作业数据列表
            source_id: 数据源ID
            
        Returns:
            dict: { new: int, updated: int, skipped_expired: int, skipped_duplicate: int }
        """
        if not assignments_data:
            return {"new": 0, "updated": 0, "skipped_expired": 0, "skipped_duplicate": 0}
            
        expire_cutoff = datetime.now() - timedelta(days=EXPIRE_DAYS)

        # 第一层：获取现有作业 remote_id 映射
        existing_query = (
            select(Assignment)
            .where(Assignment.user_id == user_id)
            .where(Assignment.remote_id != None)
        )
        existing_result = await self.db.execute(existing_query)
        existing_by_remote = {a.remote_id: a for a in existing_result.scalars().all() if a.remote_id}

        # 第二层：获取现有作业的内容指纹映射（用于内容级去重）
        content_query = (
            select(Assignment)
            .where(Assignment.user_id == user_id)
            .where(Assignment.source_id == source_id)
        )
        content_result = await self.db.execute(content_query)
        # key: (normalized_title, normalized_course_name) -> Assignment
        content_map: dict[tuple[str, str], Assignment] = {}
        for a in content_result.scalars().all():
            key = (a.title.strip().lower(), (a.course_name or "").strip().lower())
            content_map[key] = a

        # 逐个处理作业
        new_count = 0
        updated_count = 0
        skipped_expired = 0
        skipped_duplicate = 0
        for data in assignments_data:
            remote_id = data.get("remote_id")

            # ── 第一层：remote_id 匹配 ──
            if remote_id and remote_id in existing_by_remote:
                existing = existing_by_remote[remote_id]
                new_completed = data.get("is_completed", False)
                if existing.is_completed != new_completed:
                    existing.is_completed = new_completed
                    updated_count += 1
                continue

            # ── 第二层：内容级去重 ──
            title = (data.get("title") or "").strip().lower()
            course = (data.get("course_name") or "").strip().lower()
            content_key = (title, course)

            if content_key[0] and content_key in content_map:
                # 已有相同标题+课程的作业，更新其状态和截止时间
                existing = content_map[content_key]
                new_completed = data.get("is_completed", False)
                new_due_time = data.get("due_time")
                changed = False
                if existing.is_completed != new_completed:
                    existing.is_completed = new_completed
                    changed = True
                if new_due_time and existing.due_time != new_due_time:
                    existing.due_time = new_due_time
                    changed = True
                if changed:
                    updated_count += 1
                skipped_duplicate += 1
                continue

            # ── 新作业：检查过期 ──
            due_time = data.get("due_time")
            is_completed = data.get("is_completed", False)
            
            if not is_completed and due_time:
                try:
                    due_dt = due_time if isinstance(due_time, datetime) else datetime.fromisoformat(str(due_time).replace("Z", "+00:00"))
                    if due_dt.tzinfo:
                        due_dt = due_dt.replace(tzinfo=None)
                    if due_dt < expire_cutoff:
                        skipped_expired += 1
                        continue
                except (ValueError, TypeError):
                    pass

            # 创建新作业
            assignment = Assignment(
                user_id=user_id,
                source_id=source_id,
                remote_id=remote_id,
                title=data.get("title", ""),
                description=data.get("description"),
                course_name=data.get("course_name"),
                due_time=due_time,
                is_completed=is_completed,
            )
            self.db.add(assignment)
            new_count += 1

            # 加入内容去重集合，防止本次批量内自重复
            content_map[content_key] = assignment

        if new_count > 0 or updated_count > 0:
            await self.db.commit()

        logger.info(
            f"📝 保存作业: 新增 {new_count} 条，更新状态 {updated_count} 条，"
            f"跳过过期 {skipped_expired} 条，跳过重复 {skipped_duplicate} 条"
        )
        return {
            "new": new_count,
            "updated": updated_count,
            "skipped_expired": skipped_expired,
            "skipped_duplicate": skipped_duplicate,
        }

    async def mark_completed(
        self,
        assignment_id: int,
        user_id: int,
    ) -> bool:
        """标记作业为已完成"""
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
        """删除指定作业"""
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

    async def cleanup_expired_assignments(self, user_id: int) -> int:
        """
        清理已过期的未完成作业（用户手动触发）
        
        删除截止时间超过 EXPIRE_DAYS*2 天前且仍未完成的作业
        
        Returns:
            int: 删除数量
        """
        cutoff = datetime.now() - timedelta(days=EXPIRE_DAYS * 2)
        
        query = (
            delete(Assignment)
            .where(Assignment.user_id == user_id)
            .where(Assignment.is_completed == False)
            .where(Assignment.due_time < cutoff)
        )
        result = await self.db.execute(query)
        await self.db.commit()
        deleted = result.rowcount
        logger.info(f"🧹 清理过期作业: 删除 {deleted} 条")
        return deleted

    async def delete_old_completed_assignments(self, user_id: int, days: int = 30) -> int:
        """删除已完成且超过指定天数的作业"""
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