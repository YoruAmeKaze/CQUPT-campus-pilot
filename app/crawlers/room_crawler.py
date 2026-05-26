import asyncio
import logging
import re
from typing import List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class RoomCrawler:
    """重庆邮电大学教室课表爬虫（查空教室）"""

    BASE_URL = "http://jwzx.cqupt.edu.cn/kebiao"

    def __init__(self, concurrency: int = 10):
        self.concurrency = concurrency
        self._semaphore = asyncio.Semaphore(concurrency)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                },
            )
            # 先访问主页面建立 session
            await self._client.get(f"{self.BASE_URL}/index.php")
        return self._client

    async def fetch_room_list(self) -> List[dict]:
        """
        从主页面提取所有教室列表

        Returns:
            List[dict]: [{"room_name": "3105", "room_type": "教室", "capacity": 300, "building": "第三教学楼"}, ...]
        """
        client = await self._get_client()
        resp = await client.get(f"{self.BASE_URL}/index.php")
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        rooms = []

        current_building = ""
        current_type = "教室"

        # 找到教室列表区域（在 printTable 和 h3 标题中）
        for elem in soup.find_all(["h3", "div"]):
            if elem.name == "h3":
                text = elem.get_text(strip=True)
                if "教室" in text and "可容纳" in text:
                    current_type = "教室"
                    current_building = text.replace("(可容纳人数)", "").strip()
                elif "室外" in text:
                    current_type = "室外"
                    current_building = text.replace("(可容纳人数)", "").strip()
                elif "实验室" in text:
                    current_type = "实验室"
                    current_building = text.strip()
                else:
                    current_building = text
                continue

            if elem.name == "div" and "printTable" in elem.get("class", []):
                table = elem.find("table")
                if not table:
                    continue
                for td in table.find_all("td"):
                    for a in td.find_all("a", href=re.compile(r"kb_room\.php\?room=")):
                        room_name = a.get_text(strip=True)
                        # 提取容量，格式如 "3105(300)" 或 "2100(134)"
                        capacity = None
                        cap_match = re.search(r"\((\d+)\)$", room_name)
                        if cap_match:
                            capacity = int(cap_match.group(1))
                            room_name = room_name[: -len(cap_match.group(0))]

                        if room_name:
                            rooms.append({
                                "room_name": room_name,
                                "room_type": current_type,
                                "capacity": capacity,
                                "building": current_building,
                            })

        logger.info(f"✅ 从主页面提取到 {len(rooms)} 个教室/场地")
        return rooms

    async def fetch_room_schedule(self, room_name: str) -> Optional[str]:
        """
        抓取单个教室的课表页面 HTML

        Args:
            room_name: 教室名，如 "3105"

        Returns:
            Optional[str]: HTML 内容，失败返回 None
        """
        async with self._semaphore:
            try:
                client = await self._get_client()
                resp = await client.get(
                    f"{self.BASE_URL}/kb_room.php?room={room_name}"
                )
                resp.raise_for_status()
                return resp.text
            except Exception as e:
                logger.warning(f"⚠️ 抓取教室 {room_name} 失败: {e}")
                return None

    def parse_room_schedule(self, html: str, room_name: str) -> List[dict]:
        """
        解析教室课表 HTML

        Args:
            html: kb_room.php 返回的 HTML
            room_name: 教室名

        Returns:
            List[dict]: [
                {
                    "room_name": "3105",
                    "day_of_week": 1,
                    "start_slot": 1,
                    "end_slot": 2,
                    "start_week": 1,
                    "end_week": 17,
                    "week_mask": "1111111111111111100",
                    "course_name": "高等数学A(下)",
                },
                ...
            ]
        """
        soup = BeautifulSoup(html, "lxml")
        schedules = []

        # 找到课表表格（第一个 table 是课表网格）
        table = soup.find("table")
        if not table:
            return schedules

        rows = table.find_all("tr")
        if len(rows) < 2:
            return schedules

        # 解析表头获取星期映射
        header_cells = rows[0].find_all(["td", "th"])
        day_map = {}  # col_index -> day_of_week (1-7)
        for col_idx, cell in enumerate(header_cells):
            text = cell.get_text(strip=True)
            day_num = self._parse_day(text)
            if day_num:
                day_map[col_idx] = day_num

        # 解析每一行（每个时段的课）
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            # 第一列是节次信息
            slot_text = cells[0].get_text(strip=True)
            slots = self._parse_slots(slot_text)
            if not slots:
                continue
            start_slot, end_slot = slots

            # 遍历每一天
            for col_idx, cell in enumerate(cells[1:], start=1):
                day = day_map.get(col_idx)
                if day is None:
                    continue

                cell_text = cell.get_text(strip=True)
                if not cell_text or cell_text == "&nbsp;":
                    continue

                # 解析该单元格中的课程（可能有多个课程挤在一起）
                # 用 kbTd div 区分多个课程
                kb_tds = cell.find_all("div", class_="kbTd")
                if kb_tds:
                    for kb_td in kb_tds:
                        parsed = self._parse_kbtd(kb_td, room_name, day, start_slot, end_slot)
                        if parsed:
                            schedules.append(parsed)
                else:
                    # 没有 kbTd，直接解析文本
                    parsed = self._parse_cell_text(cell_text, room_name, day, start_slot, end_slot)
                    if parsed:
                        schedules.append(parsed)

        return schedules

    def _parse_day(self, text: str) -> Optional[int]:
        """解析星期文本 -> 1-7"""
        day_map = {
            "周一": 1, "星期二": 2, "周三": 3, "周四": 4, "周五": 5, "周六": 6, "周日": 7,
            "星期一": 1, "星期二": 2, "星期三": 3, "星期四": 4, "星期五": 5, "星期六": 6, "星期日": 7,
        }
        for key, val in day_map.items():
            if key in text:
                return val
        return None

    def _parse_slots(self, text: str) -> Optional[Tuple[int, int]]:
        """解析节次文本，如 '1、2节' -> (1, 2)"""
        text = text.strip()
        # 处理 "1、2节" 格式
        match = re.search(r"(\d+)[、,，]\s*(\d+)", text)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        # 处理 "1-2节" 格式
        match = re.search(r"(\d+)\s*[-~]\s*(\d+)", text)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        # 处理单个数字
        match = re.search(r"(\d+)", text)
        if match:
            n = int(match.group(1))
            return (n, n)
        return None

    def _parse_kbtd(self, kb_td, room_name: str, day: int, start_slot: int, end_slot: int) -> Optional[dict]:
        """解析单个 kbTd div 中的课程信息"""
        raw_html = str(kb_td)
        temp_soup = BeautifulSoup(raw_html, "lxml")
        div = temp_soup.find("div")
        if not div:
            return None

        lines = [line.strip() for line in div.stripped_strings if line.strip()]

        course_name = ""
        start_week = 1
        end_week = 20
        week_mask = ""

        # 提取课程名（第一行或第二行）
        for i, line in enumerate(lines):
            if "-" in line and len(line) > 5:
                # 格式: "A1110022-高等数学A(下)"
                parts = line.split("-", 1)
                course_name = parts[1].strip()
                break

        if not course_name:
            return None

        # 提取周次信息
        for line in lines:
            week_range = self._parse_week_range(line)
            if week_range:
                start_week, end_week = week_range
                break

        # 提取 week_mask (从 zc 属性)
        week_mask = kb_td.get("zc", "")

        return {
            "room_name": room_name,
            "day_of_week": day,
            "start_slot": start_slot,
            "end_slot": end_slot,
            "start_week": start_week,
            "end_week": end_week,
            "week_mask": week_mask,
            "course_name": course_name,
        }

    def _parse_cell_text(self, text: str, room_name: str, day: int, start_slot: int, end_slot: int) -> Optional[dict]:
        """直接从单元格文本中解析课程"""
        # 跳过考试安排和教学调度
        if "考试安排" in text or "教学调度" in text:
            return None

        # 提取课程名
        course_match = re.search(r"\d+-([\u4e00-\u9fffA-Za-z].*?)(?:地点|考试|$)", text)
        if not course_match:
            return None
        course_name = course_match.group(1).strip()

        # 提取周次
        week_range = self._parse_week_range(text)

        return {
            "room_name": room_name,
            "day_of_week": day,
            "start_slot": start_slot,
            "end_slot": end_slot,
            "start_week": week_range[0] if week_range else 1,
            "end_week": week_range[1] if week_range else 20,
            "week_mask": "",
            "course_name": course_name,
        }

    def _parse_week_range(self, text: str) -> Optional[Tuple[int, int]]:
        """解析周次范围"""
        multi_range = re.findall(r"(\d+)\s*[-~]\s*(\d+)", text)
        if multi_range:
            starts = [int(m[0]) for m in multi_range]
            ends = [int(m[1]) for m in multi_range]
            return (min(starts), max(ends))

        single_weeks = re.findall(r"(\d+)周", text)
        if len(single_weeks) > 1:
            weeks = [int(w) for w in single_weeks]
            return (min(weeks), max(weeks))

        range_match = re.search(r"(\d+)\s*[-~]\s*(\d+)", text)
        if range_match:
            return (int(range_match.group(1)), int(range_match.group(2)))

        single_match = re.search(r"(\d+)周", text)
        if single_match:
            week = int(single_match.group(1))
            return (week, week)

        return None

    async def refresh_all(self, existing_rooms: List[str]) -> dict:
        """
        批量刷新所有教室的课表数据

        Args:
            existing_rooms: 已有的教室名列表

        Returns:
            dict: {"total": int, "success": int, "schedules": int, "rooms": List[dict]}
        """
        logger.info(f"🏢 开始刷新 {len(existing_rooms)} 个教室的课表数据")

        # 爬取所有教室
        async def fetch_one(room_name: str) -> Tuple[str, Optional[str]]:
            html = await self.fetch_room_schedule(room_name)
            return (room_name, html)

        tasks = [fetch_one(name) for name in existing_rooms]
        results = await asyncio.gather(*tasks)

        all_schedules = []
        success_count = 0

        for room_name, html in results:
            if html:
                schedules = self.parse_room_schedule(html, room_name)
                all_schedules.append({
                    "room_name": room_name,
                    "schedules": schedules,
                })
                success_count += 1

        logger.info(f"✅ 刷新完成: {success_count}/{len(existing_rooms)} 个教室成功")

        return {
            "total": len(existing_rooms),
            "success": success_count,
            "schedules_count": sum(len(s["schedules"]) for s in all_schedules),
            "rooms": all_schedules,
        }

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
