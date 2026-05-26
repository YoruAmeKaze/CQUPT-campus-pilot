from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.services.config_store import ConfigStoreService
from app.notifications.bark_notifier import BarkNotifier
from app.notifications.feishu_notifier import FeishuNotifier

router = APIRouter(prefix="/api/notification", tags=["通知"])


class TestNotificationRequest(BaseModel):
    message: str
    title: str = None


async def _get_feishu_url(db: AsyncSession = None) -> str:
    """获取飞书 Webhook URL，优先 settings，其次数据库"""
    if settings.feishu_webhook_url:
        return settings.feishu_webhook_url
    if db:
        store = ConfigStoreService(db, settings.fernet_key)
        return await store.get("feishu_webhook_url", "")
    return ""


@router.post("/test")
async def test_notification(request: TestNotificationRequest):
    """测试 Bark 推送通知"""
    try:
        notifier = BarkNotifier()
        result = await notifier.send(
            message=request.message,
            title=request.title or "CampusPilot 测试",
        )

        if result:
            return {"success": True, "message": "Bark 推送测试成功"}
        else:
            raise HTTPException(status_code=500, detail="Bark 推送失败，请检查 Bark Key 配置")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bark 推送测试失败: {str(e)}")


@router.post("/feishu/test")
async def test_feishu_notification(db: AsyncSession = Depends(get_db)):
    """测试飞书推送通知"""
    try:
        feishu_url = await _get_feishu_url(db)
        if not feishu_url:
            raise HTTPException(status_code=500, detail="未配置飞书 Webhook URL")

        notifier = FeishuNotifier(webhook_url=feishu_url)
        result = await notifier.send_test()

        if result:
            return {"success": True, "message": "飞书推送测试成功"}
        else:
            raise HTTPException(status_code=500, detail="飞书推送失败，请检查 Webhook URL 配置")

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"飞书推送测试失败: {str(e)}")


@router.get("/status")
async def get_notification_status(db: AsyncSession = Depends(get_db)):
    """获取通知服务状态"""
    feishu_url = await _get_feishu_url(db)
    return {
        "bark_configured": bool(settings.bark_key),
        "feishu_configured": bool(feishu_url),
        "message": "通知服务运行正常",
    }