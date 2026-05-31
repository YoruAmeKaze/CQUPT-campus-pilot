"""
短期对话记忆（内存缓存）

保留最近 N 轮对话历史，用于多轮上下文理解。
每轮 = (用户消息, 机器人回复)
超过最大轮数或 TTL 后自动丢弃。
"""

import logging
import time
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class ConversationMemory:
    """短期对话记忆（进程内内存缓存）"""

    def __init__(self, max_rounds: int = 3, ttl: int = 600):
        self.max_rounds = max_rounds
        self.ttl = ttl
        self._store: Dict[str, list] = {}

    def add(self, session_id: str, user_message: str, bot_reply: str):
        """记录一轮对话"""
        now = time.time()
        if session_id not in self._store:
            self._store[session_id] = []
        self._store[session_id].append((now, user_message, bot_reply))
        self._store[session_id] = self._store[session_id][-self.max_rounds:]
        logger.debug(f"记忆已更新 [{session_id}] ({len(self._store[session_id])}/{self.max_rounds}轮)")

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """获取历史对话消息列表，按时间顺序排列，用于注入 LLM 上下文"""
        self._cleanup()
        pairs = self._store.get(session_id, [])
        messages = []
        for _, user_msg, bot_reply in pairs:
            messages.append({"role": "user", "content": user_msg})
            messages.append({"role": "assistant", "content": bot_reply})
        return messages

    def clear(self, session_id: str):
        """清除指定会话的记忆"""
        self._store.pop(session_id, None)
        logger.info(f"记忆已清除 [{session_id}]")

    def _cleanup(self):
        """清理过期会话"""
        now = time.time()
        expired = [
            sid for sid, entries in self._store.items()
            if entries and now - entries[-1][0] > self.ttl
        ]
        for sid in expired:
            del self._store[sid]
            logger.debug(f"记忆已过期 [{sid}]")


memory = ConversationMemory(max_rounds=3)
