"""
飞书应用事件回调 API

接收飞书应用的事件推送：
- URL 验证挑战（challenge）
- 消息事件（用户 @机器人）

包含消息去重机制，防止同一消息被多次处理
"""

import json
import logging
import time

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.feishu_app_service import FeishuAppService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/feishu/app", tags=["飞书应用"])

feishu_app = FeishuAppService()

# 已处理消息缓存（去重）
# key: message_id, value: timestamp
_processed_messages: dict = {}
_DEDUP_TTL = 30  # 30秒内同一消息ID不再处理


def _is_duplicate(message_id: str) -> bool:
    """检查消息是否已处理过（去重）"""
    now = time.time()
    # 清理过期记录
    expired = [mid for mid, ts in _processed_messages.items() if now - ts > _DEDUP_TTL]
    for mid in expired:
        _processed_messages.pop(mid, None)

    if message_id in _processed_messages:
        logger.warning(f"⏭️ 跳过重复消息: {message_id[:20]}...")
        return True

    _processed_messages[message_id] = now
    return False


@router.post("/event")
async def receive_event(request: Request, db: AsyncSession = Depends(get_db)):
    """
    接收飞书事件回调

    飞书在以下情况会 POST 到此端点：
    1. 配置事件订阅时的 URL 验证
    2. 用户 @机器人 或私聊机器人时的消息事件
    """
    body = await request.json()
    logger.debug(f"收到飞书事件: {json.dumps(body, ensure_ascii=False)[:200]}")

    parsed = FeishuAppService.parse_event_body(body)

    if not parsed:
        return JSONResponse(content={"code": -1, "msg": "解析失败"}, status_code=400)

    if parsed["type"] == "url_verify":
        challenge = parsed["challenge"]
        logger.info("飞书事件回调 URL 验证成功")
        return JSONResponse(content={"challenge": challenge})

    if parsed["type"] == "message":
        chat_id = parsed.get("chat_id", "")
        text = parsed.get("text", "")
        chat_type = parsed.get("chat_type", "")
        message_id = parsed.get("message_id", "")

        logger.info(f"收到飞书消息: 类型={chat_type}, chat_id={chat_id[:20]}..., 内容={text[:50]}")

        if not feishu_app.is_configured:
            logger.warning("飞书应用未配置，无法回复")
            return JSONResponse(content={"code": 0, "msg": "ok"})

        # 去重检查
        if message_id and _is_duplicate(message_id):
            return JSONResponse(content={"code": 0, "msg": "ok"})

        await feishu_app.send_text_reply(chat_id, text, db=db)

        return JSONResponse(content={"code": 0, "msg": "ok"})

    return JSONResponse(content={"code": 0, "msg": "ok"})


@router.get("/status")
async def get_feishu_app_status():
    """获取飞书应用配置状态"""
    return {
        "configured": feishu_app.is_configured,
        "has_app_id": bool(feishu_app.app_id),
        "has_app_secret": bool(feishu_app.app_secret),
        "message": "已配置" if feishu_app.is_configured else "未配置飞书应用",
    }


@router.post("/test")
async def test_app():
    """测试飞书应用功能（检查 token 获取）"""
    if not feishu_app.is_configured:
        raise HTTPException(status_code=400, detail="飞书应用未配置")

    token = await feishu_app._get_tenant_access_token()
    if token:
        return {"success": True, "message": "飞书应用配置正确，token 获取成功"}
    else:
        raise HTTPException(status_code=500, detail="获取飞书 token 失败，请检查 App ID 和 App Secret")
