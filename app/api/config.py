from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.config_store import ConfigStoreService
from app.config import settings

router = APIRouter(prefix="/api/config", tags=["配置"])


class ConfigResponse(BaseModel):
    student_id: str
    term_start_date: str
    bark_key: str
    deploy_mode: str


class ConfigUpdate(BaseModel):
    term_start_date: str = None
    bark_key: str = None


def _get_store(db: AsyncSession) -> ConfigStoreService:
    return ConfigStoreService(db, settings.fernet_key)


@router.get("", response_model=ConfigResponse)
async def get_config(db: AsyncSession = Depends(get_db)):
    """获取系统配置（从数据库读取）"""
    store = _get_store(db)
    return {
        "student_id": settings.student_id,
        "term_start_date": await store.get("term_start_date", settings.term_start_date),
        "bark_key": await store.get("bark_key", settings.bark_key),
        "deploy_mode": settings.deploy_mode,
    }


@router.put("")
async def update_config(config: ConfigUpdate, db: AsyncSession = Depends(get_db)):
    """更新系统配置（写入数据库）"""
    store = _get_store(db)
    try:
        if config.term_start_date is not None:
            await store.set("term_start_date", config.term_start_date, "学期开始日期")
        if config.bark_key is not None:
            await store.set("bark_key", config.bark_key, "Bark iOS 推送 Key")
        return {"message": "配置更新成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")


@router.get("/scheduler")
async def get_scheduler_status():
    """获取定时任务状态"""
    from app.main import scheduler

    jobs = []
    if scheduler and scheduler.scheduler:
        for job in scheduler.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "trigger": str(job.trigger),
                "next_run_time": str(job.next_run_time) if job.next_run_time else None,
                "enabled": job.enabled,
            })
    return {"jobs": jobs}
