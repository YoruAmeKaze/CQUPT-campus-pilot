"""
定时任务调度器
使用 APScheduler 实现定时任务
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class TaskScheduler:
    """定时任务调度器"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        self._registered_tasks = []

    def add_daily_task(
        self,
        func,
        hour: int = 8,
        minute: int = 0,
        name: Optional[str] = None,
        **kwargs
    ):
        """
        添加每日定时任务

        Args:
            func: 任务函数（必须是 async 函数）
            hour: 小时（0-23）
            minute: 分钟（0-59）
            name: 任务名称
            **kwargs: 传递给任务函数的参数
        """
        trigger = CronTrigger(hour=hour, minute=minute)
        task_name = name or func.__name__
        
        self.scheduler.add_job(
            func,
            trigger=trigger,
            id=task_name,
            name=task_name,
            kwargs=kwargs,
            replace_existing=True
        )
        
        self._registered_tasks.append({
            "name": task_name,
            "type": "daily",
            "time": f"{hour:02d}:{minute:02d}"
        })
        
        logger.info(f"✅ 已注册每日任务: {task_name} ({hour:02d}:{minute:02d})")

    def add_hourly_task(
        self,
        func,
        minute: int = 0,
        name: Optional[str] = None,
        **kwargs
    ):
        """
        添加每小时定时任务

        Args:
            func: 任务函数（必须是 async 函数）
            minute: 分钟（0-59）
            name: 任务名称
            **kwargs: 传递给任务函数的参数
        """
        trigger = CronTrigger(minute=minute)
        task_name = name or func.__name__
        
        self.scheduler.add_job(
            func,
            trigger=trigger,
            id=task_name,
            name=task_name,
            kwargs=kwargs,
            replace_existing=True
        )
        
        self._registered_tasks.append({
            "name": task_name,
            "type": "hourly",
            "minute": minute
        })
        
        logger.info(f"✅ 已注册每小时任务: {task_name} (:{minute:02d})")

    def add_interval_task(
        self,
        func,
        minutes: int = 60,
        name: Optional[str] = None,
        **kwargs
    ):
        """
        添加间隔执行任务

        Args:
            func: 任务函数（必须是 async 函数）
            minutes: 间隔分钟数
            name: 任务名称
            **kwargs: 传递给任务函数的参数
        """
        task_name = name or func.__name__
        
        self.scheduler.add_job(
            func,
            "interval",
            minutes=minutes,
            id=task_name,
            name=task_name,
            kwargs=kwargs,
            replace_existing=True
        )
        
        self._registered_tasks.append({
            "name": task_name,
            "type": "interval",
            "minutes": minutes
        })
        
        logger.info(f"✅ 已注册间隔任务: {task_name} ({minutes}分钟)")

    def add_custom_cron_task(
        self,
        func,
        cron_expression: str,
        name: Optional[str] = None,
        **kwargs
    ):
        """
        添加自定义 Cron 任务

        Args:
            func: 任务函数（必须是 async 函数）
            cron_expression: Cron 表达式（格式: minute hour day month day_of_week）
            name: 任务名称
            **kwargs: 传递给任务函数的参数
        """
        parts = cron_expression.split()
        if len(parts) != 5:
            raise ValueError("Cron 表达式格式错误，应为: minute hour day month day_of_week")
        
        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4]
        )
        
        task_name = name or func.__name__
        
        self.scheduler.add_job(
            func,
            trigger=trigger,
            id=task_name,
            name=task_name,
            kwargs=kwargs,
            replace_existing=True
        )
        
        self._registered_tasks.append({
            "name": task_name,
            "type": "cron",
            "expression": cron_expression
        })
        
        logger.info(f"✅ 已注册 Cron 任务: {task_name} ({cron_expression})")

    def start(self):
        """启动调度器"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("🚀 定时任务调度器已启动")
            
            # 打印所有已注册的任务
            if self._registered_tasks:
                logger.info("📋 已注册的定时任务:")
                for task in self._registered_tasks:
                    if task["type"] == "daily":
                        logger.info(f"  - {task['name']}: 每日 {task['time']}")
                    elif task["type"] == "hourly":
                        logger.info(f"  - {task['name']}: 每小时 {task['minute']}分")
                    elif task["type"] == "interval":
                        logger.info(f"  - {task['name']}: 每{task['minutes']}分钟")
                    elif task["type"] == "cron":
                        logger.info(f"  - {task['name']}: {task['expression']}")

    def shutdown(self):
        """停止调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("🛑 定时任务调度器已停止")

    @property
    def running(self) -> bool:
        """检查调度器是否正在运行"""
        return self.scheduler.running

    def get_jobs(self):
        """获取所有任务列表"""
        return [
            {
                "id": job.id,
                "name": job.name,
                "trigger": str(job.trigger),
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None
            }
            for job in self.scheduler.get_jobs()
        ]
