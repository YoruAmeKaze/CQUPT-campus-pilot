import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AiProvider, User
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai/providers", tags=["AI 配置"])


class ProviderCreate(BaseModel):
    name: str
    api_key: str
    base_url: str
    model: str


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None


class ProviderResponse(BaseModel):
    id: int
    name: str
    api_key: str
    base_url: str
    model: str
    is_active: bool


async def _get_or_create_user(db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.id == 1))
    user = result.scalar_one_or_none()
    if not user:
        user = User(id=1, student_id="default_user")
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


async def _deactivate_all(db: AsyncSession, user_id: int):
    result = await db.execute(
        select(AiProvider).where(AiProvider.user_id == user_id, AiProvider.is_active == True)
    )
    for provider in result.scalars().all():
        provider.is_active = False


@router.get("", response_model=List[ProviderResponse])
async def list_providers(db: AsyncSession = Depends(get_db)):
    """获取所有 AI 配置"""
    user = await _get_or_create_user(db)
    result = await db.execute(
        select(AiProvider).where(AiProvider.user_id == user.id).order_by(AiProvider.created_at)
    )
    return [
        ProviderResponse(
            id=p.id, name=p.name, api_key=p.api_key,
            base_url=p.base_url, model=p.model, is_active=p.is_active,
        )
        for p in result.scalars().all()
    ]


@router.post("", response_model=ProviderResponse)
async def create_provider(provider: ProviderCreate, db: AsyncSession = Depends(get_db)):
    """添加 AI 配置"""
    user = await _get_or_create_user(db)

    first = await db.execute(
        select(AiProvider).where(AiProvider.user_id == user.id).limit(1)
    )
    is_first = first.scalar_one_or_none() is None

    new_provider = AiProvider(
        user_id=user.id,
        name=provider.name,
        api_key=provider.api_key,
        base_url=provider.base_url,
        model=provider.model,
        is_active=is_first,
    )
    db.add(new_provider)
    await db.commit()
    await db.refresh(new_provider)

    logger.info(f"✅ 新增 AI 配置: {provider.name} ({provider.model})")
    return ProviderResponse(
        id=new_provider.id, name=new_provider.name,
        api_key=new_provider.api_key, base_url=new_provider.base_url,
        model=new_provider.model, is_active=new_provider.is_active,
    )


@router.put("/{provider_id}", response_model=ProviderResponse)
async def update_provider(provider_id: int, update: ProviderUpdate, db: AsyncSession = Depends(get_db)):
    """更新 AI 配置"""
    result = await db.execute(select(AiProvider).where(AiProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="AI 配置不存在")

    if update.name is not None:
        provider.name = update.name
    if update.api_key is not None:
        provider.api_key = update.api_key
    if update.base_url is not None:
        provider.base_url = update.base_url
    if update.model is not None:
        provider.model = update.model

    await db.commit()
    await db.refresh(provider)
    return ProviderResponse(
        id=provider.id, name=provider.name,
        api_key=provider.api_key, base_url=provider.base_url,
        model=provider.model, is_active=provider.is_active,
    )


@router.delete("/{provider_id}")
async def delete_provider(provider_id: int, db: AsyncSession = Depends(get_db)):
    """删除 AI 配置"""
    result = await db.execute(select(AiProvider).where(AiProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="AI 配置不存在")

    was_active = provider.is_active
    await db.delete(provider)

    # 如果删除的是当前激活的，激活另一个
    if was_active:
        remaining = await db.execute(
            select(AiProvider).where(AiProvider.user_id == provider.user_id).limit(1)
        )
        next_provider = remaining.scalar_one_or_none()
        if next_provider:
            next_provider.is_active = True

    await db.commit()
    return {"message": "AI 配置已删除"}


@router.post("/{provider_id}/activate", response_model=ProviderResponse)
async def activate_provider(provider_id: int, db: AsyncSession = Depends(get_db)):
    """切换当前使用的 AI 配置"""
    result = await db.execute(select(AiProvider).where(AiProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="AI 配置不存在")

    await _deactivate_all(db, provider.user_id)
    provider.is_active = True
    await db.commit()
    await db.refresh(provider)

    logger.info(f"✅ 切换 AI 配置: {provider.name} ({provider.model})")
    return ProviderResponse(
        id=provider.id, name=provider.name,
        api_key=provider.api_key, base_url=provider.base_url,
        model=provider.model, is_active=provider.is_active,
    )
