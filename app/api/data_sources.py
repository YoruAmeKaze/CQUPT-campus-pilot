import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import DataSource, User
from app.services.config_store import ConfigStoreService
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data-sources", tags=["数据源"])


async def get_user_id(db: AsyncSession) -> int:
    from app.config import settings
    result = await db.execute(select(User).where(User.student_id == settings.student_id))
    user = result.scalar_one_or_none()
    if user:
        return user.id
    return 1


class DataSourceCreate(BaseModel):
    type: str
    name: str
    username: str = ""
    password: str = ""


class DataSourceResponse(BaseModel):
    id: int
    type: str
    name: str
    enabled: bool
    username: str
    last_sync: Optional[str] = None
    sync_status: str


@router.get("", response_model=List[DataSourceResponse])
async def list_sources(db: AsyncSession = Depends(get_db)):
    """获取所有数据源"""
    user_id = await get_user_id(db)
    result = await db.execute(
        select(DataSource).where(DataSource.user_id == user_id)
    )
    store = ConfigStoreService(db, settings.fernet_key)
    config_username_map = {
        "chaoxing": await store.get("chaoxing_username", ""),
        "smartestu": await store.get("smartestu_student_id", ""),
    }
    sources = []
    for ds in result.scalars().all():
        creds = {}
        if ds.credentials:
            import json
            try:
                creds = store._decrypt_credentials(ds.credentials)
            except Exception:
                creds = {}
        username = creds.get("username", creds.get("student_id", ""))
        if not username:
            username = config_username_map.get(ds.type, "")
        sources.append({
            "id": ds.id,
            "type": ds.type,
            "name": ds.name,
            "enabled": ds.enabled,
            "username": username,
            "last_sync": ds.last_sync.isoformat() if ds.last_sync else None,
            "sync_status": ds.sync_status,
        })
    return sources


@router.post("")
async def create_source(
    source: DataSourceCreate,
    db: AsyncSession = Depends(get_db),
):
    """添加数据源"""
    user_id = await get_user_id(db)
    store = ConfigStoreService(db, settings.fernet_key)

    if source.type == "chaoxing":
        credentials = {"username": source.username, "password": source.password}
    elif source.type == "smartestu":
        credentials = {"student_id": source.username, "password": source.password}
    else:
        credentials = {"username": source.username, "password": source.password}

    await store.save_data_source(user_id, source.type, source.name, credentials)

    return {"success": True, "message": "数据源已添加"}


@router.delete("/{source_id}")
async def delete_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除数据源"""
    user_id = await get_user_id(db)
    result = await db.execute(
        select(DataSource).where(
            DataSource.id == source_id,
            DataSource.user_id == user_id,
        )
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    await db.delete(ds)
    await db.commit()
    return {"success": True, "message": "数据源已删除"}
