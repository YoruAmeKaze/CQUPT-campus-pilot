from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.notifications.bark_notifier import BarkNotifier

router = APIRouter(prefix="/api/notification", tags=["通知"])


class TestNotificationRequest(BaseModel):
    message: str
    title: str = None


@router.post("/test")
async def test_notification(request: TestNotificationRequest):
    """测试推送通知"""
    try:
        notifier = BarkNotifier()
        result = await notifier.send(
            message=request.message,
            title=request.title or "CampusPilot 测试",
        )
        
        if result:
            return {"success": True, "message": "推送测试成功"}
        else:
            raise HTTPException(status_code=500, detail="推送失败，请检查 Bark Key 配置")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"推送测试失败: {str(e)}")


@router.get("/status")
async def get_notification_status():
    """获取通知服务状态"""
    from app.config import settings
    
    return {
        "bark_configured": bool(settings.bark_key),
        "message": "Bark 推送服务已就绪" if settings.bark_key else "Bark 推送服务未配置",
    }
