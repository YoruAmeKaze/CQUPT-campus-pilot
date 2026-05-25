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
        获取所有课程的作业
        策略：进入每门课的课程页面 → 提取作业链接 → 访问作业列表 → 解析HTML
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
                    course_assignments = await self._fetch_course_work(c)
                    assignments.extend(course_assignments)
                except Exception as e:
                    logger.warning(f"    ⚠️ {e}")

            logger.info(f"✅ 共获取到 {len(assignments)} 个作业")
            return assignments

        except Exception as e:
            logger.error(f"❌ 获取作业失败: {e}", exc_info=True)
            return assignments

    async def _fetch_course_work(self, course: Dict) -> List[Dict]:
        """获取单门课程的作业"""
        results = []

        # 1. 访问课程中间页（302重定向到课程主页，同时获取 enc/openc 参数）
        middle_url = (
            f"{self.HOST_CP}/visit/stucoursemiddle"
            f"?courseid={course['courseid']}"
            f"&clazzid={course['clazzid']}"
            f"&vc=1&cpi={course['cpi']}"
        )
        resp = await self.client.get(middle_url, follow_redirects=True)
        current_url = str(resp.url)

        # 从最终 URL 提取参数
        enc = ""
        openc = ""
        if "?" in current_url:
            qs = parse_qs(current_url.split("?")[1])
            enc = (qs.get("enc") or [""])[0]
            openc = (qs.get("openc") or [""])[0]

        if not enc:
            # 备用：从页面HTML的data属性中提取
            for m in re.finditer(r'data="([^"]*getAllWork[^"]*)"', resp.text):
                work_url = m.group(1)
                if "?" in work_url:
                    wqs = parse_qs(work_url.split("?")[1])
                    enc = (wqs.get("enc") or [""])[0]
                    openc = (wqs.get("openc") or [""])[0]

        if not enc:
            logger.warning(f"    ⚠️ 无法获取 enc 参数，跳过")
            return results

        # 2. 访问作业页面
        work_page_url = (
            f"{self.HOST_CP}/work/getAllWork"
            f"?classId={course['clazzid']}"
            f"&courseId={course['courseid']}"
            f"&isdisplaytable=2&mooc=1"
            f"&ut=s&enc={enc}"
            f"&cpi={course['cpi']}"
            f"&openc={openc}"
        )

        work_resp = await self.client.get(work_page_url)

        if work_resp.status_code != 200:
            return results

        # 3. 解析作业HTML
        results = self._parse_work_page(work_resp.text, course["name"])
        if results:
            logger.info(f"    ✅ {len(results)} 个作业")

        return results

    def _parse_work_page(self, html: str, course_name: str) -> List[Dict]:
        """从作业页面HTML中解析作业列表"""
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text("\n", strip=True)
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        assignments = []
        for i, line in enumerate(lines):
            if line == "开始时间：" and i > 0 and i + 5 < len(lines):
                title = lines[i - 1]
                if not title or len(title) > 50 or len(title) < 2:
                    continue
                if title in ("我的作业", "待批作业", "首页", "作业", "考试"):
                    continue

                start_time = lines[i + 1]
                due_time = lines[i + 3]
                status = lines[i + 5]

                due_dt = None
                for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
                    try:
                        due_dt = datetime.strptime(due_time, fmt)
                        break
                    except ValueError:
                        pass

                is_completed = status in ("已提交", "已完成", "已批阅", "待批阅")

                uid = hashlib.md5(
                    f"{course_name}_{title}_{due_time}".encode()
                ).hexdigest()[:16]

                assignments.append({
                    "remote_id": uid,
                    "title": title[:200],
                    "course_name": course_name,
                    "due_time": due_dt,
                    "is_completed": is_completed,
                    "description": f"状态: {status}",
                })

        return assignments

    # ───── 外部接口 ─────

    async def crawl_and_parse(self) -> List[Dict[str, Any]]:
        return await self.fetch_assignments()
