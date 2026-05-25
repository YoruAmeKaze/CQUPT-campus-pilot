import logging
import re
from typing import List, Optional

try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    # 定义一些占位类型，避免类型注解报错
    Browser = None
    Page = None

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from bs4 import BeautifulSoup

from app.config import settings

logger = logging.getLogger(__name__)


class JwxtCrawler:
    """重庆邮电大学教务系统课表爬虫 (Playwright 版本)"""

    BASE_URL = "http://jwzx.cqupt.edu.cn/kebiao/kb_stu.php"  # 使用 HTTP（HTTPS 有协议问题）

    def __init__(self, student_id: Optional[str] = None, headless: bool = True):
        self.student_id = student_id or settings.student_id
        if not self.student_id:
            raise ValueError("学号不能为空，请在 .env 中配置 STUDENT_ID")

        self.headless = headless
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("⚠️ Playwright 未安装，无法进行网络抓取，但解析功能仍可用")

    async def _init_browser(self):
        """初始化 Playwright 浏览器"""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright 未安装，无法初始化浏览器")
            
        if self.browser is not None:
            return

        playwright = await async_playwright().start()

        # 启动浏览器（使用系统 Chrome，带反检测配置）
        self.browser = await playwright.chromium.launch(
            channel='chrome',  # 使用系统安装的 Chrome
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )

        # 创建浏览器上下文（模拟真实浏览器）
        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
        )

        # 注入反检测脚本
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)

        self.page = await context.new_page()

        logger.info("✅ Playwright 浏览器初始化完成")

    async def fetch_schedule_with_httpx(self) -> str:
        """
        使用 httpx 抓取课表页面 HTML（轻量级方案）
        
        Returns:
            str: 课表页面的 HTML 内容
        """
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx 未安装，请安装 httpx 以使用此功能")
            
        schedule_url = f"{self.BASE_URL}?xh={self.student_id}"
        logger.info(f"🌐 使用 httpx 访问课表页面: {schedule_url}")
        
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(schedule_url, headers=headers)
            response.raise_for_status()
            
            html = response.text
            
            # 保存 HTML 用于调试
            with open('debug_schedule.html', 'w', encoding='utf-8') as f:
                f.write(html)
            logger.info(f"📄 已保存 HTML 到 debug_schedule.html")
            
            logger.info(f"✅ 成功获取课表页面，共 {len(html)} 字节")
            return html

    async def fetch_schedule(self) -> str:
        """
        使用 Playwright 抓取课表页面 HTML
        
        Returns:
            str: 课表页面的 HTML 内容
        """
        await self._init_browser()

        schedule_url = f"{self.BASE_URL}?xh={self.student_id}"
        
        logger.info(f"🌐 访问课表页面: {schedule_url}")
        
        try:
            # 设置真实的请求头（完全模拟真实浏览器）
            await self.page.set_extra_http_headers({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0',
            })
            
            # 直接访问课表页面（不需要先访问主页）
            response = await self.page.goto(
                schedule_url,
                wait_until='domcontentloaded',
                timeout=30000,
            )

            if not response:
                raise Exception("课表页面未响应")

            status = response.status
            logger.info(f"📄 课表页面响应状态: {status}")

            # 处理各种 HTTP 状态码
            if status >= 400:
                logger.warning(f"⚠️ 收到 HTTP {status} 错误")
            
            # 额外等待（确保动态内容加载完成）
            await self.page.wait_for_timeout(2000)

            # 等待课表表格加载完成
            try:
                await self.page.wait_for_selector(
                    'table.kbtable, table#kbtable, table:has(th:has-text("周一"))',
                    timeout=15000
                )
                logger.info("✅ 课表表格已加载")
            except Exception:
                logger.warning("⚠️ 未检测到标准课表表格，尝试获取页面内容...")

            # 获取完整的页面 HTML
            html = await self.page.content()
            
            # 保存 HTML 用于调试（临时）
            with open('debug_schedule.html', 'w', encoding='utf-8') as f:
                f.write(html)
            logger.info(f"📄 已保存 HTML 到 debug_schedule.html")
            
            logger.info(f"✅ 成功获取课表页面，大小: {len(html)} 字节")
            return html
            
        except Exception as e:
            logger.error(f"❌ 抓取失败: {e}", exc_info=True)
            
            # 尝试截图保存（用于调试）
            if self.page:
                try:
                    screenshot_path = 'debug_schedule.png'
                    await self.page.screenshot(path=screenshot_path, full_page=True)
                    logger.info(f"📸 已保存调试截图: {screenshot_path}")
                except:
                    pass
            
            raise Exception(f"抓取课表失败: {e}")

    def parse_courses(self, html: str) -> List[dict]:
        """
        解析课表HTML，提取课程信息
        
        Args:
            html: 课表页面HTML
            
        Returns:
            List[dict]: 课程列表，每门课程包含完整信息
        """
        soup = BeautifulSoup(html, "lxml")
        courses = []

        try:
            # 查找课表表格（通常在kbtable类中）
            table = soup.find("table", {"class": "kbtable"}) or soup.find("table", {"id": "kbtable"})
            
            if not table:
                # 尝试查找任何包含课程的表格
                tables = soup.find_all("table")
                for t in tables:
                    if "周一" in t.get_text() or "星期" in t.get_text():
                        table = t
                        break
            
            if not table:
                logger.warning("⚠️ 未找到课表表格")
                # 输出页面部分内容用于调试
                title = soup.find("title")
                if title:
                    logger.info(f"页面标题: {title.get_text()}")
                return []

            # 解析表格行
            rows = table.find_all("tr")
            logger.info(f"📊 找到课表表格，共 {len(rows)} 行")
            
            # 节次时间映射（重邮标准时间表）
            slot_time_map = {
                1: ("08:00", "09:40"),
                2: ("08:00", "09:40"),
                3: ("10:15", "11:55"),
                4: ("10:15", "11:55"),
                5: ("14:00", "15:40"),
                6: ("14:00", "15:40"),
                7: ("16:15", "17:55"),
                8: ("16:15", "17:55"),
                9: ("19:00", "20:40"),
                10: ("19:00", "20:40"),
                11: ("20:50", "22:30"),
                12: ("20:50", "22:30"),
            }

            for row in rows:
                cells = row.find_all(["td", "th"])
                
                if len(cells) < 8:  # 至少需要：节次 + 周一到周日
                    continue
                
                # 获取当前行对应的节次
                first_cell = cells[0].get_text(strip=True)
                try:
                    current_slots = self._parse_slot(first_cell)
                except ValueError:
                    continue
                
                # 遍历每一天的单元格（从第2列开始是周一）
                for day_idx, cell in enumerate(cells[1:], start=1):
                    if day_idx > 7:  # 只处理周一到周日
                        break
                    
                    # 查找所有kbTd div（可能有多个课程）
                    kb_tds = cell.find_all("div", class_="kbTd")
                    
                    for kb_td in kb_tds:
                        # 解析这个div里的课程
                        cell_course = self._parse_kbtd(kb_td, day_of_week=day_idx, slots=current_slots, time_map=slot_time_map)
                        if cell_course:
                            courses.append(cell_course)

            logger.info(f"✅ 成功解析出 {len(courses)} 门课程")
            return courses

        except Exception as e:
            logger.error(f"❌ 解析课表失败: {e}", exc_info=True)
            raise Exception(f"解析课表失败: {e}")

    def _parse_slot(self, slot_text: str) -> tuple:
        """解析节次文本，返回 (起始节, 结束节)"""
        slot_text = slot_text.strip()
        
        # 处理"1、2节"格式
        if "、" in slot_text:
            parts = slot_text.split("、")
            # 提取数字部分（去掉"节"字）
            start = int(parts[0])
            end = int(parts[1].split("节")[0])
            return (start, end)
        # 处理"1-2节"格式
        elif "-" in slot_text:
            parts = slot_text.split("-")
            return (int(parts[0]), int(parts[1]))
        else:
            # 尝试提取单个数字
            import re
            match = re.search(r"(\d+)", slot_text)
            if match:
                slot = int(match.group(1))
                return (slot, slot)
            raise ValueError(f"无法解析节次: {slot_text}")

    def _parse_kbtd(self, kb_td, day_of_week: int, slots: tuple, time_map: dict) -> Optional[dict]:
        """
        解析单个kbTd div中的课程信息
        格式通常是：
        A08252A1110311018
        A1110311-大学物理B（上）
        地点：3302 
        1-4周,6-14周
        龙春红 必修 3.5学分
        """
        # 获取zc属性（周次二进制标记）
        week_mask = kb_td.get("zc", "")
        
        # 获取原始HTML内容，按<br>分割
        raw_html = str(kb_td)
        temp_soup = BeautifulSoup(raw_html, "lxml")
        
        # 提取所有文本节点，保持顺序
        text_parts = []
        for elem in temp_soup.div.contents:
            if isinstance(elem, str) and elem.strip():
                text_parts.append(elem.strip())
            elif elem.name == "br":
                continue
            elif elem.get_text(strip=True):
                text_parts.append(elem.get_text(strip=True))
        
        # 清理文本
        lines = [line.strip() for line in text_parts if line.strip()]
        
        if len(lines) < 4:
            logger.warning(f"⚠️ 课程信息不足: {lines}")
            return None
        
        course_name = ""
        teacher = ""
        location = ""
        start_week = 1
        end_week = 20  # 默认最大周数改为20
        
        # 提取课程名（第2行）
        if len(lines) > 1:
            name_part = lines[1]
            if "-" in name_part:
                # 格式：课程号-课程名
                course_name = name_part.split("-", 1)[1]
            else:
                course_name = name_part
        
        # 提取地点（第3行）
        if len(lines) > 2:
            location_part = lines[2]
            if "：" in location_part:
                location = location_part.split("：", 1)[1].strip()
            elif ":" in location_part:
                location = location_part.split(":", 1)[1].strip()
            else:
                location = location_part.strip()
        
        # 提取周次（第4行）
        if len(lines) > 3:
            week_part = lines[3]
            week_range = self._parse_week_range(week_part)
            if week_range:
                start_week, end_week = week_range
        
        # 提取教师和连堂节数（第5行及以后）
        actual_start_slot = slots[0]
        actual_end_slot = slots[1]
        if len(lines) > 4:
            teacher_info = " ".join(lines[4:])
            consecutive_match = re.search(r'(\d+)节连上', teacher_info)
            if consecutive_match:
                consecutive_classes = int(consecutive_match.group(1))
                actual_end_slot = actual_start_slot + consecutive_classes - 1
            teacher_parts = teacher_info.split()
            for part in teacher_parts:
                if part not in ["必修", "选修", "4节连上", "3节连上"] and len(part) >= 2:
                    teacher = part
                    break
        
        # 获取时间
        start_time = time_map.get(actual_start_slot, ("08:00", "09:40"))[0] if actual_start_slot in time_map else "08:00"
        end_time = time_map.get(actual_end_slot, ("08:00", "09:40"))[1] if actual_end_slot in time_map else "09:40"

        # 解析多地点信息
        location_schedule = self._parse_location_schedule(location, (start_week, end_week))

        if not course_name:
            course_name = f"未知课程-{day_of_week}-{actual_start_slot}"

        return {
            "name": course_name,
            "teacher": teacher,
            "location": location,
            "location_schedule": location_schedule,
            "day_of_week": day_of_week,
            "start_week": start_week,
            "end_week": end_week,
            "week_mask": week_mask,
            "start_slot": actual_start_slot,
            "end_slot": actual_end_slot,
            "start_time": start_time,
            "end_time": end_time,
        }

    def _parse_location_schedule(self, location: str, week_range: tuple) -> Optional[list]:
        """
        解析多地点信息

        支持格式：
        - "A101" -> [({"start_week": 1, "end_week": 20, "location": "A101"})]
        - "1-4周:A101, 5-8周:A102" -> [{"start_week":1,"end_week":4,"location":"A101"},{"start_week":5,"end_week":8,"location":"A102"}]
        - "1-2周:A101, 5-8周:A102, 9-16周:A103" -> 解析为列表

        Args:
            location: 地点字符串
            week_range: 默认周次范围

        Returns:
            Optional[list]: 地点列表，每个元素包含 start_week, end_week, location
        """
        if not location:
            return None

        location = location.strip()
        if not location:
            return None

        # 检查是否包含周次前缀格式 "1-4周:A101, 5-8周:A102"
        multi_match = re.findall(r'(\d+)\s*[-~]\s*(\d+)\s*周\s*[:：]\s*([^,，]+)', location)
        if multi_match and len(multi_match) > 1:
            schedule = []
            for start, end, loc in multi_match:
                schedule.append({
                    "start_week": int(start),
                    "end_week": int(end),
                    "location": loc.strip(),
                })
            return schedule

        # 单地点，返回包含默认周次的列表
        default_start, default_end = week_range if week_range else (1, 20)
        return [{"start_week": default_start, "end_week": default_end, "location": location}]

    def _parse_week_range(self, text: str) -> Optional[tuple]:
        """
        解析周次范围
        支持格式：
        - "20周" -> (20, 20)  只在第20周（如金工实习）
        - "1-16周" -> (1, 16)
        - "1-4周,6-14周" -> (1, 14)
        - "1周,7周" -> (1, 7)
        - "2-16周双周" -> (2, 16)
        - "3-17周单周" -> (3, 17)
        - "13周" -> (13, 13)  单周课程（如物理实验）
        """
        # 首先查找所有范围（包括用逗号分隔的多个范围）
        # 匹配 "1-4周,6-14周" 或 "1-4周,6-14周,16-18周" 等格式
        multi_range_match = re.findall(r'(\d+)\s*[-~]\s*(\d+)', text)
        if multi_range_match and len(multi_range_match) > 0:
            # 有多个范围的情况
            starts = [int(m[0]) for m in multi_range_match]
            ends = [int(m[1]) for m in multi_range_match]
            return (min(starts), max(ends))
        
        # 匹配 "1周,7周" 这种多个单周（没有横杠）
        single_weeks = re.findall(r'(\d+)周', text)
        if len(single_weeks) > 1:
            weeks = [int(w) for w in single_weeks]
            return (min(weeks), max(weeks))
        
        # 匹配单个范围 "1-16周"
        range_match = re.search(r'(\d+)\s*[-~]\s*(\d+)', text)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            return (start, end)
        
        # 匹配单个周数 "13周" 或 "20周"
        single_week_match = re.search(r'(\d+)周', text)
        if single_week_match:
            week = int(single_week_match.group(1))
            return (week, week)
        
        # 匹配 "第X周"
        match = re.search(r'第\s*(\d+)\s*周', text)
        if match:
            week = int(match.group(1))
            return (week, week)
        
        # 默认返回 None
        return None

    async def crawl_and_parse(self) -> List[dict]:
        """
        一键抓取并解析课表（优先使用 httpx）
        
        Returns:
            List[dict]: 课程列表
        """
        try:
            # 优先尝试 httpx（轻量级方案）
            if HTTPX_AVAILABLE:
                html = await self.fetch_schedule_with_httpx()
            elif PLAYWRIGHT_AVAILABLE:
                html = await self.fetch_schedule()
            else:
                raise RuntimeError("需要安装 httpx 或 playwright 才能抓取课表")
                
            courses = self.parse_courses(html)
            return courses
        finally:
            await self.close()

    async def close(self):
        """关闭浏览器"""
        if self.page:
            await self.page.close()
            self.page = None
        
        if self.browser:
            await self.browser.close()
            self.browser = None
        
        logger.info("🔒 浏览器已关闭")
