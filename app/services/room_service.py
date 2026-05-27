import json
import logging
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crawlers.room_crawler import RoomCrawler
from app.db.models import RoomSchedule

logger = logging.getLogger(__name__)


class RoomService:
    """教室课表数据服务（查空教室）"""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _extract_building_from_room_name(self, room_name: str) -> Optional[str]:
        """从教室名提取教学楼编号（4位数字教室名：第一位为教学楼编号）"""
        if not room_name or len(room_name) != 4:
            return None
        if room_name.isdigit():
            building_num = room_name[0]
            return f"教学楼{building_num}"
        return None

    def _is_xiantao_building(self, building: Optional[str]) -> bool:
        """判断是否属于仙桃校区的教学楼"""
        if not building:
            return False
        # 假设仙桃校区的教学楼名称带有特殊标识，或者以特定字符开头
        # 这里根据实际情况调整判断逻辑，暂时用示例规则
        keywords = ["仙桃", "Xiantao", "XT"]
        return any(kw in building for kw in keywords)

    def _should_include_room(self, room_info: dict, explicit_outdoor_filter: bool = False) -> bool:
        """根据配置判断是否应该包含此教室
        Args:
            room_info: 教室信息
            explicit_outdoor_filter: 是否明确筛选室外教室（只有为True时才显示室外教室）
        """
        campus = settings.campus or "main"
        enable_lab = settings.enable_lab_query or False
        building = room_info.get("building", "")
        room_type = room_info.get("room_type", "")

        # 1. 校区过滤
        is_xiantao = self._is_xiantao_building(building)
        if campus == "main" and is_xiantao:
            return False
        if campus == "xiantao" and not is_xiantao:
            return False

        # 2. 实验室开关过滤
        if room_type == "实验室" and not enable_lab:
            return False

        # 3. 过滤网络教室和待定教室
        excluded_types = ["网络教室", "待定教室"]
        if room_type in excluded_types:
            return False
        if "网络教室" in room_type or "待定教室" in room_type:
            return False

        # 4. 室外教室默认不显示，只有明确筛选时才显示
        if room_type == "室外" and not explicit_outdoor_filter:
            return False

        return True

    def _calculate_week_number(self, target_date: Optional[date] = None) -> int:
        """计算指定日期是第几周"""
        if target_date is None:
            target_date = date.today()
        term_start = datetime.strptime(settings.term_start_date, "%Y-%m-%d").date()
        delta_days = (target_date - term_start).days
        if delta_days < 0:
            return 1
        return (delta_days // 7) + 1

    def _is_in_week(self, week_mask: Optional[str], start_week: int, end_week: int, week: int) -> bool:
        """检查指定周是否有课"""
        if week_mask:
            if 1 <= week <= len(week_mask):
                return week_mask[week - 1] == "1"
            return False
        return start_week <= week <= end_week

    async def refresh_room_data(self) -> dict:
        """
        刷新所有教室的课表数据（全量更新）

        1. 获取教室列表
        2. 抓取每个教室的课表
        3. 替换数据库中的旧数据

        Returns:
            dict: {"success": bool, "rooms_count": int, "schedules_count": int, "message": str}
        """
        crawler = RoomCrawler(concurrency=10)

        try:
            # 1. 获取教室列表
            room_list = await crawler.fetch_room_list()

            if not room_list:
                return {
                    "success": False,
                    "rooms_count": 0,
                    "schedules_count": 0,
                    "message": "未获取到教室列表",
                }

            # 2. 批量抓取课表
            room_names = [r["room_name"] for r in room_list]
            room_info_map = {r["room_name"]: r for r in room_list}

            result = await crawler.refresh_all(room_names)

            # 3. 清空旧数据
            await self.db.execute(delete(RoomSchedule))

            # 4. 插入新数据
            inserted = 0
            for room_data in result["rooms"]:
                room_name = room_data["room_name"]
                info = room_info_map.get(room_name, {})

                for sch in room_data["schedules"]:
                    # 跳过考试安排等特殊条目（课程名不应包含特殊标记）
                    if not sch["course_name"] or len(sch["course_name"]) > 100:
                        continue

                    record = RoomSchedule(
                        room_name=sch["room_name"],
                        room_type=info.get("room_type", "教室"),
                        capacity=info.get("capacity"),
                        building=info.get("building", ""),
                        day_of_week=sch["day_of_week"],
                        start_slot=sch["start_slot"],
                        end_slot=sch["end_slot"],
                        start_week=sch["start_week"],
                        end_week=sch["end_week"],
                        week_mask=sch.get("week_mask", ""),
                        course_name=sch["course_name"],
                    )
                    self.db.add(record)
                    inserted += 1

            await self.db.commit()

            logger.info(
                f"✅ 教室数据刷新完成: {result['success']} 个教室, {inserted} 条课表记录"
            )

            return {
                "success": True,
                "rooms_count": result["success"],
                "schedules_count": inserted,
                "message": f"刷新完成：{result['success']} 个教室，{inserted} 条课表记录",
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"❌ 刷新教室数据失败: {e}", exc_info=True)
            return {
                "success": False,
                "rooms_count": 0,
                "schedules_count": 0,
                "message": f"刷新失败: {str(e)}",
            }
        finally:
            await crawler.close()

    async def query_empty_rooms(
        self,
        week: Optional[int] = None,
        day_of_week: Optional[int] = None,
        start_slot: Optional[int] = None,
        end_slot: Optional[int] = None,
        building: Optional[str] = None,
        room_type: Optional[str] = None,
        min_capacity: Optional[int] = None,
    ) -> List[dict]:
        """
        查询空教室

        Args:
            week: 周次，默认当前周
            day_of_week: 星期几（1-7），默认今天
            start_slot: 开始节次，默认查询全天
            end_slot: 结束节次
            building: 教学楼筛选
            room_type: 教室类型筛选
            min_capacity: 最少容纳人数

        Returns:
            List[dict]: 空教室列表
        """
        from datetime import date

        today = date.today()
        if week is None:
            week = self._calculate_week_number(today)
        if day_of_week is None:
            day_of_week = today.weekday() + 1  # 0=周一 -> 1=周一

        # 查询该时间段有课的教室
        query = select(RoomSchedule).where(
            RoomSchedule.day_of_week == day_of_week,
        )

        if start_slot:
            query = query.where(RoomSchedule.end_slot >= start_slot)
        if end_slot:
            query = query.where(RoomSchedule.start_slot <= end_slot)
        else:
            query = query.where(RoomSchedule.start_slot <= (start_slot or 12) + 1)

        result = await self.db.execute(query)
        all_schedules = result.scalars().all()

        # 检查每个记录是否在本周有课
        occupied_rooms = set()
        for sch in all_schedules:
            if self._is_in_week(sch.week_mask, sch.start_week, sch.end_week, week):
                occupied_rooms.add(sch.room_name)

        # 获取所有教室列表
        all_rooms_query = select(RoomSchedule.room_name, RoomSchedule.room_type,
                                  RoomSchedule.capacity, RoomSchedule.building).distinct()
        all_rooms_result = await self.db.execute(all_rooms_query)
        all_rooms_rows = all_rooms_result.all()

        # 去重并构建教室信息
        seen = set()
        room_infos = {}
        for row in all_rooms_rows:
            if row.room_name not in seen:
                seen.add(row.room_name)
                room_infos[row.room_name] = {
                    "room_name": row.room_name,
                    "room_type": row.room_type,
                    "capacity": row.capacity,
                    "building": row.building,
                }

        # 没有课表的教室默认视为空教室
        empty_rooms = []
        for name, info in room_infos.items():
            if name not in occupied_rooms:
                # 如果building字段是room_type（如"教室"）或为空，从教室名提取
                building_raw = info.get("building") or ""
                room_type_db = info.get("room_type") or ""
                if not building_raw or building_raw == room_type_db:
                    extracted = self._extract_building_from_room_name(name)
                    if extracted:
                        info["building"] = extracted

                # 应用校区、实验室、网络教室和室外教室过滤
                explicit_outdoor_filter = (room_type == "室外")
                if not self._should_include_room(info, explicit_outdoor_filter):
                    continue
                # 应用用户筛选
                if building and building not in (info.get("building") or ""):
                    continue
                if room_type and info.get("room_type") != room_type:
                    continue
                if min_capacity and (info.get("capacity") or 0) < min_capacity:
                    continue

                empty_rooms.append(info)

        # 按教学楼和教室名排序
        empty_rooms.sort(key=lambda r: (r.get("building") or "", r["room_name"]))

        return empty_rooms

    async def get_buildings(self) -> List[dict]:
        """获取所有教学楼列表（用于前端筛选）"""
        query = select(RoomSchedule.building, RoomSchedule.room_type).distinct()
        result = await self.db.execute(query)
        rows = result.all()

        seen = set()
        buildings = []

        # 1. 从数据库 building 字段提取
        for row in rows:
            key = f"{row.building}|{row.room_type}"
            if row.building and key not in seen:
                building_info = {
                    "name": row.building,
                    "type": row.room_type,
                }
                if not self._should_include_room(building_info, explicit_outdoor_filter=False):
                    continue
                seen.add(key)
                buildings.append(building_info)

        # 2. 从4位数字教室名的第1位数字提取教学楼
        room_query = select(RoomSchedule.room_name).distinct()
        room_result = await self.db.execute(room_query)
        extracted_seen = set()
        for (room_name,) in room_result.all():
            extracted = self._extract_building_from_room_name(room_name)
            if extracted and extracted not in extracted_seen:
                already_added = any(b["name"] == extracted for b in buildings)
                if not already_added:
                    test_info = {"building": extracted, "room_type": "教室"}
                    if self._should_include_room(test_info, explicit_outdoor_filter=False):
                        extracted_seen.add(extracted)
                        buildings.append({"name": extracted, "type": "教室"})

        return sorted(buildings, key=lambda b: b["name"])

    async def get_stats(self) -> dict:
        """获取数据统计"""
        from sqlalchemy import func

        total_result = await self.db.execute(
            select(func.count(RoomSchedule.id))
        )
        total_schedules = total_result.scalar() or 0

        rooms_result = await self.db.execute(
            select(RoomSchedule.room_name).distinct()
        )
        total_rooms = len(rooms_result.all())

        types_result = await self.db.execute(
            select(RoomSchedule.room_type, func.count(RoomSchedule.id))
            .group_by(RoomSchedule.room_type)
        )
        type_stats = {row[0]: row[1] for row in types_result.all()}

        return {
            "total_rooms": total_rooms,
            "total_schedules": total_schedules,
            "type_stats": type_stats,
        }
