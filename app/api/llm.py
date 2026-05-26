"""
LLM / AI 对话 API
"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from app.llm.client import simple_chat, check_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/llm", tags=["AI 对话"])


class ChatRequest(BaseModel):
    message: str


@router.post("/chat")
async def chat(request: ChatRequest):
    """与 AI 对话"""
    reply = await simple_chat(request.message)
    return {"reply": reply}


@router.get("/status")
async def llm_status():
    """检查 LLM 服务状态"""
    api_key_valid = await check_api_key()
    return {
        "configured": api_key_valid,
        "message": "AI 服务正常" if api_key_valid else "API Key 未配置或无效",
    }
