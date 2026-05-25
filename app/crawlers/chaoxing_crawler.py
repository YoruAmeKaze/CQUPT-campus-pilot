import logging
import re
import hashlib
from base64 import b64encode
from typing import List, Optional, Dict, Any
from datetime import datetime
from urllib.parse import urljoin, urlencode, parse_qs

import httpx
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding

from app.config import settings

logger = logging.getLogger(__name__)


def aes_cbc_encrypt(plaintext: str, key: str) -> str:
    """AES-CBC 加密"""
    key_bytes = key.encode("utf-8")
    iv_bytes = key.encode("utf-8")
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plaintext.encode("utf-8")) + padder.finalize()
    cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(iv_bytes))
    encryptor = cipher.encryptor()
    ct = encryptor.update(padded) + encryptor.finalize()
    return b64encode(ct).decode("utf-8")


class ChaoxingCrawler:
    """学习通（超星）真实爬虫"""

    HOST_CP = "https://mooc1.chaoxing.com"
    HOST_PASSPORT = "https://passport2.chaoxing.com"
    HOST_MOBILE = "https://mobilelearn.chaoxing.com"
    AES_KEY = "u2oh6Vu^HWe4_AES"

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        cookies_str: Optional[str] = None,
    ):
        self.username = username or settings.chaoxing_username or ""
        self.password = password or settings.chaoxing_password or ""
        self._cookies: Dict[str, str] = {}
        self.client: Optional[httpx.AsyncClient] = None

        if cookies_str:
            for item in cookies_str.split(";"):
                item = item.strip()
                if "=" in item:
                    k, v = item.split("=", 1)
                    self._cookies[k.strip()] = v.strip()

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            timeout=60.0, follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
        if self._cookies:
            self.client.cookies.update(self._cookies)
        return self

    async def __aexit__(self, *args):
        if self.client:
            await self.client.aclose()

    # ───── 登录 ─────

    async def login(self) -> bool:
        if not self.username or not self.password:
            logger.error("❌ 请配置 .env 中的 CHAOXING_USERNAME 和 CHAOXING_PASSWORD")
            return False
        try:
            logger.info(f"🔐 登录学习通 - {self.username}")
            enc_phone = aes_cbc_encrypt(self.username, self.AES_KEY)
            enc_pwd = aes_cbc_encrypt(self.password, self.AES_KEY)
            resp = await self.client.post(
                f"{self.HOST_PASSPORT}/fanyalogin",
                data={"uname": enc_phone, "password": enc_pwd, "fid": "-1",
                      "refer": "https://mooc1.chaoxing.com", "t": "true",
                      "forbidotherlogin": "false", "validate": ""},
            )
            result = resp.json()
            if result.get("status") is True:
                logger.info("✅ 登录成功")
                self._cookies = dict(self.client.cookies)
                return True
            logger.warning(f"⚠️ 登录失败: {result.get('msg2', '')}")
            return False
        except Exception as e:
            logger.error(f"❌ 登录异常: {e}", exc_info=True)
            return False

    async def ensure_login(self) -> bool:
        if not self._cookies:
            return await self.login()
        if await self.is_logged_in():
            return True
        return await self.login()

    async def is_logged_in(self) -> bool:
        try:
            resp = await self.client.get(f"{self.HOST_CP}/visit/courses")
            return "passport2" not in str(resp.url) and "登录" not in resp.text[:500]
        except Exception:
            return False

    # ───── 课程 ─────

    async def fetch_courses(self) -> List[Dict[str, Any]]:
        """
        获取课程列表，返回带 courseid/clazzid/cpi 的课程信息
        """
        courses = []
        try:
            if not await self.ensure_login():
                return courses

            resp = await self.client.get(f"{self.HOST_CP}/visit/courses")
            soup = BeautifulSoup(resp.text, "lxml")

            # 新版: stucoursemiddle 链接
            for link in soup.find_all("a", href=re.compile(r"stucoursemiddle")):
                href = link.get("href", "")
                qs = parse_qs(href.split("?")[1]) if "?" in href else {}
                cid = (qs.get("courseid") or [None])[0]
                clazzid = (qs.get("clazzid") or [None])[0]
                cpi = (qs.get("cpi") or [None])[0]
                name = link.get("title", "") or link.get_text(strip=True) or ""
                name = re.sub(r"\s+", " ", name).strip()

                if not cid:
                    continue

                # 去重，但保留有名字的版本
                existing = next((c for c in courses if c["courseid"] == cid), None)
                if existing:
                    if name and not existing["name"]:
                        existing["name"] = name
                else:
                    courses.append({
                        "courseid": cid,
                        "clazzid": clazzid or "",
                        "cpi": cpi or "",
                        "name": name,
                    })

            logger.info(f"📚 获取到 {len(courses)} 门课程")
            return courses

        except Exception as e:
            logger.error(f"❌ 获取课程失败: {e}", exc_info=True)
            return courses

    # ───── 作业 ─────

    async def fetch_assignments(self) -> List[Dict[str, Any]]:
        """
        获取所有课程的待办作业
        API: /api/workTestPendingNew (GET)
        """
        assignments = []
        try:
            if not await self.ensure_login():
                return assignments

            courses = await self.fetch_courses()
            if not courses:
                return assignments

            logger.info(f"📖 从 {len(courses)} 门课程获取作业...")

            for i, c in enumerate(courses, 1):
                name = c["name"] or f"课程{c['courseid']}"
                logger.info(f"  [{i}/{len(courses)}] {name}")

                try:
                    resp = await self.client.get(
                        f"{self.HOST_CP}/api/workTestPendingNew",
                        params={"courseId": c["courseid"], "clazzId": c["clazzid"]},
                    )
                    data = resp.json()
                except Exception:
                    data = []

                if isinstance(data, list):
                    for item in data:
                        a = self._parse_assign_item(item, name)
                        if a:
                            assignments.append(a)

            # 也尝试获取已结束的作业
            try:
                resp2 = await self.client.get(
                    f"{self.HOST_CP}/api/workTestPendingNew",
                    params={"stateType": "2"},
                )
                finished = resp2.json()
                if isinstance(finished, list):
                    for item in finished:
                        cname = item.get("courseName", "") or item.get("course_name", "") or "未知课程"
                        a = self._parse_assign_item(item, cname)
                        if a:
                            a["is_completed"] = True
                            assignments.append(a)
            except Exception:
                pass

            logger.info(f"✅ 共获取到 {len(assignments)} 个作业")
            return assignments

        except Exception as e:
            logger.error(f"❌ 获取作业失败: {e}", exc_info=True)
            return assignments

    def _parse_assign_item(self, item: dict, course_name: str) -> Optional[Dict]:
        """解析单个作业项"""
        if not item or not isinstance(item, dict):
            return None

        title = (item.get("title") or item.get("name") or item.get("workName") or "").strip()
        if not title:
            return None

        due_time = None
        due_str = item.get("endTime") or item.get("deadline") or item.get("endtime") or ""
        if due_str:
            try:
                due_time = datetime.fromtimestamp(int(due_str) / 1000)
            except (ValueError, OSError):
                due_time = self._parse_due_time(str(due_str))

        is_completed = item.get("status") in ("已完成", "已提交", "已批阅", "2", "3")

        uid = item.get("id") or hashlib.md5(f"{course_name}_{title}_{due_str}".encode()).hexdigest()[:16]

        return {
            "remote_id": str(uid),
            "title": title[:200],
            "course_name": course_name,
            "due_time": due_time,
            "is_completed": is_completed,
            "description": item.get("description") or item.get("desc") or "",
        }

    def _parse_due_time(self, text: str) -> Optional[datetime]:
        patterns = [
            r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s*(\d{1,2})[:：]?(\d{2})",
            r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2})[:：]?(\d{2})",
            r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})",
            r"(\d{4})年(\d{1,2})月(\d{1,2})日",
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                try:
                    parts = [int(m.group(i)) for i in range(1, 6) if m.group(i)]
                    y, mo, d = parts[0], parts[1], parts[2]
                    h = parts[3] if len(parts) > 3 else 23
                    mi = parts[4] if len(parts) > 4 else 59
                    return datetime(y, mo, d, h, mi)
                except (ValueError, IndexError):
                    continue
        return None

    # ───── 外部接口 ─────

    async def crawl_and_parse(self) -> List[Dict[str, Any]]:
        return await self.fetch_assignments()
