"""
飞书 Bot 通知服务

使用飞书群机器人 Webhook 发送通知
配置方式：在飞书群中添加自定义机器人，获取 Webhook URL

飞书 Webhook API：
- 文本消息：POST {webhook_url} { "msg_type": "text", "content": { "text": "..." } }
- 富文本消息：POST {webhook_url} { "msg_type": "post", "content": { "post": { "zh_cn": { "content": [...] } } } }
"""

import httpx
import logging
from typing import Optional, List, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)


class FeishuNotifier:
    """飞书群机器人通知服务"""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.feishu_webhook_url

    async def _send(self, payload: dict) -> bool:
        """发送消息到飞书 Webhook"""
        if not self.webhook_url:
            logger.warning("未配置飞书 Webhook URL，跳过推送")
            return False

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self.webhook_url, json=payload)

                if resp.status_code == 200:
                    result = resp.json()
                    if result.get("code") == 0:
                        logger.info("飞书推送成功")
                        return True
                    else:
                        logger.error(f"飞书推送失败: {result.get('msg', '未知错误')}")
                        return False
                else:
                    logger.error(f"飞书 API 请求失败: HTTP {resp.status_code} {resp.text[:200]}")
                    return False

        except Exception as e:
            logger.error(f"飞书推送异常: {e}")
            return False

    async def send_text(self, text: str) -> bool:
        """发送纯文本消息"""
        payload = {
            "msg_type": "text",
            "content": {"text": text},
        }
        return await self._send(payload)

    async def send_post(self, title: str, content: List[List[Dict[str, Any]]]) -> bool:
        """发送富文本消息"""
        payload = {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": title,
                        "content": content,
                    }
                }
            },
        }
        return await self._send(payload)

    @staticmethod
    def text_tag(text: str, bold: bool = False) -> Dict[str, Any]:
        """创建文本标签"""
        if bold:
            return {"tag": "text", "text": f"【{text}】"}
        return {"tag": "text", "text": text}

    @staticmethod
    def link_tag(text: str, url: str) -> Dict[str, Any]:
        """创建链接标签"""
        return {"tag": "a", "text": text, "href": url}

    @staticmethod
    def at_tag(user_id: str = "all") -> Dict[str, Any]:
        """创建 @ 标签"""
        return {"tag": "at", "user_id": user_id}

    async def send_schedule_reminder(self, courses: List[dict]) -> bool:
        """发送每日课表提醒"""
        if not courses:
            return await self.send_text("📅 今日无课，好好休息")

        from datetime import date
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        today_weekday = date.today().weekday()

        content = []
        content.append([self.text_tag(f"📅 {weekday_names[today_weekday]}课表（共{len(courses)}节）", bold=True)])
        content.append([self.text_tag("")])

        for i, course in enumerate(courses, 1):
            name = course.get("name", "未知课程")
            time = course.get("start_time", "")
            end = course.get("end_time", "")
            loc = course.get("location", "")
            line = f"{i}. {name}  {time}-{end}  📍{loc}"
            content.append([self.text_tag(line)])

        return await self.send_post("CampusPilot 每日课表", content)

    async def send_assignment_reminder(
        self, course_name: str, title: str, due_time: str, hours_left: int
    ) -> bool:
        """发送作业截止提醒"""
        if hours_left <= 1:
            emoji = "🚨"
            text = f"{emoji} 【{course_name}】{title}\n截止：{due_time}\n⚠️ 即将截止！"
        elif hours_left <= 24:
            text = f"⏰ 【{course_name}】{title}\n截止：{due_time}\n还剩 {hours_left} 小时"
        else:
            text = f"📝 【{course_name}】{title}\n截止：{due_time}\n还剩 {hours_left} 小时"

        return await self.send_text(text)

    async def send_new_assignment(self, course_name: str, title: str, due_time: str) -> bool:
        """发送新作业通知"""
        text = f"✨ 【{course_name}】{title}\n截止时间：{due_time}"
        return await self.send_text(text)

    async def send_daily_summary(
        self,
        course_count: int,
        pending_assignments: int,
        upcoming_assignments: List[Dict],
    ) -> bool:
        """发送每日学习摘要"""
        content = []

        content.append([self.text_tag("📊 今日学习摘要", bold=True)])
        content.append([self.text_tag(f"📚 今日课程：{course_count} 节")])
        content.append([self.text_tag(f"📝 待完成作业：{pending_assignments} 个")])

        if upcoming_assignments:
            content.append([self.text_tag("")])
            content.append([self.text_tag("⏰ 近期截止：", bold=True)])
            for a in upcoming_assignments[:5]:
                time_str = a.get("due_time", "")[:10]
                title = a.get("title", "")
                course = a.get("course_name", "")
                content.append([self.text_tag(f"  · {title} ({course}) - {time_str}")])

        if pending_assignments > 0:
            content.append([self.text_tag("")])
            content.append([self.text_tag(f"💪 加油，还有 {pending_assignments} 个作业等着你！")])

        return await self.send_post("每日摘要", content)

    async def send_test(self) -> bool:
        """发送测试消息"""
        return await self.send_text("✅ CampusPilot 飞书机器人连接成功！\n通知推送功能正常 🎉")
