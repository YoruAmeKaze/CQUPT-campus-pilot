import logging
import re
from typing import List, Optional, Dict, Any
from datetime import datetime

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class SmartestuCrawler:
    """数你最灵爬虫"""

    BASE = "https://smartestu.cn"

    def __init__(
        self,
        student_id: Optional[str] = None,
        password: Optional[str] = None,
        school_code: Optional[str] = None,
    ):
        self._raw_student_id = student_id or settings.smartestu_student_id or ""
        self.password = password or settings.smartestu_password or ""
        self.school_code = school_code or settings.smartestu_school_id or "cqupt"
        # 数你最灵的 schoolUserId 格式为 {schoolCode}-{studentId}
        self.student_id = f"{self.school_code}-{self._raw_student_id}" if self._raw_student_id and "-" not in self._raw_student_id else self._raw_student_id
        self._token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Origin": self.BASE,
                "Referer": f"{self.BASE}/",
            },
        )
        return self

    async def __aexit__(self, *args):
        if self.client:
            await self.client.aclose()

    async def login(self) -> bool:
        """登录获取 JWT Token"""
        if not self.student_id or not self.password:
            logger.error("❌ 请配置数你最灵学号和密码")
            return False

        try:
            logger.info(f"🔐 登录数你最灵 - {self._raw_student_id} (schoolUserId: {self.student_id})")

            resp = await self.client.post(
                f"{self.BASE}/api/auth/login",
                json={
                    "schoolUserId": self.student_id,
                    "password": self.password,
                },
            )

            if resp.status_code == 200:
                data = resp.json()
                self._token = data.get("token") or data.get("access_token")
                self._refresh_token = data.get("refreshToken") or data.get("refresh_token")

                if self._token:
                    logger.info("✅ 数你最灵登录成功")
                    return True

            msg = ""
            try:
                msg = resp.json().get("message", "")
            except Exception:
                msg = resp.text[:100]

            logger.warning(f"⚠️ 登录失败: {msg}")
            return False

        except Exception as e:
            logger.error(f"❌ 登录异常: {e}", exc_info=True)
            return False

    async def ensure_login(self) -> bool:
        """确保已登录"""
        if self._token:
            return True
        return await self.login()

    async def fetch_assignments(self) -> List[Dict[str, Any]]:
        """获取作业列表"""
        if not await self.ensure_login():
            raise Exception("数你最灵登录失败，请检查账号密码或注册账号")

        logger.info("📖 获取数你最灵作业...")

        # 尝试多个作业接口
        apis = [
            f"{self.BASE}/api/homework/student/mark/queryHomeworks",
            f"{self.BASE}/api/homework/student/homework/query",
        ]

        for api_url in apis:
            try:
                resp = await self.client.post(
                    api_url,
                    headers={"Authorization": f"Bearer {self._token}"},
                    json={},
                    timeout=15.0,
                )

                if resp.status_code == 401 and self._refresh_token:
                    logger.info("🔄 Token 过期，尝试刷新...")
                    if await self._refresh():
                        resp = await self.client.post(
                            api_url,
                            headers={"Authorization": f"Bearer {self._token}"},
                            json={},
                            timeout=15.0,
                        )

                if resp.status_code == 200:
                    data = resp.json()
                    items = data if isinstance(data, list) else data.get("homeworks", data.get("data", []))
                    if items:
                        assignments = []
                        for item in items:
                            a = self._parse_assignment(item)
                            if a:
                                assignments.append(a)
                        logger.info(f"✅ 获取到 {len(assignments)} 个作业")
                        return assignments
                    else:
                        logger.info("  📭 作业列表为空")
                        return []

                msg = ""
                try:
                    msg = ": " + resp.json().get("msg", resp.text[:100])
                except Exception:
                    msg = ""
                logger.info(f"  API {api_url.split('/')[-1]} 返回 {resp.status_code}{msg}")

            except Exception as e:
                logger.info(f"  API {api_url.split('/')[-1]} 异常: {e}")
                continue

        raise Exception("数你最灵作业接口暂不可用")

    def _parse_assignment(self, item: dict) -> Optional[Dict]:
        """解析单个作业"""
        title = (
            item.get("title")
            or item.get("assignmentName")
            or item.get("name")
            or ""
        )
        if not title:
            return None

        course_name = (
            item.get("courseName")
            or item.get("course")
            or item.get("subjectName")
            or "未知课程"
        )

        due_time = None
        due_str = (
            item.get("dueTime")
            or item.get("deadline")
            or item.get("endTime")
            or item.get("end_time")
            or ""
        )
        if due_str:
            try:
                due_time = datetime.fromisoformat(due_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                try:
                    due_time = datetime.strptime(str(due_str)[:16], "%Y-%m-%dT%H:%M")
                except (ValueError, AttributeError):
                    pass

        is_completed = item.get("isCompleted") or item.get("completed") or False
        status = item.get("status", "")
        if isinstance(is_completed, str):
            is_completed = is_completed.lower() in ("true", "1", "yes", "已完成", "已提交")

        remote_id = str(
            item.get("id")
            or item.get("_id")
            or item.get("homeworkId")
            or ""
        )

        return {
            "remote_id": remote_id,
            "title": title[:200],
            "course_name": course_name[:200],
            "due_time": due_time,
            "is_completed": bool(is_completed),
            "description": item.get("description", ""),
        }

    async def _refresh(self) -> bool:
        """刷新 Token"""
        try:
            resp = await self.client.post(
                f"{self.BASE}/api/auth/refresh",
                json={"refreshToken": self._refresh_token} if self._refresh_token else {},
            )
            if resp.status_code == 200:
                data = resp.json()
                self._token = data.get("token") or data.get("access_token")
                return self._token is not None
        except Exception:
            pass
        return False

    async def crawl_and_parse(self) -> List[Dict[str, Any]]:
        return await self.fetch_assignments()
