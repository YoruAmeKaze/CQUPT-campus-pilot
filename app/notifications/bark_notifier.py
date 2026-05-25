"""
Bark 推送通知服务
Bark 官网：https://day.app/
Bark API：https://github.com/Finb/Bark

图标说明：
- 可以使用任意图片 URL 作为通知图标
- 推荐尺寸：512x512 像素
- 支持 PNG、JPEG、GIF 格式
"""

import httpx
import logging
from typing import Optional, List
from app.config import settings

logger = logging.getLogger(__name__)


# 默认图标配置
# 使用可爱的机器人图标作为默认，紧急提醒使用带感叹号的机器人图标
DEFAULT_ICONS = {
    "schedule": "https://neeko-copilot.bytedance.net/api/text_to_image?prompt=cute%20blue%20robot%20with%20graduation%20cap%20mascot%20minimalist%20flat%20design&image_size=square",  # 课表图标
    "assignment": "https://neeko-copilot.bytedance.net/api/text_to_image?prompt=cute%20blue%20robot%20with%20graduation%20cap%20mascot%20minimalist%20flat%20design&image_size=square",  # 作业图标
    "todo": "https://neeko-copilot.bytedance.net/api/text_to_image?prompt=cute%20blue%20robot%20with%20graduation%20cap%20mascot%20minimalist%20flat%20design&image_size=square",  # 待办图标
    "urgent": "https://neeko-copilot.bytedance.net/api/text_to_image?prompt=cute%20blue%20robot%20with%20graduation%20cap%20surprised%20expression%20orange%20exclamation%20mark%20alert%20minimalist%20flat%20design&image_size=square",  # 紧急提醒图标（带感叹号的机器人）
    "default": "https://neeko-copilot.bytedance.net/api/text_to_image?prompt=cute%20blue%20robot%20with%20graduation%20cap%20mascot%20minimalist%20flat%20design&image_size=square",  # 默认图标
}


class BarkNotifier:
    """Bark 推送服务"""

    def __init__(self, bark_key: Optional[str] = None, icons: Optional[dict] = None):
        self.bark_key = bark_key or settings.bark_key
        self.api_base = f"https://api.day.app/{self.bark_key}"
        self.icons = {**DEFAULT_ICONS, **(icons or {})}  # 合并默认图标和自定义图标

    async def send(
        self,
        message: str,
        title: Optional[str] = None,
        sound: str = "alarm",
        level: str = "timeSensitive",
        icon: Optional[str] = None,
        **kwargs
    ) -> bool:
        """
        发送 Bark 推送

        Args:
            message: 推送内容（会自动处理换行和 URL 编码）
            title: 推送标题
            sound: 推送声音
            level: 推送级别（active, timeSensitive, passive）
            icon: 推送图标 URL
            **kwargs: 其他 Bark 支持的参数

        Returns:
            bool: 推送是否成功
        """
        if not self.bark_key:
            logger.warning("未配置 Bark Key，跳过推送")
            return False

        try:
            # 处理消息中的换行符，转换为 URL 友好的格式
            # Bark 支持用 -/ 分割多行
            message = message.replace("\n", "-/")

            # 构建 URL
            url = f"{self.api_base}/{message}"

            # 构建查询参数
            params = {}
            if title:
                params["title"] = title
            if sound:
                params["sound"] = sound
            if level:
                params["level"] = level
            if icon:
                params["icon"] = icon

            # 添加其他参数
            for key, value in kwargs.items():
                if value is not None:
                    params[key] = value

            # 发送请求
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10.0)

                if response.status_code == 200:
                    result = response.json()
                    if result.get("code") == 200:
                        logger.info(f"Bark 推送成功：{title or message[:20]}")
                        return True
                    else:
                        logger.error(f"Bark 推送失败：{result.get('message', 'Unknown error')}")
                        return False
                else:
                    logger.error(f"Bark API 请求失败：HTTP {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"Bark 推送异常：{e}")
            return False

    async def send_schedule_reminder(self, courses: List[dict]) -> bool:
        """
        发送每日课表提醒

        Args:
            courses: 课程列表，每门课包含 name, time, location 等信息

        Returns:
            bool: 推送是否成功
        """
        if not courses:
            message = "今天没课，好好休息"
        else:
            lines = ["今日课表"]
            for course in courses:
                name = course.get('name', '未知')[:10]  # 限制课程名长度
                time = course.get('start_time', '')
                loc = course.get('location', '')[:6]  # 限制地点长度
                lines.append(f"{name} {time} {loc}")

            message = " ".join(lines)

        return await self.send(
            message=message,
            title="今日课表",
            sound="notification",
            level="timeSensitive",
            icon=self.icons["schedule"]
        )

    async def send_assignment_reminder(
        self,
        course_name: str,
        title: str,
        due_time: str,
        hours_left: int
    ) -> bool:
        """
        发送作业截止提醒

        Args:
            course_name: 课程名称
            title: 作业标题
            due_time: 截止时间
            hours_left: 剩余小时数

        Returns:
            bool: 推送是否成功
        """
        if hours_left <= 1:
            message = f"🚨 【{course_name}】{title}\n截止时间：{due_time}\n⚠️ 即将截止！"
            icon = self.icons["urgent"]
        elif hours_left <= 24:
            message = f"⏰ 【{course_name}】{title}\n截止时间：{due_time}\n还剩 {hours_left} 小时"
            icon = self.icons["assignment"]
        else:
            message = f"📝 【{course_name}】{title}\n截止时间：{due_time}\n还剩 {hours_left} 小时"
            icon = self.icons["assignment"]

        return await self.send(
            message=message,
            title="⏰ 作业提醒",
            sound="alarm",
            level="timeSensitive",
            icon=icon
        )

    async def send_new_assignment(self, course_name: str, title: str, due_time: str) -> bool:
        """
        发送新作业通知

        Args:
            course_name: 课程名称
            title: 作业标题
            due_time: 截止时间

        Returns:
            bool: 推送是否成功
        """
        message = f"✨ 【{course_name}】{title}\n截止时间：{due_time}"

        return await self.send(
            message=message,
            title="📝 新作业提醒",
            sound="notes",
            level="active",
            icon=self.icons["assignment"]
        )

    async def send_todo_reminder(self, title: str, due_time: Optional[str] = None) -> bool:
        """
        发送待办事项提醒

        Args:
            title: 待办标题
            due_time: 截止时间（可选）

        Returns:
            bool: 推送是否成功
        """
        if due_time:
            message = f"📌 {title}\n截止时间：{due_time}"
        else:
            message = f"📌 {title}"

        return await self.send(
            message=message,
            title="📌 待办提醒",
            sound="reminder",
            level="timeSensitive",
            icon=self.icons["todo"]
        )

    async def send_custom(self, message: str, title: Optional[str] = None, icon: Optional[str] = None) -> bool:
        """
        发送自定义消息

        Args:
            message: 推送内容
            title: 推送标题（可选）
            icon: 推送图标（可选）

        Returns:
            bool: 推送是否成功
        """
        return await self.send(
            message=message, 
            title=title or "CampusPilot",
            icon=icon
        )
