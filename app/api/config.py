from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.config import settings
import json

router = APIRouter(prefix="/api/config", tags=["配置"])


class ConfigResponse(BaseModel):
    student_id: str
    term_start_date: str
    bark_key: str
    deploy_mode: str


class ConfigUpdate(BaseModel):
    student_id: str = None
    term_start_date: str = None
    bark_key: str = None


@router.get("", response_model=ConfigResponse)
async def get_config():
    """获取系统配置"""
    return {
        "student_id": settings.student_id,
        "term_start_date": settings.term_start_date,
        "bark_key": settings.bark_key,
        "deploy_mode": settings.deploy_mode,
    }


@router.put("")
async def update_config(config: ConfigUpdate):
    """更新系统配置"""
    try:
        with open(".env", "r", encoding="utf-8") as f:
            content = f.read()
        
        if config.student_id is not None:
            content = content.replace(
                f"STUDENT_ID={settings.student_id}",
                f"STUDENT_ID={config.student_id}"
            )
        
        if config.term_start_date is not None:
            content = content.replace(
                f"TERM_START_DATE={settings.term_start_date}",
                f"TERM_START_DATE={config.term_start_date}"
            )
        
        if config.bark_key is not None:
            content = content.replace(
                f"BARK_KEY={settings.bark_key}",
                f"BARK_KEY={config.bark_key}"
            )
        
        with open(".env", "w", encoding="utf-8") as f:
            f.write(content)
        
        return {"message": "配置更新成功", "config": config.dict(exclude_none=True)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")


@router.get("/scheduler")
async def get_scheduler_status():
    """获取定时任务状态"""
    from app.main import scheduler
    
    jobs = []
    if scheduler.scheduler:
        for job in scheduler.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "trigger": str(job.trigger),
                "next_run_time": str(job.next_run_time) if job.next_run_time else None,
                "enabled": job.enabled,
            })
    
    return {"jobs": jobs}
