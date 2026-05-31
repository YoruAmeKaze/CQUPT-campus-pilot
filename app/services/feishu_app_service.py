"""
飞书应用（App）服务

支持双向对话：
1. 接收飞书事件回调（消息事件）
2. 获取 tenant_access_token
3. 通过飞书 API 发送消息回复
"""

import json
import logging
from typing import Optional, Dict, Any

import httpx

from app.config import settings
from app.llm.client import chat_completion

logger = logging.getLogger(__name__)

FEISHU_API_BASE = "https://open.feishu.cn/open-apis"


class FeishuAppService:
    """飞书应用服务"""

    def __init__(self, app_id: str = None, app_secret: str = None):
        self.app_id = app_id or settings.feishu_app_id
        self.app_secret = app_secret or settings.feishu_app_secret
        self._tenant_access_token: Optional[str] = None
        self._token_expires_at: int = 0

    @property
    def is_configured(self) -> bool:
        """检查飞书应用是否已配置"""
        return bool(self.app_id and self.app_secret)

    async def _get_tenant_access_token(self) -> Optional[str]:
        """
        获取 tenant_access_token

        飞书 API: POST /open-apis/auth/v3/tenant_access_token/internal
        """
        if not self.is_configured:
            logger.warning("飞书应用未配置（缺少 App ID 或 App Secret）")
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal",
                    json={
                        "app_id": self.app_id,
                        "app_secret": self.app_secret,
                    },
                )

                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == 0:
                        token = data.get("tenant_access_token")
                        expire = data.get("expire", 7200)
                        logger.info(f"获取 tenant_access_token 成功（有效期 {expire}s）")
                        return token
                    else:
                        logger.error(f"获取 token 失败: {data.get('msg')}")
                        return None
                else:
                    logger.error(f"获取 token HTTP 错误: {resp.status_code}")
                    return None

        except Exception as e:
            logger.error(f"获取 tenant_access_token 异常: {e}")
            return None

    async def _ensure_token(self) -> Optional[str]:
        """确保 token 有效，必要时刷新（token 有效期 2 小时）"""
        import time
        now = int(time.time())
        if not self._tenant_access_token or now >= self._token_expires_at:
            self._tenant_access_token = await self._get_tenant_access_token()
            if self._tenant_access_token:
                self._token_expires_at = now + 7000  # 提前 200s 刷新
        return self._tenant_access_token

    async def send_message(
        self,
        chat_id: str,
        text: str,
        msg_type: str = "text",
    ) -> bool:
        """
        发送消息到飞书会话

        API: POST /open-apis/im/v1/messages
        """
        token = await self._ensure_token()
        if not token:
            logger.warning("无法获取 token，跳过消息发送")
            return False

        content = json.dumps({"text": text}) if msg_type == "text" else text

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{FEISHU_API_BASE}/im/v1/messages",
                    params={"receive_id_type": "chat_id"},
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "receive_id": chat_id,
                        "msg_type": msg_type,
                        "content": content,
                    },
                )

                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == 0:
                        logger.info(f"飞书消息发送成功: {chat_id}")
                        return True
                    else:
                        logger.error(f"飞书消息发送失败: {data.get('msg')}")
                        # token 过期，清除重试
                        if data.get("code") == 99991663:
                            self._tenant_access_token = None
                        return False
                else:
                    logger.error(f"飞书消息发送 HTTP 错误: {resp.status_code}")
                    return False

        except Exception as e:
            logger.error(f"飞书消息发送异常: {e}")
            return False

    async def send_text_reply(
        self, chat_id: str, user_message: str, db=None
    ) -> bool:
        """
        处理用户消息并通过 AI 回复

        先判断是否为数据查询，是则使用 Text-to-SQL，否则正常聊天

        Args:
            chat_id: 飞书会话 ID
            user_message: 用户消息
            db: 数据库会话（可选），有则支持查询，无则纯对话
        """
        logger.info(f"🤖 AI 处理消息: chat_id={chat_id}, 内容={user_message[:50]}")

        if db:
            from app.llm.client import chat_or_reply
            ai_reply = await chat_or_reply(
                user_message=user_message,
                db=db,
                session_id=chat_id,
            )
        else:
            from app.llm.client import chat_completion
            ai_reply = await chat_completion(
                messages=[{"role": "user", "content": user_message}],
            )

        return await self.send_message(chat_id, ai_reply)

    async def verify_url(self) -> Dict[str, Any]:
        """
        验证飞书事件回调 URL

        飞书在配置事件订阅时会发送 challenge 验证
        """
        return {}

    @staticmethod
    def parse_event_body(body: dict) -> Optional[Dict[str, Any]]:
        """
        解析飞书事件回调 body

        飞书 v2.0 事件结构：
        {
            "schema": "2.0",
            "header": {"event_id": "...", "event_type": "im.message.receive_v1", ...},
            "event": {
                "sender": {...},
                "message": {"chat_id": "...", "message_type": "text", "content": "{...}", ...}
            }
        }

        返回消息事件的关键信息
        """
        try:
            # 处理 URL 验证挑战
            if "challenge" in body:
                return {"type": "url_verify", "challenge": body["challenge"]}

            # 飞书 v2.0: event_type 在 header 中
            header = body.get("header", {})
            event_type = header.get("event_type", "")
            event = body.get("event", {})

            # im.message.receive_v1 - 收到消息事件
            if event_type == "im.message.receive_v1":
                message = event.get("message", {})
                sender = event.get("sender", {})

                chat_type = message.get("chat_type", "")
                msg_type = message.get("message_type", "")
                content_raw = message.get("content", "{}")

                content = json.loads(content_raw) if isinstance(content_raw, str) else content_raw
                text = content.get("text", "") if isinstance(content, dict) else str(content)

                # @机器人消息格式: "@机器人名 内容"，提取实际内容
                import re
                text = re.sub(r"^@[\u4e00-\u9fa5\w]+\s*", "", text).strip()

                chat_id = message.get("chat_id", "")

                logger.info(f"解析消息事件: type={chat_type}, chat_id={chat_id[:20]}, text={text[:50]}")

                return {
                    "type": "message",
                    "chat_id": chat_id,
                    "chat_type": chat_type,
                    "sender_id": sender.get("sender_id", {}).get("open_id", ""),
                    "text": text,
                    "message_id": message.get("message_id", ""),
                }

            if event_type:
                logger.info(f"忽略未处理的事件类型: {event_type}")
            else:
                logger.debug(f"收到未知事件结构: {str(body)[:200]}")

            return {"type": "unknown", "event_type": event_type}

        except Exception as e:
            logger.error(f"解析飞书事件失败: {e}", exc_info=True)
            return None
