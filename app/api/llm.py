"""
LLM / AI 对话 API
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.llm.client import simple_chat, chat_or_reply, check_api_key, chat_with_tools

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/llm", tags=["AI 对话"])


class ChatRequest(BaseModel):
    message: str


@router.post("/chat")
async def chat(request: ChatRequest):
    """与 AI 对话（简单模式）"""
    reply = await simple_chat(request.message)
    return {"reply": reply}


@router.post("/test")
async def test_bot(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """测试机器人回复（完整模拟飞书机器人回复流程）"""
    reply = await chat_or_reply(request.message, db)
    return {"reply": reply}


@router.get("/status")
async def llm_status():
    """检查 LLM 服务状态"""
    api_key_valid = await check_api_key()
    return {
        "configured": api_key_valid,
        "message": "AI 服务正常" if api_key_valid else "API Key 未配置或无效",
    }
