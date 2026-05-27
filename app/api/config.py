from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.config_store import ConfigStoreService
from app.config import settings

router = APIRouter(prefix="/api/config", tags=["配置"])


_config_fields = [
    "term_start_date", "bark_key", "feishu_webhook_url",
    "student_id", "chaoxing_username", "chaoxing_password",
    "smartestu_student_id", "smartestu_password",
    "deepseek_api_key", "deepseek_model", "llm_base_url",
    "feishu_app_id", "feishu_app_secret",
    "tunnel_server_host", "tunnel_server_user",
    "tunnel_remote_port", "tunnel_local_port", "tunnel_key_path",
    "vpn_host", "vpn_username", "vpn_password",
    "campus", "enable_lab_query",
]


class ConfigResponse(BaseModel):
    deploy_mode: str
    auto_cleanup_enabled: bool = False
    auto_cleanup_days: int = 30
    term_start_date: str = ""
    bark_key: str = ""
    feishu_webhook_url: str = ""
    student_id: str = ""
    chaoxing_username: str = ""
    chaoxing_password: str = ""
    smartestu_student_id: str = ""
    smartestu_password: str = ""
    deepseek_api_key: str = ""
    deepseek_model: str = ""
    llm_base_url: str = ""
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    tunnel_server_host: str = ""
    tunnel_server_user: str = ""
    tunnel_remote_port: str = ""
    tunnel_local_port: str = ""
    tunnel_key_path: str = ""
    vpn_host: str = ""
    vpn_username: str = ""
    vpn_password: str = ""
    campus: str = "main"
    enable_lab_query: bool = False


class ConfigUpdate(BaseModel):
    deploy_mode: Optional[str] = None
    auto_cleanup_enabled: Optional[bool] = None
    auto_cleanup_days: Optional[int] = None
    term_start_date: Optional[str] = None
    bark_key: Optional[str] = None
    feishu_webhook_url: Optional[str] = None
    student_id: Optional[str] = None
    chaoxing_username: Optional[str] = None
    chaoxing_password: Optional[str] = None
    smartestu_student_id: Optional[str] = None
    smartestu_password: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    deepseek_model: Optional[str] = None
    llm_base_url: Optional[str] = None
    feishu_app_id: Optional[str] = None
    feishu_app_secret: Optional[str] = None
    tunnel_server_host: Optional[str] = None
    tunnel_server_user: Optional[str] = None
    tunnel_remote_port: Optional[str] = None
    tunnel_local_port: Optional[str] = None
    tunnel_key_path: Optional[str] = None
    vpn_host: Optional[str] = None
    vpn_username: Optional[str] = None
    vpn_password: Optional[str] = None
    campus: Optional[str] = None
    enable_lab_query: Optional[bool] = None


def _get_store(db: AsyncSession) -> ConfigStoreService:
    return ConfigStoreService(db, settings.fernet_key)


async def _read_config_value(store: ConfigStoreService, key: str) -> str:
    return await store.get(key, getattr(settings, key, ""))


async def _build_config_response(store: ConfigStoreService) -> dict:
    resp = {
        "deploy_mode": settings.deploy_mode,
    }
    for field in _config_fields:
        resp[field] = await _read_config_value(store, field)
    resp["auto_cleanup_enabled"] = (await store.get("auto_cleanup_enabled", "false")) == "true"
    resp["auto_cleanup_days"] = int(await store.get("auto_cleanup_days", "30"))
    resp["enable_lab_query"] = (await store.get("enable_lab_query", "false")) == "true"
    return resp


@router.get("", response_model=ConfigResponse)
async def get_config(db: AsyncSession = Depends(get_db)):
    """获取系统配置（数据库优先，.env 兜底）"""
    store = _get_store(db)
    return await _build_config_response(store)


@router.put("")
async def update_config(config: ConfigUpdate, db: AsyncSession = Depends(get_db)):
    """更新系统配置（写入数据库 + 更新运行时内存）"""
    store = _get_store(db)
    try:
        update_map = {}
        if config.term_start_date is not None:
            update_map["term_start_date"] = config.term_start_date
        if config.bark_key is not None:
            update_map["bark_key"] = config.bark_key
        if config.feishu_webhook_url is not None:
            update_map["feishu_webhook_url"] = config.feishu_webhook_url
            settings.feishu_webhook_url = config.feishu_webhook_url
        if config.auto_cleanup_enabled is not None:
            update_map["auto_cleanup_enabled"] = "true" if config.auto_cleanup_enabled else "false"
        if config.auto_cleanup_days is not None:
            update_map["auto_cleanup_days"] = str(config.auto_cleanup_days)

        for field in ["student_id", "chaoxing_username", "chaoxing_password",
                       "smartestu_student_id", "smartestu_password",
                       "deepseek_api_key", "deepseek_model", "llm_base_url",
                       "feishu_app_id", "feishu_app_secret",
                       "tunnel_server_host", "tunnel_server_user",
                       "tunnel_remote_port", "tunnel_local_port", "tunnel_key_path",
                       "vpn_host", "vpn_username", "vpn_password",
                       "campus"]:
            val = getattr(config, field, None)
            if val is not None:
                update_map[field] = val

        if config.enable_lab_query is not None:
            update_map["enable_lab_query"] = "true" if config.enable_lab_query else "false"

        for key, value in update_map.items():
            await store.set(key, value, SYSTEM_KEYS_DESC.get(key, ""))
            if hasattr(settings, key):
                setattr(settings, key, value)

        return {"message": "配置更新成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")


SYSTEM_KEYS_DESC = {
    "term_start_date": "学期开始日期",
    "bark_key": "Bark iOS 推送 Key",
    "feishu_webhook_url": "飞书 Webhook URL",
    "auto_cleanup_enabled": "自动清理开关",
    "auto_cleanup_days": "数据保留天数",
    "student_id": "学号",
    "chaoxing_username": "学习通账号",
    "chaoxing_password": "学习通密码",
    "smartestu_student_id": "数你最灵学号",
    "smartestu_password": "数你最灵密码",
    "deepseek_api_key": "DeepSeek API Key",
    "deepseek_model": "DeepSeek 模型",
    "llm_base_url": "LLM API 地址",
    "feishu_app_id": "飞书应用 App ID",
    "feishu_app_secret": "飞书应用 App Secret",
    "tunnel_server_host": "公网服务器地址",
    "tunnel_server_user": "公网服务器用户名",
    "tunnel_remote_port": "远程端口",
    "tunnel_local_port": "本地端口",
    "tunnel_key_path": "SSH 密钥路径",
    "vpn_host": "VPN 地址",
    "vpn_username": "VPN 用户名",
    "vpn_password": "VPN 密码",
    "campus": "校区选择 (main/xiantao)",
    "enable_lab_query": "启用实验室查询",
}


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
