import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.room_service import RoomService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rooms", tags=["空教室"])


@router.get("/empty")
async def query_empty_rooms(
    week: int = Query(None, description="周次，默认当前周"),
    day_of_week: int = Query(None, description="星期几 1-7，默认今天"),
    start_slot: int = Query(None, description="开始节次"),
    end_slot: int = Query(None, description="结束节次"),
    building: str = Query(None, description="教学楼筛选"),
    room_type: str = Query(None, description="教室类型（教室/实验室/室外）"),
    min_capacity: int = Query(None, description="最少容纳人数"),
    db: AsyncSession = Depends(get_db),
):
    """查询空教室"""
    service = RoomService(db)
    rooms = await service.query_empty_rooms(
        week=week,
        day_of_week=day_of_week,
        start_slot=start_slot,
        end_slot=end_slot,
        building=building,
        room_type=room_type,
        min_capacity=min_capacity,
    )
    return {
        "success": True,
        "count": len(rooms),
        "rooms": rooms,
    }


@router.post("/refresh")
async def refresh_room_data(db: AsyncSession = Depends(get_db)):
    """刷新教室课表数据（全量更新）"""
    service = RoomService(db)
    result = await service.refresh_room_data()
    return result


@router.get("/stats")
async def get_room_stats(db: AsyncSession = Depends(get_db)):
    """获取教室数据统计"""
    service = RoomService(db)
    stats = await service.get_stats()
    return {
        "success": True,
        "stats": stats,
    }


@router.get("/buildings")
async def get_buildings(db: AsyncSession = Depends(get_db)):
    """获取所有教学楼列表（用于前端下拉筛选）"""
    service = RoomService(db)
    buildings = await service.get_buildings()
    return {
        "success": True,
        "buildings": buildings,
    }
